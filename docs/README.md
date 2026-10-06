# AgentCore workshop: facilitator overview

Attendees build the whole managed flow in the AWS console (M1 to M5): a login, an
agent, memory, tools, and authorization policies. They install nothing. They drive all of it from a small tester app
(`chat/lambda_function.py`) that each attendee deploys as a Lambda in their account. Teaching staff explain the ideas. These docs are only the steps.

Everything is in **us-east-1**.

- **[LABS.md](LABS.md)** is what attendees follow.
- **[STAFF.md](STAFF.md)** is the setup checklist and the error list. Staff read
  this first.

## The arc

| Module | What they do | Needs AWS | Time |
|---|---|---|---|
| M1 Identity | Cognito pool and users, the tester finds them | console | 15 min |
| M2 The agent | create a harness with JWT login, log in with the tester | console | 15 min |
| M3 Memory | short-term only with your own memory, then managed long-term memory | console | 15 min |
| M4 Tools | Lambda, `refund-gw`, attach to the agent | console | 20 min |
| M5 Policies | `refund-gw-jwt`, policy engine, Cedar rules, then a Dogwood rule | console | 35 min |

Budget about 100 minutes, plus 10 for the tester. If you are short on time, M5 is the one that makes the
point, so cut M3 before you cut M5.

## The idea the workshop is built around

A managed harness cannot pass the signed-in user's token to a gateway. On the
agent path the gateway only ever sees the agent's own AWS role, never the person.
So the workshop builds **two doors into one Lambda**:

```
you --login--> Cognito

  Chat tab  --> Harness --> refund-gw (AWS IAM) --> Lambda
  Tools tab --------------> refund-gw-jwt (your token, policies) --> Lambda
```

In M4 the agent gets tools and looks secure. It is not: the user's name is just a
line in a prompt, and the model follows it out of politeness. In M5 the second
door proves who you are and a policy engine checks every tool call against it.

M4 and M5 are meant to feel different. Do not add a policy engine to `refund-gw`
without reading the last section of STAFF.md.

## Prerequisites

Each attendee needs:

- A browser, and AWS console access to their account in `us-east-1`. The agent
  uses Amazon Nova Pro, which needs no model setup
- Nothing installed. No Docker and no database: orders live in the tool Lambda.

## Get an attendee running

Attendees create the tester in the Lambda console ("The tester app" in LABS.md).
Staff can also run `bash chat/deploy.sh` with the attendee's credentials, for
example in CloudShell. It finds the pool, client, harness and JWT gateway in the
account by itself, so there is no config file. `bash chat/deploy.sh down` removes
it.
