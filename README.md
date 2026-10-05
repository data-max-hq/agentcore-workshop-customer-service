# Refund Agent — AgentCore Workshop

In this workshop, people build a customer-service **refund agent** on **Amazon Bedrock AgentCore**. A signed-in customer can list their orders, check one, and ask for a refund. Along the way they add a Cognito login, memory, tools behind a gateway, Cedar policies that refuse to let one customer touch another's orders, and a Dogwood policy that remembers what happened earlier in the session.

M1 runs the agent on a laptop. Everything after that is set up by hand in the AWS Console, in **Europe (Frankfurt) eu-central-1**. The code and policies in this repo are pasted into the console as they are; there is no build step.

## Architecture

```
User → tester page (Cognito sign-in) ─┬→ Chat:  Harness → Gateway A (IAM) ─┬→ Lambda tools
                                      └→ Tools: Gateway B (JWT + Cedar) ───┘
```

The Chat path goes through the agent, so the gateway only sees the agent. The Tools path carries the user's own token, so the policy engine sees who is asking and can say no. That difference is the point of the workshop.

## Where to start

| You are | Read |
|---|---|
| A workshop attendee | [`docs/LABS.md`](docs/LABS.md): the tester, then M1–M6 |
| An instructor or maintainer | [`docs/STAFF.md`](docs/STAFF.md) for setup, errors attendees hit, and resets; [`docs/README.md`](docs/README.md) for the facilitator overview |

## Repository

| Path | What | Used in |
|---|---|---|
| `docs/LABS.md` | Step-by-step lab instructions | Attendees |
| `docs/STAFF.md` | Gotchas, IAM policies, resets | Instructors |
| `docs/refund-agent-workshop.ipynb` | The workshop story as a notebook, no code to run | Instructors |
| `agent/` | The local agent: `main.py` with three tools and in-memory orders | M1 (`make dev`) |
| `agentcore/agentcore.json` | AgentCore CLI project file for `make dev` | M1 |
| `tools/lambda_function.py` | Lambda code for the four order and refund tools | M5 |
| `tools/tool-schema.json` | Tool definitions for both gateway targets | M5, M6 |
| `policies/identity-binding.cedar` | A customer may only touch their own orders | M6 |
| `policies/refund-cap.cedar` | No refunds over $200 | M6 |
| `policies/refund-after-lookup.dogwood` | Dogwood: no refund unless you looked at that order earlier in the session | M6 |
| `policies/gateway_temporal_iam.json` | Lets gateway B keep the session history Dogwood needs | M6 |
| `chat/lambda_function.py` | The tester: sign-in page, chat, tools tab, and a lookup that finds your resources | All labs after M1 |
| `chat/lambda_policy.json` | Lets the tester read the names of your pool, harness and gateway | Tester setup |

## Shortcuts for staff

```
make dev           # M1: run the agent locally (needs npm install -g @aws/agentcore@0.31.0)
make chat-deploy   # create or update the tester in the current account, prints its URL
make chat-down     # remove it again
```
