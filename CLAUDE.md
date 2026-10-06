# agentcore-workshop-customer-service

A customer-service **refund agent** used to teach Amazon Bedrock AgentCore. Teaching
staff deliver the concepts and live help; this repo is the hands-on spine.

## What it is (current shape)

A console workshop: attendees paste the files below into the AWS console. There is
no build step, no IaC and nothing to install. See `README.md` for which file is used
in which lab.

```
tools/      M4 Lambda (4 order/refund tools, hardcoded orders) + gateway tool schema
policies/   M5 Cedar + Dogwood policies for refund-gw-jwt, and its temporal IAM
chat/       the tester: one pasteable Lambda file (page, /lookup, /mcp) + its IAM
            policy + deploy.sh for staff
docs/       LABS (attendee steps), STAFF (instructor notes), README, notebook
```

- Identity is Cognito + Cedar/Dogwood. The tester's Chat tab goes through the
  harness (identity is only a system-prompt line there); its Tools tab calls
  `refund-gw-jwt` with the user's own token, so policies see the user.

## Working style for this repo

- **Readability over cleverness.** This is example code people read to learn:
  obvious flow, minimal abstraction, a comment where a concept is taught.
- **It was deliberately minimized.** Don't re-add complexity that was removed:
  the local agent and `make dev`, CDK/IaC deploys, the old payment gateway,
  DynamoDB/Docker, or the old "four seams" scaffolding. `chat/` is the only UI we
  ship. Simplest thing that works wins.
- **Everything is pasted into the console**, so each file must work on its own
  (`chat/lambda_function.py` embeds its HTML for that reason).
- **Attendees install nothing.** Anything that needs a laptop toolchain is out.

## Tooling in this environment

- **Skills**: `aws-agents` (`agents-get-started`, `agents-build`, `agents-deploy`,
  `agents-debug`, `agents-harden`, `agents-optimize`, `agents-connect`,
  `agents-pay`) and `aws-core` (`amazon-bedrock` covers AgentCore, plus
  `aws-iam`, `aws-observability`, `aws-security`, cost skills). Invoke the
  matching skill before building or debugging agent code.
- **MCP**: `aws-core` (`run_script` for AWS API calls — prefer over the AWS CLI
  in Bash) and `awsknowledge` (AWS docs/skill lookup).
