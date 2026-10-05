"""Minimal customer-support refund agent on Amazon Bedrock AgentCore.

Runs locally with `agentcore dev` (chat UI on :8081) using in-memory demo data
-- no Docker, no DynamoDB. AgentCore Memory lights up when deployed, guarded by the
env var `agentcore deploy` sets (memory/session.py); locally a small in-process dict
remembers the conversation, so local dev needs no cloud.
"""
import contextvars
import os

from strands import Agent, tool
from bedrock_agentcore.runtime import BedrockAgentCoreApp

from model.load import load_model
from memory.session import get_memory_session_manager

app = BedrockAgentCoreApp()
log = app.logger

# Demo data -- was DynamoDB; an in-memory dict is plenty for a sample app.
ORDERS = {
    "A-1001": {"customer": "alice", "status": "delivered", "amount": 49, "item": "Wireless mouse"},
    "A-1002": {"customer": "alice", "status": "shipped", "amount": 120, "item": "Mechanical keyboard"},
    "B-2001": {"customer": "bob", "status": "delivered", "amount": 15, "item": "USB-C cable"},
    "B-2002": {"customer": "bob", "status": "delivered", "amount": 300, "item": "4K monitor"},
}

# The signed-in customer, bound per request. In a real deployment this comes from
# the verified JWT; locally it defaults so the login-less chat UI just works.
CURRENT_CUSTOMER: contextvars.ContextVar[str] = contextvars.ContextVar("customer", default="alice")
LOCAL_DEV_CUSTOMER = os.getenv("LOCAL_DEV_CUSTOMER", "alice")

# Conversation history when Memory isn't deployed (resets on restart).
LOCAL_SESSIONS: dict[str, list] = {}

SYSTEM_PROMPT = """You are the refund assistant for Acme Corp. Help the signed-in \
customer check their orders and request refunds.
- Only delivered orders can be refunded.
- Use tools for everything; never invent an order status or refund outcome.
- You act only for the signed-in customer -- never ask for a customer or account id.
- Be concise and friendly."""


@tool
def list_orders() -> str:
    """List the signed-in customer's orders."""
    me = CURRENT_CUSTOMER.get()
    mine = [f"{oid}: {o['status']}, ${o['amount']} ({o['item']})"
            for oid, o in ORDERS.items() if o["customer"] == me]
    return "\n".join(mine) or "You have no orders on your account."


@tool
def lookup_order(order_id: str) -> str:
    """Look up the status and amount of one of the customer's orders."""
    o = ORDERS.get(order_id)
    if not o or o["customer"] != CURRENT_CUSTOMER.get():
        return f"No order {order_id} found on your account."
    return f"Order {order_id}: {o['status']}, ${o['amount']} ({o['item']})."


@tool
def issue_refund(order_id: str) -> str:
    """Issue a (simulated) refund for one of the customer's delivered orders."""
    o = ORDERS.get(order_id)
    if not o or o["customer"] != CURRENT_CUSTOMER.get():
        return f"No order {order_id} found on your account."
    if o["status"] != "delivered":
        return f"Order {order_id} is '{o['status']}'; only delivered orders can be refunded."
    return f"Refunded ${o['amount']} for {order_id} (reference rf_{order_id})."


TOOLS = [list_orders, lookup_order, issue_refund]


@app.entrypoint
async def invoke(payload, context):
    customer = payload.get("customer_id") or LOCAL_DEV_CUSTOMER
    session_id = payload.get("session_id") or getattr(context, "session_id", None) or "default-session"
    prompt = payload.get("prompt", "")
    log.info("invoke customer=%s session=%s", customer, session_id)

    token = CURRENT_CUSTOMER.set(customer)
    try:
        # Memory (deployed) persists history; locally fall back to an in-process dict.
        session_manager = get_memory_session_manager(session_id, customer)
        kwargs = dict(model=load_model(), system_prompt=SYSTEM_PROMPT, tools=TOOLS)
        if session_manager:
            kwargs["session_manager"] = session_manager
        else:
            kwargs["messages"] = LOCAL_SESSIONS.get(session_id, [])
        agent = Agent(**kwargs)

        # Stream events so the chat UI renders live text (yield -> SSE endpoint).
        async for event in agent.stream_async(prompt):
            if isinstance(event, dict) and "event" in event:
                yield event

        if session_manager is None:
            LOCAL_SESSIONS[session_id] = agent.messages
    finally:
        CURRENT_CUSTOMER.reset(token)


if __name__ == "__main__":
    app.run()
