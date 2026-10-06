# Staff notes

Read this before the workshop. It covers the one design constraint that shapes
everything, what to set up in advance, the errors attendees will hit, and the IAM
policies to paste when a role is missing something.

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
| Policy engine | from the end of M5: `refund_agent_<initials>`, ENFORCE | `refund_identity_<initials>`, ENFORCE |
| What the policy sees | the harness role (`AgentCore::IamEntity`) | `AgentCore::OAuthUser` with the user's claims as tags |
| Rules | agent may use the tools, $200 cap, refund after lookup (Dogwood) | identity binding, $200 cap, refund after lookup (Dogwood) |

Gateway A stays unguarded through M4 and most of M5, so attendees can see the agent
path is open. At the end of M5 ("Guard the agent's door too") it gets its own policy
engine with every rule that does not need the user: the $200 cap and the Dogwood
lookup rule. The identity rule stays on gateway B only, because gateway A has no
user to compare. That last gap is the point of the debrief, see the bottom of this
file.

## What to set up before the room starts

1. An AWS account per attendee with console access, region `us-east-1`. If
   people share one account instead, the naming rule below is what keeps their
   resources apart, and they type their initials in the tester's Settings.
2. Bedrock model access to a Claude model in `us-east-1`.
3. Decide the Lambda approach. Either pre-deploy one shared Lambda from
   `tools/lambda_function.py` and hand out its ARN, or let each attendee
   paste the file into the Lambda console. It is one file with no dependencies, so
   pasting works fine and teaches more.
4. Tell everyone the naming rule: suffix every resource with your initials.
5. Run through the tester setup and M1 to M5 yourself once. It takes about an hour.

## Reference setup

A working copy already exists in account `925061584404`, region `eu-central-1`.
It was built before the workshop moved to `us-east-1`, so the tester only finds it
when deployed in `eu-central-1` (or with every ID under **Settings → Enter manually**).
Use it to demo, or to compare against when an attendee is stuck.

| Thing | Value |
|---|---|
| Cognito pool | `agentcore-refund-agents-username` / `eu-central-1_IBYcvqkas` |
| App client | `1m56a1m03oeop2fkhdlsmues96`, no secret, username sign-in |
| Users | `alice`, `bob`, `mateo` |
| Harness | `refund_agent_datamax-QCI0fxNU0y`, Custom JWT, memory attached |
| Gateway A | `refund-agent-gateway-2jn3rd7vee`, AWS IAM |
| Gateway B | `refund-gateway-identity-pju6ekwsja`, Custom JWT |
| Policy engine | `refund_identity-krpy87hgua`, ENFORCE, `identity_binding`, `refund_cap_200`, `refund_after_lookup` (Dogwood) |
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
| M3: the new chat still remembers with their own memory (steps 2 to 6) | their memory has a long-term strategy, or the harness is still on managed memory | check the harness's Memory section points at `refund_memory_<initials>`, and that memory has no strategies |
| M3: the new chat forgets with managed memory (step 10) | long-term facts are extracted in the background and were not there yet, or they asked as a different user | wait a minute or two and ask again, logged in as the same user. To check, open the memory and look for a record under `/actors/<username>/facts/` |
| M3: switching back to managed memory, the agent does not know the colour from before | the harness may provision a fresh managed memory, so the earlier facts are not in it | expected. Tell it again in step 8 |
| Gateway target fails with `Gateway service is not authorized to perform AssumeRole on Gateway role` | the service role was created seconds earlier and has not propagated | wait a minute and add the target again. The role is fine. |
| Harness test chat: `Failed to load tool … Failed to start MCP client … 403 Forbidden` | gateway A refused the agent. Either its inbound auth is Custom JWT (the quick-start default; the agent sends no token), or it is AWS IAM and the harness role lacks `InvokeGateway` | JWT: recreate gateway A with **AWS IAM** auth. IAM: add policy [C](#c-harness-execution-role-call-the-gateway) to the harness execution role, wait a minute, reload the chat |
| Tool calls fail and the Lambda's CloudWatch log stays empty | the gateway's service role cannot invoke the Lambda | add policy [B](#b-gateway-role-invoke-the-lambda) to the gateway service role. Console-created roles usually have it, so check first |
| Lambda console **Test** fails | the console cannot set the tool name the gateway passes in `context.client_context` | test through the gateway instead: the tester's Tools tab |
| `Runtime.ImportModuleError` or handler not found | file name and handler setting do not match | file `lambda_function.py`, handler `lambda_function.lambda_handler` (the console default) |
| Agent answers without calling a tool, or makes up an order | the gateway is not in the harness's tools, or the prompt does not push it to use them | check the harness's Tools list and the system prompt from M2 |
| M5 step 10: no option to write the policy in natural language, or it cannot see the tools | generation uses the gateway's tool schema, so it needs the policy engine and gateway B to exist, with gateway B's `orders` target READY | finish steps 1 to 8 first and pick gateway B. As a fallback, paste `policies/refund-cap.cedar` with their gateway B ARN |
| M5 step 10: the generated policy is a `permit`, the wrong tool, or a different amount | the sentence was read differently than meant | reword it plainly ("Forbid every user from processing a refund when the refund amount is greater than $200") and generate again. Compare with `policies/refund-cap.cedar` |
| M5 step 10: generated policy uses `context.input.amount > 200` and fails validation | `amount` is a Cedar decimal, so plain `>` does not type-check | regenerate, or edit it to `context.input.amount.greaterThan(decimal("200.0"))` before saving |
| Cedar: `unable to guarantee safety of access to tag "username"` | `getTag` with no presence check | add `principal.hasTag("username") &&` in front of the comparison |
| Cedar: `unexpected type: expected Long but saw decimal` | the tool's `amount` is a JSON Schema `number`, which Cedar treats as a decimal | use `context.input.amount.greaterThan(decimal("200.0"))`, not `> 200` |
| Cedar: `Overly Restrictive: Policy Engine will deny every request for AgentCore::IamEntity` | a bare `principal` in a `forbid` also covers IAM callers, and no `permit` exists for them | scope it: `principal is AgentCore::OAuthUser` |
| Tools tab: every call fails with code `-32022`, unsupported protocol version | the MCP request is missing the `MCP-Protocol-Version` header | already handled in the tester. If they wrote their own client, send `MCP-Protocol-Version: 2025-11-25`. Setting it in the `initialize` params alone is not enough. |
| Tools tab shows no tools | gateway URL wrong, or the target is not READY | check the URL ends in `/mcp` and the target status |
| Every Tools call is denied, even their own name | the gateway B target is not named `orders`, so the action names do not match the policies | recreate the target named `orders`, or edit the action names in both policies |
| M4 step 17: the agent checks the tool anyway, so there is no wrong answer to show | the model followed the tool hints in the tester's prompt | that is a fine outcome: point out nothing *forced* it. To show the stale memory, open the memory's records under `/actors/mateo/facts/` and compare with the Lambda |
| M4 step 17: still answers from memory after step 18 | the prompt change was not saved, or **Tell the agent who I am** was toggled, which resets the prompt | re-open **Settings → Enter manually** and check the sentence is there, then a new chat |
| M4 step 14: mateo's agent already says something odd about M-3001 | earlier tests left facts in mateo's memory | delete the records under `/actors/mateo/facts/`, or use the attendee's own user and one of their orders |
| M5 tests fail on M-3001 | step 20 was skipped, so it is still `cancelled` | set it back to `delivered` and **Deploy** |
| An attendee's own user sees no orders | they added themselves in M1 but no orders in the Lambda, or `customer_id` in their orders does not match the Cognito user name exactly (case, spelling) | compare the token panel's `username` with the `customer_id` in their `ORDERS` entries, fix, **Deploy** the Lambda |
| Lambda `Runtime.UserCodeSyntaxError` after adding their own orders | a missing comma or brace in the new `ORDERS` entry | each entry ends with `},`; compare with the example in LABS M4 step 3 |
| Agent asks "what is your customer id?" | **Tell the agent who I am** is not ticked | tick it in the tester's Settings |
| Tester: a resource stays unticked | it has not been created yet, or (shared account) the name does not follow `refund_<initials>` | create it, or fill that field under Settings → Enter manually |
| Tools tab: every call fails with a validation error about a missing session | a Dogwood policy is attached and the call has no `x-amzn-bedrock-agentcore-policy-session-id` | use the tester's Tools tab, which sends it. Their own clients must send it too |
| Tools tab: allowed calls fail with `Failed to get workload identity token`, denials still work | the tester always sends a policy session, and the gateway needs `GetWorkloadAccessToken` for it as soon as a policy engine is attached | add the M5 step 4 inline policy |
| Tools tab: every call fails with `AccessDenied` on `GetWorkloadAccessToken` | gateway B's role lacks the M5 step 4 inline policy | add `policies/gateway_temporal_iam.json` to the gateway's service role |
| Refund after a lookup is still denied | the lookup was in another policy session, was itself denied, or the refund was sent before the lookup's response was recorded | same session, a lookup that was allowed, and a second's pause |
| HTTP 409 `ConflictException` right after adding the Dogwood policy | adding or changing a temporal policy ends open sessions | expected. The tester starts a new session and retries by itself |
| Tester: "Lookup failed: AccessDenied" | the `chat-ui-lookup` inline policy is missing from the tester Lambda's role | add it (LABS.md, The tester app, step 5) |
| Refund denied unexpectedly | over the $200 cap (a policy denial, from the gateway), or the order is not delivered, or it was already refunded (a Lambda error) | expected. Check the order in the Lambda data. |
| A refund over $200 went through | no policy engine on that gateway yet, or it is in LOG_ONLY. The Lambda has no cap of its own, on purpose | expected before ENFORCE. Refunds reset on the Lambda's next cold start |

## The IAM policies (copy-paste)

Replace `<REGION>`, `<ACCOUNT_ID>`, `<FUNCTION_NAME>` and `<GATEWAY_ARN>`. The
gateway's own temporal-policy grant for M5 is in `policies/gateway_temporal_iam.json`.

**Which role is which:** the *gateway service role* is what a gateway uses to call
**out** to the Lambda (policies A and B). The *harness execution role* is what the
agent uses; policy C lets it call **in** to gateway A.

### A. Gateway role: trust policy

*IAM → Roles → the gateway's service role → Trust relationships → Edit.* Lets the
gateway service assume the role.

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

### B. Gateway role: invoke the Lambda

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

### C. Harness execution role: call the gateway

*IAM → Roles → the harness's execution role → Add permissions → Create inline
policy → JSON.* Only needed for gateway A, whose inbound auth is AWS IAM.

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

## The tool schema, in more depth

LABS gives attendees `tools/tool-schema.json` to paste. For questions:

- **The model reads it, the Lambda doesn't.** The gateway turns it into the MCP
  `tools/list` the agent sees. Changing a `description` changes the agent's
  behavior without touching code, which makes a good live demo.
- **Names get a target prefix.** The agent sees `<target name>___find_orders`. The
  gateway passes that full name to the Lambda in
  `context.client_context.custom["bedrockAgentCoreToolName"]`, and the Lambda routes
  on the part after `___`. Policies use the full name, which is why gateway B's
  target must be called `orders`.
- **`name` must match a tool in the Lambda.** A mismatch returns `Unknown tool`.
- **`required` is enforced on the model's side**, not the Lambda's. The Lambda still
  checks its own arguments.
- **Arguments arrive as the Lambda `event`**, just the argument dict, for example
  `{"customer_id": "alice", "item_query": "keyboard"}`.

## Resets

- Lambda refund state is in memory and resets on a cold start, so refunds come back
  by themselves after a few minutes of idling. Mention this if someone is confused
  that A-1001 is refundable again.
- Policy engine misbehaving: set the mode to LOG_ONLY, fix the policy, set it back
  to ENFORCE.
- Attendee's account is a mess: have them rebuild with new initials rather than
  untangle it.

## What each piece is, for answering questions

- `tools/lambda_function.py` is the **real** tool backend for M4 and M5. Four
  tools: `find_orders`, `get_order_transaction`, `process_refund`,
  `get_refund_status`. Every tool takes `customer_id` and only answers for that
  customer.
- The Lambda does **not** check who the caller really is. That is on purpose. The
  policy engine on gateway B is what makes `customer_id` honest. Keeping the check
  out of the Lambda is what lets M4 and M5 look different.
- `tools/tool-schema.json` is the same four tools in the shape the gateway
  target wants. Both gateways use it.
- `policies/identity-binding.cedar` and `refund-cap.cedar` are the two Cedar M5
  policies, with comments explaining the three validator errors we hit writing them.
- `policies/refund-after-lookup.dogwood` is the Dogwood M5 policy. It is a `forbid`
  with `unless temporal { formerly … }`, checked against a test engine with
  `FAIL_ON_ANY_FINDINGS`. It needs a `permit` beside it (identity-binding), or the
  analyzer rejects it as "Overly Restrictive".
- `chat/lambda_function.py` is the tester, one file holding the page, a `/lookup`
  route and a `/mcp` route. The Chat tab calls the harness. The Tools tab speaks MCP
  to gateway B through `/mcp` rather than straight from the browser, because
  browsers may not send the policy session header Dogwood needs. The gateway still
  gets the user's own token, so policies still see the user.

## Guarding gateway A (end of M5)

- Cedar denies by default, so the `agent_access` permit for `AgentCore::IamEntity`
  must exist before the engine is attached, or the agent loses every tool. If an
  attendee's chat suddenly cannot find any orders after step 18, this is why.
- The rules use `principal is AgentCore::IamEntity`, not `OAuthUser`: on this door
  the caller is the harness role. Policies written for gateway B do nothing here.
- Action names assume the target is named `orders` (M4 step 9). Gateway A's target
  in the reference account is named `target-quick-start-grvilq`, so recreate it as
  `orders` before adding these policies there.
- **Not yet verified:** whether the harness sends a policy session id when it calls a
  gateway. The Dogwood rule (step 16) needs one. If it does not, every chat tool call
  fails with a missing-session error once the engine is attached. The fix is to
  delete `agent_refund_after_lookup`; the cap still works. Check this in rehearsal
  and update LABS either way.
- Also not verified: whether the console lets one policy engine be attached to two
  gateways. The labs avoid the question with a second engine.
- Per-user rules are still impossible here. If attendees ask "so is the agent safe
  now?": the agent can no longer refund over $200 or refund an order it never looked
  up, but it can still be talked into using another customer's id. Carrying the
  user's identity through the agent needs either agent code that forwards the token
  (export the harness to Strands) or an identity provider with token exchange.
