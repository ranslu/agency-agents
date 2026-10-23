"""Behavioural evals: does an agent actually do its job, on this model?

Each agent's own *Success Metrics* and *Critical Rules* become the grading rubric, so the
eval measures the agent against what it promises. Scenarios come from its *Core Mission*.
Run the same suite across models to get a portability matrix, or export it for promptfoo.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable

from .corpus import Agent
from .runner import DEFAULT_MODEL, build_brief, call_claude

JUDGE_SYSTEM = (
    "You are a strict evaluator of AI specialist outputs. Grade only against the rubric. "
    'Reply with JSON only: {"score": 0-10, "pass": true|false, "reasons": ["..."]}'
)
UNIVERSAL_RUBRIC = [
    "Directly addresses the task rather than giving generic advice",
    "Produces a concrete deliverable (plan, code, template, table) not just prose",
    "States assumptions and risks; does not fabricate facts or results",
    "Stays in role and in the agent's specialty",
]


@dataclass
class EvalResult:
    agent: str
    model: str
    scenario: str
    score: float
    passed: bool
    reasons: list[str] = field(default_factory=list)


def _bullets(text: str, limit: int = 6) -> list[str]:
    items = [re.sub(r"[*_`]", "", m).strip() for m in re.findall(r"^\s*(?:[-*]|\d+\.)\s+(.+)$", text, re.M)]
    return [i for i in items if len(i) > 12][:limit]


def _section(agent: Agent, *keys: str) -> str:
    return "\n".join(v for k, v in agent.sections.items() if any(x in k.lower() for x in keys))


def rubric_for(agent: Agent) -> list[str]:
    own = _bullets(_section(agent, "success metric", "metrics"), 4) + _bullets(_section(agent, "critical rules", "rules"), 4)
    return UNIVERSAL_RUBRIC + own


def scenarios_for(agent: Agent, n: int = 3) -> list[str]:
    mission = _bullets(_section(agent, "mission", "capabilit", "responsibilit"), n)
    if not mission:
        mission = [agent.description]
    return [f"I need help with this: {m}. Give me your best deliverable for a mid-size company." for m in mission[:n]]


def judge(output: str, task: str, rubric: list[str], llm: Callable[[str, str], str]) -> tuple[float, bool, list[str]]:
    prompt = (f"## Task\n{task}\n\n## Rubric\n" + "\n".join(f"- {r}" for r in rubric) +
              f"\n\n## Output to grade\n{output}\n\nPass means score >= 7.")
    raw = llm(JUDGE_SYSTEM, prompt)
    m = re.search(r"\{.*\}", raw, re.S)
    try:
        data = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        data = {}
    score = float(data.get("score", 0))
    return score, bool(data.get("pass", score >= 7)), list(data.get("reasons", []))[:5]


def run_eval(agent: Agent, models: list[str] | None = None, n: int = 3, judge_model: str = DEFAULT_MODEL,
             llm_factory: Callable[[str], Callable[[str, str], str]] | None = None) -> list[EvalResult]:
    factory = llm_factory or (lambda model: lambda s, u: call_claude(s, u, model=model))
    rubric = rubric_for(agent)
    judge_llm = factory(judge_model)
    results = []
    for model in models or [DEFAULT_MODEL]:
        llm = factory(model)
        for task in scenarios_for(agent, n):
            out = llm(agent.prompt, build_brief(task))
            score, ok, reasons = judge(out, task, rubric, judge_llm)
            results.append(EvalResult(agent.slug, model, task, score, ok, reasons))
    return results


def promptfoo_config(agents: list[Agent], providers: list[str]) -> str:
    """A promptfooconfig.yaml (JSON is valid YAML) using llm-rubric assertions."""
    tests = []
    for a in agents:
        for task in scenarios_for(a):
            tests.append({
                "description": f"{a.slug}: {task[:60]}",
                "vars": {"system": a.prompt, "task": build_brief(task)},
                "assert": [{"type": "llm-rubric", "value": "\n".join(f"- {r}" for r in rubric_for(a)), "threshold": 0.7}],
            })
    config = {
        "description": "Agency agents behavioural evals",
        "prompts": [json.dumps([{"role": "system", "content": "{{system}}"}, {"role": "user", "content": "{{task}}"}])],
        "providers": providers,
        "tests": tests,
    }
    return json.dumps(config, indent=2)
