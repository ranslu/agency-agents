"""Local web dashboard + JSON API: browse, search, build teams, audit quality, run pipelines."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .corpus import by_slug, load_divisions, load_runbooks
from .quality import score_agent
from .runner import run_pipeline
from .search import Index

STATIC = Path(__file__).with_name("static")


class App:
    def __init__(self):
        self.agents = by_slug()
        self.index = Index(tuple(self.agents.values()))
        self.divisions = load_divisions()

    def route(self, method: str, path: str, query: dict, body: dict) -> tuple[int, object]:
        q = lambda k, d="": query.get(k, [d])[0]
        if path == "/api/agents":
            return 200, [a.summary() for a in self.agents.values()]
        if path == "/api/divisions":
            return 200, self.divisions
        if path.startswith("/api/agent/"):
            a = self.agents.get(path.rsplit("/", 1)[1])
            return (200, {**a.summary(), "prompt": a.prompt}) if a else (404, {"error": "not found"})
        if path == "/api/search":
            hits = self.index.search(q("q"), int(q("limit", "20")), q("division") or None)
            return 200, [{**a.summary(), "score": round(s, 2)} for a, s in hits]
        if path == "/api/team":
            team = self.index.recommend_team(q("task"), int(q("size", "5")))
            return 200, [a.summary() for a, _ in team]
        if path == "/api/quality":
            reports = sorted((score_agent(a) for a in self.agents.values()), key=lambda r: r.score)
            return 200, [{**r.__dict__, "grade": r.grade} for r in reports]
        if path == "/api/runbooks":
            return 200, load_runbooks()
        if path == "/api/run" and method == "POST":
            agents = [self.agents[s] for s in body.get("agents", []) if s in self.agents]
            if not agents or not body.get("task"):
                return 400, {"error": "need task and at least one known agent slug"}
            try:
                steps = run_pipeline(body["task"], agents, dry_run=bool(body.get("dry_run", True)))
            except Exception as e:  # surface API/key errors to the UI
                return 502, {"error": str(e)}
            return 200, [{"agent": s.agent.name, "slug": s.agent.slug, "output": s.output} for s in steps]
        return 404, {"error": "unknown endpoint"}


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send(self, code: int, payload: bytes, ctype: str):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _handle(self, method: str):
            url = urlparse(self.path)
            if not url.path.startswith("/api/"):
                return self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            body = {}
            if method == "POST":
                length = int(self.headers.get("Content-Length") or 0)
                try:
                    body = json.loads(self.rfile.read(length) or b"{}")
                except json.JSONDecodeError:
                    return self._send(400, b'{"error":"bad json"}', "application/json")
            code, data = app.route(method, url.path, parse_qs(url.query), body)
            self._send(code, json.dumps(data).encode(), "application/json")

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8787) -> None:
    server = ThreadingHTTPServer((host, port), make_handler(App()))
    print(f"Agency dashboard on http://{host}:{port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
