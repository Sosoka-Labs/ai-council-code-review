"""E2E dogfood for the oauth-pitfalls skill.

This file deliberately commits OAuth 2.0 / OIDC code that violates the patterns
documented in .ai-council/skills/oauth-pitfalls/SKILL.md. It exists to verify
the security agent actually receives the bound skill at review time: each issue
below maps to a numbered pitfall in the SKILL.md so we can confirm the agent's
review references skill-specific language (state, PKCE, alg=none, claim
validation, redirect_uri allowlisting).

DO NOT USE THIS CODE IN PRODUCTION.
"""

from __future__ import annotations

import base64
import json
from typing import Any
from urllib.parse import urlencode

# Pitfall 8: Hardcoded client secret committed to the repo.
OAUTH_CLIENT_SECRET = "s3cr3t-do-not-commit-me"  # type: ignore[var-name]
OAUTH_CLIENT_ID = "ai-council-demo-client"


# Pitfall 1: Missing `state` parameter on authorization redirect.
# Pitfall 5: No PKCE code_challenge sent from a public client.
def build_authorize_url(redirect_uri: str) -> str:
    """Build an authorization URL — no state, no PKCE."""
    params = {
        "response_type": "code",
        "client_id": OAUTH_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": "openid profile email",
    }
    return f"https://idp.example.com/authorize?{urlencode(params)}"


# Pitfall 2: Redirect URI is matched with `startswith`, not an exact allowlist.
# An attacker registers https://app.example.com.attacker.com and wins.
ALLOWED_REDIRECTS = ("https://app.example.com",)


def is_allowed_redirect(uri: str) -> bool:
    """Loose redirect URI check."""
    return any(uri.startswith(allowed) for allowed in ALLOWED_REDIRECTS)


# Pitfall 3: Accepts `alg: none` JWTs by parsing the header without validation.
# Pitfall 4: Never checks exp, iss, or aud claims.
def verify_id_token(token: str) -> dict[str, Any]:
    """'Verify' an ID token by base64-decoding its parts. No signature check."""
    header_b64, payload_b64, _sig_b64 = token.split(".")
    header = json.loads(base64.urlsafe_b64decode(header_b64 + "=="))
    payload: dict[str, Any] = json.loads(base64.urlsafe_b64decode(payload_b64 + "=="))
    if header.get("alg") == "none":
        # Cheap path — trust it.
        return payload
    # Otherwise trust it anyway. No JWKS lookup, no signature verification,
    # no exp/iss/aud checks.
    return payload


# Pitfall 6: Refresh token "rotation" that re-uses the same token forever
# and never detects replay.
class RefreshTokenStore:
    """In-memory store that never rotates."""

    def __init__(self) -> None:
        self._issued: dict[str, str] = {}

    def issue(self, user_id: str) -> str:
        """Issue a refresh token and reuse it on every subsequent call."""
        if user_id not in self._issued:
            self._issued[user_id] = f"rt_{user_id}_static"
        return self._issued[user_id]

    def exchange(self, refresh_token: str) -> str:
        """Hand back a new access token without invalidating the refresh token."""
        return f"at_{refresh_token}_new"
