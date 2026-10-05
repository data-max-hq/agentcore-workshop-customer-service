# AgentCore workshop: facilitator overview

Attendees run a refund agent on their laptop (M1), then build the whole managed
flow in the AWS console (M2 to M6): a login, an agent, memory, tools, and
authorization policies. They drive all of it from a small tester app
(`chat/lambda_function.py`) that each attendee deploys as a Lambda in their account. Teaching staff explain the ideas. These docs are only the steps.

<<<<<<< Updated upstream
- **[refund-agent-workshop.ipynb](refund-agent-workshop.ipynb)** — the console-based workshop guide (Harness → Lambda → Gateway → tools). No code to run.
- **[LABS.md](LABS.md)** — the attendee steps (M1–M5), terse, checkpoint-based.
- **[STAFF.md](STAFF.md)** — gotchas cheat sheet + the deploy rehearsal checklist. **Staff read this first.**
=======
Everything is in **eu-central-1**.

- **[LABS.md](LABS.md)** is what attendees follow.
- **[STAFF.md](STAFF.md)** is the setup checklist and the error list. Staff read
  this first.
>>>>>>> Stashed changes

## The arc

| Module | What they do | Needs AWS | Time |
|---|---|---|---|
| M1 Run it locally | `make dev`, chat, read a trace | no | 15 min |
| M2 Identity | Cognito pool and users, log in with the tester | console | 15 min |
| M3 The agent | create a harness with JWT login | console | 15 min |
| M4 Memory | attach memory, watch it remember and forget | console | 10 min |
| M5 Tools | Lambda, gateway A, attach to the agent | console | 20 min |
| M6 Policies | gateway B, policy engine, Cedar rules | console | 25 min |

Budget about 100 minutes. If you are short on time, M6 is the one that makes the
point, so cut M4 before you cut M6.

## The idea the workshop is built around

A managed harness cannot pass the signed-in user's token to a gateway. On the
agent path the gateway only ever sees the agent's own AWS role, never the person.
So the workshop builds **two doors into one Lambda**:

```
you --login--> Cognito

  Chat tab  --> Harness --> Gateway A (AWS IAM) --> Lambda
  Tools tab --------------> Gateway B (your token, policies) --> Lambda
```

In M5 the agent gets tools and looks secure. It is not: the user's name is just a
line in a prompt, and the model follows it out of politeness. In M6 the second
door proves who you are and a policy engine checks every tool call against it.

M5 and M6 are meant to feel different. Do not add a policy engine to gateway A
without reading the last section of STAFF.md.

## Prerequisites

Pin the CLI. It is pre-1.0 and moves fast.

Each attendee machine needs:

- Node 20 or newer, and Python 3.12 or newer
- The AgentCore CLI, pinned: `npm install -g @aws/agentcore@0.31.0`. M1 only.
- AWS console access to the shared account, region `eu-central-1`, with Bedrock
  access to a Claude model enabled there
- No Docker and no database. Orders live in memory, first in the local agent and
  then in the tool Lambda.

M2 to M6 are done in the console. The tester app runs on the laptop and needs no
AWS credentials, only the Cognito login.

Working set checked on 2026-10-04: `@aws/agentcore` 0.31.0, Node 24, Python 3.12.

## Get an attendee running

```bash
npm install -g @aws/agentcore@0.31.0
make dev                   # from the repo root, chat UI on http://localhost:8081
```

Then the tester: attendees create it in the Lambda console ("The tester app" in
LABS.md), or staff can run `make chat-deploy` with the attendee's credentials. It finds
the pool, client, harness and JWT gateway in the account by itself, so there is no
config file. `make chat-down` removes it.
