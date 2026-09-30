# AgentCore workshop — facilitator overview

Attendees build, run, deploy, and observe a minimal Amazon Bedrock AgentCore
agent (the refund bot — see the [top-level README](../README.md)). Concepts
and live help are delivered by **teaching staff**; these docs are just the
hands-on spine.

- **[LABS.md](LABS.md)** — the attendee steps (M1–M5), terse, checkpoint-based.
- **[STAFF.md](STAFF.md)** — gotchas cheat sheet + the deploy rehearsal checklist. **Staff read this first.**

## The arc

| Module | What they do | Needs AWS? | Time |
|---|---|---|---|
| **M1** Run & inspect | `make dev`, chat, read the Timeline/trace | no | ~15 min |
| **M2** Deploy | `make infra-deploy` → resources appear in AWS | yes | ~20 min |
| **M3** Memory | exercise the deployed agent, watch the Memory panel populate | yes | ~15 min |
| **M4** Gateway | the payout becomes a managed Lambda MCP tool | yes | ~15 min |
| **M5** Observe & tear down | traces in CloudWatch; `make infra-down` | yes | ~10 min |

**M1 is the reliable core** (local, no account, fully verified). **M2–M5 require
an AWS account** and were **not yet verified end-to-end** — see the rehearsal
checklist in STAFF.md. Suggested default: ~90 min, M1–M4, M5 as time allows.

## Prerequisites (pin these — the CLI is pre-1.0 and moves fast)

Each attendee machine needs:

- **Node 20+** and **Python 3.12+**
- **AgentCore CLI, pinned:** `npm install -g @aws/agentcore@0.31.0`
- **AWS credentials** for their provided account, with **Bedrock access to Claude** (us-east-1)
- No Docker, no database — orders are in-memory.

> Verified working set (2026-09-30): `@aws/agentcore` **0.31.0**,
> `@aws/agentcore-cdk` **0.1.0-alpha.53**, `aws-cdk-lib` ~2.261.0, Node 24, Python 3.12.
> The CDK dep is alpha and the CLI may try to auto-bump it on deploy — see STAFF.md.

## Get an attendee running (M1)

```bash
npm install -g @aws/agentcore@0.31.0
make dev            # from the repo root; chat UI at http://localhost:8081
```
