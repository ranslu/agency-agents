"""Score agent files against the house template so weak agents are easy to find."""

from __future__ import annotations

from dataclasses import dataclass, field

from .corpus import Agent

# Section families from the contributing template. Each entry lists accepted heading keywords.
SECTION_CHECKS = {
    "identity": ("identity", "who you are", "role"),
    "mission": ("mission", "core responsibilit", "capabilit", "competenc", "what you do"),
    "rules": ("critical rules", "rules", "guardrail", "constraints"),
    "deliverables": ("deliverable", "output", "template", "toolkit", "checklist"),
    "workflow": ("workflow", "process", "methodology", "framework"),
    "communication": ("communication",),
    "metrics": ("success metric", "metrics", "kpi"),
}
WEIGHTS = {"frontmatter": 15, "sections": 50, "examples": 15, "depth": 20}


@dataclass
class Report:
    slug: str
    name: str
    division: str
    score: int
    missing: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def grade(self) -> str:
        return "A" if self.score >= 90 else "B" if self.score >= 75 else "C" if self.score >= 60 else "D"


def score_agent(agent: Agent) -> Report:
    missing, notes = [], []
    fm_fields = [agent.name, agent.description, agent.color, agent.emoji, agent.vibe]
    fm = WEIGHTS["frontmatter"] * sum(bool(f) for f in fm_fields) / len(fm_fields)
    for label, val in zip(("color", "emoji", "vibe"), fm_fields[2:]):
        if not val:
            notes.append(f"frontmatter missing `{label}`")

    titles = [t.lower() for t in agent.sections]
    hit = 0
    for family, keys in SECTION_CHECKS.items():
        if any(k in t for t in titles for k in keys):
            hit += 1
        else:
            missing.append(family)
    sec = WEIGHTS["sections"] * hit / len(SECTION_CHECKS)

    fences = agent.body.count("```") // 2
    ex = WEIGHTS["examples"] * min(fences, 3) / 3
    if fences == 0:
        notes.append("no code/template examples")

    words = len(agent.body.split())
    depth = WEIGHTS["depth"] * min(words, 1500) / 1500
    if words < 600:
        notes.append(f"short prompt ({words} words)")
    if len(agent.description) < 40:
        notes.append("description too short to route on")

    return Report(agent.slug, agent.name, agent.division, round(fm + sec + ex + depth), missing, notes)
