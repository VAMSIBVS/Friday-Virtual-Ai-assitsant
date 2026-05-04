"""
Friday's Memory — Conversation history manager using SQLite.
Stores all interactions locally for context continuity.
"""

import sqlite3
import os
import json
from datetime import datetime
import config


class MemoryStore:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(config.MEMORY_DIR, "friday_memory.db")
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts       TEXT    NOT NULL,
                    role     TEXT    NOT NULL,
                    content  TEXT    NOT NULL,
                    session  TEXT    NOT NULL
                )
            """)
            conn.commit()

    def save(self, role: str, content: str, session_id: str):
        """Persist a single message."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO conversations (ts, role, content, session) VALUES (?, ?, ?, ?)",
                (datetime.utcnow().isoformat(), role, content, session_id),
            )
            conn.commit()

    def get_recent(self, n: int = 10, session_id: str = None) -> list[dict]:
        """
        Retrieve the last N messages as a list of {role, content} dicts.
        Suitable for injecting directly into the LLM messages array.
        """
        with sqlite3.connect(self.db_path) as conn:
            if session_id:
                rows = conn.execute(
                    "SELECT role, content FROM conversations "
                    "WHERE session = ? ORDER BY id DESC LIMIT ?",
                    (session_id, n),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT role, content FROM conversations ORDER BY id DESC LIMIT ?",
                    (n,),
                ).fetchall()

        # Reverse so oldest is first (correct LLM order)
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

    def clear_session(self, session_id: str):
        """Delete all messages for a given session."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM conversations WHERE session = ?", (session_id,))
            conn.commit()

    def get_session_summary(self, session_id: str) -> str:
        """Return raw text of a session for summarization."""
        msgs = self.get_recent(n=100, session_id=session_id)
        lines = [f"{m['role'].upper()}: {m['content']}" for m in msgs]
        return "\n".join(lines)
