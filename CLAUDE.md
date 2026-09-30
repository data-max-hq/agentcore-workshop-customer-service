# agentcore-workshop-customer-service

A **minimal Amazon Bedrock AgentCore sample**: a customer-service **refund agent**
used to teach AgentCore. It runs locally with one command and deploys to managed
AgentCore services when you want. Teaching staff deliver the concepts and live
help; this repo is the hands-on spine.

## What it is (current shape)

The whole agent is small and lives at the repo root (there is **no** nested
`RefundAgent/` wrapper anymore — it was flattened):

```
app/RefundAgent/
  main.py            the entire agent: BedrockAgentCoreApp entrypoint, 3 tools,
                     in-memory ORDERS dict, streamed (SSE) replies
  memory/session.py  AgentCore Memory wiring — returns None (no-op) locally
  model/load.py      the Bedrock model (Claude)
infra/payment/       fake-payout Lambda (Gateway target) — a mock, no real money
agentcore/           agentcore.json (runtime + PaymentGateway + RefundMemory) + CDK
workshop/            facilitator/attendee material (README, LABS, STAFF)
Makefile             make dev / make infra-*
```

- **No Docker, no database** — orders are an in-memory dict in `main.py`.
- **Memory and Gateway are wired but env-var-guarded**, so they are inert locally
  and activate only when deployed:
  - `MEMORY_REFUNDMEMORY_ID` unset → conversation lives in an in-process dict;
    set (by `agentcore deploy`) → **AgentCore Memory**.
  - `PAYMENT_GATEWAY_URL` unset → the in-process `issue_refund` tool does the
    payout; set → the payout is the managed **Gateway Lambda** (`infra/`).
- Identity: `customer_id` comes from the request, defaulting to `alice` locally
  (`LOCAL_DEV_CUSTOMER` to change). Real JWT identity is deferred to deploy.

## Run it

From the **repo root** (not a subdir):

```bash
npm install -g @aws/agentcore@0.31.0   # pinned; the CLI is pre-1.0
make dev                               # chat UI at http://localhost:8081
```

Use the **npm `@aws/agentcore` CLI**, never the deprecated Python
`bedrock-agentcore-starter-toolkit` (it doesn't understand this project layout).

## Deploy (optional, to a provided AWS account)

`make infra-deploy` runs `agentcore deploy` → CDK, creating the runtime + Gateway
+ Lambda + Memory. `make infra-preview` is a no-spend dry-run; `make infra-down`
tears it back down. Config is validated and **CDK-synth-clean**, but a real
`agentcore deploy` has **not been run yet** — the rehearsal checklist and its
three open questions are in [`workshop/STAFF.md`](workshop/STAFF.md).

## Working style for this repo

- **Readability over cleverness.** This is example code people read to learn:
  obvious flow, minimal abstraction, a comment where a concept is taught.
- **It was deliberately minimized.** Don't re-add complexity that was removed:
  the custom `web/` console (the AWS agent inspector on :8081 covers it),
  DynamoDB/Docker, or the old "four seams" scaffolding. Simplest thing that
  works wins.
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
