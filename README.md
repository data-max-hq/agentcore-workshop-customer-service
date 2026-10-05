# Refund Agent — AgentCore Workshop

In this workshop, people build a customer-service **refund agent** on **Amazon Bedrock AgentCore**. A signed-in customer can list their orders, check one, and ask for a refund. Along the way they add a Cognito login, memory, tools behind a gateway, Cedar policies that refuse to let one customer touch another's orders, and a Dogwood policy that remembers what happened earlier in the session.

Everything is set up by hand in the AWS Console, in **US East (N. Virginia) us-east-1**, with nothing to install. The code and policies in this repo are pasted into the console as they are; there is no build step.

## Architecture

```
User → tester page (Cognito sign-in) ─┬→ Chat:  Harness → Gateway A (IAM) ─┬→ Lambda tools
                                      └→ Tools: Gateway B (JWT + Cedar) ───┘
```

The Chat path goes through the agent, so the gateway only sees the agent. The Tools path carries the user's own token, so the policy engine sees who is asking and can say no. That difference is the point of the workshop.

## Where to start

| You are | Read |
|---|---|
| A workshop attendee | [`docs/LABS.md`](docs/LABS.md): the tester, then M1–M5 |
| An instructor or maintainer | [`docs/STAFF.md`](docs/STAFF.md) for setup, errors attendees hit, and resets; [`docs/README.md`](docs/README.md) for the facilitator overview |

## Repository

| Path | What | Used in |
|---|---|---|
| `docs/LABS.md` | Step-by-step lab instructions | Attendees |
| `docs/STAFF.md` | Gotchas, IAM policies, resets | Instructors |
| `docs/refund-agent-workshop.ipynb` | The workshop story as a notebook, no code to run | Instructors |
| `tools/lambda_function.py` | Lambda code for the four order and refund tools | M4 |
| `tools/tool-schema.json` | Tool definitions for both gateway targets | M4, M5 |
| `policies/identity-binding.cedar` | A customer may only touch their own orders | M5 |
| `policies/refund-cap.cedar` | No refunds over $200 | M5 |
| `policies/refund-after-lookup.dogwood` | Dogwood: no refund unless you looked at that order earlier in the session | M5 |
| `policies/gateway_temporal_iam.json` | Lets gateway B keep the session history Dogwood needs | M5 |
| `chat/lambda_function.py` | The tester: sign-in page, chat, tools tab, and a lookup that finds your resources | All labs |
| `chat/lambda_policy.json` | Lets the tester read the names of your pool, harness and gateway | Tester setup |

## Shortcut for staff

Instead of the console steps, you can create the tester from AWS CloudShell or any
shell with credentials for the account:

```
bash chat/deploy.sh        # create or update the tester, prints its URL
bash chat/deploy.sh down   # remove it again
```
