"""Create the local DynamoDB tables and seed demo orders.

Run from this directory after `docker compose up -d`:
    uv run python seed.py
Idempotent: existing tables are left alone; orders are re-put.
"""
import os

import boto3

ENDPOINT = os.getenv("DDB_ENDPOINT", "http://localhost:8000")
REGION = os.getenv("AWS_REGION", "us-east-1")
ddb = boto3.resource("dynamodb", endpoint_url=ENDPOINT, region_name=REGION)
client = ddb.meta.client

TABLES = {"Orders": "order_id", "Payments": "idempotency_key", "Sessions": "session_id"}

ORDERS = [
    {"order_id": "A-1001", "customer_id": "alice", "status": "delivered", "amount": 49, "item": "Wireless mouse"},
    {"order_id": "A-1002", "customer_id": "alice", "status": "shipped", "amount": 120, "item": "Mechanical keyboard"},
    {"order_id": "B-2001", "customer_id": "bob", "status": "delivered", "amount": 15, "item": "USB-C cable"},
    {"order_id": "B-2002", "customer_id": "bob", "status": "delivered", "amount": 300, "item": "4K monitor"},
]


def ensure_table(name: str, key: str) -> None:
    try:
        client.describe_table(TableName=name)
        return
    except client.exceptions.ResourceNotFoundException:
        pass
    client.create_table(
        TableName=name,
        KeySchema=[{"AttributeName": key, "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": key, "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    client.get_waiter("table_exists").wait(TableName=name)
    print(f"created table {name}")


for table_name, key_name in TABLES.items():
    ensure_table(table_name, key_name)

orders = ddb.Table("Orders")
for order in ORDERS:
    orders.put_item(Item=order)

print(f"seeded {len(ORDERS)} orders into {ENDPOINT}: "
      + ", ".join(f"{o['order_id']}({o['customer_id']}/{o['status']})" for o in ORDERS))
