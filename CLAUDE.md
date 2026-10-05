# agentcore-workshop-customer-service

A **minimal Amazon Bedrock AgentCore sample**: a customer-service **refund agent**
used to teach AgentCore. It runs locally with one command and deploys to managed
AgentCore services when you want. Teaching staff deliver the concepts and live
help; this repo is the hands-on spine.

## What it is (current shape)

A console workshop: attendees paste the files below into the AWS console. There is
no build step and no IaC. See `README.md` for which file is used in which lab.

```
agent/               M1 local agent: main.py (3 tools, in-memory ORDERS, streamed
                     replies), memory/session.py (no-op locally), model/load.py
agentcore/           agentcore.json, the CLI project file `make dev` needs
tools/               M5 Lambda (4 order/refund tools) + gateway tool schema
policies/            M6 Cedar + Dogwood policies for gateway B, and its temporal IAM
chat/                the tester: one pasteable Lambda file (page, /lookup, /mcp)
docs/                LABS (attendee steps), STAFF (instructor notes), notebook
Makefile             make dev / make chat-deploy / make chat-down
```

- **No Docker, no database** — M1 orders are an in-memory dict in `agent/main.py`.
- Memory is env-var-guarded: `MEMORY_REFUNDMEMORY_ID` unset → in-process dict.
- Identity: M1 takes `customer_id` from the request (default `alice`,
  `LOCAL_DEV_CUSTOMER` to change). Real identity is Cognito + Cedar in M2–M6.

## Run it

From the **repo root** (not a subdir):

```bash
npm install -g @aws/agentcore@0.31.0   # pinned; the CLI is pre-1.0
make dev                               # chat UI at http://localhost:8081
```

Use the **npm `@aws/agentcore` CLI**, never the deprecated Python
`bedrock-agentcore-starter-toolkit` (it doesn't understand this project layout).

## Working style for this repo

- **Readability over cleverness.** This is example code people read to learn:
  obvious flow, minimal abstraction, a comment where a concept is taught.
- **It was deliberately minimized.** Don't re-add complexity that was removed:
  CDK/IaC deploys, the old payment gateway, DynamoDB/Docker, or the old "four
  seams" scaffolding. The M1 inspector on :8081 is AWS's; `chat/` is the only UI
  we ship. Simplest thing that works wins.
- **Everything after M1 is pasted into the console**, so each file there must
  work on its own (`chat/lambda_function.py` embeds its HTML for that reason).
- Keep the local path working with **no cloud** — new managed features stay
  env-var-guarded so `make dev` never needs AWS.

## Tooling in this environment

- **Skills**: `aws-agents` (`agents-get-started`, `agents-build`, `agents-deploy`,
  `agents-debug`, `agents-harden`, `agents-optimize`, `agents-connect`,
  `agents-pay`) and `aws-core` (`amazon-bedrock` covers AgentCore, plus
  `aws-iam`, `aws-observability`, `aws-security`, cost skills). Invoke the
  matching skill before building or debugging agent code.
- **MCP**: `aws-core` (`run_script` for AWS API calls — prefer over the AWS CLI
  in Bash) and `awsknowledge` (AWS docs/skill lookup).
