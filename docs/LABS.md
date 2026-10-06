# Labs

Your instructor explains the ideas. This file is just the steps. Do them in order,
one at a time. After most steps there is a **Check** line: if what you see does not
match, stop there and fix it before you go on.

## Before you start

1. **Set the region to `us-east-1` (N. Virginia)** in the AWS console region picker.
   Everything in these labs lives there. If you build something in the wrong
   region, nothing will find it.

2. **Pick your initials.** If yours are AMG, your harness is `refund_amg`, your
   gateway `refund-gw-amg`, and so on. Copy each name exactly as the step gives
   it: gateway names do not allow underscores, so they use hyphens. You have your own AWS account, so this only
   keeps things tidy. If you ever share an account, it stops you from editing
   someone else's work, and the tester uses it to find yours.

3. **Open a notepad.** You will copy a few values and paste them later:

   | Value | You get it in | You paste it in |
   |---|---|---|
   | User pool ID | M1 step 7 | M2, M5 |
   | App client ID | M1 step 8 | M2, M5 |
   | Tools Lambda ARN | M4 step 5 | M4, M5 |
   | `refund-gw` ARN | M4 step 13 | M4 |
   | `refund-gw-jwt` ARN | M5 step 5 | M5 policies |

### Your progress

- [ ] The tester app
- [ ] M1. Identity: create your login
- [ ] M2. The agent
- [ ] M3. Memory
- [ ] M4. Tools
- [ ] M5. Policies

## What you are building

```
   you ---- login ----> Cognito
    |
    |  your token
    |
    +---> Chat tab ---> Harness ---> refund-gw ---> Lambda
    |                   (the agent)   (AWS IAM)      (orders,
    |                                                 refunds)
    |                                                   ^
    +---> Tools tab -----------------> refund-gw-jwt ---+
                                       (your token,
                                        policies check
                                        who you are)
```

One Lambda. Two ways in. The Chat tab goes through the agent, and the agent shows
the gateway its own AWS identity, not yours. The Tools tab goes straight in with
your login, so the policy engine can see you and can say no.

That difference is the whole point of the workshop.

---

# The tester app

**Goal:** a small web page, running as a Lambda in your account, that you use in
every lab. From now on, "the tester" means this page (the Lambda's Function
URL). You need nothing on your laptop but a browser.

1. Check the region picker (top right) says **US East (N. Virginia)**. Go to
   **Lambda** and choose **Create function**.

2. Choose **Author from scratch**. Name it `refund_ui_<your initials>`.

3. Open the **Runtime** dropdown and change it to **Python 3.13**. It defaults to
   Node.js, and Python code will not run there. Choose **Create function**.

   **Check:** the **Code** tab shows a file called `lambda_function.py`. If it says
   `index.mjs`, you picked the wrong runtime: delete the function and start again.

4. Paste the contents of `chat/lambda_function.py` from this repo over all the
   code in `lambda_function.py`. Choose **Deploy**.

5. Go to **Configuration** → **General configuration** → **Edit**. Set **Timeout**
   to **15** seconds. Save.

6. Give the tester permission to find your resources:
   1. Go to **Configuration** → **Permissions**.
   2. Click the **role name** → **Add permissions** → **Create inline policy** →
      **JSON**.
   3. Paste the contents of `chat/lambda_policy.json` from this repo.
   4. Choose **Next**, name it `chat-ui-lookup`, and create it.

   > This only lets the app read the names of your pool, harness and gateway, so
   > you never have to copy IDs into it.

7. Make the tester reachable from your browser:
   1. Back in Lambda, go to **Configuration** → **Function URL** → **Create function
      URL**. Choose auth type **NONE**. Save.
   2. Go to **Configuration** → **Permissions**, scroll to **Resource-based policy
      statements**, and choose **Add permissions**.
   3. Choose **Function URL**, auth type **NONE**. Save.

   **Check:** the list now has two statements, one for `lambda:InvokeFunctionUrl`
   and one for `lambda:InvokeFunction`.

   > A public function URL needs both. With only one, the page shows `Forbidden`
   > and Lambda warns that the URL "is missing permissions required for public
   > access".

8. Open your tester page:
   1. Go to **Lambda** → **Functions** → `refund_ui_<your initials>`.
   2. In **Function overview** at the top, find **Function URL** on the right. It
      looks like `https://abc123xyz.lambda-url.us-east-1.on.aws/`.
   3. Click it. The page that opens, titled **AgentCore Chat**, is your
      **tester**. Bookmark it: every lab below says "open the tester" and means
      this page.

   **Check:** the tester page loads. Click **⚙ Settings** to open it: nothing has a
   tick yet. That is expected.

As you build things in the labs below, they show up under **⚙ Settings** by
themselves. To check again, open **⚙ Settings** and press **Find my resources**.
If you share an AWS account with others, type your initials there first.

**Done.** Tick *The tester app* in your progress list.

---

# M1. Identity: create your login

**Goal:** the thing that issues tokens, and three users who can log in.

### Create the pool

1. Go to **Cognito** and choose **Create user pool**.

2. The first thing the wizard asks is your application:
   - Application type: **Single-page application** (so it has no client secret).
   - Name: `refund-tester-<your initials>`.

3. Under sign-in options, tick **User name**. Leave **Email** unticked.

   > This step matters more than it looks. If you sign in by email, Cognito sets
   > the username to a random ID like `d304d8b2-90e1-70f7`. Later your policies
   > need to compare that username to `alice`, and a random ID will never match.
   > Sign in by user name and the token says `alice`.

4. Cognito now asks for a required attribute. Choose **email**. A required
   attribute is not a sign-in option, so your username stays `alice`.

5. Turn **self-registration off**. You will add the users yourself.

6. Name the pool `refund-pool-<your initials>` and create it.

7. On the pool's overview page, copy the **User pool ID** (it looks like
   `us-east-1_AbCdEf123`) to your notepad.

### Set up the app client

8. Open **App clients**, then your client. Copy the **Client ID** to your notepad.

9. Edit the client and turn on **ALLOW_USER_PASSWORD_AUTH** under authentication
   flows. Save. The tester needs it.

### Add the users

10. Add three users. For each one:
    1. Choose **Don't send an invitation**.
    2. Enter the user name and email from the table.
    3. Tick **Mark email address as verified**.
    4. Set the password to `Workshop#2026`.

    | User name | Email |
    |---|---|
    | `alice` | `alice@example.com` |
    | `bob` | `bob@example.com` |
    | `mateo` | `mateo@example.com` |

    **Check:** the Users list shows `alice`, `bob` and `mateo`.

11. Open the tester, click **⚙ Settings**, and press **Find my resources**.

    **Check:** **User pool** and **App client** have a tick.

You log in as alice in M2: the tester only shows the login once there is an agent
to talk to.

**Done.** Tick *M1* in your progress list.

---

# M2. The agent

**Goal:** an agent that only answers people who logged in to your pool.

**You need:** your user pool ID and app client ID from M1.

### Create the harness

1. Go to **Bedrock AgentCore** → **Harness**. Choose **Create**.

2. Name it `refund_<your initials>`. The name cannot be changed later.

3. For the model, pick **Amazon Nova Pro**. Nova models are Amazon's own, so they
   work in your account straight away with no extra setup.

4. For the system prompt, paste:

   ```
   You are a customer-service refund assistant. Help the signed-in customer with
   their orders and refunds. Be brief.
   ```

5. Open **Inbound Auth** and set it up so only your pool's users get in:
   1. **Inbound Auth Type**: choose **Use JSON Web Tokens (JWT)**.
   2. **JWT schema configuration**: choose **Use existing Identity provider
      configurations**. Not *Quick create with Cognito*: that makes a new pool,
      and you want the one from M1.
   3. **Discovery URL**: paste this and replace `YOUR_POOL_ID` with your pool ID:
      ```
      https://cognito-idp.us-east-1.amazonaws.com/YOUR_POOL_ID/.well-known/openid-configuration
      ```
   4. **Allowed clients**: your app client ID.

6. Save. Wait until the status is **READY**.

7. On the details page, find the **harness ARN**. It looks like
   `arn:aws:bedrock-agentcore:us-east-1:123456789012:harness/refund_amg-AbC1234567`.

   > If you ever need to paste it, take the ARN with `:harness/` in it. The second
   > ARN on the page, with `:runtime/harness_` in it, will not work.

### Talk to it

8. In the tester, open **⚙ Settings** and press **Find my resources**.

   **Check:** **Agent (harness)** has a tick, and the login form appears.

9. Log in as **alice** with `Workshop#2026`. The first login asks you to pick a new
   password. Pick one and remember it.

10. Open the panel **What's inside my token?**

    **Check:** it shows `"username": "alice"`. If it shows a long random ID instead,
    your pool signs in by email: go back to M1 step 3 and make a new pool.

11. Open the **Chat** tab and send **hello**.

    **Check:** the agent replies.

12. Now open your harness in the console and choose **Test Harness**. Send **hello**
    there too.

    It works without any login, because the console signs you in with your AWS
    user. In the playground you can type any **Actor ID** you like, and the agent
    believes it. The rest of the labs replace that guess with a checked identity.

13. In the tester's Chat tab, ask: **what are my orders?** Then open **Raw
    response** under the reply.

    The agent cannot see any orders yet, but a harness comes with a few built-in
    tools, such as `file_operations` for files in its own sandbox. You will
    probably see it try one of them, looking for an orders file that does not
    exist. With no proper tool, an agent improvises with whatever it has. M4
    gives it the right tool.

**Done** when you are signed in as alice, your token says `"username": "alice"`,
and the agent replies. It cannot see any orders yet; that is M4. Tick *M2* in your
progress list.

---

# M3. Memory

Your harness already has memory. When you created it, AgentCore gave it a
**managed memory** with two long-term strategies. You will swap it for a plain
memory to see short-term memory on its own, then put the managed one back.

### Look at what you have

1. Open your harness and find its **Memory** section. Note the two retrieval
   configs:
   - `/actors/{actorId}/facts/` (semantic): facts about **you**, kept across chats.
   - `/actors/{actorId}/summaries/{sessionId}/` (summarization): a summary of
     **one chat**.

   `{actorId}` is your login. The tester sends your username, so alice's memory
   and bob's memory never mix.

### Short-term memory only

2. Go to **AgentCore** and then **Memory**. Create a memory resource in
   `us-east-1`. Name it `refund_memory_<your initials>`. **Do not add any
   long-term strategies.**

3. Edit your harness and switch its memory to the one you just made. Wait for
   **READY**.

4. In the Chat tab, say: **my favourite colour is green.**

5. Then ask: **what is my favourite colour?** It remembers. That is short-term
   memory: the conversation so far, kept for this chat.

6. Click **New chat** and ask again. It has forgotten. A new chat is a new
   session, and short-term memory belongs to the session.

### Long-term memory

7. Edit your harness and switch its memory back to **managed memory**. Wait for
   **READY**, and check the two retrieval configs from step 1 are there again.

8. In the Chat tab, say: **my favourite colour is green.** Ask about it in the same
   chat. It remembers, as before.

9. **Wait a minute or two.** Long-term memories are extracted in the background
   after the conversation, not instantly.

10. Click **New chat** and ask: **what is my favourite colour?** This time it
    remembers. The fact was saved under `/actors/alice/facts/`, which belongs to
    alice, not to the chat.

11. Sign out, log in as **bob**, and ask the same question. bob's agent does not
    know. Same agent, same memory resource, different actor.

**You are done when** the plain memory forgets after **New chat**, the managed
memory remembers after **New chat**, and bob does not see alice's colour.

> If step 10 still forgets, wait another minute and ask again. Extraction can take
> a little while.

---

# M4. Tools

**Goal:** the agent can look up orders and issue refunds. The tools live in a
Lambda, and a gateway puts them in front of the agent.

### Create the tools Lambda

1. Go to **Lambda** and choose **Create function**.

2. Name it `refund_tool_<your initials>`, runtime **Python 3.12** or newer. Choose
   **Create function**.

3. Paste the contents of `tools/lambda_function.py` from this repo over the default
   code.

4. Choose **Deploy**.

5. Copy the function ARN (top right of the page) to your notepad.

The Lambda holds the fake orders. alice owns A-1001 to A-1004, bob owns B-2001 and
B-2002, mateo owns M-3001 and M-3002.

### Create `refund-gw`

6. Go to **AgentCore** → **Gateways** → **Create gateway**.

7. Name it `refund-gw-<your initials>` (hyphens, not underscores). Protocol: **MCP**.

8. Set inbound auth to **AWS IAM**. This is the agent's door, so the caller is the
   agent, not a person.

9. For permissions, let it create a new service role.

10. Create the gateway and wait for **READY**. If the wizard offers to add a
    target, you can fill it in as in step 11, but do not trust it: check in
    step 12.

11. Open the gateway, go to **Targets**, and choose **Add target**:
    - Target name: `orders`
    - Target type: **Lambda**, with the function ARN from step 5
    - Tool schema: paste `tools/tool-schema.json` from this repo
    - Outbound auth: the gateway IAM role

    > If you get "Gateway service is not authorized to perform AssumeRole on
    > Gateway role", wait a minute and add the target again. The new role takes a
    > moment to become usable.

12. Wait for the target to become **READY**.

    **Check:** the gateway's **Targets** list shows `orders` as **READY**. If the
    list is empty, the target was dropped (this happens when the role was not
    ready yet): do step 11 again. A gateway with no target gives the agent no
    tools, and it will not tell you.

13. Copy the gateway's **ARN** to your notepad.

### Give the gateway to the agent

14. Edit your harness and go to **Tools**. Add an **AgentCore Gateway** tool:
    - Gateway: the ARN from step 13
    - Outbound auth: **AWS IAM**

15. Save. Wait for **READY**.

16. In the tester's **Settings**, tick **Tell the agent who I am**.

    The tester now adds a line to every message saying who is signed in, filled in
    from your token. Open **Settings** → **Enter manually** to read it.

### Try it

17. Make sure you are logged in as alice. In the Chat tab, send: **what orders do I
    have?**

    **Check:** alice sees four orders, A-1001 to A-1004.

18. In the Lambda console, open `refund_tool_<your initials>` → **Monitor** → **View
    CloudWatch logs**, and open the newest log stream.

    **Check:** the log shows a `find_orders` call.

### Look at what you just built

19. Send: **show me order B-2001.**

    **Check:** you get nothing back. That is bob's order.

It feels secure. It is not. The only reason it worked is that the tester typed
alice's name into the prompt and the model chose to obey. Nothing checked it. A
cleverer message can talk the model into passing `customer_id` of `bob`.

The gateway cannot help here, because when the agent calls it, the gateway sees the
agent's AWS role. It never sees you. M5 fixes that.

**Done.** Tick *M4* in your progress list.

---

# M5. Policies

**Goal:** a second door that does see you, with a guard on it.

**You need:** your pool ID and app client ID (M1), and the tools Lambda ARN (M4).

### Create `refund-gw-jwt`

1. Create `refund-gw-jwt` the same way as `refund-gw` in M4:
   1. Go to **AgentCore** → **Gateways** → **Create gateway**.
   2. Name it `refund-gw-jwt-<your initials>` (hyphens, not underscores). Protocol: **MCP**.
   3. For permissions, let it create a new service role.

2. Set up inbound auth the same way as the harness in M2 step 5:
   1. Choose **JSON Web Tokens (JWT)**, then **Use existing Identity provider
      configurations**.
   2. **Discovery URL**: paste this and replace `YOUR_POOL_ID` with your user pool
      ID from your notepad (it looks like `us-east-1_AbCdEf123`):
      ```
      https://cognito-idp.us-east-1.amazonaws.com/YOUR_POOL_ID/.well-known/openid-configuration
      ```
   3. **Allowed clients**: your app client ID from your notepad.

3. Create the gateway and wait for **READY**. Then open it, go to **Targets**, and
   add a target named `orders`, with the **same Lambda** and the **same tool
   schema** as M4.

   **Check:** **Targets** shows `orders` as **READY**. If the list is empty, add
   it again.

   > The name must be `orders` exactly. Policy rules refer to tools as
   > `<target name>___<tool name>`, so the rules below only work if the target is
   > called `orders`.

4. Give `refund-gw-jwt` one extra permission it needs later.

   **Why:** in this lab the policies remember what you did earlier in a *policy
   session* (for example: "did you look at this order before refunding it?"). To
   use a session, `refund-gw-jwt` has to fetch a short-lived token for itself. Its
   service role, the AWS identity the gateway acts as, is not allowed to do that
   yet. If you skip this, every allowed call fails later with `Failed to get
   workload identity token`.

   1. Go to **AgentCore** → **Gateways** and open `refund-gw-jwt-<your initials>`.
   2. In the gateway details, find **IAM Role**. It is shown as an ARN like
      `arn:aws:iam::123456789012:role/service-role/AmazonBedrockAgentCoreGatewayDefaultServiceRole1791287121014`.
      Copy the part after the last `/`: that is the role name.
   3. Go to **IAM** → **Roles**, paste the role name into the search box, and open
      the role.

      > `refund-gw` has a role with a similar name but a different number. Use the
      > one shown on `refund-gw-jwt`.
   4. On the **Permissions** tab, open the **Add permissions** dropdown and choose
      **Create inline policy**.
   5. Switch the policy editor from **Visual** to **JSON**. Delete everything in
      the box.
   6. Paste the contents of `policies/gateway_temporal_iam.json` from this repo.
      It allows one action, `bedrock-agentcore:GetWorkloadAccessToken`, and nothing
      else.
   7. Choose **Next**. Name the policy `policy-sessions` and choose **Create
      policy**.

   **Check:** back on the role's **Permissions** tab, `policy-sessions` is in the
   list.

5. Copy `refund-gw-jwt`'s **ARN** to your notepad.

6. In the tester, open **⚙ Settings** and press **Find my resources**.

   **Check:** **Gateway (Tools tab)** has a tick, and the **Tools** tab works.

### See the open door

7. Logged in as alice, open the **Tools** tab. Call `orders___find_orders` with
   `customer_id` = `alice`.

   **Check:** you get alice's orders.

8. Call it again with `customer_id` = `bob`.

   **Check:** you get bob's orders. **That is the problem.** There is no guard yet.

### Add the guard

9. Go to **AgentCore** → **Policy**. Create a policy engine named
   `refund_identity_<your initials>`. Letters, digits and underscores only, no
   hyphens.

10. Add a policy called `identity_binding`. Paste this, then **replace
    `YOUR_REFUND_GW_JWT_ARN`** with the `refund-gw-jwt` ARN from your notepad
    (step 5). Keep the quotes around it. The line should end up like:

    ```
    resource == AgentCore::Gateway::"arn:aws:bedrock-agentcore:us-east-1:123456789012:gateway/refund-gw-jwt-amg-abc123defg"
    ```

    > If you get `ARN "YOUR_REFUND_GW_JWT_ARN" should have 6 components`, you
    > pasted the placeholder without replacing it.

    ```cedar
    permit (
        principal is AgentCore::OAuthUser,
        action in [
            AgentCore::Action::"orders___find_orders",
            AgentCore::Action::"orders___get_order_transaction",
            AgentCore::Action::"orders___process_refund",
            AgentCore::Action::"orders___get_refund_status"
        ],
        resource == AgentCore::Gateway::"YOUR_REFUND_GW_JWT_ARN"
    )
    when {
        principal.hasTag("username") &&
        context.input.customer_id == principal.getTag("username")
    };
    ```

    This says: you may use these four tools, but only when the `customer_id` you
    send matches the user name on your token.

11. Add a second policy called `refund_cap_200`. Again, replace
    `YOUR_REFUND_GW_JWT_ARN` with your `refund-gw-jwt` ARN:

    ```cedar
    forbid (
        principal is AgentCore::OAuthUser,
        action == AgentCore::Action::"orders___process_refund",
        resource == AgentCore::Gateway::"YOUR_REFUND_GW_JWT_ARN"
    )
    when {
        context.input.amount.greaterThan(decimal("200.0"))
    };
    ```

    This says: never pay out more than $200, whoever asks. A `forbid` always beats
    a `permit`.

12. Attach the policy engine to `refund-gw-jwt` so it starts checking calls:
    1. Go to **AgentCore** → **Gateways** and open `refund-gw-jwt-<your initials>`.
    2. Choose **Edit** and find the **Policy engine** section.
    3. Select `refund_identity_<your initials>`.
    4. Set the mode to **ENFORCE**. (The other mode, LOG_ONLY, only writes down
       what it would have done and lets everything through.)
    5. Save and wait for the gateway to be **READY** again.

    **Check:** the gateway details show your policy engine, mode **ENFORCE**.

### Show that the guard works

Stay logged in as **alice** and use the Tools tab for each step.

13. `find_orders`, `customer_id` = `alice`. **Check:** allowed.

14. `find_orders`, `customer_id` = `bob`. **Check:** denied.

15. `get_order_transaction`, `customer_id` = `bob`, `order_id` = `B-2001`.
    **Check:** denied.

16. `process_refund`, `alice`, `A-1004`, amount `300`. **Check:** denied, over the
    cap.

17. `process_refund`, `alice`, `A-1001`, amount `49`. **Check:** allowed.

You have shown one allow and three denies.

### Add a rule with memory (Dogwood)

Cedar judges each call on its own. It cannot know whether you looked at an order
before you asked to refund it. Dogwood is Cedar plus the history of your session,
so it can.

18. In your policy engine, add a policy called `refund_after_lookup`. Choose
    **Dogwood** as the policy language. Paste this and, as before, replace
    `YOUR_REFUND_GW_JWT_ARN` with your `refund-gw-jwt` ARN:

    ```
    forbid (
        principal is AgentCore::OAuthUser,
        action == AgentCore::Action::"orders___process_refund",
        resource == AgentCore::Gateway::"YOUR_REFUND_GW_JWT_ARN"
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

19. Log out, log in as **bob**, open the Tools tab, and click **New session**.

20. `process_refund`, `bob`, `B-2001`, amount `15`. **Check:** denied, you never
    looked at it.

21. `get_order_transaction`, `bob`, `B-2001`. **Check:** allowed.

22. Wait a second (the lookup is recorded just after it returns), then repeat
    step 20. **Check:** allowed.

23. Click **New session** and repeat step 20 once more. **Check:** denied, because
    the new session has no history. (The policy decides first, so you see the
    deny, not the Lambda saying the order is already refunded.)

**Done** when the same refund was denied, then allowed, then denied again in a new
session. Tick *M5* in your progress list.

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
