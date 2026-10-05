# Staff notes

<<<<<<< Updated upstream
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
=======
Read this before the workshop. It covers the one design constraint that shapes
everything, what to set up in advance, and the errors attendees will hit.
>>>>>>> Stashed changes

## The constraint you must understand

A managed **Harness cannot pass the signed-in user's token to a Gateway.**

When a harness calls a gateway it can sign with its own AWS role, send nothing, or
send a token from the AgentCore token vault. There is no option that forwards the
caller's token. The vault can do an on-behalf-of exchange, but that needs an
identity provider that supports RFC 8693 token exchange, and Cognito does not.

So on the agent path, the gateway sees `AgentCore::IamEntity`, which is the
harness role. It has none of the user's claims. A rule like
`principal.getTag("username") == "alice"` can never match there.

This is why the workshop uses **two gateways over one Lambda**:

| | Gateway A | Gateway B |
|---|---|---|
| Inbound auth | AWS IAM | Custom JWT |
| Who calls it | the harness | the tester app, with the user's token |
| Policy engine | none | yes, in ENFORCE |
| What the policy sees | the harness role | `AgentCore::OAuthUser` with the user's claims as tags |

Gateway A is left unguarded on purpose. The contrast between the two doors is the
lesson in M5 and M6. Do not "fix" it by adding a policy engine to gateway A without
reading the note at the bottom of this file.

## What to set up before the room starts

1. One AWS account with console access for everyone, region `eu-central-1`.
2. Bedrock model access to a Claude model in `eu-central-1`.
3. Decide the Lambda approach. Either pre-deploy one shared Lambda from
   `infra/orders/lambda_function.py` and hand out its ARN, or let each attendee
   paste the file into the Lambda console. It is one file with no dependencies, so
   pasting works fine and teaches more.
4. Tell everyone the naming rule: suffix every resource with your initials.
5. Run through M2 to M6 yourself once in the account. It takes about an hour.

## Reference setup

A working copy already exists in account `925061584404`, region `eu-central-1`.
Use it to demo, or to compare against when an attendee is stuck.

| Thing | Value |
|---|---|
| Cognito pool | `agentcore-refund-agents-username` / `eu-central-1_IBYcvqkas` |
| App client | `1m56a1m03oeop2fkhdlsmues96`, no secret, username sign-in |
| Users | `alice`, `bob`, `mateo` |
| Harness | `refund_agent_datamax-QCI0fxNU0y`, Custom JWT, memory attached |
| Gateway A | `refund-agent-gateway-2jn3rd7vee`, AWS IAM |
| Gateway B | `refund-gateway-identity-pju6ekwsja`, Custom JWT |
| Policy engine | `refund_identity-krpy87hgua`, ENFORCE, two policies |
| Lambda | `refund_agent_tool` |

`mateo` has a permanent password (`Workshop#2026`). `alice` and `bob` are still on
first login, so the password-change screen can be demonstrated.

## Errors attendees will hit

| What they see | Why | Fix |
|---|---|---|
| Token panel shows a random ID instead of `alice` | the pool signs in by email, so Cognito set the username to a UUID | rebuild the pool with **User name** as the sign-in option. Nothing else fixes it. |
| `USER_PASSWORD_AUTH flow not enabled` | app client missing the flow | turn on ALLOW_USER_PASSWORD_AUTH on the app client |
| `NotAuthorizedException` | wrong user name or password | retype it |
| Tester: 401 or 403 from the agent | discovery URL or allowed clients on the harness do not match the pool | compare them character by character. Tokens also expire after an hour, so sign out and in. |
| Tester: 404 from the agent | wrong ARN, region or endpoint | use the `:harness/` ARN, not the `:runtime/harness_` one |
| `managed by a harness ... cannot be invoked directly` | they pasted the `:runtime/harness_` ARN | use the `:harness/` ARN from the details page |
| Gateway target fails with `Gateway service is not authorized to perform AssumeRole on Gateway role` | the service role was created seconds earlier and has not propagated | wait a minute and add the target again. The role is fine. |
| Cedar: `unable to guarantee safety of access to tag "username"` | `getTag` with no presence check | add `principal.hasTag("username") &&` in front of the comparison |
| Cedar: `unexpected type: expected Long but saw decimal` | the tool's `amount` is a JSON Schema `number`, which Cedar treats as a decimal | use `context.input.amount.greaterThan(decimal("200.0"))`, not `> 200` |
| Cedar: `Overly Restrictive: Policy Engine will deny every request for AgentCore::IamEntity` | a bare `principal` in a `forbid` also covers IAM callers, and no `permit` exists for them | scope it: `principal is AgentCore::OAuthUser` |
| Tools tab: every call fails with code `-32022`, unsupported protocol version | the MCP request is missing the `MCP-Protocol-Version` header | already handled in the tester. If they wrote their own client, send `MCP-Protocol-Version: 2025-11-25`. Setting it in the `initialize` params alone is not enough. |
| Tools tab shows no tools | gateway URL wrong, or the target is not READY | check the URL ends in `/mcp` and the target status |
| Every Tools call is denied, even their own name | the gateway B target is not named `orders`, so the action names do not match the policies | recreate the target named `orders`, or edit the action names in both policies |
| Agent asks "what is your customer id?" | **Tell the agent who I am** is not ticked | tick it in the tester's Settings |
| Tester: a resource stays unticked | it has not been created yet, or (shared account) the name does not follow `refund_<initials>` | create it, or fill that field under Settings → Enter manually |
| Tester: "Lookup failed: AccessDenied" | the `chat-ui-lookup` inline policy is missing from the tester Lambda's role | add it (LABS.md, The tester app, step 5) |
| Refund denied unexpectedly | over the $200 cap, or the order is not delivered, or it was already refunded | expected. Check the order in the Lambda data. |

## Resets

- Local agent stuck: `pkill -f "agentcore dev"` then `make dev`.
- Lambda refund state is in memory and resets on a cold start, so refunds come back
  by themselves after a few minutes of idling. Mention this if someone is confused
  that A-1001 is refundable again.
- Policy engine misbehaving: set the mode to LOG_ONLY, fix the policy, set it back
  to ENFORCE.
- Attendee's account is a mess: have them rebuild with new initials rather than
  untangle it.

## What each piece is, for answering questions

- `app/RefundAgent/main.py` is the **local only** agent used in M1. It has its own
  small set of tools and its own order list, and it defaults the customer to
  `alice`. It is not used in M2 to M6.
- `infra/orders/lambda_function.py` is the **real** tool backend for M5 and M6. Four
  tools: `find_orders`, `get_order_transaction`, `process_refund`,
  `get_refund_status`. Every tool takes `customer_id` and only answers for that
  customer.
- The Lambda does **not** check who the caller really is. That is on purpose. The
  policy engine on gateway B is what makes `customer_id` honest. Keeping the check
  out of the Lambda is what lets M5 and M6 look different.
- `infra/orders/tool-schema.json` is the same four tools in the shape the gateway
  target wants. Both gateways use it.
- `agentcore/policies/identity-binding.cedar` and `refund-cap.cedar` are the two M6
  policies, with comments explaining the three validator errors we hit writing them.
- `ui/lambda_function.py` is the tester, one file holding the page and a `/lookup` route. The Chat tab calls the harness. The Tools tab speaks
  MCP straight to gateway B with the user's token.
- The chat UI on :8081 during M1 is AWS's own agent inspector. It ships with
  `agentcore dev`. We did not write it.

## Older files still in the repo

These are from the earlier CLI-based version of the workshop. They are not used by
M1 to M6 and may confuse people who go looking.

- `agentcore/policies/refund.cedar` and `refund.dogwood` refer to tool names that no
  longer exist (`payment___list_orders` and friends).
- `infra/payment/handler.py` is the old two-tool payout Lambda.
- `infra/interceptor/handler.py` is an unused gateway interceptor.
- `agentcore/agentcore.json` plus `make infra-deploy` still describe the old CDK
  deployment. It is untested and is not part of these labs.

Delete them when you are sure nothing in your run depends on them.

## If you want to guard gateway A too

You can, but it is more work than it looks, and you lose the M5 and M6 contrast.

- Cedar denies by default, so attaching a policy engine to gateway A without a
  `permit` for `AgentCore::IamEntity` will block the agent from every tool.
- Gateway A's target in the reference account is named `target-quick-start-grvilq`,
  so its action names are `target-quick-start-grvilq___find_orders` and so on. You
  would want to recreate that target as `orders` first.
- You still cannot write per-user rules there. Only rules about the arguments, like
  the $200 cap, and about the agent's own role.
