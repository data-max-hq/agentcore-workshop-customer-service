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

| | `refund-gw` | `refund-gw-jwt` |
|---|---|---|
| Inbound auth | AWS IAM | Custom JWT |
| Who calls it | the harness | the tester app, with the user's token |
| Policy engine | none | yes, in ENFORCE |
| What the policy sees | the harness role | `AgentCore::OAuthUser` with the user's claims as tags |

`refund-gw` is left unguarded on purpose. The contrast between the two doors is the
lesson in M4 and M5. Do not "fix" it by adding a policy engine to `refund-gw` without
reading the note at the bottom of this file.

## What to set up before the room starts

1. An AWS account per attendee with console access, region `us-east-1`. If
   people share one account instead, the naming rule below is what keeps their
   resources apart, and they type their initials in the tester's Settings.
   Check two account guardrails before the day, in one attendee account:
   - **Region.** Workshop accounts are limited to `us-east-1`, which is why the
     labs use it. Resources made in any other region fail or are invisible to
     the tester.
   - **Public Lambda permissions.** The tester is a function URL with auth NONE,
     which needs a resource-based policy granting `*`. If an SCP blocks that,
     the tester cannot work and you need another plan.
2. Nothing to enable for the model: the labs use **Amazon Nova Pro**, which is
   first-party and needs no AWS Marketplace subscription. If you switch to a
   third-party model such as Claude, an admin must send one message to it in
   **Bedrock** → **Playground** in every attendee account first; the harness role
   cannot subscribe, so the agent fails with `aws-marketplace:Subscribe` access
   denied.
3. Decide the Lambda approach. Either pre-deploy one shared Lambda from
   `tools/lambda_function.py` and hand out its ARN, or let each attendee
   paste the file into the Lambda console. It is one file with no dependencies, so
   pasting works fine and teaches more.
4. Tell everyone the naming rule: suffix every resource with your initials.
5. Run through the tester setup and M1 to M5 yourself once, in an account set up
   like the attendees' (not the reference account). It takes about an hour.

## Reference setup

A working copy already exists in account `925061584404`, region `eu-central-1`.
It was built before the workshop moved to `us-east-1`, so the tester only finds it
when deployed in `eu-central-1` (or with every ID under **Settings → Enter manually**).
It also still uses a Claude model, so its ARNs and model differ from what attendees
build. Use it to demo, or to compare against when an attendee is stuck.

| Thing | Value |
|---|---|
| Cognito pool | `agentcore-refund-agents-username` / `eu-central-1_IBYcvqkas` |
| App client | `1m56a1m03oeop2fkhdlsmues96`, no secret, username sign-in |
| Users | `alice`, `bob`, `mateo` |
| Harness | `refund_agent_datamax-QCI0fxNU0y`, Custom JWT, memory attached |
| `refund-gw` | `refund-agent-gateway-2jn3rd7vee`, AWS IAM |
| `refund-gw-jwt` | `refund-gateway-identity-pju6ekwsja`, Custom JWT |
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
| Harness test chat: `Failed to load tool … Failed to start MCP client … 403 Forbidden` | `refund-gw` refused the agent. Either its inbound auth is Custom JWT (the quick-start default; the agent sends no token), or it is AWS IAM and the harness role lacks `InvokeGateway` | JWT: recreate `refund-gw` with **AWS IAM** auth. IAM: add policy [C](#c-harness-execution-role-call-the-gateway) to the harness execution role, wait a minute, reload the chat |
| Tool calls fail and the Lambda's CloudWatch log stays empty | the gateway's service role cannot invoke the Lambda | add policy [B](#b-gateway-role-invoke-the-lambda) to the gateway service role. Console-created roles usually have it, so check first |
| Lambda console **Test** fails | the console cannot set the tool name the gateway passes in `context.client_context` | test through the gateway instead: the tester's Tools tab |
| `Runtime.ImportModuleError` or handler not found | file name and handler setting do not match | file `lambda_function.py`, handler `lambda_function.lambda_handler` (the console default) |
| Agent answers without calling a tool, or makes up an order | the gateway is not in the harness's tools, or the prompt does not push it to use them | check the harness's Tools list and the system prompt from M2 |
| Creating a policy: `ARN "YOUR_REFUND_GW_JWT_ARN" should have 6 components separated by ":"` | the placeholder was pasted without being replaced | replace it with the `refund-gw-jwt` ARN from the gateway page, inside the quotes |
| Cedar: `unable to guarantee safety of access to tag "username"` | `getTag` with no presence check | add `principal.hasTag("username") &&` in front of the comparison |
| Cedar: `unexpected type: expected Long but saw decimal` | the tool's `amount` is a JSON Schema `number`, which Cedar treats as a decimal | use `context.input.amount.greaterThan(decimal("200.0"))`, not `> 200` |
| Cedar: `Overly Restrictive: Policy Engine will deny every request for AgentCore::IamEntity` | a bare `principal` in a `forbid` also covers IAM callers, and no `permit` exists for them | scope it: `principal is AgentCore::OAuthUser` |
| Tools tab: every call fails with code `-32022`, unsupported protocol version | the MCP request is missing the `MCP-Protocol-Version` header | already handled in the tester. If they wrote their own client, send `MCP-Protocol-Version: 2025-11-25`. Setting it in the `initialize` params alone is not enough. |
| Tools tab shows no tools | gateway URL wrong, or the target is not READY | check the URL ends in `/mcp` and the target status |
| Every Tools call is denied, even their own name | the `refund-gw-jwt` target is not named `orders`, so the action names do not match the policies | recreate the target named `orders`, or edit the action names in both policies |
| Agent asks "what is your customer id?" | **Tell the agent who I am** is not ticked | tick it in the tester's Settings |
| Tester: a resource stays unticked | it has not been created yet, or (shared account) the name does not follow the lab's naming (`refund_<initials>`, `refund-gw-jwt` `refund-gw-jwt-<initials>`) | create it, or fill that field under Settings → Enter manually |
| Tools tab: every call fails with a validation error about a missing session | a Dogwood policy is attached and the call has no `x-amzn-bedrock-agentcore-policy-session-id` | use the tester's Tools tab, which sends it. Their own clients must send it too |
| Tools tab: allowed calls fail with `Failed to get workload identity token`, denials still work | the tester always sends a policy session, and the gateway needs `GetWorkloadAccessToken` for it as soon as a policy engine is attached | add the M5 step 4 inline policy |
| Tools tab: every call fails with `AccessDenied` on `GetWorkloadAccessToken` | `refund-gw-jwt`'s role lacks the M5 step 4 inline policy | add `policies/gateway_temporal_iam.json` to the gateway's service role |
| Refund after a lookup is still denied | the lookup was in another policy session, was itself denied, or the refund was sent before the lookup's response was recorded | same session, a lookup that was allowed, and a second's pause |
| HTTP 409 `ConflictException` right after adding the Dogwood policy | adding or changing a temporal policy ends open sessions | expected. The tester starts a new session and retries by itself |
| Attendee cannot find "the tester" | it is the page at the tester Lambda's **Function URL** (Lambda → the function → Function overview → Function URL), titled **AgentCore Chat** | open it and bookmark it (LABS.md, The tester app, step 8) |
| Attendee cannot find **Find my resources** | it is inside the **⚙ Settings** box, which starts collapsed | click **⚙ Settings** to open it |
| Lambda console, on **Deploy**: `The provided project hash … does not match the remote hash` | the code editor still holds an older copy of the function, typically after deleting and recreating a function with the same name, or with two tabs open on it | close other tabs on that function, hard-refresh (Cmd/Ctrl+Shift+R), paste again and **Deploy** |
| Tester: "Lookup failed: AccessDenied" | the `chat-ui-lookup` inline policy is missing from the tester Lambda's role | add it (LABS.md, The tester app, step 6) |
| Tester URL: `Forbidden`, and Lambda says the URL "is missing permissions required for public access" | a NONE-auth URL needs both `lambda:InvokeFunctionUrl` and `lambda:InvokeFunction` for `*`; the console sometimes adds only one | LABS.md, The tester app, step 7 (**Add permissions** → **Function URL** → **NONE** adds both). If that fails with AccessDenied, an SCP blocks public Lambda permissions in the account |
| Tester URL: `Internal Server Error`, log says `Runtime.UserCodeSyntaxError` with `nodejs` in it | the function was created with the default Node.js runtime, so the Python code is in `index.mjs` | delete and recreate with **Python 3.13** (LABS.md, The tester app, step 3). Also check the log ARN says `us-east-1` |
| Chat: `Model access is denied … aws-marketplace:ViewSubscriptions, aws-marketplace:Subscribe` | the harness uses a third-party model (e.g. Claude) the account has not subscribed to, and the harness role cannot subscribe | switch the harness to **Amazon Nova Pro** (LABS.md, M2 step 3), or have an admin send one message to that model in **Bedrock** → **Playground** and wait 5 minutes |
| Chat: `Harness is not in an invokable state: CREATING` (or `UPDATING`) | the message was sent before the harness was READY | wait for READY and send again |
| Harness ends up with a new Cognito pool it did not ask for | **Quick create configurations with Cognito** was chosen under Inbound Auth | edit the harness: **Use JSON Web Tokens (JWT)** → **Use existing Identity provider configurations**, with the M1 pool's discovery URL and client ID |
| M3: agent refuses "what is my favourite colour?" as off-topic | Nova Pro sticks to the system prompt ("orders and refunds") more strictly than Claude did | not a memory problem. Use an on-topic fact instead, e.g. "for any refund I want the money back on my original card", then "how do I like my refunds paid?" |
| M3 step 10: a new chat still does not remember | long-term memories are extracted in the background, usually within a minute or two; or the harness is still on the plain memory from step 2; or **Tell the agent who I am** is ticked and Nova goes hunting for orders instead | wait and ask again; check the harness is back on **managed memory** with the semantic `/actors/{actorId}/facts/` config; untick the box until M4 |
| After M4 the agent still uses `file_operations`, and Test Harness shows no error | `refund-gw` has **no target**: it was added in the create wizard while the new service role was not usable yet, and got dropped silently | open `refund-gw` → **Targets**; if empty, add `orders` again (LABS M4 step 11) and wait for READY |
| Before M4, asked for orders, the agent calls `file_operations` on a path like `/user_data/<name>/orders.txt` and says it cannot find them | the harness has built-in tools (files in its sandbox); with no order tool yet, Nova tries those | expected before M4 (LABS M2 step 13 points it out). After M4 it should call `orders___find_orders`; if it still reaches for files, check the gateway is in the harness's **Tools** list and READY |
| In M2 the agent already knows the user's name and mentions `find_orders` | **Tell the agent who I am** is ticked early; that sends the M4 system prompt, which names the user and the tools | expected once ticked. Untick it to see M2 as written |
| Chat reply starts with the model's own reasoning ("The user has requested… I need to use…") | Nova writes its reasoning in `<thinking>` tags; an older tester showed the text inside them | paste the current `chat/lambda_function.py` and **Deploy**. The tester now hides it; **Raw response** still shows it |
| Refund denied unexpectedly | over the $200 cap, or the order is not delivered, or it was already refunded | expected. Check the order in the Lambda data. |

## The IAM policies (copy-paste)

Replace `<REGION>`, `<ACCOUNT_ID>`, `<FUNCTION_NAME>` and `<GATEWAY_ARN>`. The
gateway's own temporal-policy grant for M5 is in `policies/gateway_temporal_iam.json`.

**Which role is which:** the *gateway service role* is what a gateway uses to call
**out** to the Lambda (policies A and B). The *harness execution role* is what the
agent uses; policy C lets it call **in** to `refund-gw`.

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
policy → JSON.* Only needed for `refund-gw`, whose inbound auth is AWS IAM.

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
  on the part after `___`. Policies use the full name, which is why `refund-gw-jwt`'s
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
  policy engine on `refund-gw-jwt` is what makes `customer_id` honest. Keeping the check
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
  route and a `/mcp` route. It takes its region from where the Lambda runs and from
  the pool ID, so nothing in it is tied to `us-east-1`. It hides Nova's
  `<thinking>` blocks in chat replies. The Chat tab calls the harness. The Tools tab speaks MCP
  to `refund-gw-jwt` through `/mcp` rather than straight from the browser, because
  browsers may not send the policy session header Dogwood needs. The gateway still
  gets the user's own token, so policies still see the user.

## If you want to guard `refund-gw` too

You can, but it is more work than it looks, and you lose the M4 and M5 contrast.

- Cedar denies by default, so attaching a policy engine to `refund-gw` without a
  `permit` for `AgentCore::IamEntity` will block the agent from every tool.
- `refund-gw`'s target in the reference account is named `target-quick-start-grvilq`,
  so its action names are `target-quick-start-grvilq___find_orders` and so on. You
  would want to recreate that target as `orders` first.
- You still cannot write per-user rules there. Only rules about the arguments, like
  the $200 cap, and about the agent's own role.
