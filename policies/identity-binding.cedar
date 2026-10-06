// Policy 1 of 2 — "you may only act as yourself".
//
// Cedar is deny-by-default, so this single permit is what makes the gateway
// usable at all. The condition binds the `customer_id` tool argument to the
// verified Cognito username carried on the JWT, so the caller (or a model
// acting for them) cannot pass someone else's name.
//
// `username` is a TAG because AgentCore turns every top-level JWT claim into a
// tag on the AgentCore::OAuthUser principal. It reads "alice" only because the
// pool signs in by USER NAME — an email-sign-in pool would put a UUID here.

permit (
    principal is AgentCore::OAuthUser,
    action in [
        AgentCore::Action::"orders___find_orders",
        AgentCore::Action::"orders___get_order_transaction",
        AgentCore::Action::"orders___process_refund",
        AgentCore::Action::"orders___get_refund_status"
    ],
    resource == AgentCore::Gateway::"YOUR_REFUND_GW_JWT_ARN"
)
when {
    principal.hasTag("username") &&
    context.input.customer_id == principal.getTag("username")
};
