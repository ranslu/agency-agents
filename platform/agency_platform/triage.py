"""Automated first-pass review of agent changes, to shrink the maintainer PR backlog.

For every added/changed agent file it checks frontmatter, template coverage and quality grade,
and flags near-duplicates of existing agents. The output is a markdown report suitable for a
sticky PR comment, plus a verdict per file: ready / needs-work / possible-duplicate / invalid.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .corpus import REPO_ROOT, load_agent, load_corpus, load_divisions
from .quality import score_agent
from .similarity import nearest

DUPLICATE_THRESHOLD = 0.80
OVERLAP_THRESHOLD = 0.60
READY_SCORE = 75


@dataclass
class FileReview:
    path: str
    verdict: str
    score: int | None = None
    grade: str = ""
    problems: list[str] = field(default_factory=list)
    similar: list[tuple[str, float]] = field(default_factory=list)


def changed_files(base: str, root: Path = REPO_ROOT) -> list[str]:
    out = subprocess.run(["git", "diff", "--name-only", "--diff-filter=AM", f"{base}...HEAD"],
                         cwd=root, capture_output=True, text=True, check=True).stdout
    return [p for p in out.split() if p.endswith(".md")]


def review_file(rel: str, root: Path = REPO_ROOT) -> FileReview | None:
    divisions = load_divisions(root)
    p = Path(rel)
    if p.is_absolute() or p.exists():  # accept paths relative to the cwd, too
        try:
            rel = str(p.resolve().relative_to(root))
        except ValueError:
            return None
    division = rel.split("/", 1)[0]
    if division not in divisions:
        return None  # not an agent file (README, strategy, integrations…)
    path = root / rel
    agent = load_agent(path, division, root)
    if agent is None:
        return FileReview(rel, "invalid", problems=["missing frontmatter `name` and/or `description`"])
    report = score_agent(agent)
    problems = [f"missing section: {m}" for m in report.missing] + report.notes
    corpus = [a for a in load_corpus(root) if a.path != rel]
    similar = [(a.slug, round(s, 2)) for a, s in nearest(agent, corpus, 3) if s >= OVERLAP_THRESHOLD]
    if similar and similar[0][1] >= DUPLICATE_THRESHOLD:
        verdict = "possible-duplicate"
    elif report.score >= READY_SCORE and not any(p.startswith("frontmatter") for p in problems):
        verdict = "ready"
    else:
        verdict = "needs-work"
    return FileReview(rel, verdict, report.score, report.grade, problems, similar)


ICON = {"ready": "🟢", "needs-work": "🟡", "possible-duplicate": "🟠", "invalid": "🔴"}


def render(reviews: list[FileReview]) -> str:
    if not reviews:
        return "## 🤖 Agency triage\n\nNo agent files changed."
    lines = ["## 🤖 Agency triage", "", "| File | Verdict | Grade | Notes |", "|---|---|---|---|"]
    for r in reviews:
        notes = "; ".join(r.problems[:4]) or "—"
        if r.similar:
            notes += " · similar to " + ", ".join(f"`{s}` ({v})" for s, v in r.similar)
        lines.append(f"| `{r.path}` | {ICON[r.verdict]} {r.verdict} | {r.grade} {r.score if r.score is not None else ''} | {notes} |")
    lines += ["", "Fix scaffolds locally with `python3 platform/agency.py fix <slug> --write`. "
              "This is an automated first pass; a maintainer still makes the call."]
    return "\n".join(lines)
