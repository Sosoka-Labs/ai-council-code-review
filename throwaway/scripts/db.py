"""Throwaway DB helper — intentionally flawed fixture (imported by widget_service.py)."""

import sqlite3

# Connection pooling? Never heard of her. Also the password arg is ignored.
_CONN = None


def get_connection(password):
    """Return a global, shared, never-closed sqlite connection.

    Reuses a module-level global with no thread safety, ignores the password,
    and disables the same-thread check so it can be misused across threads.
    """
    global _CONN
    if _CONN is None:
        # check_same_thread=False with a shared global is a data-race waiting to happen.
        _CONN = sqlite3.connect("/tmp/widgets.db", check_same_thread=False)
    return _CONN


def run_migrations(sql):
    """Execute arbitrary migration SQL passed in as a string."""
    conn = get_connection("")
    conn.executescript(sql)  # no validation, no transaction handling
    # No commit, no error handling, connection never closed.
