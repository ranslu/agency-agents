"""Repair agents that are missing house-template sections.

Offline it inserts a structured scaffold derived from the agent's own description, so a
contributor fills in specifics instead of starting from nothing. With ANTHROPIC_API_KEY set
(--ai) it asks Claude to write the missing sections in the agent's existing voice.
"""

from __future__ import annotations

import difflib
from pathlib import Path

from .corpus import REPO_ROOT, Agent
from .quality import score_agent

HEADINGS = {
    "identity": "## 🧠 Your Identity & Memory",
    "mission": "## 🎯 Your Core Mission",
    "rules": "## 🚨 Critical Rules You Must Follow",
    "deliverables": "## 📋 Your Technical Deliverables",
    "workflow": "## 🔄 Your Workflow Process",
    "communication": "## 💭 Your Communication Style",
    "metrics": "## 🎯 Your Success Metrics",
}


def scaffold(agent: Agent, family: str) -> str:
    d = agent.description.rstrip(".")
    role = agent.name
    bodies = {
        "identity": f"- **Role**: {role}\n- **Focus**: {d}\n- **Personality**: {agent.vibe or 'Precise, pragmatic, outcome-driven'}\n"
                    "- **Memory**: You remember which approaches worked for past projects and which failed, and why",
        "mission": f"- Deliver {d.lower()}\n- Turn ambiguous requests into a scoped plan before executing\n"
                   "- Leave every engagement with artifacts the team can reuse",
        "rules": "- Ask for missing context instead of guessing when the cost of a wrong assumption is high\n"
                 "- State assumptions, risks and trade-offs explicitly\n"
                 "- Never claim a result you have not verified; label estimates as estimates\n"
                 "- Stay inside your specialty and hand off work that belongs to another specialist",
        "deliverables": f"### {role} Deliverable Template\n\n```markdown\n# [Project] — {role} Report\n\n"
                        "## Context\n[Goal, constraints, inputs received]\n\n## Analysis\n[Findings with evidence]\n\n"
                        "## Recommendations\n| Priority | Action | Expected impact | Effort |\n|---|---|---|---|\n\n"
                        "## Next steps & handoff\n[Owner, deadline, what the next specialist needs]\n```",
        "workflow": "1. **Discover** — clarify goal, audience, constraints and definition of done\n"
                    "2. **Assess** — review current state and gather evidence\n"
                    "3. **Plan** — propose an approach with trade-offs; confirm before heavy work\n"
                    "4. **Execute** — produce the deliverable in small, reviewable increments\n"
                    "5. **Verify & hand off** — check against success metrics and write handoff notes",
        "communication": "- Lead with the answer, then the reasoning\n- Use concrete numbers, examples and file/line references\n"
                         "- Flag uncertainty plainly: \"I'm confident about X, unsure about Y because Z\"",
        "metrics": "- Deliverables accepted without major rework\n- Recommendations tied to a measurable outcome and baseline\n"
                   "- Zero unverified claims in final output\n- Handoffs require no clarification round-trip",
    }
    return f"{HEADINGS[family]}\n\n{bodies[family]}\n"


def ai_sections(agent: Agent, families: list[str]) -> str:
    from .runner import call_claude

    wanted = "\n".join(HEADINGS[f] for f in families)
    prompt = (f"Here is an agent definition:\n\n{agent.body}\n\nWrite ONLY these missing sections, in the same "
              f"voice, specific to this agent's domain (concrete templates, real metrics, domain rules):\n\n{wanted}\n\n"
              "Return markdown starting with the first heading. No preamble.")
    return call_claude("You are a meticulous editor of AI agent system prompts.", prompt).strip() + "\n"


def fix_agent(agent: Agent, use_ai: bool = False, root: Path = REPO_ROOT) -> tuple[str, str, list[str]]:
    """Return (original_text, fixed_text, families_added)."""
    path = root / agent.path
    original = path.read_text(encoding="utf-8")
    missing = score_agent(agent).missing
    if not missing:
        return original, original, []
    addition = ai_sections(agent, missing) if use_ai else "\n".join(scaffold(agent, f) for f in missing)
    fixed = original.rstrip("\n") + "\n\n" + addition
    return original, fixed, missing


def unified(agent: Agent, original: str, fixed: str) -> str:
    return "".join(difflib.unified_diff(original.splitlines(True), fixed.splitlines(True),
                                        f"a/{agent.path}", f"b/{agent.path}"))
