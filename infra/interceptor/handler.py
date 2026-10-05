"""Gateway REQUEST interceptor — attach the verified caller to every tool call.

This is how identity "attaches" to the tools. The AgentCore Gateway validates the
inbound Cognito JWT, then (because this interceptor is attached with
passRequestHeaders=True) hands us the request WITH the Authorization header. We
decode the caller's username and force it onto the tool arguments as `customer`,
so the tools act as the signed-in user no matter what the model passed — the
model can't spoof another identity.

Deploy as its own Lambda, then attach it to the gateway (CloudShell):

    import boto3
    boto3.client("bedrock-agentcore-control", region_name="eu-central-1").update_gateway(
        gatewayIdentifier="<GATEWAY_ID>",
        interceptorConfigurations=[{
            "interceptor": {"lambda": {"arn": "<THIS_LAMBDA_ARN>"}},
            "interceptionPoints": ["REQUEST"],
            "inputConfiguration": {"passRequestHeaders": True},
        }],
    )

Then the tool Lambda's `customer` is always the verified caller (its own
_caller_identity fallback becomes unnecessary).
"""
import base64
import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _claims(token: str) -> dict:
    try:
        part = token.split(".")[1]
        part += "=" * (-len(part) % 4)
        return json.loads(base64.urlsafe_b64decode(part))
    except Exception:
        return {}


def _caller(headers: dict) -> str | None:
    auth = headers.get("Authorization") or headers.get("authorization") or ""
    token = auth[7:] if auth.lower().startswith("bearer ") else auth
    c = _claims(token) if token else {}
    return c.get("username") or c.get("cognito:username") or c.get("email") or c.get("sub")


def _inject(body, customer: str):
    """Force `customer` onto the tool-call arguments wherever they live."""
    if isinstance(body, str):
        try:
            return json.dumps(_inject(json.loads(body), customer))
        except Exception:
            return body
    if isinstance(body, dict):
        params = body.get("params")
        if isinstance(params, dict) and isinstance(params.get("arguments"), dict):
            params["arguments"]["customer"] = customer
        elif isinstance(body.get("arguments"), dict):
            body["arguments"]["customer"] = customer
    return body


def lambda_handler(event, context):
    req = event.get("mcp", {}).get("gatewayRequest", {})
    headers = req.get("headers", {}) or {}
    body = req.get("body", {})
    customer = _caller(headers)
    # Log once so you can confirm the real event shape in CloudWatch, then trust it.
    logger.info(json.dumps({"customer": customer, "body_type": type(body).__name__,
                            "body": body}, default=str))
    if customer:
        body = _inject(body, customer)
    return {
        "interceptorInputVersion": "1.0",
        "mcp": {"transformedGatewayRequest": {"headers": headers, "body": body}},
    }


if __name__ == "__main__":
    tok = "h." + base64.urlsafe_b64encode(json.dumps({"username": "mateo"}).encode()).decode().rstrip("=") + ".s"
    ev = {"mcp": {"gatewayRequest": {
        "headers": {"Authorization": "Bearer " + tok},
        "body": {"params": {"name": "list_orders", "arguments": {}}}}}}
    out = lambda_handler(ev, None)
    args = out["mcp"]["transformedGatewayRequest"]["body"]["params"]["arguments"]
    assert args["customer"] == "mateo", out
    assert out["interceptorInputVersion"] == "1.0", out
    print("interceptor self-check OK: injected customer=mateo")
