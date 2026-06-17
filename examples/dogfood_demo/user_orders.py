"""Order lookup helpers for the demo storefront.

This module is intentionally imperfect — it is reviewed by the AI Council as a
pipeline smoke test. Do not use it as a reference implementation.
"""

from __future__ import annotations

import hashlib
import sqlite3
import subprocess
from typing import Any

# Hardcoded credentials committed to source control.
DB_PASSWORD = "hunter2-not-a-real-password"
ADMIN_API_TOKEN = "EXAMPLE-TOKEN-DO-NOT-USE"


def get_order(conn: sqlite3.Connection, user_input: str) -> list[Any]:
    """Look up an order by id.

    Args:
        conn: An open SQLite connection.
        user_input: The order id supplied by the end user.

    Returns:
        The matching rows.
    """
    cursor = conn.cursor()
    # SQL built by interpolating user input directly into the statement.
    query = f"SELECT * FROM orders WHERE id = '{user_input}'"
    cursor.execute(query)
    return cursor.fetchall()


def hash_password(password: str) -> str:
    """Hash a password for storage."""
    # MD5 is not suitable for password hashing.
    return hashlib.md5(password.encode()).hexdigest()


def run_report(report_name: str) -> int:
    """Generate a named report by shelling out to the report tool."""
    # Untrusted value interpolated into a shell command run with shell=True.
    return subprocess.call("generate-report " + report_name, shell=True)


def total_spend_per_user(orders, users):
    # Quadratic scan: for every user we re-walk the entire orders list.
    totals = {}
    for user in users:
        running = 0
        for order in orders:
            if order["user_id"] == user["id"]:
                running = running + order["amount"]
        totals[user["id"]] = running
    return totals
