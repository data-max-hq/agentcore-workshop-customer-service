"""DynamoDB access for the app's own business state.

Two kinds of state live here, and keeping them apart is the whole lesson of
seam 2:
  Orders    = authoritative business truth. Order status is ALWAYS read from
              here, never from what the model "remembers".
  Sessions  = the conversation transcript, so a customer can come back and
              continue where they left off.

(The refund/payout ledger is the payment gateway's own Payments table -- see
payment_gateway.py.)

WORKSHOP SEAM (local vs cloud): DDB_ENDPOINT points boto3 at DynamoDB Local.
Unset it (remove endpoint_url) and this same code talks to real DynamoDB in the
cloud -- that one-line change is the local->deployed story.
"""
import json
import logging
import os

import boto3

log = logging.getLogger("store")

_ddb = boto3.resource(
    "dynamodb",
    endpoint_url=os.getenv("DDB_ENDPOINT"),  # None -> real cloud DynamoDB
    region_name=os.getenv("AWS_REGION", "us-east-1"),
)

ORDERS = _ddb.Table("Orders")
SESSIONS = _ddb.Table("Sessions")


def get_order(order_id: str) -> dict | None:
    return ORDERS.get_item(Key={"order_id": order_id}).get("Item")


def load_session(session_id: str) -> list:
    """Return the stored message history for a session, or [] if new.

    WORKSHOP SEAM 2 ("forgot the case"): skip this load and the agent starts
    every request from scratch and asks the customer to begin again.
    """
    item = SESSIONS.get_item(Key={"session_id": session_id}).get("Item")
    return json.loads(item["messages"]) if item else []


def save_session(session_id: str, messages: list) -> None:
    # Stored as one JSON string so nested tool blocks and any numbers survive a
    # round-trip without fighting DynamoDB's typed-attribute rules.
    SESSIONS.put_item(Item={"session_id": session_id, "messages": json.dumps(messages, default=str)})


if __name__ == "__main__":
    # Self-check for seam 2 storage. Requires DynamoDB Local + tables
    # (docker compose up && uv run python seed.py).
    sid = "SELFTEST-SESSION"
    save_session(sid, [{"role": "user", "content": "remember the blue widget"}])
    loaded = load_session(sid)
    assert loaded and loaded[0]["content"] == "remember the blue widget", loaded
    SESSIONS.delete_item(Key={"session_id": sid})
    assert load_session(sid) == []
    print("store self-check OK: session round-trips through DynamoDB")
