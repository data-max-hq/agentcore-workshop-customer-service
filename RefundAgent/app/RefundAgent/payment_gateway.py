"""Mock external payment processor -- the flaky dependency (seams 1 & 4).

This stands in for a real refund/payout API. It has its own ledger (the
Payments table) and is idempotent by the idempotency_key the caller supplies:
the SAME key never pays twice, a NEW key always does. That is the whole of
seam 1 -- whether the caller sends a stable key or a fresh one each time
decides whether a retry refunds once or twice.

Knobs (env vars, read per call so a running dev server can be flipped):
  PAYMENT_LATENCY_MS  artificial latency per call (default 50)
  PAYMENT_FAIL        "1" -> always raise, simulating an outage

Calls go through call_with_timeout(), which bounds both time and retries (seam 4).
"""
import concurrent.futures
import json
import logging
import os
import time
import uuid

import boto3
from botocore.exceptions import ClientError

log = logging.getLogger("payment")

_ddb = boto3.resource(
    "dynamodb",
    endpoint_url=os.getenv("DDB_ENDPOINT"),  # None -> real cloud DynamoDB
    region_name=os.getenv("AWS_REGION", "us-east-1"),
)
PAYMENTS = _ddb.Table("Payments")  # PK: idempotency_key. One row == one real payout.


class PaymentError(Exception):
    pass


def process_refund(idempotency_key: str, order_id: str, amount: int) -> dict:
    """Pay out a refund exactly once per idempotency_key.

    A conditional put on the key is what makes a duplicate a no-op. Give the same
    key twice -> one Payments row (one payout). Give two different keys for the
    same order -> two rows (the "refunded twice" bug).
    """
    time.sleep(int(os.getenv("PAYMENT_LATENCY_MS", "50")) / 1000)
    if os.getenv("PAYMENT_FAIL") == "1":
        raise PaymentError("payment gateway unavailable")

    payment = {
        "idempotency_key": idempotency_key,
        "payment_id": uuid.uuid4().hex,
        "order_id": order_id,
        "amount": amount,
    }
    try:
        PAYMENTS.put_item(Item=payment, ConditionExpression="attribute_not_exists(idempotency_key)")
        log.info(json.dumps({"gateway": "process_refund", "order_id": order_id,
                             "key": idempotency_key, "result": "paid", "payment_id": payment["payment_id"]}))
        return {"status": "paid", "payment_id": payment["payment_id"], "amount": amount}
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            log.info(json.dumps({"gateway": "process_refund", "order_id": order_id,
                                 "key": idempotency_key, "result": "duplicate_ignored"}))
            return {"status": "already_paid", "amount": amount}
        raise


def payments_for(order_id: str) -> list[dict]:
    """Every payout recorded for an order (the authoritative refund record).

    Scan is fine here: the local ledger is tiny. order_id is aliased because
    attribute names are safest passed via ExpressionAttributeNames.
    """
    resp = PAYMENTS.scan(
        FilterExpression="#oid = :o",
        ExpressionAttributeNames={"#oid": "order_id"},
        ExpressionAttributeValues={":o": order_id},
    )
    return resp.get("Items", [])


def call_with_timeout(fn, timeout: float = 2.0, retries: int = 2):
    """Call fn with a per-attempt timeout and a bounded number of retries.

    WORKSHOP SEAM 4: a hanging dependency is survived because each attempt is
    capped at `timeout` and total attempts are capped at 1 + `retries`.
    To break it: drop the timeout (fut.result() with no timeout) and/or make
    the loop unbounded (while True) -- the request then hangs and the tool-call
    count climbs without end.

    Note: a timed-out attempt's thread keeps running in the background (a plain
    function can't be force-killed); fine for a mock, and idempotency by key
    means a late-completing attempt still can't double-pay.
    """
    last_error = None
    for attempt in range(1, retries + 2):
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(fn)
            try:
                return future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                last_error = TimeoutError(f"gateway timed out after {timeout}s")
                log.warning(json.dumps({"gateway": "timeout", "attempt": attempt, "timeout_s": timeout}))
            except Exception as exc:  # gateway raised (e.g. outage)
                last_error = exc
                log.warning(json.dumps({"gateway": "error", "attempt": attempt, "error": str(exc)}))
        time.sleep(0.1 * attempt)  # small backoff between attempts
    raise last_error


if __name__ == "__main__":
    # Self-checks. The idempotency check needs DynamoDB Local + tables
    # (docker compose up && uv run python seed.py).
    import store  # noqa: F401  (ensures env is the same; not otherwise used)

    # seam 4: a call slower than the timeout is bounded, not hung.
    calls = {"n": 0}

    def slow():
        calls["n"] += 1
        time.sleep(1.0)

    try:
        call_with_timeout(slow, timeout=0.1, retries=2)
        raise AssertionError("expected a TimeoutError")
    except TimeoutError:
        pass
    assert calls["n"] == 3, calls  # 1 initial + 2 retries, not unbounded

    # seam 1: same key pays once, different keys pay twice.
    oid = "SELFTEST-1"
    for item in payments_for(oid):
        PAYMENTS.delete_item(Key={"idempotency_key": item["idempotency_key"]})
    process_refund(f"rf_{oid}", oid, 1)
    process_refund(f"rf_{oid}", oid, 1)  # same key -> no second payout
    assert len(payments_for(oid)) == 1, "stable key should pay once"
    process_refund(uuid.uuid4().hex, oid, 1)  # fresh key -> a second payout
    assert len(payments_for(oid)) == 2, "a new key should pay again"
    for item in payments_for(oid):
        PAYMENTS.delete_item(Key={"idempotency_key": item["idempotency_key"]})
    print("payment_gateway self-check OK: timeout bounded to 3 attempts; stable key pays once, new key pays again")
