import json
import sys
import threading
import unittest
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agency_platform.corpus import load_corpus, parse_frontmatter, split_sections  # noqa: E402
from agency_platform.mcp_server import Server  # noqa: E402
from agency_platform.memory import Memory  # noqa: E402
from agency_platform.quality import score_agent  # noqa: E402
from agency_platform.runner import run_pipeline  # noqa: E402
from agency_platform.search import Index  # noqa: E402


class CorpusTest(unittest.TestCase):
    def test_frontmatter_scalars_quotes_and_folded(self):
        fm, body = parse_frontmatter('---\nname: X\ndescription: >\n  one\n  two\nvibe: "a \\"q\\""\n---\n# Body\n')
        self.assertEqual(fm, {"name": "X", "description": "one two", "vibe": 'a "q"'})
        self.assertEqual(body.strip(), "# Body")

    def test_no_frontmatter(self):
        self.assertEqual(parse_frontmatter("# hi")[0], {})

    def test_sections_strip_emoji(self):
        self.assertIn("Your Core Mission", split_sections("## 🎯 Your Core Mission\ntext\n## Next\n"))

    def test_corpus_loads_with_unique_slugs(self):
        agents = load_corpus()
        self.assertGreater(len(agents), 100)
        slugs = [a.slug for a in agents]
        self.assertEqual(len(slugs), len(set(slugs)))
        self.assertTrue(all(a.name and a.description for a in agents))


class SearchTest(unittest.TestCase):
    index = Index()

    def test_frontend_query_finds_frontend_developer(self):
        top = [a.slug for a, _ in self.index.search("react frontend components", 3)]
        self.assertIn("engineering-frontend-developer", top)

    def test_division_filter(self):
        self.assertTrue(all(a.division == "marketing" for a, _ in self.index.search("growth", 10, "marketing")))

    def test_team_covers_each_clause_and_respects_size(self):
        team = self.index.recommend_team("mobile app with tiktok marketing and HIPAA compliance", 5)
        slugs = [a.slug for a, _ in team]
        self.assertEqual(len(slugs), 5)
        self.assertEqual(slugs[0], "agents-orchestrator")
        self.assertIn("marketing-tiktok-strategist", slugs)
        self.assertTrue(any("compliance" in s for s in slugs))


class QualityTest(unittest.TestCase):
    def test_scores_in_range(self):
        for a in load_corpus():
            r = score_agent(a)
            self.assertTrue(0 <= r.score <= 100, a.slug)


class MemoryTest(unittest.TestCase):
    def test_remember_recall_search_rollback(self):
        m = Memory(":memory:")
        m.remember("chose postgres", "p", "eng", checkpoint="v1")
        m.remember("switched to sqlite", "p", "eng")
        self.assertEqual(len(m.recall("p", "eng")), 2)
        self.assertEqual(m.search("postgres", "p")[0]["content"], "chose postgres")
        self.assertEqual(m.rollback("v1", "p"), 1)
        self.assertEqual(len(m.recall("p")), 1)
        with self.assertRaises(KeyError):
            m.rollback("nope", "p")


class RunnerTest(unittest.TestCase):
    def test_handoff_passes_previous_output(self):
        agents = list(load_corpus()[:2])
        seen = []
        steps = run_pipeline("do it", agents, llm=lambda s, u: (seen.append(u), f"out-{len(seen)}")[1])
        self.assertEqual([s.output for s in steps], ["out-1", "out-2"])
        self.assertIn("out-1", seen[1])
        self.assertIn(agents[0].name, seen[1])


class McpTest(unittest.TestCase):
    server = Server(memory=Memory(":memory:"))

    def call(self, method, params=None, mid=1):
        return self.server.handle({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}})

    def test_initialize_and_lists(self):
        self.assertIn("tools", self.call("initialize")["result"]["capabilities"])
        names = {t["name"] for t in self.call("tools/list")["result"]["tools"]}
        self.assertTrue({"search_agents", "recommend_team", "remember"} <= names)
        self.assertGreater(len(self.call("prompts/list")["result"]["prompts"]), 100)

    def test_tool_call_and_prompt_get(self):
        res = self.call("tools/call", {"name": "search_agents", "arguments": {"query": "kubernetes devops"}})
        self.assertTrue(json.loads(res["result"]["content"][0]["text"]))
        p = self.call("prompts/get", {"name": "engineering-frontend-developer", "arguments": {"task": "build X"}})
        self.assertIn("build X", p["result"]["messages"][0]["content"]["text"])

    def test_errors(self):
        self.assertTrue(self.call("tools/call", {"name": "get_agent", "arguments": {"slug": "nope"}})["result"]["isError"])
        self.assertEqual(self.call("bogus")["error"]["code"], -32601)
        self.assertIsNone(self.server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))


class WebTest(unittest.TestCase):
    def test_api_endpoints(self):
        from http.server import ThreadingHTTPServer
        from agency_platform.web import App, make_handler

        srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(App()))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        try:
            get = lambda p: json.load(urllib.request.urlopen(base + p))
            self.assertGreater(len(get("/api/agents")), 100)
            self.assertTrue(get("/api/search?q=seo"))
            self.assertEqual(len(get("/api/team?task=saas+launch&size=4")), 4)
            req = urllib.request.Request(base + "/api/run", method="POST", headers={"content-type": "application/json"},
                                         data=json.dumps({"task": "t", "agents": ["agents-orchestrator"]}).encode())
            self.assertIn("dry run", json.load(urllib.request.urlopen(req))[0]["output"])
            self.assertIn(b"Agency Platform", urllib.request.urlopen(base + "/").read())
        finally:
            srv.shutdown()


if __name__ == "__main__":
    unittest.main()
