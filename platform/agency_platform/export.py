"""Export agents to open, tool-neutral formats so no per-tool adaptation is needed.

- skills:     Agent Skills open standard (agentskills.io) — one folder per agent with SKILL.md.
              Read natively by Claude Code/Claude apps and a growing list of other agents.
- agents-md:  a single AGENTS.md roster (agents.md) any coding agent reads as project context.
- json:       [{name, description, instructions}] for OpenAI-compatible / custom runtimes.
- txt:        bare system prompts, one file per agent, for anything else.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .corpus import Agent

FORMATS = ("skills", "agents-md", "json", "txt")


def skill_name(slug: str) -> str:
    """Agent Skills names: lowercase letters, digits and hyphens, max 64 chars."""
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9-]", "-", slug.lower())).strip("-")[:64]


def _yaml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)  # a JSON string is a valid YAML scalar


def skill_md(agent: Agent) -> str:
    desc = f"{agent.description.rstrip().rstrip('.')}. Use when you need a {agent.name}."[:1024]
    return (f"---\nname: {skill_name(agent.slug)}\ndescription: {_yaml_str(desc)}\n"
            f"metadata:\n  division: {agent.division}\n  source: {agent.path}\n---\n\n{agent.prompt}\n")


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
