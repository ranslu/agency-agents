"""Model Context Protocol server (stdio, JSON-RPC 2.0) for The Agency.

Exposes every agent as an MCP *prompt* (so clients list them as slash commands) and
offers tools to search the roster, build teams, read runbooks, score quality, and use
persistent project memory.

Register with Claude Code:
    claude mcp add agency -- python3 /path/to/agency-agents/platform/agency.py mcp
"""

from __future__ import annotations

import json
import sys
from typing import Any

from . import __version__
from .corpus import by_slug, load_runbooks
from .memory import Memory
from .quality import score_agent
from .search import Index

PROTOCOL_VERSION = "2025-06-18"


def _schema(props: dict[str, tuple[str, str]], required: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {k: {"type": t, "description": d} for k, (t, d) in props.items()},
        "required": required,
    }


TOOLS = [
    ("search_agents", "Find agents whose expertise matches a query.",
     _schema({"query": ("string", "What you need help with"), "limit": ("integer", "Max results (default 8)"),
              "division": ("string", "Restrict to one division, e.g. engineering")}, ["query"])),
    ("get_agent", "Return an agent's full system prompt and metadata by slug.",
     _schema({"slug": ("string", "Agent slug, e.g. engineering-frontend-developer")}, ["slug"])),
    ("recommend_team", "Assemble a cross-functional team for a task.",
     _schema({"task": ("string", "Project or task description"), "size": ("integer", "Team size (default 5)")}, ["task"])),
    ("list_runbooks", "List the NEXUS scenario runbooks and their rosters.", _schema({}, [])),
    ("score_agent", "Audit an agent file against the house template.",
     _schema({"slug": ("string", "Agent slug")}, ["slug"])),
    ("remember", "Store a memory for a project (optionally tagged with a checkpoint name).",
     _schema({"content": ("string", "What to remember"), "project": ("string", "Project key"),
              "agent": ("string", "Agent slug"), "checkpoint": ("string", "Checkpoint label")}, ["content"])),
    ("recall", "Recall recent memories for a project/agent.",
     _schema({"project": ("string", "Project key"), "agent": ("string", "Agent slug"),
              "limit": ("integer", "Max rows")}, [])),
    ("search_memory", "Full-text search across stored memories.",
     _schema({"query": ("string", "Words to find"), "project": ("string", "Project key")}, ["query"])),
    ("rollback", "Delete memories written after a checkpoint.",
     _schema({"checkpoint": ("string", "Checkpoint label"), "project": ("string", "Project key")}, ["checkpoint"])),
]


class Server:
    def __init__(self, memory: Memory | None = None):
        self.agents = by_slug()
        self.index = Index(tuple(self.agents.values()))
        self._memory = memory

    @property
    def memory(self) -> Memory:
        if self._memory is None:
            self._memory = Memory()
        return self._memory

    # --- tool implementations -------------------------------------------------
    def _agent(self, slug: str):
        if slug not in self.agents:
            raise ValueError(f"unknown agent {slug!r}; use search_agents to find slugs")
        return self.agents[slug]

    def call_tool(self, name: str, args: dict) -> Any:
        if name == "search_agents":
            hits = self.index.search(args["query"], int(args.get("limit", 8)), args.get("division"))
            return [{**a.summary(), "score": round(s, 2)} for a, s in hits]
        if name == "get_agent":
            a = self._agent(args["slug"])
            return {**a.summary(), "prompt": a.prompt}
        if name == "recommend_team":
            team = self.index.recommend_team(args["task"], int(args.get("size", 5)))
            return [{"slug": a.slug, "name": a.name, "division": a.division, "why": a.description} for a, _ in team]
        if name == "list_runbooks":
            return load_runbooks()
        if name == "score_agent":
            r = score_agent(self._agent(args["slug"]))
            return {**r.__dict__, "grade": r.grade}
        if name == "remember":
            return {"id": self.memory.remember(args["content"], args.get("project", "default"),
                                               args.get("agent", "any"), checkpoint=args.get("checkpoint"))}
        if name == "recall":
            return self.memory.recall(args.get("project", "default"), args.get("agent"), int(args.get("limit", 20)))
        if name == "search_memory":
            return self.memory.search(args["query"], args.get("project"))
        if name == "rollback":
            return {"removed": self.memory.rollback(args["checkpoint"], args.get("project", "default"))}
        raise ValueError(f"unknown tool {name!r}")

    # --- JSON-RPC dispatch ------------------------------------------------------
    def handle(self, msg: dict) -> dict | None:
        method, mid, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
        if mid is None:  # notification
            return None
        try:
            result = self._dispatch(method, params)
            return {"jsonrpc": "2.0", "id": mid, "result": result}
        except KeyError as e:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"missing/unknown: {e}"}}
        except NotImplementedError:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}

    def _dispatch(self, method: str, params: dict) -> Any:
        if method == "initialize":
            return {
                "protocolVersion": params.get("protocolVersion", PROTOCOL_VERSION),
                "capabilities": {"tools": {}, "prompts": {}},
                "serverInfo": {"name": "agency-platform", "version": __version__},
            }
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": [{"name": n, "description": d, "inputSchema": s} for n, d, s in TOOLS]}
        if method == "tools/call":
            try:
                out = self.call_tool(params["name"], params.get("arguments") or {})
                return {"content": [{"type": "text", "text": json.dumps(out, indent=2, default=str)}]}
            except (ValueError, KeyError) as e:
                return {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}
        if method == "prompts/list":
            return {"prompts": [
                {"name": a.slug, "title": f"{a.emoji} {a.name}".strip(), "description": a.description,
                 "arguments": [{"name": "task", "description": "What you want this agent to do", "required": False}]}
                for a in self.agents.values()
            ]}
        if method == "prompts/get":
            a = self._agent(params["name"])
            task = (params.get("arguments") or {}).get("task", "")
            text = a.prompt + (f"\n\n---\n\n# Your task\n\n{task}" if task else "")
            return {"description": a.description,
                    "messages": [{"role": "user", "content": {"type": "text", "text": text}}]}
        raise NotImplementedError(method)


def serve_stdio() -> None:
    server = Server()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        else:
            reply = server.handle(msg)
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()
