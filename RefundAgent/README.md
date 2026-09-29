# RefundAgent — AgentCore workshop bot

A customer-support **refund agent** on Amazon Bedrock AgentCore. A signed-in
customer can look up their orders and request refunds. It runs **entirely on
your machine** — the only thing that leaves is the model call to Bedrock.

It works correctly today. The workshop breaks it on purpose (see the four
**seams** below) so attendees find and fix real production failures.

## TL;DR — run it

Prereqs: **Docker**, **[uv](https://docs.astral.sh/uv/)**, **AWS credentials**
with Bedrock access to Claude, and the **AgentCore CLI**
(`npm install -g @aws/agentcore`).

```bash
cd RefundAgent
make up      # terminal 1: DynamoDB Local + seed demo orders
make dev     # terminal 2: the agent — leave running (API :8080, chat UI :8081)
make demo    # terminal 3: fire real refunds and assert all four seams pass
```

`make help` lists every target. `make down` tears down the state.

Talk to it directly:

```bash
curl -s -X POST http://localhost:8080/invocations -H 'Content-Type: application/json' \
  -d '{"prompt":"Refund my order A-1001.","customer_id":"alice","session_id":"s1"}'
```

Seeded orders: `A-1001` (alice, delivered), `A-1002` (alice, shipped),
`B-2001` / `B-2002` (bob, delivered). Only **delivered** orders can be refunded.

## What happens on one request

A request is `{prompt, customer_id, session_id}`. Here's the whole path
(`main.py` `invoke`):

```
POST /invocations {prompt, customer_id, session_id}
        │
        ▼
 main.py  ── bind customer_id to CURRENT_CUSTOMER   (seam 3: who is calling)
        │   load the past messages for session_id   (seam 2: what was said before)
        ▼
 Strands Agent (model = Bedrock Claude Sonnet 4.5)
        │   the model decides which tool(s) to call
        ▼
 tools.py  lookup_order · issue_refund · get_refund_status
        │   every tool: checks the order belongs to CURRENT_CUSTOMER (seam 3)
        │             + logs name/caller/latency via @observed  (seam 4)
        ▼
 store.py (Orders, Sessions)      payment_gateway.py (Payments ledger)
        │   business truth                mock payout API, idempotent by key
        ▼   + call_with_timeout: bounded timeout & retries (seams 1 & 4)
 main.py  ── save the updated messages back to session_id   (seam 2)
        ▼
 {"response": "..."}
```

`customer_id` stands in for the authenticated identity. **In a real deployment
it comes from the verified JWT, never the payload** — that swap is one of the
workshop's later steps.

## The three tables (state model)

State is small but split on purpose — the split *is* seam 2.

| Table | Owner | Holds | Why it's separate |
|-------|-------|-------|-------------------|
| `Orders` | the app (`store.py`) | order status, amount, owner | **Authoritative business truth.** Status is always read from here, never from what the model "remembers". |
| `Sessions` | the app (`store.py`) | the conversation transcript per `session_id` | Lets a customer come back and continue where they left off. |
| `Payments` | the payment gateway (`payment_gateway.py`) | one row per real payout, keyed by idempotency key | **Authoritative refund ledger.** Refund status is read from here — one row = one payout. |

All three live in **DynamoDB Local** (Docker), reset every time the container
stops. The *same boto3 code* talks to real DynamoDB in the cloud if you unset
`DDB_ENDPOINT` — that one line is the whole local→deployed change.

## The four seams (what the workshop breaks)

Each production concern is handled correctly today at a single spot marked
`# WORKSHOP SEAM`. Break it, watch it fail, fix it.

| # | Concern | Done correctly | Break it → |
|---|---------|----------------|-----------|
| 1 | Idempotency / safe retries | `issue_refund` sends a **stable** key (`rf_<order>`); the gateway records one `Payments` row per key | fresh key each call (`uuid4`) → a retry writes a second payout → **refunded twice** |
| 2 | Session + authoritative status | conversation loaded/saved from `Sessions`; refund status read from the `Payments` **ledger**, not chat memory | skip `load_session` (**forgets**) or answer status from the conversation (**remembers wrong**) |
| 3 | Identity / tenant isolation | caller's `customer_id` comes from request **context**; every tool checks ownership | take `customer_id` as a tool argument → one customer **refunds another's order** |
| 4 | Timeout / retry / observability | gateway called via `call_with_timeout` (per-attempt timeout, ≤ 1+2 retries); every tool logs name/caller/latency | drop the timeout / make retries unbounded → requests **hang**, tool calls climb |

## File map

```
app/RefundAgent/
  main.py            entrypoint: binds identity, loads/saves session, runs the agent
  tools.py           lookup_order, issue_refund, get_refund_status   (seams 1, 3, 4)
  store.py           Orders + Sessions — the app's business state     (seam 2)
  payment_gateway.py mock payout API + Payments ledger + call_with_timeout (seams 1, 4)
  model/load.py      the Bedrock model (Claude Sonnet 4.5)
  seed.py            create local tables + seed demo orders
docker-compose.yml   DynamoDB Local (in-memory, resets on stop)
Makefile             the run targets below
demo.sh              exercises and asserts all four seams
```

## Verify the logic (no server, no model needed)

Fast feedback while editing the seams — these run the self-checks in the
modules directly:

```bash
make verify   # payment_gateway.py (seams 1 & 4) + store.py (seam 2 storage)
```

## Demo seam 4 (timeout) live

Restart the agent with the gateway slowed past the 2s timeout:

```bash
cd app/RefundAgent
PAYMENT_LATENCY_MS=5000 DDB_ENDPOINT=http://localhost:8000 agentcore dev --port 8080
```

A refund then returns a clean timeout and the logs show attempts capped at 3.
(`PAYMENT_FAIL=1` instead simulates a full outage.)

## Teardown

```bash
make down    # stops DynamoDB Local and wipes its in-memory tables
# Ctrl+C the `make dev` server
```

Nothing exists in AWS to clean up — this project is never deployed. Deferred to
a later (deploy) phase: AgentCore Memory, real JWT identity, AgentCore
Observability / CloudWatch. Run `agentcore --help` for the CLI reference.
