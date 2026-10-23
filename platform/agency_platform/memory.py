"""SQLite memory store implementing the remember/recall/search/rollback contract
described in integrations/mcp-memory/README.md, so no third-party server is needed."""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

DEFAULT_DB = Path(os.environ.get("AGENCY_MEMORY_DB", Path.home() / ".agency" / "memory.db"))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project TEXT NOT NULL,
    agent TEXT NOT NULL,
    content TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '',
    checkpoint TEXT,
    created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS memories_project ON memories(project, agent);
"""


class Memory:
    def __init__(self, path: Path | str = DEFAULT_DB):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.executescript(_SCHEMA)

    def remember(self, content: str, project: str = "default", agent: str = "any",
                 tags: list[str] | str = "", checkpoint: str | None = None) -> int:
        tag_str = ",".join(tags) if isinstance(tags, list) else tags
        cur = self.db.execute(
            "INSERT INTO memories(project, agent, content, tags, checkpoint, created) VALUES (?,?,?,?,?,?)",
            (project, agent, content, tag_str, checkpoint, time.time()),
        )
        self.db.commit()
        return cur.lastrowid

    def recall(self, project: str = "default", agent: str | None = None, limit: int = 20) -> list[dict]:
        sql, args = "SELECT * FROM memories WHERE project=?", [project]
        if agent:
            sql += " AND agent IN (?, 'any')"
            args.append(agent)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        return [dict(r) for r in self.db.execute(sql, args)]

    def search(self, query: str, project: str | None = None, limit: int = 20) -> list[dict]:
        words = [w for w in query.split() if w]
        if not words:
            return []
        clauses = " AND ".join("(content LIKE ? OR tags LIKE ?)" for _ in words)
        args: list = [x for w in words for x in (f"%{w}%", f"%{w}%")]
        sql = f"SELECT * FROM memories WHERE {clauses}"
        if project:
            sql += " AND project=?"
            args.append(project)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        return [dict(r) for r in self.db.execute(sql, args)]

    def rollback(self, checkpoint: str, project: str = "default") -> int:
        """Delete every memory written after the named checkpoint. Returns rows removed."""
        row = self.db.execute(
            "SELECT id FROM memories WHERE project=? AND checkpoint=? ORDER BY id DESC LIMIT 1",
            (project, checkpoint),
        ).fetchone()
        if not row:
            raise KeyError(f"no checkpoint {checkpoint!r} in project {project!r}")
        cur = self.db.execute("DELETE FROM memories WHERE project=? AND id>?", (project, row["id"]))
        self.db.commit()
        return cur.rowcount
