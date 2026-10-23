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


class FixTest(unittest.TestCase):
    def test_scaffold_adds_only_missing_sections_and_raises_score(self):
        from agency_platform.corpus import Agent, split_sections
        from agency_platform.fix import scaffold

        body = "## Identity\nx\n"
        a = Agent("s", "Tester", "Tests things thoroughly for teams", "testing", "testing/s.md", body=body,
                  sections=split_sections(body))
        before = score_agent(a)
        added = "\n".join(scaffold(a, f) for f in before.missing)
        a.body = body + added
        a.sections = split_sections(a.body)
        after = score_agent(a)
        self.assertEqual(after.missing, [])
        self.assertGreater(after.score, before.score)


class EvalTest(unittest.TestCase):
    def test_rubric_uses_agent_metrics_and_judge_parses_json(self):
        from agency_platform.evals import judge, rubric_for, run_eval, scenarios_for, UNIVERSAL_RUBRIC

        a = next(x for x in load_corpus() if x.slug == "engineering-frontend-developer")
        self.assertGreater(len(rubric_for(a)), len(UNIVERSAL_RUBRIC))
        self.assertTrue(scenarios_for(a))
        score, ok, _ = judge("out", "t", ["r"], lambda s, u: 'noise {"score": 8, "pass": true, "reasons": ["good"]}')
        self.assertEqual((score, ok), (8.0, True))
        fake = lambda model: (lambda s, u: '{"score": 6, "pass": false}' if "Rubric" in u else f"answer from {model}")
        results = run_eval(a, ["m1", "m2"], n=2, llm_factory=fake)
        self.assertEqual({r.model for r in results}, {"m1", "m2"})
        self.assertFalse(any(r.passed for r in results))


class ExportTest(unittest.TestCase):
    def test_skills_names_follow_spec(self):
        import re
        import tempfile
        from agency_platform.export import export, skill_name

        self.assertEqual(skill_name("Foo_Bar--baz"), "foo-bar-baz")
        with tempfile.TemporaryDirectory() as d:
            agents = list(load_corpus()[:5])
            export(agents, "skills", Path(d))
            for a in agents:
                text = (Path(d) / skill_name(a.slug) / "SKILL.md").read_text()
                name = re.search(r"^name: (.+)$", text, re.M).group(1)
                self.assertRegex(name, r"^[a-z0-9-]{1,64}$")
            export(agents, "agents-md", Path(d))
            self.assertIn(agents[0].name, (Path(d) / "AGENTS.md").read_text())


class TriageTest(unittest.TestCase):
    def test_existing_good_agent_is_ready_and_non_agent_ignored(self):
        from agency_platform.triage import review_file

        self.assertEqual(review_file("engineering/engineering-frontend-developer.md").verdict, "ready")
        self.assertIsNone(review_file("README.md"))

    def test_copy_is_flagged_duplicate(self):
        import shutil
        import tempfile
        from agency_platform.corpus import REPO_ROOT, load_corpus as lc
        from agency_platform.triage import review_file

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for f in ("divisions.json",):
                shutil.copy(REPO_ROOT / f, root / f)
            (root / "engineering").mkdir()
            src = REPO_ROOT / "engineering" / "engineering-frontend-developer.md"
            shutil.copy(src, root / "engineering" / "engineering-frontend-developer.md")
            (root / "engineering" / "copy.md").write_text(src.read_text().replace("Frontend Developer", "UI Dev"))
            lc.cache_clear()
            try:
                self.assertEqual(review_file("engineering/copy.md", root).verdict, "possible-duplicate")
            finally:
                lc.cache_clear()


if __name__ == "__main__":
    unittest.main()
