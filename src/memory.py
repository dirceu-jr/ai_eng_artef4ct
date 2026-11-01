"""Persistência de histórico de conversas em SQLite e exportação estruturada para Markdown."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any

from src.config import MEMORY_DB_PATH


class ConversationMemory:
    """Gerencia sessões de atendimento e mensagens persistidas em SQLite."""

    def __init__(self, db_path: Path = MEMORY_DB_PATH) -> None:
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._connect()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                tool_calls_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            );
            """
        )
        conn.commit()
        conn.close()

    def ensure_session(self, session_id: str, title: str = "Atendimento Empório da Música") -> None:
        now = datetime.now(timezone.utc).isoformat()
        conn = self._connect()
        row = conn.execute("SELECT session_id FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO sessions (session_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (session_id, title, now, now),
            )
            conn.commit()
        conn.close()

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
        title: str | None = None,
    ) -> None:
        self.ensure_session(session_id, title=title or f"Sessão {session_id}")
        now = datetime.now(timezone.utc).isoformat()
        tc_json = json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None
        conn = self._connect()
        conn.execute(
            "INSERT INTO messages (session_id, role, content, tool_calls_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, tc_json, now),
        )
        conn.execute("UPDATE sessions SET updated_at = ? WHERE session_id = ?", (now, session_id))
        conn.commit()
        conn.close()

    def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT id, role, content, tool_calls_json, created_at FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
        conn.close()
        result: list[dict[str, Any]] = []
        for r in rows:
            tcs = json.loads(r["tool_calls_json"]) if r["tool_calls_json"] else []
            result.append(
                {
                    "id": r["id"],
                    "role": r["role"],
                    "content": r["content"],
                    "tool_calls": tcs,
                    "created_at": r["created_at"],
                }
            )
        return result

    def clear_session(self, session_id: str) -> None:
        conn = self._connect()
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()

    def list_sessions(self) -> list[dict[str, Any]]:
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT s.session_id, s.title, s.created_at, s.updated_at, COUNT(m.id) AS message_count
            FROM sessions s
            LEFT JOIN messages m ON m.session_id = s.session_id
            GROUP BY s.session_id
            ORDER BY s.updated_at DESC
            """
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def export_session_markdown(self, session_id: str, scenario_title: str | None = None) -> str:
        """Exporta uma sessão de conversa completa em formato Markdown legível com rastreio de tools."""
        messages = self.get_messages(session_id)
        header = scenario_title or f"Exemplo de Atendimento — Sessão `{session_id}`"
        lines: list[str] = [f"# {header}", ""]

        for msg in messages:
            if msg["role"] == "user":
                lines.append(f"### 👤 Cliente\n\n{msg['content']}\n")
            else:
                if msg["tool_calls"]:
                    lines.append("<details>")
                    lines.append(
                        f"<summary>🔧 <b>Ferramentas consultadas pelo Agente ({len(msg['tool_calls'])})</b></summary>\n"
                    )
                    for tc in msg["tool_calls"]:
                        args_str = json.dumps(tc.get("args", {}), ensure_ascii=False)
                        lines.append(f"- **`{tc.get('name')}`** — Argumentos: `{args_str}`")
                    lines.append("\n</details>\n")
                lines.append(f"### 🎸 Assistente Empório da Música\n\n{msg['content']}\n")
            lines.append("---\n")

        return "\n".join(lines).strip() + "\n"
