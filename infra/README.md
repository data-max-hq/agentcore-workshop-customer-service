# infra/ — payment gateway as an AgentCore Gateway + Lambda

A PoC that moves the payout from an **in-process tool** (`issue_refund` in
`app/RefundAgent/main.py`) to a **managed AgentCore Gateway MCP tool** backed by
an AWS Lambda. The payout is still **fake** — a mock, no real
money and no real processor — it just now runs as cloud infrastructure the agent
calls over MCP.

This is the "AgentCore Gateway vs self-hosted MCP" trade-off from the top-level
README, made concrete.

## What's here

```
infra/
  payment/handler.py   the fake-payout Lambda: process_refund + get_refund_status
  README.md            this file
```

The gateway itself is declared in **`agentcore/agentcore.json`** (that's where
AgentCore reads infrastructure from — the CDK in `agentcore/cdk/` just builds
what the spec describes). The relevant block:

```jsonc
"agentCoreGateways": [{
  "name": "PaymentGateway",
  "protocolType": "MCP",
  "authorizerType": "NONE",
  "targets": [{
    "name": "payment",
    "targetType": "lambda",              // AgentCore builds + deploys the Lambda from our code
    "toolDefinitions": [ process_refund, get_refund_status ],
    "compute": {
      "host": "Lambda",
      "implementation": { "language": "Python", "path": "infra/payment", "handler": "handler.lambda_handler" },
      "pythonVersion": "PYTHON_3_12"
    }
  }]
}]
```

At deploy time AgentCore zips `infra/payment/`, creates the Lambda, and exposes
its two tools through a managed MCP Gateway. Each tool call arrives at the Lambda
with the tool name in `context.client_context.custom["bedrockAgentCoreToolName"]`
as `payment___<tool>`; `handler.py` routes on that.

## Try the Lambda locally (no AWS)

```bash
python3 infra/payment/handler.py     # runs the built-in self-check
```

## Deploy

Prereqs: AWS credentials for the target account (deploys to the account/region
`agentcore` is configured for) and the AgentCore CLI.

```bash
make infra-preview   # dry-run: shows what AWS resources would be created, no spend
make infra-deploy    # creates the Gateway + Lambda + IAM (via CDK)
make infra-down      # removes them again
```

> **Footprint:** `agentcore deploy` deploys the **whole project stack**, so it
> also creates the agent **runtime** in the cloud, not just the gateway+lambda.
> The runtime won't serve real traffic unless you also move state
> (`Orders`/`Sessions`/`Payments`) to real DynamoDB — for this PoC you can keep
> running the agent locally with `make dev` and just use the deployed gateway.
> Cost is small (Lambda + Gateway are pennies/idle) and everything is removable
> with `make infra-down`.

## Point the agent at the deployed gateway (follow-up)

Provisioning is done above; to make the **agent call** the gateway tools, add a
small MCP client and include it in the agent's toolset. Sketch:

```python
# app/RefundAgent/mcp_client.py
import os
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

def payment_gateway_client() -> MCPClient | None:
    url = os.environ.get("PAYMENT_GATEWAY_URL")   # set by the deploy; unset locally
    return MCPClient(lambda: streamablehttp_client(url)) if url else None
```

```python
# main.py — add the gateway's tools alongside the local ones
gw = payment_gateway_client()
tools_list = tools.TOOLS + ([gw] if gw else [])   # Strands lists/calls MCP tools for you
agent = Agent(model=load_model(), system_prompt=SYSTEM_PROMPT, tools=tools_list, ...)
```

Guarded on the env var, so local dev without the gateway is unaffected. Say the
word and I'll wire this in.

## ponytail notes

- The Lambda is **stateless** — `process_refund` returns a deterministic
  reference (`rf_<order_id>`), which is idempotent by construction for a demo.
  Real at-most-once payout needs a ledger; add a DynamoDB table + an `iamPolicy`
  grant on the target's `compute` when the PoC needs it.
- No `requirements.txt` — the handler is stdlib-only, so there's nothing to
  install.
