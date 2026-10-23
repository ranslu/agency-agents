"""Run a sequence of agents on a task, passing each one's output to the next as a handoff.

Uses the Anthropic Messages API over plain HTTPS (no SDK needed). Set ANTHROPIC_API_KEY.
Without a key, or with dry_run=True, it prints the prompts it would send.
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Callable

from .corpus import Agent
from .memory import Memory

API_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com") + "/v1/messages"
DEFAULT_MODEL = os.environ.get("AGENCY_MODEL", "claude-sonnet-5-5")

HANDOFF = """## Handoff from {prev_name}

{prev_output}

---
Continue the project from your specialty. Build on the work above rather than redoing it,
flag anything in it you disagree with, and end with a short "Handoff notes" section for the next specialist."""


@dataclass
class Step:
    agent: Agent
    prompt: str
    output: str = ""


def call_claude(system: str, user: str, model: str = DEFAULT_MODEL, max_tokens: int = 4096) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    body = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }).encode()
    req = urllib.request.Request(API_URL, data=body, headers={
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = json.load(resp)
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def run_pipeline(task: str, agents: list[Agent], *, model: str = DEFAULT_MODEL, dry_run: bool = False,
                 memory: Memory | None = None, project: str = "default",
                 on_step: Callable[[Step], None] | None = None,
                 llm: Callable[[str, str], str] | None = None) -> list[Step]:
    steps: list[Step] = []
    llm = llm or (lambda s, u: call_claude(s, u, model=model))
    for i, agent in enumerate(agents):
        prompt = f"# Task\n\n{task}"
        if memory:
            past = memory.recall(project=project, agent=agent.slug, limit=5)
            if past:
                prompt += "\n\n## Project memory\n\n" + "\n".join(f"- {m['content'][:500]}" for m in reversed(past))
        if steps:
            prev = steps[-1]
            prompt += "\n\n" + HANDOFF.format(prev_name=prev.agent.name, prev_output=prev.output)
        step = Step(agent, prompt)
        step.output = f"[dry run: {agent.name} would answer here]" if dry_run else llm(agent.prompt, prompt)
        if memory and not dry_run:
            memory.remember(step.output[:4000], project=project, agent=agent.slug,
                            tags=["pipeline-output"], checkpoint=f"step-{i}")
        steps.append(step)
        if on_step:
            on_step(step)
    return steps
