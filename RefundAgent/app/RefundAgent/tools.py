"""The agent's tools, and the two cross-cutting seams they enforce:

  seam 3 (identity): the caller's customer_id comes from CURRENT_CUSTOMER, a
    context variable set by the entrypoint from the authenticated request --
    never from a tool argument the model fills in. Tools then check that the
    order actually belongs to that customer.

  seam 4 (observability): @observed wraps every tool with structured timing
    logs, so slow/looping tool calls are visible.
"""
import contextvars
import functools
import json
import logging
import time

from strands import tool

import payment_gateway
import store

log = logging.getLogger("refund")

# Set once per request by the entrypoint from the authenticated identity.
CURRENT_CUSTOMER: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_customer", default=None)


def _caller() -> str:
    customer = CURRENT_CUSTOMER.get()
    if not customer:
        # No authenticated identity -> refuse rather than act on an unknown caller.
        raise PermissionError("no authenticated customer in request context")
    return customer


def observed(fn):
    """Log tool name, caller, outcome, and latency for every call (seam 4)."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        start = time.monotonic()
        status = "ok"
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            status = f"error:{type(exc).__name__}"
            raise
        finally:
            log.info(json.dumps({
                "tool": fn.__name__,
                "customer": CURRENT_CUSTOMER.get(),
                "status": status,
                "latency_ms": round((time.monotonic() - start) * 1000),
            }))

    return wrapper


def _owned_order(order_id: str):
    """Return the order iff it belongs to the authenticated caller (seam 3).

    Returns the same None for 'no such order' and 'not your order' so a customer
    can't probe for other people's order ids.
    """
    order = store.get_order(order_id)
    if not order or order["customer_id"] != _caller():
        return None
    return order


@tool
@observed
def lookup_order(order_id: str) -> str:
    """Look up the status and amount of one of the current customer's orders.

    Args:
        order_id: The order identifier, e.g. "A-1001".
    """
    order = _owned_order(order_id)
    if not order:
        return f"No order {order_id} found on your account."
    return f"Order {order_id}: status={order['status']}, amount=${order['amount']}, item={order['item']}."


@tool
@observed
def issue_refund(order_id: str) -> str:
    """Issue a refund for one of the current customer's delivered orders. Safe to retry.

    Args:
        order_id: The order identifier to refund, e.g. "A-1001".
    """
    order = _owned_order(order_id)
    if not order:
        return f"No order {order_id} found on your account."
    if order["status"] != "delivered":
        return f"Order {order_id} is '{order['status']}'; only delivered orders can be refunded."

    # WORKSHOP SEAM 1: a STABLE idempotency key derived from the order. Because
    # it is the same on every attempt, the gateway pays out at most once no
    # matter how many times this runs. Break it by using a fresh key each call
    # (e.g. uuid4().hex) -> a retry refunds twice.
    idempotency_key = f"rf_{order_id}"

    # seam 4: pay through the bounded-timeout helper so a slow/broken gateway
    # can't hang us.
    result = payment_gateway.call_with_timeout(
        lambda: payment_gateway.process_refund(idempotency_key, order_id, order["amount"]),
        timeout=2.0,
        retries=2,
    )
    if result["status"] == "already_paid":
        return f"Refund for {order_id} was already processed -- ${order['amount']} is on its way."
    return f"Refunded ${order['amount']} for {order_id}."


@tool
@observed
def get_refund_status(order_id: str) -> str:
    """Report the authoritative refund status for one of the current customer's orders.

    Args:
        order_id: The order identifier, e.g. "A-1001".
    """
    order = _owned_order(order_id)
    if not order:
        return f"No order {order_id} found on your account."
    # WORKSHOP SEAM 2 ("remembered the wrong status"): read from the gateway's
    # authoritative payout ledger -- not from the conversation.
    payments = payment_gateway.payments_for(order_id)
    if not payments:
        return f"No refund on record for {order_id}. Order status is '{order['status']}'."
    total = sum(int(p["amount"]) for p in payments)
    return f"Refund for {order_id}: settled, ${total} paid across {len(payments)} payout(s)."


TOOLS = [lookup_order, issue_refund, get_refund_status]
