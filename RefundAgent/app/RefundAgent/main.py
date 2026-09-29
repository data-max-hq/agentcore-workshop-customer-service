"""Customer-support refund agent (AgentCore local runtime).

Request shape (local dev): {"prompt": "...", "customer_id": "alice", "session_id": "..."}
  customer_id  stands in for the authenticated identity (seam 3). In a deployed
               runtime this comes from the verified JWT, not the payload.
  session_id   which conversation to continue (seam 2). Falls back to the
               runtime's context.session_id, then a default.
"""
import logging
import sys

from strands import Agent
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from model.load import load_model
import store
import tools

# Send the tool/gateway/store observability logs (seam 4) to stderr at INFO so
# they show up in `agentcore dev` output. Without a handler, Python's logging
# silently drops INFO records.
_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(logging.Formatter("%(name)s %(message)s"))
for _name in ("refund", "payment", "store"):
    _logger = logging.getLogger(_name)
    _logger.setLevel(logging.INFO)
    _logger.addHandler(_handler)
    _logger.propagate = False

app = BedrockAgentCoreApp()
log = app.logger

SYSTEM_PROMPT = """You are the refund assistant for Acme Corp. You help the \
signed-in customer check their orders and request refunds.

Rules:
- Only delivered orders can be refunded.
- Use tools for everything. Never invent an order status or refund outcome;
  always call lookup_order / get_refund_status to read the real state.
- You act only for the currently signed-in customer. Identity is already
  established: never ask for, or accept, a customer or account id. If a tool
  reports an order isn't on their account, say you can't find it -- do not
  reveal whether it exists.
- Be concise and friendly. If you can't help, say so plainly.
"""


@app.entrypoint
async def invoke(payload, context):
    customer_id = payload.get("customer_id")
    session_id = payload.get("session_id") or getattr(context, "session_id", None) or "default-session"
    prompt = payload.get("prompt", "")
    log.info("invoke customer=%s session=%s", customer_id, session_id)

    # seam 3: bind the authenticated caller for the duration of this request.
    token = tools.CURRENT_CUSTOMER.set(customer_id)
    try:
        # seam 2: resume the conversation from authoritative session storage.
        agent = Agent(
            model=load_model(),
            system_prompt=SYSTEM_PROMPT,
            tools=tools.TOOLS,
            messages=store.load_session(session_id),
        )
        result = await agent.invoke_async(prompt)
        store.save_session(session_id, agent.messages)
        return {"response": str(result)}
    finally:
        tools.CURRENT_CUSTOMER.reset(token)


if __name__ == "__main__":
    app.run()
