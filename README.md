# RefundAgent — a minimal Amazon Bedrock AgentCore agent

A customer-support **refund agent**: a signed-in customer can list orders, check
status, and request refunds. It runs **locally with one command** — no Docker,
no database — and grows into two managed AgentCore services when you deploy.

## Run it

Prereqs: **AWS credentials** with Bedrock access to Claude, and the **AgentCore
CLI**, pinned: `npm install -g @aws/agentcore@0.31.0`.

```bash
make dev        # runs the agent; open the chat UI at http://localhost:8081
```

Try: *"what orders do I have?"*, *"refund A-1001"*. The login-less chat UI signs
you in as `alice` by default (`LOCAL_DEV_CUSTOMER=bob make dev` to switch).

Demo data (in `main.py`): `A-1001` (alice, delivered), `A-1002` (alice, shipped),
`B-2001` / `B-2002` (bob, delivered). Only **delivered** orders can be refunded.

## Files

```
app/RefundAgent/
  main.py            the whole agent: BedrockAgentCoreApp entrypoint, 3 tools,
                     in-memory orders, streamed replies
  memory/session.py  AgentCore Memory wiring (no-op locally; real when deployed)
  model/load.py      the Bedrock model (Claude)
infra/               optional: the payout as a managed Gateway + Lambda (see infra/README.md)
agentcore/           project config (agentcore.json) + CDK for deploy
```

## How it works

`agentcore dev` serves the app as an HTTP endpoint (chat UI on :8081). Each
request `{prompt, customer_id?, session_id?}` binds the caller, runs a Strands
`Agent` (Bedrock Claude) that calls the tools, and streams the reply.

Two managed services are wired but **guarded by an env var**, so they're inert
locally and light up only when deployed:

| Service | Local (`make dev`) | Deployed (`make infra-deploy`) |
|---|---|---|
| **Memory** | in-process dict remembers the conversation | AgentCore **Memory** persists it (`memory/session.py`) |
| **Gateway** | `issue_refund` runs in-process | the payout is a managed **Lambda MCP tool** (`infra/`) |

That's the whole point of the shape: the same code runs on your laptop and, with
`agentcore deploy`, against real AgentCore Memory + Gateway — no rewrite.

## Deploy the managed services (optional)

```bash
make infra-preview   # dry-run: what AWS resources would be created (no spend)
make infra-deploy    # create the Gateway + Lambda + Memory
make infra-down      # remove them again
```

See [`infra/README.md`](infra/README.md) for the Gateway/Lambda details and cost notes.

## Running this as a workshop

Facilitator + attendee material is in [`workshop/`](workshop/README.md) — the
lab steps, prereqs, and a staff cheat sheet.
