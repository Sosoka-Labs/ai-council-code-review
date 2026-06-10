"""Test file for AI Council pipeline end-to-end test.

This file contains deliberate security issues for the agents to find.
DO NOT USE THIS CODE IN PRODUCTION.
"""

from __future__ import annotations

import pickle  # noqa: I001
import sys  # noqa: F401

# Security issue 1: Hardcoded secret
AWS_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"  # type: ignore[var-name]
API_SECRET = "sk-12345-deadbeef-secret-leak"  # type: ignore[var-name]


# Security issue 2: SQL injection
def get_user_by_id(user_input: str) -> str:
    """Retrieve user by ID — vulnerable to SQL injection."""
    query = f"SELECT * FROM users WHERE id = {user_input}"
    return query


# Security issue 3: Unsafe deserialization
def load_user_data(data: bytes) -> object:
    """Load user data from untrusted source — pickle RCE risk."""
    return pickle.loads(data)  # type: ignore[return-value]


# Security issue 4: Command injection via os.system
def run_report(filename: str) -> None:
    """Run a report — vulnerable to command injection."""
    import os

    os.system(f"cat {filename}")  # type: ignore[arg-type]


# Quality issue 1: Missing type hints and error handling
def process_data(data):  # type: ignore[no-untyped-def]
    """Process data without type hints or validation."""
    result = data.split(",")
    return result[0]


# Quality issue 2: Deep nesting and magic numbers
def calculate_score(values):  # type: ignore[no-untyped-def]
    """Calculate score with poor structure."""
    score = 0
    if values:
        for v in values:
            if v > 0:
                if v > 10:
                    score += 42
                elif v > 5:
                    score += 7
                else:
                    score += 1
    return score


# Quality issue 3: Unused import and dead code
_UNUSED_VAR = "this is never used"


def unused_function():  # type: ignore[no-untyped-def]
    """This function is never called."""
    pass


# ── New planted issues (added for OpenAI pipeline test) ─────────────────────


# Security issue 5: Path traversal — user-controlled path joined without validation
def read_user_file(username: str) -> str:
    """Return contents of a user's profile file."""
    import os

    base_dir = "/var/app/profiles"
    path = os.path.join(base_dir, username, "profile.txt")  # type: ignore[arg-type]
    with open(path) as f:  # noqa: PTH123
        return f.read()
    # username="../../../etc/passwd" walks out of base_dir


# Security issue 6: Insecure PRNG used for security-sensitive token generation
def generate_session_token(user_id: int) -> str:
    """Generate a session token for the given user."""
    import random  # noqa: S311

    token = f"{user_id}-{random.randint(0, 999999):06d}"  # type: ignore[call-overload]
    return token
    # random.randint is not cryptographically secure; use secrets.token_hex instead


# Security issue 7: SSRF — outbound HTTP request to a user-supplied URL
def fetch_user_avatar(avatar_url: str) -> bytes:
    """Fetch the user's avatar image from the provided URL."""
    import urllib.request

    with urllib.request.urlopen(avatar_url) as resp:  # noqa: S310  # type: ignore[arg-type]
        return resp.read()
    # avatar_url is untrusted; an attacker can supply http://169.254.169.254/latest/meta-data/
