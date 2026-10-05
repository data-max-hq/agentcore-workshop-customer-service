"""Refund tools, served as AgentCore Gateway Lambda tools.

In the managed-harness workshop the agent has NO local code: every tool it can
call comes from this Gateway Lambda, so the Gateway's policy engine (Cedar +
Dogwood) can authorize each call by the signed-in user's verified identity.

The order data lives here (it used to be an in-memory dict in the agent). Each
tool takes the acting `customer` as an argument; a Cedar policy binds that
argument to the caller's verified JWT identity
(`context.input.customer == principal.getTag("username")`), so the agent cannot
act for anyone but the signed-in user. The ownership check below is
defense-in-depth under that policy, not the only guard.

The Gateway routes each MCP tool call here and passes the tool name in
context.client_context.custom["bedrockAgentCoreToolName"] as "<target>___<tool>".
"""
import base64
import json
import logging
from typing import Any, Dict

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _claims_from_jwt(token: str) -> Dict[str, Any]:
    """Decode a JWT payload (no verification — the gateway already validated it)."""
    try:
        part = token.split(".")[1]
        part += "=" * (-len(part) % 4)
        return json.loads(base64.urlsafe_b64decode(part))
    except Exception:
        return {}


def _caller_identity(event: Dict[str, Any], context) -> str | None:
    """Best-effort: the verified caller the Gateway forwards, if any.

    Where the identity lands depends on your gateway config, so we check the
    common spots and (in lambda_handler) log what we saw. Returns a username-ish
    claim or None. If None, fall back to the `customer` argument (policy-bound).
    """
    custom = getattr(getattr(context, "client_context", None), "custom", {}) or {}
    authz = event.get("requestContext", {}).get("authorizer", {}) if isinstance(event, dict) else {}
    for src in (custom, authz.get("claims", {}) if isinstance(authz, dict) else {}):
        for k in ("username", "cognito:username", "email", "sub"):
            if isinstance(src, dict) and src.get(k):
                return src[k]
    # A forwarded bearer token we can decode ourselves.
    headers = event.get("headers", {}) if isinstance(event, dict) else {}
    auth = custom.get("Authorization") or custom.get("authorization") or headers.get("Authorization", "")
    token = auth[7:] if isinstance(auth, str) and auth.lower().startswith("bearer ") else auth
    if token:
        c = _claims_from_jwt(token)
        return c.get("username") or c.get("cognito:username") or c.get("email") or c.get("sub")
    return None

# Seed orders (mock). customer is the Cognito username the policy binds to.
ORDERS = {
    "A-1001": {"customer": "alice", "status": "delivered", "amount": 49, "item": "Wireless mouse"},
    "A-1002": {"customer": "alice", "status": "shipped", "amount": 120, "item": "Mechanical keyboard"},
    "B-2001": {"customer": "bob", "status": "delivered", "amount": 15, "item": "USB-C cable"},
    "B-2002": {"customer": "bob", "status": "delivered", "amount": 300, "item": "4K monitor"},
}

TOOLS = {}


def tool(name: str):
    """Register a function as a gateway tool."""
    def decorator(func):
        TOOLS[name] = func
        return func
    return decorator


def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Route a gateway MCP tool call to the matching function."""
    custom = getattr(getattr(context, "client_context", None), "custom", {}) or {}
    extended = custom.get("bedrockAgentCoreToolName", "")
    tool_name = extended.split("___", 1)[1] if "___" in extended else extended

    # Prefer the VERIFIED caller the gateway forwards over any model-supplied
    # `customer`; the log line shows what identity actually arrived (CloudWatch).
    caller = _caller_identity(event, context)
    logger.info(json.dumps({"tool": tool_name, "caller": caller,
                            "client_context_custom": {k: custom[k] for k in custom},
                            "args": event}, default=str))
    if caller:
        event = {**event, "customer": caller}

    handler = TOOLS.get(tool_name)
    if not handler:
        return {"statusCode": 400, "body": json.dumps({"error": f"Unknown tool: {tool_name}"})}
    try:
        return {"statusCode": 200, "body": json.dumps({"result": handler(event)})}
    except Exception as exc:  # surface the message to the model, don't leak a stack
        logger.exception("tool failed")
        return {"statusCode": 500, "body": json.dumps({"error": str(exc)})}


# Said in chat when no verified identity reached the tool — so the failure is
# obvious (gateway not forwarding identity) instead of the model inventing "no DB".
_NO_IDENTITY = ("I couldn't determine who you're signed in as — no verified caller "
                "reached this tool. Check that the gateway forwards the Cognito "
                "identity to the Lambda target.")


def _owned(customer: str, order_id: str) -> Dict[str, Any] | None:
    """The order iff it exists and belongs to `customer`, else None."""
    o = ORDERS.get(order_id)
    return o if o and o["customer"] == customer else None


@tool("list_orders")
def list_orders(event: Dict[str, Any]) -> str:
    """List the acting customer's orders.

    Args:
        customer: the signed-in customer (policy-bound to the caller's identity)
    """
    customer = event.get("customer")
    if not customer:
        return _NO_IDENTITY
    mine = [f"{oid}: {o['status']}, ${o['amount']} ({o['item']})"
            for oid, o in ORDERS.items() if o["customer"] == customer]
    return "; ".join(mine) if mine else "You have no orders."


@tool("lookup_order")
def lookup_order(event: Dict[str, Any]) -> str:
    """Look up one of the customer's orders.

    Args:
        customer: the signed-in customer (policy-bound to the caller's identity)
        order_id: the order to look up, e.g. "A-1001"
    """
    customer, order_id = event.get("customer"), event.get("order_id")
    if not customer:
        return _NO_IDENTITY
    if not order_id:
        return "Which order? Give an order id like A-1001."
    o = _owned(customer, order_id)
    if not o:
        return f"No order {order_id} found on your account."
    return f"Order {order_id}: {o['status']}, ${o['amount']} ({o['item']})."


@tool("process_refund")
def process_refund(event: Dict[str, Any]) -> str:
    """Issue a (fake) refund for a delivered order the customer owns. Safe to retry.

    Args:
        customer: the signed-in customer (policy-bound to the caller's identity)
        order_id: the order to refund, e.g. "A-1001"
        amount: refund amount in dollars
    """
    customer, order_id, amount = event.get("customer"), event.get("order_id"), event.get("amount")
    if not customer:
        return _NO_IDENTITY
    if not order_id or amount is None:
        return "Which order and amount? Give an order id (e.g. A-1001) and a dollar amount."
    o = _owned(customer, order_id)
    if not o:
        return f"No order {order_id} found on your account."
    if o["status"] != "delivered":
        return f"Order {order_id} is '{o['status']}'; only delivered orders can be refunded."

    # ponytail: stable reference = idempotent by construction for this PoC. The
    # real gateway records one ledger row per key in DynamoDB; add that table +
    # an iamPolicy grant when the PoC needs true at-most-once across retries.
    reference = f"rf_{order_id}"
    return (
        f"Refund accepted for order {order_id}: ${amount} "
        f"(reference {reference}). This is a simulated payout -- no real money moved."
    )


@tool("get_refund_status")
def get_refund_status(event: Dict[str, Any]) -> str:
    """Report the (fake) settled status of a refund for an order the customer owns.

    Args:
        customer: the signed-in customer (policy-bound to the caller's identity)
        order_id: the order to check, e.g. "A-1001"
    """
    customer, order_id = event.get("customer"), event.get("order_id")
    if not customer:
        return _NO_IDENTITY
    if not order_id:
        return "Which order? Give an order id like A-1001."
    if not _owned(customer, order_id):
        return f"No order {order_id} found on your account."
    return f"Refund for order {order_id}: settled (reference rf_{order_id}, simulated)."


if __name__ == "__main__":
    # Self-check: routing + every tool + the ownership boundary, no AWS needed.
    class _Ctx:
        class client_context:
            custom = {"bedrockAgentCoreToolName": "payment___list_orders"}

    def call(tool_name, args):
        _Ctx.client_context.custom["bedrockAgentCoreToolName"] = f"payment___{tool_name}"
        return lambda_handler(args, _Ctx())

    r = call("list_orders", {"customer": "alice"})
    assert r["statusCode"] == 200 and "A-1001" in r["body"] and "B-2001" not in r["body"], r

    r = call("lookup_order", {"customer": "alice", "order_id": "A-1001"})
    assert "delivered" in r["body"], r
    r = call("lookup_order", {"customer": "alice", "order_id": "B-2001"})  # bob's → hidden
    assert "No order B-2001" in r["body"], r

    r = call("process_refund", {"customer": "alice", "order_id": "A-1001", "amount": 49})
    assert "rf_A-1001" in r["body"], r
    r = call("process_refund", {"customer": "alice", "order_id": "A-1002", "amount": 120})  # shipped
    assert "only delivered" in r["body"], r
    r = call("process_refund", {"customer": "alice", "order_id": "B-2001", "amount": 15})  # bob's
    assert "No order B-2001" in r["body"], r

    bad = call("nope", {})
    assert bad["statusCode"] == 400, bad
    print("payment lambda self-check OK: routing + 4 tools + ownership boundary")
