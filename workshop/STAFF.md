# Staff notes — read before the workshop

# Console workshop (refund-agent-workshop.ipynb)

## Errors we've hit (symptom → cause → fix)

| Attendee sees | Cause | Fix |
|---|---|---|
| Gateway target fails: *"Gateway service is not authorized to perform AssumeRole on Gateway role. Update trust policy and retry"* | Usually: the console just created the Gateway role and IAM hasn't propagated yet | **Wait ~1 min and retry creating the target.** That fixed it for us. If it persists: check the role's trust policy ([A](#a-gateway-role--trust-policy)), and that its `aws:SourceArn` region matches the Gateway's region |
| Harness test chat: *"Failed to load tool … Failed to start MCP client … 403 Forbidden"* | The Gateway refused the agent's connection. Either the Gateway's inbound auth is **JWT/Cognito** (quick start default — the agent sends no token), or it's **IAM** and the Harness role lacks `InvokeGateway` | Check the Gateway's inbound auth. JWT → recreate the Gateway with **IAM** auth. IAM → add policy [C](#c-harness-execution-role--call-the-gateway) to the **Harness execution role**. Wait a minute, reload the chat |
| Tool call errors / Lambda never invoked (nothing in its CloudWatch logs) | The Gateway role can't invoke the Lambda | Add policy [B](#b-gateway-role--invoke-the-lambda) to the **Gateway service role** (console-created roles usually have it — check first) |
| Lambda console **Test** returns `Unknown tool: ` | The test event has no `tool_name` (the console can't set `client_context` the way the Gateway does) | Add `"tool_name": "find_orders"` (or `get_order_transaction`) to the test event |
| `Runtime.ImportModuleError` / handler not found | Code file and handler setting don't match | File must be `lambda_function.py` with handler `lambda_function.lambda_handler` (the console default) |
| Agent answers without calling a tool, or makes up an order | Tools not attached, or the prompt doesn't push it to use them | Check the Gateway is in the Harness's tools; check the system prompt from step 1 is in place |

## The IAM policies (copy-paste)

Replace `<REGION>`, `<ACCOUNT_ID>`, `<FUNCTION_NAME>`, `<GATEWAY_ARN>`.

### A. Gateway role — trust policy
*IAM → Roles → the Gateway's service role → Trust relationships → Edit.* Lets the Gateway service assume the role.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "bedrock-agentcore.amazonaws.com" },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": { "aws:SourceAccount": "<ACCOUNT_ID>" },
        "ArnLike": { "aws:SourceArn": "arn:aws:bedrock-agentcore:<REGION>:<ACCOUNT_ID>:gateway/*" }
      }
    }
  ]
}
```

### B. Gateway role — invoke the Lambda
*Same role → Permissions → Add permissions → Create inline policy → JSON.*

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "lambda:InvokeFunction",
      "Resource": "arn:aws:lambda:<REGION>:<ACCOUNT_ID>:function:<FUNCTION_NAME>"
    }
  ]
}
```

### C. Harness execution role — call the Gateway
*IAM → Roles → the Harness's execution role → Add permissions → Create inline policy → JSON.* Only needed with **IAM** inbound auth on the Gateway. This one is in the attendee notebook (step 4).

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "bedrock-agentcore:InvokeGateway",
      "Resource": "<GATEWAY_ARN>"
    }
  ]
}
```

**Which role is which:** the *Gateway service role* is what the Gateway uses to call **out** (to the Lambda) — policies A + B. The *Harness execution role* is what the agent uses — policy C lets it call **in** to the Gateway.

## The tool schema, in more depth

The notebook gives attendees the short version (name / description / inputSchema). For questions:

- **The model reads it, the Lambda doesn't.** The Gateway turns it into the MCP `tools/list` the agent sees. Changing a `description` changes agent behavior without touching code — a good live demo.
- **Names get a target prefix.** The agent sees `<target-name>___find_orders`. The Gateway passes that full name to the Lambda in `context.client_context.custom["bedrockAgentCoreToolName"]`; the handler routes on the part after `___`, so the target can be named anything.
- **`name` must match a tool registered in the Lambda** (`@tool("find_orders")`). A mismatch → the Lambda returns `Unknown tool`.
- **`required`** is enforced on the model's side, not the Lambda's — the handler still checks its own arguments (`Missing required parameter …`).
- **Inline vs S3:** same JSON either way; inline is simplest in the console.
- **Arguments arrive as the Lambda `event`** — just the argument dict, e.g. `{"customer_id": "alice", "item_query": "keyboard"}`.

---

# CLI / IaC path (not used in the console workshop)

The notes below are for the original `agentcore` CLI + CDK setup in this repo.

## Gotchas cheat sheet (symptom → cause → fix)

| Attendee sees | Cause | Fix |
|---|---|---|
| `agentcore: command not found` | CLI not installed | `npm install -g @aws/agentcore@0.31.0` |
| `No agent project found` / "old Python CLI" | the deprecated `bedrock-agentcore-starter-toolkit` is on PATH | uninstall it; install `@aws/agentcore` (npm). `make check` detects this. |
| `make dev` fails, `agentcore` not found | installed but PATH doesn't include the npm global bin | ensure npm global bin (e.g. `~/.local/bin`) is on PATH |
| Chat UI shows raw `{"response": ...}` JSON | entrypoint returned a dict instead of streaming | `main.py` must `yield` events (already fixed here) |
| Chat says "authentication issue / not signed in" | no identity in the request | local dev defaults to `alice`; `LOCAL_DEV_CUSTOMER` overrides |
| Lambda deploy fails: `pyproject.toml not found` | a Gateway Lambda code dir needs one | `infra/payment/pyproject.toml` exists here; any new Lambda dir needs one too |
| **Memory panel empty** | `MEMORY_REFUNDMEMORY_ID` not set → agent used the local in-process dict | expected locally; only populates against the **deployed** runtime (see rehearsal Q1) |
| Bedrock `AccessDenied` / model not found | account lacks Bedrock access to Claude in us-east-1 | enable model access; confirm region |

## Version pinning (the CLI is pre-1.0 — pin it)

Verified working set (2026-09-30):

- `@aws/agentcore` **0.31.0** — install with `@0.31.0`, don't let attendees grab latest
- `@aws/agentcore-cdk` **0.1.0-alpha.53** (in `agentcore/cdk/package.json`)
- `aws-cdk-lib` ~2.261.0, Node 20+, Python 3.12+

⚠️ On deploy the CLI's "Sync CDK dependencies" step may **auto-bump** the alpha
CDK dep (we saw `alpha.53 → alpha.54`). Decide during rehearsal whether to let it
bump or pin it, and lock the same version on every machine.

## Deploy rehearsal checklist — do this before the workshop

Done locally so far: `agentcore validate` = Valid, and **CDK synth passes with
runtime + Gateway + Memory** (config is structurally sound). **Not yet verified:
an actual `agentcore deploy`.** In a sandbox account, run through this and record
what breaks:

1. `aws sts get-caller-identity` — right account + region (us-east-1).
2. `make infra-preview` — dry-run clean.
3. `make infra-deploy` — approve the one-time **CDK bootstrap**. Watch for:
   - IAM permission errors during bootstrap/deploy
   - the runtime, gateway, Lambda, and Memory all creating
4. **Q1 — how do attendees exercise Memory/Gateway?** Confirm whether
   `agentcore dev` locally picks up the **deployed** `MEMORY_*_ID` /
   `PAYMENT_GATEWAY_URL`, or whether they must invoke the **deployed** runtime
   (e.g. `agentcore invoke`). Whichever works, put the exact command into
   LABS.md M3/M4 (they're marked ⏳ until then).
5. **Q2 — gateway → Lambda permission.** Issue a refund on the deployed agent and
   confirm the Gateway can invoke the Lambda (check the Lambda's CloudWatch logs
   for the `process_refund` call). If it 403s, the target's invoke permission
   needs sorting.
6. **Q3 — Memory writes.** Confirm the conversation actually lands in the Memory
   panel / `agentcore` memory APIs.
7. `make infra-down` then verify in the console that resources are gone (no spend).
8. Time the whole run — that sets the real M2–M5 budget.

Update LABS.md (flip ⏳ → ✅) and this file with anything you hit.

## Fast resets during the workshop

- Local agent stuck: `pkill -f "agentcore dev"` then `make dev`.
- Deploy in a weird state: re-run `make infra-deploy` (reconciles the CDK stack).
- Full teardown: `make infra-down`.
- Fresh account: attendees get a new one; just re-run M2.

## What each moving part is (for answering questions)

- `main.py` — the whole agent: entrypoint + 3 tools + in-memory `ORDERS`. Memory
  and Gateway are wired but **env-var-guarded**, so they're inert locally and
  activate when deployed.
- `memory/session.py` — returns `None` (no-op) unless `MEMORY_REFUNDMEMORY_ID` is set.
- `infra/payment/handler.py` — the fake payout Lambda (Gateway target); mock, no real money.
- `agentcore/agentcore.json` — declares runtime + PaymentGateway + RefundMemory; `agentcore deploy` builds it via CDK.
- The chat UI + Timeline/Resources/Memory panels on :8081 are AWS's **agent
  inspector** (ships with `agentcore dev`) — not custom code.
