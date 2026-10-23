"""BM25 search and task routing over the agent corpus."""

from __future__ import annotations

import math
import re
from collections import Counter

from .corpus import Agent, load_corpus

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#.-]*")
_STOP = frozenset(
    "a an and are as at be by for from has have i in is it its me my of on or our that the this "
    "to was we what when which who will with you your need help want build make can do".split()
)

# Field weights: a hit in the name or description says more than one deep in the body.
_FIELDS = (("name", 4.0), ("description", 3.0), ("vibe", 1.5), ("division", 1.0), ("body", 1.0))
_K1, _B = 1.4, 0.75


def tokenize(text: str) -> list[str]:
    out = []
    for tok in _TOKEN_RE.findall(text.lower()):
        tok = tok.strip(".-")
        # "e-commerce" and "ecommerce" should match: index the joined form plus each part.
        parts = [tok.replace("-", "")] + (tok.split("-") if "-" in tok else [])
        for t in parts:
            if t and t not in _STOP and len(t) > 1:
                out.append(t[:-1] if len(t) > 4 and t.endswith("s") and not t.endswith("ss") else t)
    return out


class Index:
    def __init__(self, agents: tuple[Agent, ...] | None = None):
        self.agents = list(agents if agents is not None else load_corpus())
        self.docs: list[Counter] = []
        self.lengths: list[float] = []
        df: Counter = Counter()
        for a in self.agents:
            tf: Counter = Counter()
            for fname, weight in _FIELDS:
                for tok in tokenize(getattr(a, fname)):
                    tf[tok] += weight
            self.docs.append(tf)
            self.lengths.append(sum(tf.values()))
            df.update(tf.keys())
        n = len(self.agents) or 1
        self.avg_len = sum(self.lengths) / n
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def search(self, query: str, limit: int = 10, division: str | None = None) -> list[tuple[Agent, float]]:
        terms = tokenize(query)
        scored = []
        for a, tf, length in zip(self.agents, self.docs, self.lengths):
            if division and a.division != division:
                continue
            score = 0.0
            for t in terms:
                f = tf.get(t)
                if f:
                    score += self.idf[t] * f * (_K1 + 1) / (f + _K1 * (1 - _B + _B * length / self.avg_len))
            if score > 0:
                scored.append((a, score))
        scored.sort(key=lambda x: -x[1])
        return scored[:limit]

    def recommend_team(self, task: str, size: int = 5, per_division: int = 2) -> list[tuple[Agent, float]]:
        """Pick a cross-functional team for a task.

        Each clause of the task ("..., with X and Y") first gets its best-matching agent, so
        secondary needs are not drowned out by the dominant one; remaining seats go to the
        best overall matches, capped per division. The orchestrator leads teams of 4+,
        mirroring the NEXUS runbooks.
        """
        team: list[tuple[Agent, float]] = []
        counts: Counter = Counter()

        def add(a: Agent, s: float, cap: bool = True) -> bool:
            if len(team) >= size or any(a.slug == t.slug for t, _ in team):
                return False
            if cap and counts[a.division] >= per_division:
                return False
            team.append((a, s))
            counts[a.division] += 1
            return True

        if size >= 4:
            orch = next((a for a in self.agents if a.slug == "agents-orchestrator"), None)
            if orch:
                add(orch, 0.0, cap=False)
        clauses = [c for c in re.split(r",|;|\band\b|\bwith\b|\bplus\b|\bthen\b", task, flags=re.I) if tokenize(c)]
        if len(clauses) > 1:
            for clause in clauses:
                for a, s in self.search(clause, limit=10):
                    if add(a, s):
                        break
        for a, s in self.search(task, limit=len(self.agents)):
            if len(team) >= size:
                break
            add(a, s)
        return team
