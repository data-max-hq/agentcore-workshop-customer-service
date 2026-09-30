"""Fake payment gateway, as an AgentCore Gateway Lambda tool.

This is the cloud twin of the local `payment_gateway.py`: a MOCK payout API --
no real money moves, no real processor. It exists to show the payout become a
managed AgentCore Gateway MCP tool the agent calls, instead of an in-process
Python function.

The Gateway routes each MCP tool call here and passes the tool name in
context.client_context.custom["bedrockAgentCoreToolName"] as "<target>___<tool>".
"""
import json
import logging
from typing import Any, Dict

logger = logging.getLogger()
logger.setLevel(logging.INFO)

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


@tool("process_refund")
def process_refund(event: Dict[str, Any]) -> str:
    """Issue a (fake) refund for a delivered order. Safe to retry.

    Args:
        order_id: the order to refund, e.g. "A-1001"
        amount: refund amount in dollars
    """
    order_id = event.get("order_id")
    amount = event.get("amount")
    if not order_id or amount is None:
        return "Missing required parameter: order_id and amount are both required."

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
    """Report the (fake) settled status of a refund.

    Args:
        order_id: the order to check, e.g. "A-1001"
    """
    order_id = event.get("order_id")
    if not order_id:
        return "Missing required parameter: order_id."
    return f"Refund for order {order_id}: settled (reference rf_{order_id}, simulated)."


if __name__ == "__main__":
    # Self-check: routing + both tools, no AWS needed.
    class _Ctx:
        class client_context:
            custom = {"bedrockAgentCoreToolName": "payment___process_refund"}

    ok = lambda_handler({"order_id": "A-1001", "amount": 49}, _Ctx())
    assert ok["statusCode"] == 200 and "rf_A-1001" in ok["body"], ok
    _Ctx.client_context.custom["bedrockAgentCoreToolName"] = "payment___get_refund_status"
    st = lambda_handler({"order_id": "A-1001"}, _Ctx())
    assert st["statusCode"] == 200 and "settled" in st["body"], st
    _Ctx.client_context.custom["bedrockAgentCoreToolName"] = "payment___nope"
    bad = lambda_handler({}, _Ctx())
    assert bad["statusCode"] == 400, bad
    print("payment lambda self-check OK: routing + process_refund + get_refund_status")
