"""Export agents to open, tool-neutral formats so no per-tool adaptation is needed.

- skills:     Agent Skills open standard (agentskills.io) — one folder per agent with SKILL.md.
              Read natively by Claude Code/Claude apps and a growing list of other agents.
- agents-md:  a single AGENTS.md roster (agents.md) any coding agent reads as project context.
- json:       [{name, description, instructions}] for OpenAI-compatible / custom runtimes.
- txt:        bare system prompts, one file per agent, for anything else.
- skill-bundle: ONE Agent Skill ("agency-roster") holding every agent as a reference file plus an
              index, so a single upload (e.g. claude.ai custom skills) makes the whole roster usable.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .corpus import Agent

FORMATS = ("skills", "skill-bundle", "agents-md", "json", "txt")
BUNDLE_NAME = "agency-roster"


def skill_name(slug: str) -> str:
    """Agent Skills names: lowercase letters, digits and hyphens, max 64 chars."""
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9-]", "-", slug.lower())).strip("-")[:64]


def _yaml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)  # a JSON string is a valid YAML scalar


def skill_md(agent: Agent) -> str:
    desc = f"{agent.description.rstrip().rstrip('.')}. Use when you need a {agent.name}."[:1024]
    return (f"---\nname: {skill_name(agent.slug)}\ndescription: {_yaml_str(desc)}\n"
            f"metadata:\n  division: {agent.division}\n  source: {agent.path}\n---\n\n{agent.prompt}\n")


def bundle_skill_md(agents: list[Agent]) -> str:
    divisions = sorted({a.division for a in agents})
    desc = (f"Roster of {len(agents)} specialist AI agent personas ({', '.join(divisions)}). Use when the user "
            "asks for a specialist, expert or role (e.g. frontend developer, SEO, compliance auditor, growth hacker), "
            "wants a team assembled for a project, or says 'act as' / 'use the ... agent'.")[:1024]
    return f"""---
name: {BUNDLE_NAME}
description: {_yaml_str(desc)}
---

# Agency Roster

A library of {len(agents)} specialist personas. Each one is a full system prompt with identity, rules,
deliverables, workflow and success metrics.

## How to use

1. Find the right specialist in `references/INDEX.md` (one row per agent: slug, name, division, when to use).
2. Read `references/<slug>.md` and adopt that persona: follow its critical rules, workflow and deliverable formats.
3. For a project needing several roles, pick one agent per need (lead with `agents-orchestrator` for 4+ roles),
   state the team, then work through the roles in order, handing off between them explicitly.
4. Only load the agents you need; never read the whole library at once.
"""


def bundle_index(agents: list[Agent]) -> str:
    lines = ["# Agent index", "", "| Slug | Agent | Division | Use when |", "|---|---|---|---|"]
    lines += [f"| `{a.slug}` | {a.emoji} {a.name} | {a.division} | {a.description.replace('|', '/')[:200]} |"
              for a in agents]
    return "\n".join(lines) + "\n"


def agents_md(agents: list[Agent]) -> str:
    lines = ["# AGENTS.md — The Agency roster", "",
             "Specialist personas available to this project. When a task matches a specialist, "
             "adopt that persona by reading its file and following its workflow and rules.", ""]
    by_div: dict[str, list[Agent]] = {}
    for a in agents:
        by_div.setdefault(a.division, []).append(a)
    for div, items in sorted(by_div.items()):
        lines += [f"## {div}", "", "| Agent | Use when | File |", "|---|---|---|"]
        lines += [f"| {a.emoji} {a.name} | {a.description.replace('|', '/')[:160]} | `{a.path}` |" for a in items]
        lines.append("")
    return "\n".join(lines)


def export(agents: list[Agent], fmt: str, out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    if fmt == "skills":
        for a in agents:
            d = out / skill_name(a.slug)
            d.mkdir(exist_ok=True)
            (d / "SKILL.md").write_text(skill_md(a), encoding="utf-8")
    elif fmt == "skill-bundle":
        root = out / BUNDLE_NAME
        (root / "references").mkdir(parents=True, exist_ok=True)
        (root / "SKILL.md").write_text(bundle_skill_md(agents), encoding="utf-8")
        (root / "references" / "INDEX.md").write_text(bundle_index(agents), encoding="utf-8")
        for a in agents:
            (root / "references" / f"{a.slug}.md").write_text(a.prompt + "\n", encoding="utf-8")
    elif fmt == "agents-md":
        (out / "AGENTS.md").write_text(agents_md(agents), encoding="utf-8")
    elif fmt == "json":
        data = [{"name": a.slug, "description": a.description, "instructions": a.prompt} for a in agents]
        (out / "agents.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    elif fmt == "txt":
        for a in agents:
            (out / f"{a.slug}.txt").write_text(a.prompt + "\n", encoding="utf-8")
    else:
        raise ValueError(f"unknown format {fmt!r}; choose from {', '.join(FORMATS)}")
    return len(agents)
