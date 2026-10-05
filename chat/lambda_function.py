# The workshop chat UI, in one file so it can be pasted into the Lambda console.
# Serves the page (HTML at the bottom), plus GET /lookup which finds this account's Cognito pool,
# app client, harness and JWT gateway, so nobody has to copy IDs around, and POST /mcp which
# forwards the Tools tab's calls to that gateway (see mcp_forward for why). In a shared account,
# ?initials=amg picks the ones named by the workshop convention. The page then talks to
# Cognito / AgentCore straight from the browser.
import base64
import json
import os
import re
import urllib.error
import urllib.request

import boto3

REGION = os.environ["AWS_REGION"]


def _pages(call, key, token_in, token_out, **kw):
    while True:
        page = call(**kw)
        yield from page.get(key, [])
        if not page.get(token_out):
            return
        kw[token_in] = page[token_out]


def _pick(items, name_key, name, initials):
    """(item, why-not). With initials: the item named by the convention. Without: the only one there
    is, which is the normal case in a fresh per-attendee account."""
    items = list(items)
    if initials:
        hit = next((i for i in items if i[name_key].lower() == name), None)
        return hit, None if hit else f"no {name} yet"
    if len(items) == 1:
        return items[0], None
    return None, "none yet" if not items else f"{len(items)} found, type your initials to choose"


def lookup(initials: str) -> dict:
    """Each value is found or missing independently, so the page can say which lab is still to do."""
    idp = boto3.client("cognito-idp")
    ac = boto3.client("bedrock-agentcore-control")
    found, missing = {"region": REGION}, {}

    pool, missing["user_pool_id"] = _pick(_pages(idp.list_user_pools, "UserPools", "NextToken", "NextToken",
                                                 MaxResults=60), "Name", f"refund-pool-{initials}", initials)
    if pool:
        found["user_pool_id"] = pool["Id"]
        client, missing["client_id"] = _pick(_pages(idp.list_user_pool_clients, "UserPoolClients", "NextToken",
                                                    "NextToken", UserPoolId=pool["Id"], MaxResults=60),
                                             "ClientName", f"refund-tester-{initials}", initials)
        if client:
            found["client_id"] = client["ClientId"]
    else:
        missing["client_id"] = "needs the user pool first"

    harness, missing["agent_arn"] = _pick(_pages(ac.list_harnesses, "harnesses", "nextToken", "nextToken",
                                                 maxResults=100), "harnessName", f"refund_{initials}", initials)
    if harness:
        found["agent_arn"] = harness["arn"]

    # only the JWT gateway: the harness's own gateway is IAM-authorized and useless from the browser
    gateways = (g for g in _pages(ac.list_gateways, "items", "nextToken", "nextToken", maxResults=100)
                if initials or g.get("authorizerType") == "CUSTOM_JWT")
    gw, missing["gateway_url"] = _pick(gateways, "name", f"refund_gw_jwt_{initials}", initials)
    if gw:
        found["gateway_url"] = f"https://{gw['gatewayId']}.gateway.bedrock-agentcore.{REGION}.amazonaws.com/mcp"
    return {"found": found, "missing": {k: v for k, v in missing.items() if v}}


# Only ever forward to an AgentCore gateway's MCP endpoint, so this can't be used as an open proxy.
GATEWAY_URL = re.compile(r"https://[a-z0-9-]+\.gateway\.bedrock-agentcore\.[a-z0-9-]+\.amazonaws\.com/mcp")
FORWARD = ("authorization", "content-type", "accept", "mcp-protocol-version", "mcp-session-id",
           "x-amzn-bedrock-agentcore-policy-session-id")


def mcp_forward(event) -> dict:
    """Pass one Tools-tab call through to gateway B, with the caller's own token.

    The browser can't call the gateway directly once Dogwood is in play: temporal
    policies need the x-amzn-bedrock-agentcore-policy-session-id header on every
    call, and the gateway's CORS rules don't let a browser send it. Going through
    here also lets the page read Mcp-Session-Id. The gateway still sees the user's
    JWT, so Cedar and Dogwood still see the user, not this Lambda.
    """
    headers = event.get("headers") or {}   # function URLs lower-case header names
    target = headers.get("x-gateway-url", "")
    if not GATEWAY_URL.fullmatch(target):
        return _json(400, {"error": {"message": "Gateway URL should look like https://…gateway.bedrock-agentcore.<region>.amazonaws.com/mcp"}})
    body = event.get("body") or ""
    body = base64.b64decode(body) if event.get("isBase64Encoded") else body.encode()
    req = urllib.request.Request(target, data=body, method="POST",
                                 headers={k: headers[k] for k in FORWARD if k in headers})
    try:
        resp = urllib.request.urlopen(req, timeout=12)
    except urllib.error.HTTPError as e:   # 4xx/5xx still carry a useful body
        resp = e
    with resp:
        out = {"Content-Type": resp.headers.get("content-type", "application/json")}
        if resp.headers.get("mcp-session-id"):
            out["Mcp-Session-Id"] = resp.headers["mcp-session-id"]
        return {"statusCode": resp.status, "headers": out, "body": resp.read().decode()}


def _json(status, body):
    return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body)}


def lambda_handler(event, context):
    if event.get("rawPath") == "/lookup":
        initials = (event.get("queryStringParameters") or {}).get("initials", "").strip().lower()
        if initials and not re.fullmatch(r"[a-z0-9]{1,10}", initials):
            return _json(400, {"error": "Initials should be letters and numbers only, like amg."})
        try:
            return _json(200, lookup(initials))
        except Exception as e:  # surface AWS errors (e.g. missing permission) to the page
            return _json(500, {"error": f"{type(e).__name__}: {e}"})
    if event.get("rawPath") == "/mcp":
        return mcp_forward(event)
    return {"statusCode": 200, "headers": {"Content-Type": "text/html; charset=utf-8"}, "body": HTML}


# ---- the page -------------------------------------------------------------------
HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AgentCore Chat</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/12.0.2/marked.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/dompurify/3.1.6/purify.min.js"></script>
<style>
  :root { --accent:#ED7445; --accent-soft:rgba(237,116,69,.14); --bg:#0e1117; --panel:#161a22;
          --line:rgba(255,255,255,.08); --text:#e8eaed; --muted:#9aa0a8; --ok:#3fb950; --bad:#f85149; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--text); font:15px/1.5 system-ui,-apple-system,sans-serif; }
  main { max-width:820px; margin:0 auto; padding:2.5rem 16px 6rem; }
  .hero { text-align:center; margin-bottom:1.75rem; }
  .hero h1 { font-size:2.4rem; letter-spacing:-.02em; margin:0 0 .35rem; }
  .hero h1 i { color:var(--accent); filter:drop-shadow(0 0 14px rgba(237,116,69,.45)); margin-right:.3rem; }
  .grad { background:linear-gradient(90deg,#fff 0%,#ED7445 160%); -webkit-background-clip:text;
          background-clip:text; -webkit-text-fill-color:transparent; }
  .hero p { color:var(--muted); margin:0; }
  .rule { height:2px; width:72px; margin:0 auto 1.75rem; border-radius:2px;
          background:linear-gradient(90deg,transparent,var(--accent),transparent); }
  .hidden { display:none !important; }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:1rem; margin-bottom:1rem; }
  .narrow { max-width:400px; margin:0 auto; }
  .hint { display:block; font-size:.8rem; opacity:.75; margin-top:.1rem; }
  .found { list-style:none; padding:0; margin:.6rem 0; }
  .found li { margin:.25rem 0; }
  .found .yes i { color:var(--ok); } .found .no i { color:var(--muted); }
  label.check { display:flex; gap:.5rem; align-items:baseline; color:var(--text); }
  label.check input { width:auto; }
  label.check .hint { display:inline; }
  label { display:block; font-size:.88rem; color:var(--muted); margin:.6rem 0 .25rem; }
  input, textarea, select { width:100%; background:var(--bg); color:var(--text); border:1px solid var(--line);
          border-radius:8px; padding:.55rem .7rem; font:inherit; }
  textarea { font:13px/1.4 ui-monospace,monospace; }
  input:focus, textarea:focus, select:focus { outline:none; border-color:var(--accent); box-shadow:0 0 0 3px var(--accent-soft); }
  button { background:var(--panel); color:var(--text); border:1px solid var(--line); border-radius:8px;
          padding:.5rem .9rem; font:inherit; cursor:pointer; }
  button:hover { border-color:var(--accent); }
  button.primary { background:linear-gradient(135deg,#F08A5D,#ED7445); border:none; color:#fff;
          box-shadow:0 4px 14px rgba(237,116,69,.35); }
  button:disabled { opacity:.5; cursor:wait; }
  .full { width:100%; margin-top:1rem; }
  .msg { border-radius:8px; padding:.7rem .9rem; margin:.6rem 0; }
  .err { background:rgba(248,81,73,.12); border:1px solid rgba(248,81,73,.35); }
  .info { background:rgba(88,166,255,.1); border:1px solid rgba(88,166,255,.3); }
  .ok { background:rgba(63,185,80,.12); border:1px solid rgba(63,185,80,.35); }
  .muted { color:var(--muted); font-size:.9rem; }
  .bar { display:flex; gap:.5rem; align-items:center; flex-wrap:wrap; }
  .bar .who { flex:1; color:var(--muted); font-size:.9rem; }
  .bar .who i { color:var(--accent); margin-right:.45rem; }
  .bar .who b { color:var(--text); }
  pre { background:var(--bg); border:1px solid var(--line); border-radius:8px; padding:.7rem; overflow:auto;
        font-size:12.5px; white-space:pre-wrap; word-break:break-all; max-height:400px; }
  details summary { cursor:pointer; color:var(--muted); }
  details summary:hover { color:var(--accent); }
  .tabs { display:flex; gap:1.2rem; border-bottom:1px solid var(--line); margin:1.5rem 0 1rem; }
  .tabs button { background:none; border:none; border-bottom:2px solid transparent; border-radius:0; padding:.5rem 0; color:var(--muted); }
  .tabs button.on { color:var(--text); border-bottom-color:var(--accent); }
  .chat .m { display:flex; gap:.7rem; margin:1rem 0; }
  .chat .m > i { width:28px; height:28px; flex:none; border-radius:6px; display:grid; place-items:center;
                 background:var(--panel); color:var(--accent); font-size:13px; }
  .chat .m.user > i { color:#58a6ff; }
  .chat .body { flex:1; min-width:0; }
  .chat .body > :first-child { margin-top:.2rem; }
  .composer { position:fixed; left:0; right:0; bottom:0; background:linear-gradient(transparent,var(--bg) 30%); padding:1.5rem 16px 1rem; }
  .composer form { max-width:820px; margin:0 auto; display:flex; gap:.5rem; }
  .composer input { border-radius:14px; padding:.75rem 1rem; }
</style>
</head>
<body>
<main>
  <div class="hero"><h1><i class="fa-solid fa-robot"></i><span class="grad">AgentCore Chat</span></h1>
    <p>Sign in with your Cognito user, then talk to your agent.</p></div>
  <div class="rule"></div>

  <!-- settings: each attendee fills in their own; kept in this browser only -->
  <details id="cfgBox" class="card">
    <summary><i class="fa-solid fa-gear"></i> Settings</summary>
    <form id="fFind">
      <label>Your initials <span class="hint">Only needed if you share an AWS account. The ones in your resource names, e.g. <code>amg</code> for <code>refund_amg</code></span></label>
      <div class="bar"><input id="initials" placeholder="amg" maxlength="10" autocapitalize="off" spellcheck="false" style="flex:1">
        <button class="primary"><i class="fa-solid fa-magnifying-glass"></i> Find my resources</button></div>
    </form>
    <ul id="found" class="found"></ul>
    <label class="check"><input id="identity" type="checkbox"> Tell the agent who I am <span class="hint">Identity lab, step 12</span></label>
    <details style="margin-top:.8rem"><summary>Enter manually</summary>
    <form id="fCfg">
      <label>User pool ID <span class="hint">Cognito → User pools → your pool. Looks like <code>us-east-1_AbC123xyz</code></span></label>
      <input data-key="user_pool_id" placeholder="us-east-1_AbC123xyz" spellcheck="false">
      <label>App client ID <span class="hint">Cognito → your pool → App clients. 26 letters and numbers</span></label>
      <input data-key="client_id" placeholder="1abc2def3ghi4jkl5mno6pqr7s" spellcheck="false">
      <label>Agent ARN <span class="hint">Bedrock AgentCore → your harness → details. Starts with <code>arn:aws:bedrock-agentcore:</code></span></label>
      <input data-key="agent_arn" placeholder="arn:aws:bedrock-agentcore:us-east-1:123456789012:harness/…" spellcheck="false">
      <label>Gateway URL <span class="hint">Optional, from the gateway lab. Ends in <code>/mcp</code></span></label>
      <input data-key="gateway_url" placeholder="https://…gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp" spellcheck="false">
      <label>System prompt <span class="hint">Optional, from the identity lab. <code>{username}</code> becomes the signed-in user</span></label>
      <textarea data-key="system_prompt" rows="4"></textarea>
      <button class="full">Save</button>
    </form>
    </details>
    <div id="cfgErr"></div>
  </details>

  <section id="vLogin" class="narrow hidden">
    <form id="fLogin" class="card">
      <label>Email</label><input id="user" autocomplete="username" required>
      <label>Password</label><input id="pass" type="password" autocomplete="current-password" required>
      <button class="primary full">Sign in</button>
    </form>
    <form id="fNewPw" class="card hidden">
      <div class="msg info">First login — choose a permanent password.</div>
      <label>New password</label><input id="np1" type="password" autocomplete="new-password" required>
      <label>Repeat new password</label><input id="np2" type="password" autocomplete="new-password" required>
      <button class="primary full">Set password &amp; sign in</button>
    </form>
    <div id="loginErr"></div>
  </section>

  <section id="vApp" class="hidden">
    <div class="bar">
      <div class="who"><i class="fa-regular fa-user"></i><b id="who"></b> · signs out in <span id="left"></span></div>
      <button id="bNew"><i class="fa-regular fa-comment"></i> New chat</button>
      <button id="bOut"><i class="fa-solid fa-right-from-bracket"></i> Sign out</button>
    </div>
    <details class="card" style="margin-top:1rem">
      <summary><i class="fa-solid fa-key"></i> What's inside my token?</summary>
      <p class="muted">The agent verifies the signature via the Discovery URL and checks <code>client_id</code> is in its <b>Allowed clients</b> list.</p>
      <pre id="claims"></pre><pre id="rawTok"></pre>
    </details>

    <div class="tabs">
      <button data-tab="chat" class="on">Chat — through the agent</button>
      <button data-tab="tools">Tools — direct, policy-enforced</button>
    </div>

    <div id="tChat">
      <div id="chat" class="chat"><p class="muted">Ask your agent anything to get started.</p></div>
      <div class="composer"><form id="fChat">
        <input id="prompt" placeholder="Message your agent…" autocomplete="off">
        <button class="primary"><i class="fa-solid fa-paper-plane"></i></button>
      </form></div>
    </div>

    <div id="tTools" class="hidden">
      <div id="toolsNoGw" class="msg info hidden">Add your <b>Gateway URL</b> under Settings to use this tab.</div>
      <div id="toolsUi">
        <p class="muted">Calling the gateway <b>as you</b> (<code id="me"></code>). The policy engine binds
          <code>customer_id</code> to your verified username — try someone else's and watch it refuse.</p>
        <p class="muted">Policy session <code id="psid"></code> — Dogwood rules only see calls made in this session.
          <button id="bPsid" type="button">New session</button></p>
        <button id="bLoad"><i class="fa-solid fa-rotate"></i> Load tools</button>
        <form id="fTool" class="hidden">
          <label>Tool</label><select id="toolSel"></select>
          <div id="toolArgs"></div>
          <button class="primary full">Call tool</button>
        </form>
        <div id="toolOut"></div>
      </div>
    </div>
  </section>
</main>

<script>
const SESSION_MS = 15 * 60 * 1000;   // workshop rule: sign out 15 min after sign-in
const DEFAULTS = {
  region: "us-east-1", user_pool_id: "", client_id: "", agent_arn: "", gateway_url: "", system_prompt: "",
};
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const md = s => DOMPurify.sanitize(marked.parse(s));
const note = (cls, html) => `<div class="msg ${cls}">${html}</div>`;
const newId = () => crypto.randomUUID().replace(/-/g, "") + crypto.randomUUID().replace(/-/g, "");

// tokens live in memory only: a reload signs you out too
// policySid groups Tools-tab calls into one Dogwood policy session (the history temporal policies see)
const S = { token: null, username: "", challenge: null, signedInAt: 0, sessionId: newId(), policySid: newId(), mcpSid: null, tools: [] };

// ---------------------------------------------------------------- config ---
function loadCfg() {
  try { return { ...DEFAULTS, ...JSON.parse(localStorage.getItem("cfg") || "{}") }; } catch { return { ...DEFAULTS }; }
}
let cfg = loadCfg();

function validate(c) {
  const p = [], pool = c.user_pool_id.trim(), client = c.client_id.trim(), arn = c.agent_arn.trim();
  const POOL = /^[a-z]{2}-[a-z]+-\d_[0-9a-zA-Z]+$/, CLIENT = /^[0-9a-z]{20,128}$/,
        ARN = /^arn:aws[\w-]*:bedrock-agentcore:[a-z0-9-]+:\d{12}:(harness\/|runtime\/harness_)[\w-]+$/;
  if (!POOL.test(pool)) p.push(CLIENT.test(pool)
      ? "User pool ID looks like a <b>Client ID</b>. The pool ID contains the region and an underscore, e.g. <code>us-east-1_AbC123xyz</code>."
      : "User pool ID should look like <code>us-east-1_AbC123xyz</code>.");
  else if (!pool.startsWith(c.region + "_")) p.push(`User pool ID starts with a different region than <b>${esc(c.region)}</b>.`);
  if (!CLIENT.test(client)) p.push("Client ID should be ~26 lowercase letters/numbers (no underscore).");
  if (!ARN.test(arn)) p.push("Agent ARN should be your harness ARN, like <code>…:harness/refund_amg-AbC1234567</code>.");
  else if (!arn.includes(`:${c.region}:`)) p.push(`Agent ARN is in a different region than <b>${esc(c.region)}</b>.`);
  return p;
}

// ---- find my resources: the Lambda looks them up by the workshop naming convention
const WORKSHOP_PROMPT = 'You are a customer-service refund assistant. The signed-in customer is "{username}" - Cognito verified that identity. Pass customer_id="{username}" to every tool call. Never ask the customer for their customer id and never use a different one. Use find_orders to list their orders, get_order_transaction for one order\'s details, process_refund to refund a delivered order, and get_refund_status to check a refund. Refunds over $200 are not allowed. Be brief.';
const LABELS = { user_pool_id: "User pool", client_id: "App client", agent_arn: "Agent (harness)", gateway_url: "Gateway (Tools tab)" };

function saveCfg(patch) {
  const saved = JSON.parse(localStorage.getItem("cfg") || "{}");
  localStorage.setItem("cfg", JSON.stringify({ ...saved, ...patch }));
  cfg = loadCfg();
}

async function findResources(quiet) {
  const initials = $("initials").value.trim().toLowerCase();
  localStorage.setItem("initials", initials);
  if (!quiet) $("found").innerHTML = '<li class="muted"><i class="fa-solid fa-spinner fa-spin"></i> Looking…</li>';
  try {
    const r = await fetch("lookup?initials=" + encodeURIComponent(initials)), d = await r.json();
    if (!r.ok) throw new Error(d.error);
    const relogin = ["user_pool_id", "client_id"].some(k => d.found[k] && cfg[k] !== d.found[k]);
    saveCfg(d.found); S.looked = true;
    $("found").innerHTML = Object.entries(LABELS).map(([k, label]) => d.found[k]
        ? `<li class="yes"><i class="fa-solid fa-circle-check"></i> ${label}</li>`
        : `<li class="no"><i class="fa-regular fa-circle"></i> ${label} <span class="muted">— ${esc(d.missing[k])}</span></li>`).join("");
    if (relogin) signOut(); else render();
  } catch (err) { $("found").innerHTML = `<li>${note("err", "Lookup failed: " + esc(err.message))}</li>`; }
}
$("fFind").onsubmit = e => { e.preventDefault(); findResources(false); };
$("identity").onchange = e => { saveCfg({ system_prompt: e.target.checked ? WORKSHOP_PROMPT : "" }); render(); };

const cfgInputs = () => document.querySelectorAll("#fCfg [data-key]");
$("fCfg").onsubmit = e => {
  e.preventDefault();
  const saved = Object.fromEntries([...cfgInputs()].map(i => [i.dataset.key, i.value.trim()]));
  saved.region = saved.user_pool_id.match(/^([a-z]{2}-[a-z]+-\d)_/)?.[1] || DEFAULTS.region;   // the pool ID starts with its region
  localStorage.setItem("cfg", JSON.stringify(saved));
  cfg = loadCfg();
  signOut();
};

// ---------------------------------------------------------------- cognito --
async function cognito(action, body) {
  const r = await fetch(`https://cognito-idp.${cfg.region}.amazonaws.com/`, {
    method: "POST", body: JSON.stringify(body),
    headers: { "Content-Type": "application/x-amz-json-1.1", "X-Amz-Target": `AWSCognitoIdentityProviderService.${action}` },
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(`${data.__type || r.status}: ${data.message || ""}`);
  return data;
}

function decodeJwt(t) {
  try { return JSON.parse(atob(t.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))); } catch { return {}; }
}
const actorId = t => { const c = decodeJwt(t); return c.username || c["cognito:username"] || c.email || c.sub; };

function signedIn(result) {
  S.token = result.AccessToken; S.challenge = null; S.signedInAt = Date.now();
  render();
}

function signOut() {
  Object.assign(S, { token: null, challenge: null, mcpSid: null, tools: [], sessionId: newId(), policySid: newId() });
  $("chat").innerHTML = '<p class="muted">Ask your agent anything to get started.</p>';
  $("toolOut").innerHTML = ""; $("fTool").classList.add("hidden");
  render();
}

// session clock: hard sign-out 15 min after sign-in, or when the token itself expires
setInterval(() => {
  if (!S.token) return;
  const left = Math.min(S.signedInAt + SESSION_MS, decodeJwt(S.token).exp * 1000) - Date.now();
  if (left <= 0) {
    signOut();
    $("loginErr").innerHTML = note("info", "Your 15-minute session ended. Sign in again.");
    return;
  }
  $("left").textContent = `${Math.floor(left / 60000)}:${String(Math.floor(left / 1000) % 60).padStart(2, "0")}`;
}, 1000);

$("fLogin").onsubmit = async e => {
  e.preventDefault();
  const btn = e.submitter; btn.disabled = true; $("loginErr").innerHTML = "";
  S.username = $("user").value.trim();
  try {
    const params = { USERNAME: S.username, PASSWORD: $("pass").value };
    const res = await cognito("InitiateAuth", { AuthFlow: "USER_PASSWORD_AUTH", ClientId: cfg.client_id.trim(), AuthParameters: params });
    if (res.ChallengeName === "NEW_PASSWORD_REQUIRED") { S.challenge = res.Session; render(); }
    else if (res.AuthenticationResult) signedIn(res.AuthenticationResult);
    else $("loginErr").innerHTML = note("err", "Unexpected challenge: " + esc(res.ChallengeName));
  } catch (err) {
    let html = note("err", esc(err.message));
    if (/USER_PASSWORD_AUTH|flow not enabled/i.test(err.message))
      html += note("info", "Enable <b>ALLOW_USER_PASSWORD_AUTH</b> on the app client (Cognito → App clients → Edit → Authentication flows).");
    else if (err.message.includes("SECRET_HASH"))
      html += note("info", "The app client has a secret. Create it as a <b>Single-page application</b> client instead, which has none.");
    $("loginErr").innerHTML = html;
  } finally { btn.disabled = false; $("pass").value = ""; }
};

$("fNewPw").onsubmit = async e => {
  e.preventDefault();
  if ($("np1").value !== $("np2").value) { $("loginErr").innerHTML = note("err", "Passwords don't match."); return; }
  const btn = e.submitter; btn.disabled = true; $("loginErr").innerHTML = "";
  try {
    const resp = { USERNAME: S.username, NEW_PASSWORD: $("np1").value };
    const res = await cognito("RespondToAuthChallenge", { ChallengeName: "NEW_PASSWORD_REQUIRED", ClientId: cfg.client_id.trim(), ChallengeResponses: resp, Session: S.challenge });
    signedIn(res.AuthenticationResult);
  } catch (err) { $("loginErr").innerHTML = note("err", esc(err.message)); }
  finally { btn.disabled = false; $("np1").value = $("np2").value = ""; }
};

$("bOut").onclick = signOut;
$("bNew").onclick = () => { S.sessionId = newId(); $("chat").innerHTML = '<p class="muted">Ask your agent anything to get started.</p>'; };

// ---------------------------------------------------------------- agent ----
function extractText(d) {
  if (typeof d === "string") return d;
  if (Array.isArray(d)) { const p = d.map(extractText).filter(Boolean); return p.length ? p.join("") : null; }
  if (d && typeof d === "object") {
    // harness streams events like {"contentBlockDelta": {"delta": {"text": "..."}}}
    for (const k of ["result","response","output","answer","text","message","content","completion","contentBlockDelta","delta"])
      if (k in d) { const f = extractText(d[k]); if (f) return f; }
  }
  return null;
}

// The console also shows a …:runtime/harness_<id> ARN for the same harness; accept it and use …:harness/<id>.
function harnessUrl() {
  const arn = cfg.agent_arn.trim().replace(":runtime/harness_", ":harness/");
  return `https://bedrock-agentcore.${cfg.region}.amazonaws.com/harnesses/invoke?harnessArn=${encodeURIComponent(arn)}`;
}

// AWS binary event-stream frame: [4B total][4B headers len][4B prelude crc][headers][payload][4B crc]
function* eventStream(buf) {
  const v = new DataView(buf);
  for (let i = 0; i + 16 <= buf.byteLength;) {
    const total = v.getUint32(i), hdr = v.getUint32(i + 4);
    if (total < 16 || i + total > buf.byteLength) break;
    yield new Uint8Array(buf, i + 12 + hdr, total - 16 - hdr);
    i += total;
  }
}

async function invokeAgent(message) {
  const body = { messages: [{ role: "user", content: [{ text: message }] }] };
  const actor = actorId(S.token);
  if (actor) {
    body.actorId = actor;   // partition Memory by the signed-in user
    // The harness can't see the caller's claims, so the app tells the model who it verified.
    // A convenience, NOT a security boundary — that lives in the gateway's Cedar policies (Tools tab).
    if (cfg.system_prompt) body.systemPrompt = [{ text: cfg.system_prompt.replaceAll("{username}", actor) }];
  }
  const r = await fetch(harnessUrl(), { method: "POST", body: JSON.stringify(body), headers: {
    Authorization: `Bearer ${S.token}`, "Content-Type": "application/json",
    "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": S.sessionId,
  }});
  const ctype = r.headers.get("content-type") || "";
  const chunks = [], raw = [];
  if (ctype.includes("vnd.amazon.eventstream")) {
    const dec = new TextDecoder();
    for (const p of eventStream(await r.arrayBuffer())) {
      try { const o = JSON.parse(dec.decode(p)); raw.push(JSON.stringify(o)); const t = extractText(o); if (t) chunks.push(t); } catch {}
    }
    return [r.status, chunks.join(""), raw.join("\n")];
  }
  const text = await r.text();   // errors come back as plain JSON
  try { return [r.status, extractText(JSON.parse(text)) || text, text]; } catch { return [r.status, text, text]; }
}

function explainError(status, raw) {
  const hints = {
    401: "The agent rejected the token. Check the agent's **Inbound auth**: the Discovery URL must be `https://cognito-idp." + cfg.region + ".amazonaws.com/" + cfg.user_pool_id.trim() + "/.well-known/openid-configuration`, and **Allowed clients** must contain your Client ID.",
    403: "Access denied. The agent may still be set to **IAM** auth, or your token's client isn't in **Allowed clients**.",
    404: "Agent not found. Check the harness ARN on its details page in the console, and the region.",
    400: "Bad request. The harness rejected the message; the raw response below says why.",
    424: "The agent itself failed. Check its logs in CloudWatch.",
    500: "The agent itself failed. Check its logs in CloudWatch.",
  };
  return `**HTTP ${status}.** ${hints[status] || "Unexpected error."}\n\n\`\`\`\n${raw.slice(0, 1500)}\n\`\`\``;
}

function addMsg(role, html) {
  const chat = $("chat"); chat.querySelector("p.muted")?.remove();
  const el = document.createElement("div");
  el.className = "m " + role;
  el.innerHTML = `<i class="fa-solid ${role === "user" ? "fa-user" : "fa-robot"}"></i><div class="body">${html}</div>`;
  chat.append(el); el.scrollIntoView({ block: "end" });
  return el.querySelector(".body");
}

$("fChat").onsubmit = async e => {
  e.preventDefault();
  const prompt = $("prompt").value.trim(); if (!prompt || !S.token) return;
  $("prompt").value = ""; const btn = e.submitter; btn.disabled = true;
  addMsg("user", esc(prompt).replace(/\n/g, "<br>"));
  const out = addMsg("assistant", '<span class="muted"><i class="fa-solid fa-spinner fa-spin"></i> Thinking…</span>');
  try {
    const [status, text, raw] = await invokeAgent(prompt);
    const reply = status === 200 ? text : explainError(status, raw);
    out.innerHTML = md(reply) + (raw && raw !== reply ? `<details><summary>Raw response</summary><pre>${esc(raw.slice(0, 5000))}</pre></details>` : "");
  } catch (err) {
    out.innerHTML = md(`**Could not reach the agent.** ${err.message}`);
  } finally { btn.disabled = false; out.scrollIntoView({ block: "end" }); }
};

// ---------------------------------------------------------------- mcp -----
// The Tools tab talks to the JWT-authorized gateway directly, with YOUR token, so the gateway
// sees you as AgentCore::OAuthUser and Cedar can bind customer_id to your verified username.
// Goes through this Lambda's /mcp, which forwards to the gateway: a browser may not send the
// policy session header that Dogwood (temporal) policies need.
async function mcpPost(payload, retried) {
  const headers = { Authorization: `Bearer ${S.token}`, "Content-Type": "application/json",
    Accept: "application/json, text/event-stream",
    // Without this header the gateway assumes MCP 2025-03-26 and rejects every call with -32022.
    "MCP-Protocol-Version": "2025-11-25",
    "X-Gateway-Url": cfg.gateway_url.trim(),
    "x-amzn-bedrock-agentcore-policy-session-id": S.policySid };
  if (S.mcpSid && S.mcpSid !== "-") headers["Mcp-Session-Id"] = S.mcpSid;
  const r = await fetch("mcp", { method: "POST", headers, body: JSON.stringify(payload) });
  if (!S.mcpSid) S.mcpSid = r.headers.get("Mcp-Session-Id") || null;
  let body = await r.text();
  // Adding or changing a temporal policy ends open policy sessions (409): start a fresh one and retry once.
  if (r.status === 409 && !retried) { newPolicySession(); return mcpPost(payload, true); }
  if (!("id" in payload)) return {};
  if ((r.headers.get("content-type") || "").includes("text/event-stream"))
    body = body.split("\n").filter(l => l.startsWith("data:")).map(l => l.slice(5).trim()).join("");
  try { return JSON.parse(body); } catch { return { error: { code: r.status, message: body.slice(0, 2000) } }; }
}

async function mcpRpc(method, params) {
  if (!S.mcpSid) {
    await mcpPost({ jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2025-11-25", capabilities: {},
      clientInfo: { name: "agentcore-workshop-tester", version: "1.0" } } });
    await mcpPost({ jsonrpc: "2.0", method: "notifications/initialized" });
    S.mcpSid ||= "-";   // "-" = stateless, no id
  }
  return mcpPost({ jsonrpc: "2.0", id: 2, method, ...(params ? { params } : {}) });
}

function unwrapToolResult(result) {   // MCP content -> Lambda {statusCode, body} -> {"result": ...}
  try {
    let d = JSON.parse(result.content[0].text);
    if (typeof d.body === "string") d = JSON.parse(d.body);
    return d.result ?? d;
  } catch { return result; }
}

async function loadTools() {
  $("toolOut").innerHTML = '<p class="muted"><i class="fa-solid fa-spinner fa-spin"></i> Listing tools…</p>';
  $("fTool").classList.add("hidden"); S.mcpSid = null;
  try { S.tools = (await mcpRpc("tools/list")).result?.tools || []; }
  catch (err) { S.tools = []; $("toolOut").innerHTML = note("err", "Could not reach the gateway. " + esc(err.message)); return; }
  if (!S.tools.length) { $("toolOut").innerHTML = note("err", "No tools returned. Check the gateway URL, and that its target is READY."); return; }
  $("toolOut").innerHTML = "";
  $("toolSel").innerHTML = S.tools.map(t => `<option${t.name === "orders___find_orders" ? " selected" : ""}>${esc(t.name)}</option>`).join("");
  $("fTool").classList.remove("hidden"); renderArgs();
}

function renderArgs() {
  const schema = S.tools.find(t => t.name === $("toolSel").value)?.inputSchema || {};
  const req = new Set(schema.required || []), me = actorId(S.token) || S.username;
  $("toolArgs").innerHTML = Object.entries(schema.properties || {}).map(([k, spec]) => {
    const num = spec.type === "number";
    return `<label title="${esc(spec.description || "")}">${esc(k)}${req.has(k) ? " *" : ""}</label>
      <input name="${esc(k)}" ${num ? 'type="number" step="1" min="0" value="49"' : `value="${k === "customer_id" ? esc(me) : ""}"`}
        data-num="${num}" placeholder="${esc(spec.description || "")}">`;
  }).join("");
}

function newPolicySession() { S.policySid = newId(); $("psid").textContent = S.policySid.slice(0, 8) + "…"; }
$("bLoad").onclick = loadTools;
$("bPsid").onclick = () => { newPolicySession(); $("toolOut").innerHTML = note("info", "New policy session: Dogwood rules start with an empty history."); };
$("toolSel").onchange = renderArgs;
$("fTool").onsubmit = async e => {
  e.preventDefault();
  const btn = e.submitter; btn.disabled = true;
  const args = {};
  for (const i of $("toolArgs").querySelectorAll("input")) if (i.value !== "") args[i.name] = i.dataset.num === "true" ? Number(i.value) : i.value;
  let resp;
  try { resp = await mcpRpc("tools/call", { name: $("toolSel").value, arguments: args }); }
  catch (err) { resp = { error: { message: err.message } }; }
  finally { btn.disabled = false; }
  const result = resp.result || {}, error = resp.error || {};
  $("toolOut").innerHTML = (error.message || result.isError
      ? note("err", "<b>DENIED</b> — the policy engine refused this call.") + (error.message ? `<pre>${esc(error.message)}</pre>` : "")
      : note("ok", "<b>ALLOWED</b>") + `<pre>${esc(JSON.stringify(unwrapToolResult(result), null, 2))}</pre>`)
    + `<details><summary>Raw JSON-RPC</summary><pre>${esc(JSON.stringify(resp, null, 2).slice(0, 5000))}</pre></details>`;
};

// ---------------------------------------------------------------- tabs / render
document.querySelectorAll(".tabs button").forEach(b => b.onclick = () => {
  document.querySelectorAll(".tabs button").forEach(x => x.classList.toggle("on", x === b));
  $("tChat").classList.toggle("hidden", b.dataset.tab !== "chat");
  $("tTools").classList.toggle("hidden", b.dataset.tab !== "tools");
  if (b.dataset.tab === "tools" && cfg.gateway_url.trim() && !S.tools.length) loadTools();
});

function render() {
  const problems = validate(cfg);
  cfgInputs().forEach(i => i.value = cfg[i.dataset.key] ?? "");
  $("identity").checked = !!cfg.system_prompt;
  $("cfgBox").open = problems.length > 0;
  const fresh = !localStorage.getItem("cfg");   // first visit: nothing entered yet, so welcome rather than scold
  $("cfgErr").innerHTML = !problems.length ? ""
    : fresh || S.looked ? note("info", "Your resources show up here as you build them in the labs. Press <b>Find my resources</b> to check again.")
    : note("err", "Almost there. Check these settings:<ul>" + problems.map(p => `<li>${p}</li>`).join("") + "</ul>");
  $("vLogin").classList.toggle("hidden", problems.length > 0 || !!S.token);
  $("fLogin").classList.toggle("hidden", !!S.challenge);
  $("fNewPw").classList.toggle("hidden", !S.challenge);
  $("vApp").classList.toggle("hidden", problems.length > 0 || !S.token);
  if (S.token) {
    const c = decodeJwt(S.token);
    $("who").textContent = S.username; $("me").textContent = actorId(S.token) || S.username;
    $("claims").textContent = JSON.stringify(Object.fromEntries(["iss","client_id","sub","username","token_use","scope","exp"].map(k => [k, c[k] ?? null])), null, 2);
    $("rawTok").textContent = S.token;
    $("psid").textContent = S.policySid.slice(0, 8) + "…";
    $("toolsNoGw").classList.toggle("hidden", !!cfg.gateway_url.trim());
    $("toolsUi").classList.toggle("hidden", !cfg.gateway_url.trim());
    $("loginErr").innerHTML = "";
  }
}
$("initials").value = localStorage.getItem("initials") || "";
render();
findResources(true);   // re-check on every visit, so resources made in later labs show up by themselves
</script>
</body>
</html>
'''


if __name__ == "__main__":  # self-check of paging + picking, no AWS needed
    pages = iter([{"Items": [{"Name": "a"}], "Next": "t"}, {"Items": [{"Name": "Refund-Pool-AMG"}]}])
    items = list(_pages(lambda **kw: next(pages), "Items", "Next", "Next"))
    assert _pick(items, "Name", "refund-pool-amg", "amg") == ({"Name": "Refund-Pool-AMG"}, None)
    assert _pick(items, "Name", "refund-pool-xyz", "xyz") == (None, "no refund-pool-xyz yet")
    assert _pick(items, "Name", "refund-pool-", "") == (None, "2 found, type your initials to choose")
    assert _pick(items[:1], "Name", "refund-pool-", "") == ({"Name": "a"}, None)
    assert _pick([], "Name", "refund-pool-", "") == (None, "none yet")
    assert GATEWAY_URL.fullmatch("https://refund-gw-abc123.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp")
    assert not GATEWAY_URL.fullmatch("https://evil.example.com/mcp")
    assert not GATEWAY_URL.fullmatch("https://x.gateway.bedrock-agentcore.us-east-1.amazonaws.com.evil.com/mcp")
    assert mcp_forward({"headers": {"x-gateway-url": "https://evil.example.com/mcp"}})["statusCode"] == 400
    print("ok")
