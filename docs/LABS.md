# Labs

Your instructor explains the ideas. This file is just the steps.

**Region for everything: `eu-central-1` (Frankfurt).** Set the region picker in the
AWS console before you start. If you build something in the wrong region, nothing
will find it.

**Name your resources with your initials.** If your initials are AMG, call your
harness `refund_amg`, your gateway `refund_gw_amg`, and so on. You have your own AWS
account, so this is only to keep things tidy. If you ever share an account, it stops
you from editing someone else's work, and the tester uses it to find yours.

## What you are building

```
   you ---- login ----> Cognito
    |
    |  your token
    |
    +---> Chat tab ---> Harness ---> Gateway A ---> Lambda
    |                   (the agent)   (AWS IAM)      (orders,
    |                                                 refunds)
    |                                                   ^
    +---> Tools tab -----------------> Gateway B -------+
                                       (your token,
                                        policies check
                                        who you are)
```

One Lambda. Two ways in. The Chat tab goes through the agent, and the agent shows
the gateway its own AWS identity, not yours. The Tools tab goes straight in with
your login, so the policy engine can see you and can say no.

That difference is the whole point of the workshop.

## The tester app

You will use a small web app for every lab after M1. It runs in your own AWS
account as a Lambda, so you need nothing on your laptop. Set it up once:

1. Go to **Lambda** and choose **Create function**.
2. Choose **Author from scratch**. Name it `refund_ui_<your initials>`, runtime
   **Python 3.13**. Choose **Create function**.
3. In the **Code** tab, paste the contents of `chat/lambda_function.py` from this repo
   over the default code, then choose **Deploy**.
4. Go to **Configuration**, then **General configuration**, then **Edit**. Set the
   **Timeout** to **15** seconds and save.
5. Go to **Configuration**, then **Permissions**, and click the role name. In the
   IAM page that opens, choose **Add permissions**, then **Create inline policy**,
   then **JSON**. Paste the contents of `chat/lambda_policy.json` from this repo,
   choose **Next**, name it `chat-ui-lookup`, and create it.

   > This only lets the app read the names of your pool, harness and gateway, so
   > you never have to copy IDs into it.

6. Back in Lambda, go to **Configuration**, then **Function URL**, then **Create
   function URL**. Choose auth type **NONE** and save.
7. Open the **Function URL** and bookmark it. That is your tester.

As you build things in the labs below, they show up under **Settings** in the
tester by themselves. Press **Find my resources** to check again. If you share an
AWS account with others, type your initials there first.

---

# M1. Run the agent on your laptop

No AWS needed. This is the "before" picture.

1. Install the CLI:
   ```bash
   npm install -g @aws/agentcore@0.31.0
   ```
2. Start the agent from the repo root. Leave it running.
   ```bash
   make dev
   ```
3. Open http://localhost:8081.
4. Ask: **what orders do I have?** You get A-1001 and A-1002.
5. Ask: **refund A-1001.** You get a fake refund.
6. Ask: **what did I just refund?** It remembers.
7. Open the **Timeline** panel and click your last request.

**You are done when** you can see a trace with a model call and tool calls in it,
each with a time next to it.

Now try this:

```bash
LOCAL_DEV_CUSTOMER=bob make dev
```

Ask for A-1001. It is not on bob's account. That looks like security, but it is
not. The name `alice` is just a default in the code. Nobody checked a password.
The rest of the labs replace that guess with a real, checked identity.

---

# M2. Identity: create your login

You are making the thing that issues tokens.

1. Go to **Cognito** and choose **Create user pool**.

2. Under sign-in options, tick **User name**. Leave **Email** unticked.

   > This step matters more than it looks. If you sign in by email, Cognito sets
   > the username to a random ID like `d304d8b2-90e1-70f7`. Later your policies
   > need to compare that username to `alice`, and a random ID will never match.
   > Sign in by user name and the token says `alice`.

3. Cognito will now ask you to pick a required attribute. Choose **email**. That is
   fine. A required attribute is not the same as a sign-in option, so your username
   stays `alice`.

4. Turn **self-registration off**. You will add the users yourself.

5. Create an app client:
   - Type: **Single-page application**, so it has no client secret.
   - Name it `refund-tester-<your initials>`.

6. Name the pool `refund-pool-<your initials>` and create it.

7. Open the app client and turn on **ALLOW_USER_PASSWORD_AUTH** under
   authentication flows. The tester app needs it.

8. Add three users. For each one choose **Don't send an invitation**, tick
   **Mark email address as verified**, and set the password to `Workshop#2026`.

   | User name | Email |
   |---|---|
   | `alice` | `alice@example.com` |
   | `bob` | `bob@example.com` |
   | `mateo` | `mateo@example.com` |

9. Open the tester and press **Find my resources**. **User pool** and **App client**
   get a tick.

10. Log in as **alice**. The first login asks you to pick a new password.

**You are done when** the tester says you are signed in as alice, and the panel
**What's inside my token?** shows `"username": "alice"`. If it shows a long random
ID instead, go back to step 2.

---

# M3. The agent

1. Go to **Bedrock AgentCore** and then **Harness**. Choose **Create**.

2. Name it `refund_<your initials>`. The name cannot be changed later.

3. Pick a Claude model that is available in `eu-central-1`.

4. For the system prompt, paste:

   ```
   You are a customer-service refund assistant. Help the signed-in customer with
   their orders and refunds. Be brief.
   ```

5. Set **Inbound auth** to **Custom JWT**:

   - **Discovery URL**, with your own pool ID in it:
     ```
     https://cognito-idp.eu-central-1.amazonaws.com/YOUR_POOL_ID/.well-known/openid-configuration
     ```
   - **Allowed clients**: your app client ID.

6. Save and wait for the status to become **READY**.

7. Copy the **harness ARN** from the details page. It looks like
   `arn:aws:bedrock-agentcore:eu-central-1:123456789012:harness/refund_amg-AbC1234567`.

   > Take the ARN with `:harness/` in it. There is a second ARN on the page with
   > `:runtime/harness_` in it. That one will not work.

8. In the tester, press **Find my resources**. **Agent (harness)** gets a tick.

9. Send **hello** in the Chat tab.

**You are done when** the agent replies. It cannot see any orders yet. That is M5.

---

# M4. Memory

1. Go to **AgentCore** and then **Memory**. Create a memory resource in
   `eu-central-1`. Name it `refund_memory_<your initials>`.

2. Edit your harness and attach that memory to it. Wait for **READY**.

3. In the Chat tab, say: **my favourite colour is green.**

4. Then ask: **what is my favourite colour?** It should remember.

5. Click **New chat** and ask again. It should have forgotten.

**You are done when** the agent remembers inside one chat and forgets after you
start a new one.

---

# M5. Tools

Now the agent gets something to do. The tools live in a Lambda, and a gateway puts
them in front of the agent.

### Create the Lambda

1. Go to **Lambda** and choose **Create function**.
2. Name it `refund_tool_<your initials>`, runtime **Python 3.12** or newer.
3. Paste the contents of `tools/lambda_function.py` from this repo over the
   default code, then choose **Deploy**.
4. Copy the function ARN.

The Lambda holds the fake orders. alice owns A-1001 to A-1004, bob owns B-2001 and
B-2002, mateo owns M-3001 and M-3002.

### Create gateway A

5. Go to **AgentCore**, then **Gateways**, then **Create gateway**.
6. Name it `refund_gw_<your initials>`. Protocol: **MCP**.
7. Set inbound auth to **AWS IAM**. This is the agent's door, so the caller is the
   agent, not a person.
8. For permissions, let it create a new service role.
9. Add a target:
   - Target name: `orders`
   - Target type: **Lambda**, pointing at the function you just made
   - Tool schema: paste `tools/tool-schema.json` from this repo
   - Outbound auth: the gateway IAM role
10. Create it and wait for **READY**.

> If you get "Gateway service is not authorized to perform AssumeRole on Gateway
> role", wait a minute and add the target again. The new role takes a moment to
> become usable.

### Hook it up

11. Edit your harness, go to **Tools**, and add an **AgentCore Gateway** tool
    pointing at your gateway ARN. Outbound auth: **AWS IAM**. Wait for **READY**.

12. The agent now needs to know who it is talking to. In the tester's **Settings**,
    tick **Tell the agent who I am**.

    The tester now adds a line to every message saying who is signed in, filled in
    from your token. Open **Settings**, then **Enter manually** to read it.

13. Log in as alice and ask: **what orders do I have?**

**You are done when** alice sees her four orders and the Lambda's CloudWatch log
shows the `find_orders` call.

### Now look at what you just built

Ask the agent: **show me order B-2001.** That is bob's order, and you get nothing
back.

It feels secure. It is not. The only reason it worked is that the tester typed
alice's name into the prompt and the model chose to obey. Nothing checked it. A
cleverer message can talk the model into passing `customer_id` of `bob`.

The gateway cannot help here, because when the agent calls it, the gateway sees the
agent's AWS role. It never sees you. M6 fixes that.

---

# M6. Policies

Here you build a second door that does see you, and you put a guard on it.

### Create gateway B

1. Create another gateway, named `refund_gw_jwt_<your initials>`. Protocol: **MCP**.

2. This time set inbound auth to **Custom JWT**, with the same two values you used
   for the harness in M3:
   - Discovery URL with your pool ID
   - Allowed clients: your app client ID

3. Add a target. Use the **same Lambda** and the **same tool schema** as M5.

   > Name this target `orders` exactly. Policy rules refer to tools as
   > `<target name>___<tool name>`, so the rules below only work if the target is
   > called `orders`.

4. Copy the gateway's **ARN** and its **URL**. The URL ends in `/mcp`.

5. In the tester, press **Find my resources**. **Gateway (Tools tab)** gets a tick,
   and the **Tools** tab starts working.

6. In the Tools tab, call `orders___find_orders` with `customer_id` set to `alice`.
   It works. Now set it to `bob`. **It also works.** There is no guard yet.

### Add the guard

7. Go to **AgentCore**, then **Policy**, and create a policy engine named
   `refund_identity_<your initials>`. Use letters, digits and underscores only. No
   hyphens.

8. Add a policy called `identity_binding`. Replace `YOUR_GATEWAY_B_ARN` with the ARN
   from step 4.

   ```cedar
   permit (
       principal is AgentCore::OAuthUser,
       action in [
           AgentCore::Action::"orders___find_orders",
           AgentCore::Action::"orders___get_order_transaction",
           AgentCore::Action::"orders___process_refund",
           AgentCore::Action::"orders___get_refund_status"
       ],
       resource == AgentCore::Gateway::"YOUR_GATEWAY_B_ARN"
   )
   when {
       principal.hasTag("username") &&
       context.input.customer_id == principal.getTag("username")
   };
   ```

   This says: you may use these four tools, but only when the `customer_id` you
   send matches the user name on your token.

9. Add a second policy called `refund_cap_200`, same ARN:

   ```cedar
   forbid (
       principal is AgentCore::OAuthUser,
       action == AgentCore::Action::"orders___process_refund",
       resource == AgentCore::Gateway::"YOUR_GATEWAY_B_ARN"
   )
   when {
       context.input.amount.greaterThan(decimal("200.0"))
   };
   ```

   This says: never pay out more than $200, whoever asks. A `forbid` always beats a
   `permit`.

10. Attach the policy engine to gateway B and set the mode to **LOG_ONLY** first.
    In this mode it writes down what it would have done but still lets everything
    through. Make a few calls, then switch it to **ENFORCE**.

### Show that it works

Log in as **alice** and use the Tools tab:

| What you call | What should happen |
|---|---|
| `find_orders` with `customer_id` = `alice` | allowed |
| `find_orders` with `customer_id` = `bob` | denied |
| `get_order_transaction` with `customer_id` = `bob`, `order_id` = `B-2001` | denied |
| `process_refund`, `alice`, `A-1004`, amount `300` | denied, over the cap |
| `process_refund`, `alice`, `A-1001`, amount `49` | allowed |

**You are done when** you can show one allow and the three denies, and the denials
appear in CloudWatch under the `aws/spans` log group.

### Add a rule with memory (Dogwood)

Cedar judges each call on its own. It cannot know whether you looked at an order
before you asked to refund it. Dogwood is Cedar plus the history of your session,
so it can.

11. Give gateway B permission to keep a session. Open gateway B in **AgentCore** and
    click its **service role**. In IAM choose **Add permissions**, then **Create
    inline policy**, then **JSON**. Paste the contents of
    `policies/gateway_temporal_iam.json` from this repo, choose **Next**, name it
    `policy-sessions`, and create it.

12. In your policy engine, add a policy called `refund_after_lookup`. Choose
    **Dogwood** as the policy language, and replace `YOUR_GATEWAY_B_ARN` again:

    ```
    forbid (
        principal is AgentCore::OAuthUser,
        action == AgentCore::Action::"orders___process_refund",
        resource == AgentCore::Gateway::"YOUR_GATEWAY_B_ARN"
    )
    unless temporal {
        formerly within 1h AgentCore::Action::"orders___get_order_transaction"::response{
            eventResource: resource,
            input.customer_id: context.input.customer_id,
            input.order_id: context.input.order_id
        }
    };
    ```

    This says: no refund unless, earlier in this session, the same customer opened
    the same order. Like the cap, it is a `forbid` on top of the first policy.

    > From now on every call must say which session it belongs to. The tester does
    > that for you: the Tools tab shows your **Policy session**.

### Show that it remembers

Log in as **alice**, open the Tools tab, and click **New session** first.

| What you call, in order | What should happen |
|---|---|
| `process_refund`, `alice`, `A-1001`, amount `49` | denied, you never looked at it |
| `get_order_transaction`, `alice`, `A-1001` | allowed |
| `process_refund`, `alice`, `A-1001`, amount `49` | allowed |

Wait a second between the last two: the lookup is recorded just after it returns.
Then click **New session** and try the refund again. It is denied, because the new
session has no history.

**You are done when** the same refund is denied, then allowed, then denied again in
a new session.

### The point

Two doors into the same Lambda.

Through the agent, your name is a sentence in a prompt. The model usually follows
it, but nothing makes it.

Through the Tools tab, your name is a signed token the gateway checked, and the
policy engine compares it to every tool call. The model cannot argue with it and
neither can you.

That is the difference between telling software who you are and proving it.

Cedar checks who you are on every call. Dogwood also checks what you did before it.

---

## If something breaks

Ask a staff member. Most problems are listed in [STAFF.md](STAFF.md). The tester shows a
hint under most errors.

To reset the local agent:

```bash
pkill -f "agentcore dev"
make dev
```
