#!/usr/bin/env bash
# Exercises all four workshop seams against a running agent and asserts the
# outcomes. Run it after:  docker compose up -d  &&  (cd app/RefundAgent && uv run python seed.py)
# and with `agentcore dev --port 8080` running in another terminal.
#
# Override the endpoints if yours differ:
#   AGENT_URL=http://localhost:8080/invocations DDB_ENDPOINT=http://localhost:8000 ./demo.sh
set -uo pipefail

AGENT_URL="${AGENT_URL:-http://localhost:8080/invocations}"
DDB=(--endpoint-url "${DDB_ENDPOINT:-http://localhost:8000}" --region "${AWS_REGION:-us-east-1}")
ORDER="A-1001"   # alice's delivered order
pass=0; fail=0

say() { curl -s -m 60 -X POST "$AGENT_URL" -H 'Content-Type: application/json' -d "$1" \
        | python3 -c 'import sys,json;print(json.load(sys.stdin).get("response","<no response>"))'; }

paycount() { aws dynamodb scan --table-name Payments "${DDB[@]}" \
        --filter-expression "#o = :o" --expression-attribute-names '{"#o":"order_id"}' \
        --expression-attribute-values "{\":o\":{\"S\":\"$1\"}}" --query 'Count' --output text; }

assert() { if [ "$2" = "$3" ]; then echo "  PASS: $1 ($2)"; pass=$((pass+1));
           else echo "  FAIL: $1 (got '$2' want '$3')"; fail=$((fail+1)); fi; }

reset() {  # delete any payouts + demo sessions for a clean, repeatable run
  for key in $(aws dynamodb scan --table-name Payments "${DDB[@]}" \
      --filter-expression "#o = :o" --expression-attribute-names '{"#o":"order_id"}' \
      --expression-attribute-values "{\":o\":{\"S\":\"$ORDER\"}}" \
      --query 'Items[].idempotency_key.S' --output text); do
    aws dynamodb delete-item --table-name Payments "${DDB[@]}" --key "{\"idempotency_key\":{\"S\":\"$key\"}}"
  done
  for sid in d1 d2 d3; do
    aws dynamodb delete-item --table-name Sessions "${DDB[@]}" --key "{\"session_id\":{\"S\":\"$sid\"}}"
  done
}

echo "Resetting demo state for $ORDER ..."; reset

echo; echo "===== Seam 1 (idempotency): a refund, then the same refund retried ====="
echo "-- Alice refunds $ORDER"; say "{\"prompt\":\"Refund my order $ORDER.\",\"customer_id\":\"alice\",\"session_id\":\"d1\"}"
assert "one payout after first refund" "$(paycount $ORDER)" "1"
echo "-- Alice refunds $ORDER again (fresh session = a retried request)"; say "{\"prompt\":\"Please refund $ORDER.\",\"customer_id\":\"alice\",\"session_id\":\"d2\"}"
assert "STILL one payout after retry (no double refund)" "$(paycount $ORDER)" "1"

echo; echo "===== Seam 3 (tenant isolation): Bob tries Alice's order ====="
echo "-- Bob looks up $ORDER"; say "{\"prompt\":\"What is the status of order $ORDER?\",\"customer_id\":\"bob\",\"session_id\":\"d3\"}"
echo "-- Bob tries to refund $ORDER"; say "{\"prompt\":\"Refund order $ORDER.\",\"customer_id\":\"bob\",\"session_id\":\"d3\"}"
assert "Bob created no payout on Alice's order" "$(paycount $ORDER)" "1"

echo; echo "===== Seam 2 (session + authoritative status): Alice returns, no order id ====="
echo "-- Alice (session d1) asks the status of 'my refund'"; say "{\"prompt\":\"whats the status of my refund?\",\"customer_id\":\"alice\",\"session_id\":\"d1\"}"
echo "   (the agent should recall $ORDER from the session AND read status from the ledger)"

echo; echo "===== RESULT: $pass passed, $fail failed ====="
echo "Seam 4 (timeout/retry) is best seen live: stop the dev server and restart it with"
echo "  PAYMENT_LATENCY_MS=5000 agentcore dev --port 8080"
echo "then issue a refund -- it returns a clean timeout and the logs show attempts capped at 3."
[ "$fail" -eq 0 ]
