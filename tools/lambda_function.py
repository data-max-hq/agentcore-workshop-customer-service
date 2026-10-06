"""Order, transaction & refund tools, behind an AgentCore Gateway.

Deployed as the Lambda `refund_agent_tool`, reached through two gateways:

  Door A  harness -> gateway (AWS_IAM)   no policy engine  -- the agent can
                                         pass ANY customer_id, so it can read
                                         anyone's orders. That's the hole.
  Door B  you     -> gateway (CUSTOM_JWT) + Cedar policies -- the policy engine
                                         forces customer_id == your verified
                                         Cognito username, so the hole closes.

Every tool takes `customer_id` and SCOPES its answer to it. The Lambda never
verifies who the caller really is -- that is the policy engine's job. Keeping
the check out of here is deliberate: it is what makes the two doors differ.

The Gateway passes the tool name in
context.client_context.custom["bedrockAgentCoreToolName"] as "<target>___<tool>";
tool arguments arrive as the `event` dict.
"""
import json
import logging
from typing import Any, Dict

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Mock database: order_id -> order + its payment transaction. All values are fake.
ORDERS: Dict[str, Dict[str, Any]] = {
    "A-1001": {
        "customer_id": "alice", "item": "Wireless mouse", "order_date": "2026-09-12",
        "status": "delivered",
        "transaction": {"transaction_id": "txn_7f3a91", "amount": 49.00, "currency": "USD",
                        "payment_method": "card ending 4242", "paid_at": "2026-09-12T10:14:00Z"},
        "refund": None,
    },
    "A-1002": {
        "customer_id": "alice", "item": "Mechanical keyboard", "order_date": "2026-09-25",
        "status": "shipped",
        "transaction": {"transaction_id": "txn_8c21d4", "amount": 120.00, "currency": "USD",
                        "payment_method": "card ending 4242", "paid_at": "2026-09-25T16:40:00Z"},
        "refund": None,
    },
    "A-1003": {
        "customer_id": "alice", "item": "Laptop stand", "order_date": "2026-08-30",
        "status": "refunded",
        "transaction": {"transaction_id": "txn_2b77e0", "amount": 35.00, "currency": "USD",
                        "payment_method": "card ending 4242", "paid_at": "2026-08-30T09:02:00Z"},
        "refund": {"refund_id": "rf_2b77e0", "amount": 35.00, "refunded_at": "2026-09-04T11:00:00Z"},
    },
    "A-1004": {  # over $200 -- the refund-cap policy demo
        "customer_id": "alice", "item": "4K monitor", "order_date": "2026-09-28",
        "status": "delivered",
        "transaction": {"transaction_id": "txn_a91e55", "amount": 300.00, "currency": "USD",
                        "payment_method": "card ending 4242", "paid_at": "2026-09-28T12:05:00Z"},
        "refund": None,
    },
    "B-2001": {
        "customer_id": "bob", "item": "USB-C cable", "order_date": "2026-09-18",
        "status": "delivered",
        "transaction": {"transaction_id": "txn_5e90aa", "amount": 15.00, "currency": "USD",
                        "payment_method": "card ending 1111", "paid_at": "2026-09-18T13:27:00Z"},
        "refund": None,
    },
    "B-2002": {
        "customer_id": "bob", "item": "Standing desk", "order_date": "2026-09-20",
        "status": "delivered",
        "transaction": {"transaction_id": "txn_c4f612", "amount": 450.00, "currency": "USD",
                        "payment_method": "card ending 1111", "paid_at": "2026-09-20T08:55:00Z"},
        "refund": None,
    },
    "M-3001": {
        "customer_id": "mateo", "item": "Webcam", "order_date": "2026-09-15",
        "status": "delivered",
        "transaction": {"transaction_id": "txn_d10b73", "amount": 89.00, "currency": "USD",
                        "payment_method": "card ending 7788", "paid_at": "2026-09-15T14:30:00Z"},
        "refund": None,
    },
    "M-3002": {  # over $200
        "customer_id": "mateo", "item": "Monitor arm", "order_date": "2026-09-22",
        "status": "delivered",
        "transaction": {"transaction_id": "txn_e4471c", "amount": 210.00, "currency": "USD",
                        "payment_method": "card ending 7788", "paid_at": "2026-09-22T09:41:00Z"},
        "refund": None,
    },
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
    extended = context.client_context.custom.get("bedrockAgentCoreToolName", "")
    tool_name = extended.split("___", 1)[1] if "___" in extended else extended
    logger.info(json.dumps({"tool": tool_name, "args": event}))

    handler = TOOLS.get(tool_name)
    if not handler:
        return {"statusCode": 400, "body": json.dumps({"error": f"Unknown tool: {tool_name}"})}
    try:
        return {"statusCode": 200, "body": json.dumps({"result": handler(event)})}
    except Exception as exc:  # surface the message to the model, don't leak a stack
        logger.exception("tool failed")
        return {"statusCode": 500, "body": json.dumps({"error": str(exc)})}


def _owned(customer_id: str, order_id: str):
    """The order, but only if customer_id owns it. Scoping, not authentication."""
    order = ORDERS.get(order_id)
    return order if order and order["customer_id"] == customer_id else None


@tool("find_orders")
def find_orders(event: Dict[str, Any]) -> Dict[str, Any]:
    """List a customer's orders, optionally filtered by item name.

    Args:
        customer_id: whose orders to list, e.g. "alice"
        item_query: optional, case-insensitive text to match in the item name
    """
    customer_id = event.get("customer_id")
    if not customer_id:
        return {"error": "Missing required parameter: customer_id."}
    query = (event.get("item_query") or "").lower()

    return {"orders": [
        {"order_id": oid, "item": o["item"], "status": o["status"], "order_date": o["order_date"],
         "amount": o["transaction"]["amount"], "currency": o["transaction"]["currency"]}
        for oid, o in ORDERS.items()
        if o["customer_id"] == customer_id and query in o["item"].lower()
    ]}


@tool("get_order_transaction")
def get_order_transaction(event: Dict[str, Any]) -> Dict[str, Any]:
    """One order's status, payment transaction and any refund -- scoped to customer_id.

    Args:
        customer_id: the customer the order must belong to
        order_id: the order to look up, e.g. "A-1001"
    """
    customer_id, order_id = event.get("customer_id"), event.get("order_id")
    if not customer_id or not order_id:
        return {"error": "Missing required parameter: customer_id and order_id are both required."}
    order = _owned(customer_id, order_id)
    if not order:
        return {"error": f"No order {order_id} found for {customer_id}."}
    return {"order_id": order_id, **order}


@tool("process_refund")
def process_refund(event: Dict[str, Any]) -> Dict[str, Any]:
    """Issue a (simulated) refund for a delivered order. Mock -- no real money.

    Args:
        customer_id: the customer the order must belong to
        order_id: the order to refund, e.g. "A-1001"
        amount: refund amount in dollars
    """
    customer_id, order_id = event.get("customer_id"), event.get("order_id")
    amount = event.get("amount")
    if not customer_id or not order_id or amount is None:
        return {"error": "Missing required parameter: customer_id, order_id and amount are all required."}

    order = _owned(customer_id, order_id)
    if not order:
        return {"error": f"No order {order_id} found for {customer_id}."}
    if order["refund"]:
        return {"error": f"Order {order_id} was already refunded ({order['refund']['refund_id']})."}
    if order["status"] != "delivered":
        return {"error": f"Order {order_id} is {order['status']}; only delivered orders can be refunded."}

    amount = float(amount)
    paid = order["transaction"]["amount"]
    if amount <= 0 or amount > paid:
        return {"error": f"Refund must be between $0 and the ${paid:.2f} paid for {order_id}."}
    # No $200 cap here on purpose: the cap is a gateway policy (M5), so when a refund
    # over $200 is refused, it was the policy that refused it.

    refund = {"refund_id": "rf_" + order["transaction"]["transaction_id"][4:],
              "amount": amount, "status": "settled"}
    order["refund"] = refund          # ponytail: in-memory, resets on cold start -- fine for a workshop
    order["status"] = "refunded"
    return {"order_id": order_id, **refund}


@tool("get_refund_status")
def get_refund_status(event: Dict[str, Any]) -> Dict[str, Any]:
    """Report whether an order has a (simulated) settled refund.

    Args:
        customer_id: the customer the order must belong to
        order_id: the order to check, e.g. "A-1001"
    """
    customer_id, order_id = event.get("customer_id"), event.get("order_id")
    if not customer_id or not order_id:
        return {"error": "Missing required parameter: customer_id and order_id are both required."}
    order = _owned(customer_id, order_id)
    if not order:
        return {"error": f"No order {order_id} found for {customer_id}."}
    return {"order_id": order_id, "refund": order["refund"]}


if __name__ == "__main__":
    # Self-check: routing + scoping + the refund rules. No AWS needed.
    class _Ctx:
        class client_context:
            custom = {}

    def call(tool_name, args):
        _Ctx.client_context.custom["bedrockAgentCoreToolName"] = f"orders___{tool_name}"
        out = lambda_handler(args, _Ctx())
        return out["statusCode"], json.loads(out["body"])

    # find_orders scopes to the customer
    _, r = call("find_orders", {"customer_id": "alice"})
    ids = {o["order_id"] for o in r["result"]["orders"]}
    assert ids == {"A-1001", "A-1002", "A-1003", "A-1004"}, ids
    _, r = call("find_orders", {"customer_id": "alice", "item_query": "keyboard"})
    assert [o["order_id"] for o in r["result"]["orders"]] == ["A-1002"], r

    # reads are scoped: alice cannot see bob's order even by id
    _, r = call("get_order_transaction", {"customer_id": "alice", "order_id": "B-2001"})
    assert "No order B-2001" in r["result"]["error"], r
    _, r = call("get_order_transaction", {"customer_id": "bob", "order_id": "B-2001"})
    assert r["result"]["transaction"]["transaction_id"] == "txn_5e90aa", r

    # refund rules
    _, r = call("process_refund", {"customer_id": "alice", "order_id": "B-2001", "amount": 10})
    assert "No order B-2001" in r["result"]["error"], r          # not hers
    _, r = call("process_refund", {"customer_id": "alice", "order_id": "A-1002", "amount": 10})
    assert "only delivered" in r["result"]["error"], r           # shipped
    _, r = call("process_refund", {"customer_id": "alice", "order_id": "A-1003", "amount": 10})
    assert "already refunded" in r["result"]["error"], r
    _, r = call("process_refund", {"customer_id": "alice", "order_id": "A-1004", "amount": 300})
    assert r["result"]["status"] == "settled", r                 # no cap here: that's the policy's job
    _, r = call("process_refund", {"customer_id": "alice", "order_id": "A-1001", "amount": 49})
    assert r["result"]["status"] == "settled", r                 # the happy path
    _, r = call("get_refund_status", {"customer_id": "alice", "order_id": "A-1001"})
    assert r["result"]["refund"]["amount"] == 49, r
    _, r = call("process_refund", {"customer_id": "alice", "order_id": "A-1001", "amount": 49})
    assert "already refunded" in r["result"]["error"], r         # idempotent-ish

    # unknown tool
    assert call("nope", {})[0] == 400

    print("orders lambda self-check OK: routing, scoping, refund rules")
