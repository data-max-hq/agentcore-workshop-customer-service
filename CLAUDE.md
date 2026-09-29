# agentcore-workshop-customer-service

Hands-on workshop teaching AWS attendees the basics of **Amazon Bedrock AgentCore** through a customer-service agent. The repo is the sample app attendees build on and break.

## Purpose

Teach how an agentic AI product behaves in production: scaling, security, tenant/data isolation, and cost control. AgentCore is the focus; we also touch other AWS services, open-source tools, and open-weights models.

Workshop themes (what code and exercises should illustrate):
- Crash recovery, retries, high availability
- Where agent memory and execution state live — AgentCore Memory vs DynamoDB
- Auth for long-running tasks; keeping tenants isolated
- Guardrails across model providers; central access/usage/cost management
- Observability — AgentCore Observability vs Langfuse
- Runtime resources and cost; AgentCore Gateway vs self-hosted MCP
- Model routing for cost efficiency

The hands-on section walks through **deliberate failure scenarios**: investigate what went wrong, fix it, re-test. Some code will be intentionally broken or naive — confirm before "fixing" something that may be a teaching exercise.

## Audience

Workshop attendees, not seasoned maintainers. Optimize example code for **readability over cleverness**: obvious flow, minimal abstraction, comments where a concept is being taught. This is one place a little extra explanation earns its keep.

## Tooling in this environment

- **Skills**: `aws-agents` (`agents-get-started`, `agents-build`, `agents-deploy`, `agents-debug`, `agents-harden`, `agents-optimize`, `agents-connect`, `agents-pay`) and `aws-core` (`amazon-bedrock` covers AgentCore/Harness, plus `aws-iam`, `aws-observability`, `aws-database`, `aws-security`, cost skills). Invoke the matching skill before building or debugging agent code.
- **MCP**: `aws-core` (`run_script` for AWS API calls — prefer it over the AWS CLI in Bash) and `awsknowledge` (AWS docs/skill lookup).

## Status

As of 2026-09-29: the baseline refund bot is built and working in `RefundAgent/`
(Strands + Bedrock, run locally via `agentcore dev`; state in DynamoDB Local via
Docker). Nothing is deployed to AWS. All four failure domains are implemented
correctly, each at a `# WORKSHOP SEAM` marker to be broken later:

1. Idempotency — stable idempotency key to the payment gateway (`tools.py issue_refund`)
2. Session/authoritative status — `Sessions` table + status read from the `Payments` ledger (`store.py`, `tools.py`)
3. Tenant isolation — `customer_id` from request context, tools check ownership (`tools.py`)
4. Timeout/retry/observability — `call_with_timeout` + structured tool logs (`payment_gateway.py`)

Run steps and the seam-by-seam breakdown: `RefundAgent/README.md`. Verify with
`RefundAgent/demo.sh`. Deferred to a later (deploy) phase: AgentCore Memory, real
JWT identity, AgentCore Observability/CloudWatch.
