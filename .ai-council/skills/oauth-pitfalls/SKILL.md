---
name: oauth-pitfalls
description: Use when reviewing OAuth 2.0 flows, token handling, or PKCE implementations. Covers common pitfalls in authorization code flow, client credentials, refresh token rotation, and JWT validation. Apply any time auth/, oauth/, token, or session-related files appear in the diff.
---
# OAuth Pitfalls

Security review guidance for OAuth 2.0 flows, token handling, and related authentication code.

---

## 1. Missing or unvalidated `state` parameter

**What to check:** Every authorization request must generate a cryptographically random `state` value, store it in the session before redirecting, and verify it exactly on the callback. Look for missing generation, predictable values (timestamps, UUIDs v4 are fine; sequential integers are not), or callbacks that accept any incoming `state` without comparison.

**Why it matters:** Without `state` validation the flow is vulnerable to CSRF — an attacker can craft a link that completes authorization under the victim's session, binding the victim's account to the attacker's tokens.

---

## 2. Redirect URI not strictly allowlisted

**What to check:** Confirm that the authorization server (or the client's own callback handler) validates `redirect_uri` against an exact allowlist, not a prefix or domain-match. Check for open redirect vectors in the callback route itself (e.g., `next=` parameters that accept arbitrary URLs).

**Why it matters:** A loose redirect_uri match lets an attacker steal the authorization code by pointing `redirect_uri` to a controlled domain. The authorization server delivers the code to the attacker, who exchanges it for tokens.

---

## 3. Accepting `alg: none` in JWT validation

**What to check:** Verify that JWT validation rejects tokens with `alg: none` or an empty algorithm. Also check that the validator does not trust the `alg` header to select the verification key — it should enforce the expected algorithm (e.g., RS256) regardless of what the token claims.

**Why it matters:** Libraries that trust the `alg` header allow an attacker to forge tokens by stripping the signature and setting `alg: none`. Downgrade to HS256 is a related variant when the server's RS256 public key is used as an HMAC secret.

---

## 4. JWT claims not validated (exp, iss, aud)

**What to check:** After signature verification, confirm that `exp` (expiration) is checked against current time, `iss` (issuer) is compared to the expected authorization server URL, and `aud` (audience) is compared to the client ID or resource identifier. Missing any one of these is a separate finding.

**Why it matters:** A valid signature proves the token was issued by someone with the private key — it says nothing about whether the token is expired, came from the right issuer, or was intended for this service. Accepting tokens from a different audience enables token substitution attacks.

---

## 5. Authorization code not single-use / no PKCE on public clients

**What to check:** For public clients (SPAs, mobile apps), confirm PKCE (`code_challenge` / `code_verifier`) is used on every authorization request. For confidential clients, confirm codes are invalidated after first use and short-lived (< 5 minutes). Look for authorization code exchanges that don't include or verify `code_verifier`.

**Why it matters:** PKCE binds a specific exchange to the original authorization request, preventing code interception attacks where an attacker intercepts the authorization code (e.g., via a malicious redirect or referrer header) and races to exchange it.

---

## 6. Refresh token rotation not enforced

**What to check:** When a refresh token is used to obtain a new access token, confirm the old refresh token is immediately invalidated. Check that if the same refresh token is presented twice (replay), both the replayed request and any previously issued tokens from that lineage are revoked (rotation with reuse detection).

**Why it matters:** Without rotation, a stolen refresh token gives an attacker indefinite access. Without reuse detection, an attacker can silently drain a compromised token without alerting the legitimate client's eventual failure.

---

## 7. Tokens stored in `localStorage` or exposed to JavaScript

**What to check:** In frontend code, look for access tokens or refresh tokens written to `localStorage` or `sessionStorage`. Prefer `httpOnly` cookies for refresh tokens. Also check that tokens are not embedded in URLs, query parameters, or log statements.

**Why it matters:** `localStorage` is accessible to any JavaScript on the page, including injected scripts via XSS. A single XSS vulnerability in any third-party script becomes a full token exfiltration.

---

## 8. Client secret hardcoded or committed

**What to check:** Scan for `client_secret`, OAuth credentials, or API keys stored in source files, configuration checked into version control, or environment variable defaults that look like real secrets. Also check that `client_credentials` flows are only used server-side, never in browser or mobile code.

**Why it matters:** A hardcoded or committed secret is immediately extractable by anyone with repository read access, including past contributors and users of public forks. Rotation is the only remediation after exposure.
