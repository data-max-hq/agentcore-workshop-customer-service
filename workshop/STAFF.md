# Staff notes — read before the workshop

## Gotchas cheat sheet (symptom → cause → fix)

| Attendee sees | Cause | Fix |
|---|---|---|
| `agentcore: command not found` | CLI not installed | `npm install -g @aws/agentcore@0.31.0` |
| `No agent project found` / "old Python CLI" | the deprecated `bedrock-agentcore-starter-toolkit` is on PATH | uninstall it; install `@aws/agentcore` (npm). `make check` detects this. |
| `make dev` fails, `agentcore` not found | installed but PATH doesn't include the npm global bin | ensure npm global bin (e.g. `~/.local/bin`) is on PATH |
| Chat UI shows raw `{"response": ...}` JSON | entrypoint returned a dict instead of streaming | `main.py` must `yield` events (already fixed here) |
| Chat says "authentication issue / not signed in" | no identity in the request | local dev defaults to `alice`; `LOCAL_DEV_CUSTOMER` overrides |
| Lambda deploy fails: `pyproject.toml not found` | a Gateway Lambda code dir needs one | `infra/payment/pyproject.toml` exists here; any new Lambda dir needs one too |
| **Memory panel empty** | `MEMORY_REFUNDMEMORY_ID` not set → agent used the local in-process dict | expected locally; only populates against the **deployed** runtime (see rehearsal Q1) |
| Bedrock `AccessDenied` / model not found | account lacks Bedrock access to Claude in us-east-1 | enable model access; confirm region |

## Version pinning (the CLI is pre-1.0 — pin it)

Verified working set (2026-09-30):

- `@aws/agentcore` **0.31.0** — install with `@0.31.0`, don't let attendees grab latest
- `@aws/agentcore-cdk` **0.1.0-alpha.53** (in `agentcore/cdk/package.json`)
- `aws-cdk-lib` ~2.261.0, Node 20+, Python 3.12+

⚠️ On deploy the CLI's "Sync CDK dependencies" step may **auto-bump** the alpha
CDK dep (we saw `alpha.53 → alpha.54`). Decide during rehearsal whether to let it
bump or pin it, and lock the same version on every machine.

## Deploy rehearsal checklist — do this before the workshop

Done locally so far: `agentcore validate` = Valid, and **CDK synth passes with
runtime + Gateway + Memory** (config is structurally sound). **Not yet verified:
an actual `agentcore deploy`.** In a sandbox account, run through this and record
what breaks:

1. `aws sts get-caller-identity` — right account + region (us-east-1).
2. `make infra-preview` — dry-run clean.
3. `make infra-deploy` — approve the one-time **CDK bootstrap**. Watch for:
   - IAM permission errors during bootstrap/deploy
   - the runtime, gateway, Lambda, and Memory all creating
4. **Q1 — how do attendees exercise Memory/Gateway?** Confirm whether
   `agentcore dev` locally picks up the **deployed** `MEMORY_*_ID` /
   `PAYMENT_GATEWAY_URL`, or whether they must invoke the **deployed** runtime
   (e.g. `agentcore invoke`). Whichever works, put the exact command into
   LABS.md M3/M4 (they're marked ⏳ until then).
5. **Q2 — gateway → Lambda permission.** Issue a refund on the deployed agent and
   confirm the Gateway can invoke the Lambda (check the Lambda's CloudWatch logs
   for the `process_refund` call). If it 403s, the target's invoke permission
   needs sorting.
6. **Q3 — Memory writes.** Confirm the conversation actually lands in the Memory
   panel / `agentcore` memory APIs.
7. `make infra-down` then verify in the console that resources are gone (no spend).
8. Time the whole run — that sets the real M2–M5 budget.

Update LABS.md (flip ⏳ → ✅) and this file with anything you hit.

## Fast resets during the workshop

- Local agent stuck: `pkill -f "agentcore dev"` then `make dev`.
- Deploy in a weird state: re-run `make infra-deploy` (reconciles the CDK stack).
- Full teardown: `make infra-down`.
- Fresh account: attendees get a new one; just re-run M2.

## What each moving part is (for answering questions)

- `main.py` — the whole agent: entrypoint + 3 tools + in-memory `ORDERS`. Memory
  and Gateway are wired but **env-var-guarded**, so they're inert locally and
  activate when deployed.
- `memory/session.py` — returns `None` (no-op) unless `MEMORY_REFUNDMEMORY_ID` is set.
- `infra/payment/handler.py` — the fake payout Lambda (Gateway target); mock, no real money.
- `agentcore/agentcore.json` — declares runtime + PaymentGateway + RefundMemory; `agentcore deploy` builds it via CDK.
- The chat UI + Timeline/Resources/Memory panels on :8081 are AWS's **agent
  inspector** (ships with `agentcore dev`) — not custom code.
