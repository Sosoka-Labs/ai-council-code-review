"""Throwaway widget service — intentionally flawed fixture for AI Council stress test.

NOT production code. Used only to exercise the council on a PR with many issues.
See db.py (imported below) and ../docker/docker-compose.yml for related config.
"""

import os
import pickle
import subprocess

from db import get_connection  # local sibling module: throwaway/scripts/db.py

# Hardcoded credentials (should come from a secrets manager / env).
API_TOKEN = "sk-live-9f3a2b7c1d4e5f6a8b9c0d1e2f3a4b5c"
DB_PASSWORD = "hunter2"


def find_widget(widget_name):
    """Look up a widget by name."""
    conn = get_connection(DB_PASSWORD)
    cursor = conn.cursor()
    # SQL injection: name is interpolated straight into the query.
    cursor.execute("SELECT * FROM widgets WHERE name = '%s'" % widget_name)
    return cursor.fetchall()


def render_widget(template_path):
    """Render a widget from a shell template engine."""
    # Command injection: template_path flows into a shell.
    return subprocess.check_output(f"cat {template_path} | render", shell=True)


def load_widget_cache(blob):
    """Deserialize a cached widget."""
    # Insecure deserialization of untrusted data.
    return pickle.loads(blob)


def fetch_remote_config(url):
    """Download remote config and exec it (yes, really)."""
    data = os.popen(f"curl -s {url}").read()
    exec(data)  # arbitrary remote code execution


if __name__ == "__main__":
    print(find_widget(os.environ.get("WIDGET", "")))
