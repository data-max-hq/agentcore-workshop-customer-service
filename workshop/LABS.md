# Labs

Concepts come from your instructor. These are just the steps and how to know
you're done. Run everything from the repo root.

Status legend: ✅ verified locally · ⏳ drafted, to be finalized after the deploy
rehearsal (STAFF.md).

---

## M1 — Run & inspect (local, no AWS) ✅

```bash
npm install -g @aws/agentcore@0.31.0
make dev            # from the repo root; leave running; chat UI on http://localhost:8081
```

In the chat UI (http://localhost:8081):
1. Ask **"what orders do I have?"** → lists A-1001, A-1002 (you're signed in as `alice`).
2. Ask **"refund A-1001"** → a simulated refund with a reference.
3. Ask **"what did I just refund?"** → it remembers (local in-process history).
4. Open the **Timeline / Traces** panel and click your last request.

**✅ Done when:** you can see a trace whose spans include the **model call** and
your **tool calls** (`lookup_order`, `issue_refund`), each with a duration.

> Try `LOCAL_DEV_CUSTOMER=bob make dev` and ask for A-1001 — it's not on bob's
> account. That's tenant isolation: identity comes from the request, not the model.

---

## M2 — Deploy to AWS ⏳

Uses your provided account (us-east-1). Confirm creds first: `aws sts get-caller-identity`.

```bash
make infra-preview   # dry-run: what will be created (no spend)
make infra-deploy    # creates the runtime + PaymentGateway + Lambda + RefundMemory
```

First deploy in a fresh account will **bootstrap** CDK (one-time). Approve when prompted.

**⏳ Done when:** the inspector's **Resources** panel shows your deployed
runtime, gateway, and memory (and `agentcore` reports success).

---

## M3 — Memory ⏳

Exercise the **deployed** agent (not local `make dev`) so it runs with the
Memory resource attached, then look at the **Memory** panel.

- Have a short multi-turn conversation with the deployed agent (refund something,
  then ask a follow-up that relies on the earlier turn).
- Open the **Memory** panel.

**⏳ Done when:** the Memory panel shows the stored conversation — the same
history that was a throwaway in-process dict locally is now persisted by
**AgentCore Memory**.

---

## M4 — Gateway (the payout as a managed tool) ⏳

The deployed agent's refund now runs through the **PaymentGateway → Lambda**
instead of the in-process `issue_refund`.

- Issue a refund on the deployed agent.
- Open the **Timeline** for that request.

**⏳ Done when:** the trace shows the refund handled by the **gateway tool**
(`process_refund`), and the Lambda's invocation appears in its CloudWatch logs.

---

## M5 — Observe & tear down ⏳

- Browse the request **Traces** (Timeline) and the Lambda logs — this is
  **AgentCore Observability**, the deployed version of M1's local traces.
- Tear everything back down:

```bash
make infra-down      # removes the gateway; reconciles the stack
```

**⏳ Done when:** the resources are gone from the account (no lingering spend).

---

### If your environment breaks
Ask a staff member — most issues are in [STAFF.md](STAFF.md). Quick resets:
`pkill -f "agentcore dev"` (restart local), or re-run `make infra-deploy` (reconcile deploy).
