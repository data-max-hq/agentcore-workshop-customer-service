// Point-in-time authorization for the PaymentGateway tools (Lab 5).
// Deny-by-default: a request is allowed only if a `permit` applies and no
// `forbid` overrides it. Paste these into the policy engine in the console.
//
// Placeholders to replace:
//   <GATEWAY_ARN>  your gateway ARN: AgentCore console -> Gateways -> details.
//   target name    actions are "<target>___<tool>"; our target is `payment`
//                  (agentcore.json). Match whatever you named the target.
//   "username"     the principal TAG that carries the Cognito username claim.
//                  Verify the exact tag name in the console's policy tester;
//                  the Cognito access token also exposes `sub` and `client_id`.

// Reads: a customer may only act on their OWN identity. The `customer` tool
// argument is bound to the verified JWT identity, so the agent cannot look up
// or check another person's orders even if the model tries.
permit (
    principal is AgentCore::OAuthUser,
    action in [
        AgentCore::Action::"payment___list_orders",
        AgentCore::Action::"payment___lookup_order",
        AgentCore::Action::"payment___get_refund_status"
    ],
    resource == AgentCore::Gateway::"<GATEWAY_ARN>"
)
when {
    context.input.customer == principal.getTag("username")
};

// Guardrail: never pay out more than $200, whoever asks. A `forbid` overrides
// any `permit`, so this caps the refund permit in refund.dogwood too.
forbid (
    principal,
    action == AgentCore::Action::"payment___process_refund",
    resource == AgentCore::Gateway::"<GATEWAY_ARN>"
)
when {
    context.input.amount > 200
};
