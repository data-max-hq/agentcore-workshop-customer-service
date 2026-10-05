// Policy 2 of 2 — "nobody refunds more than $200, ever".
//
// A forbid always beats a permit, so this caps the refund allowed by
// identity-binding.cedar without touching it.
//
// Two things the Cedar analyzer taught us here:
//
//  1. `amount` is JSON Schema "number", which AgentCore models as a Cedar
//     DECIMAL — plain `> 200` fails with "expected Long but saw decimal".
//     Use the decimal extension's .greaterThan().
//
//  2. A bare `principal` also covers AgentCore::IamEntity, and since the only
//     permit is for OAuthUser, the analyzer rejects it as "Overly Restrictive"
//     (always-deny for IamEntity). Scoping the forbid to OAuthUser costs
//     nothing: this gateway is CUSTOM_JWT, so every caller is an OAuthUser.

forbid (
    principal is AgentCore::OAuthUser,
    action == AgentCore::Action::"orders___process_refund",
    resource == AgentCore::Gateway::"arn:aws:bedrock-agentcore:eu-central-1:925061584404:gateway/refund-gateway-identity-pju6ekwsja"
)
when {
    context.input.amount.greaterThan(decimal("200.0"))
};
