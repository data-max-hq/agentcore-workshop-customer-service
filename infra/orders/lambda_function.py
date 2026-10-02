"""Order & transaction lookup, as an AgentCore Gateway Lambda tool.

The agent calls this when a customer says "I want to refund my order ..." --
first to find which order they mean, then to read its transaction details.

The "database" is a static dict below (a mock -- all values are fake). Later it
becomes a DynamoDB table; the tool signatures stay the same.

The Gateway routes each MCP tool call here and passes the tool name in
context.client_context.custom["bedrockAgentCoreToolName"] as "<target>___<tool>".
The tool arguments arrive as the `event` dict.
"""
import json
import logging
from typing import Any, Dict

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Mock database: order_id -> order + its payment transaction. All values are fake.
ORDERS: Dict[str, Dict[str, Any]] = {
    "A-1001": {
        "customer_id": "alice",
        "item": "Wireless mouse",
        "order_date": "2026-09-12",
        "status": "delivered",
        "transaction": {
            "transaction_id": "txn_7f3a91",
            "amount": 49.00,
            "currency": "USD",
            "payment_method": "card ending 4242",
            "paid_at": "2026-09-12T10:14:00Z",
        },
        "refund": None,
    },
    "A-1002": {
        "customer_id": "alice",
        "item": "Mechanical keyboard",
        "order_date": "2026-09-25",
        "status": "shipped",
        "transaction": {
            "transaction_id": "txn_8c21d4",
            "amount": 120.00,
            "currency": "USD",
            "payment_method": "card ending 4242",
            "paid_at": "2026-09-25T16:40:00Z",
        },
        "refund": None,
    },
    "A-1003": {
        "customer_id": "alice",
        "item": "Laptop stand",
        "order_date": "2026-08-30",
        "status": "refunded",
        "transaction": {
            "transaction_id": "txn_2b77e0",
            "amount": 35.00,
            "currency": "USD",
            "payment_method": "card ending 4242",
            "paid_at": "2026-08-30T09:02:00Z",
        },
        "refund": {"refund_id": "rf_2b77e0", "amount": 35.00, "refunded_at": "2026-09-04T11:00:00Z"},
    },
    "B-2001": {
        "customer_id": "bob",
        "item": "USB-C cable",
        "order_date": "2026-09-18",
        "status": "delivered",
        "transaction": {
            "transaction_id": "txn_5e90aa",
            "amount": 15.00,
            "currency": "USD",
            "payment_method": "card ending 1111",
            "paid_at": "2026-09-18T13:27:00Z",
        },
        "refund": None,
    },
    "B-2002": {
        "customer_id": "bob",
        "item": "4K monitor",
        "order_date": "2026-09-20",
        "status": "delivered",
        "transaction": {
            "transaction_id": "txn_c4f612",
            "amount": 300.00,
            "currency": "USD",
            "payment_method": "card ending 1111",
            "paid_at": "2026-09-20T08:55:00Z",
        },
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
    # The Lambda console's Test button can't set client_context -- for console tests,
    # put the tool name in the test event as "tool_name" instead.
    custom = context.client_context.custom if context.client_context else {}
    extended = custom.get("bedrockAgentCoreToolName") or event.pop("tool_name", "")
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


@tool("find_orders")
def find_orders(event: Dict[str, Any]) -> Dict[str, Any]:
    """Find a customer's orders, optionally filtered by item name.

    Used when the customer doesn't give an order id ("refund my keyboard").

    Args:
        customer_id: the customer whose orders to search, e.g. "alice"
        item_query: optional, case-insensitive text to match in the item name
    """
    customer_id = event.get("customer_id")
    if not customer_id:
        return {"error": "Missing required parameter: customer_id."}
    query = (event.get("item_query") or "").lower()

    matches = [
        {"order_id": oid, "item": o["item"], "status": o["status"], "order_date": o["order_date"],
         "amount": o["transaction"]["amount"], "currency": o["transaction"]["currency"]}
        for oid, o in ORDERS.items()
        if o["customer_id"] == customer_id and query in o["item"].lower()
    ]
    return {"orders": matches}


@tool("get_order_transaction")
def get_order_transaction(event: Dict[str, Any]) -> Dict[str, Any]:
    """Get one order's full details: status, payment transaction, and any refund.

    Args:
        order_id: the order to look up, e.g. "A-1001"
    """
    # WORKSHOP NOTE: this trusts any order_id and returns whoever owns it -- there
    # is no ownership check. That's deliberate: it's the hole the identity step
    # (failure mode 3) closes.
    order_id = event.get("order_id")
    if not order_id:
        return {"error": "Missing required parameter: order_id."}
    order = ORDERS.get(order_id)
    if not order:
        return {"error": f"No order {order_id} found."}
    return {"order_id": order_id, **order}


if __name__ == "__main__":
    # Self-check: routing + both tools, no AWS needed.
    class _Ctx:
        class client_context:
            custom = {"bedrockAgentCoreToolName": "orders___find_orders"}

    found = lambda_handler({"customer_id": "alice", "item_query": "keyboard"}, _Ctx())
    assert found["statusCode"] == 200 and "A-1002" in found["body"], found
    _Ctx.client_context.custom["bedrockAgentCoreToolName"] = "orders___get_order_transaction"
    txn = lambda_handler({"order_id": "A-1001"}, _Ctx())
    assert txn["statusCode"] == 200 and "txn_7f3a91" in txn["body"], txn
    missing = lambda_handler({"order_id": "Z-9999"}, _Ctx())
    assert "No order Z-9999" in missing["body"], missing
    _Ctx.client_context.custom["bedrockAgentCoreToolName"] = "orders___nope"
    assert lambda_handler({}, _Ctx())["statusCode"] == 400

    class _ConsoleCtx:  # what a Lambda console test looks like: no client_context
        client_context = None

    console = lambda_handler({"tool_name": "find_orders", "customer_id": "alice"}, _ConsoleCtx())
    assert console["statusCode"] == 200 and "A-1001" in console["body"], console
    print("orders lambda self-check OK: routing + both tools + console test events")
