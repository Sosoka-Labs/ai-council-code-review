"""Test file for AI Council pipeline end-to-end test.

This file contains deliberate security issues for the agents to find.
"""

from __future__ import annotations

import pickle


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
