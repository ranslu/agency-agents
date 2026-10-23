"""TF-IDF cosine similarity between agents, for duplicate / overlap detection."""

from __future__ import annotations

import math
from collections import Counter

from .corpus import Agent
from .search import tokenize


def _vectors(agents: list[Agent]) -> list[dict[str, float]]:
    tfs = [Counter(tokenize(f"{a.name} {a.description} {a.body}")) for a in agents]
    df = Counter(t for tf in tfs for t in tf)
    n = len(agents)
    vecs = []
    for tf in tfs:
        v = {t: (1 + math.log(c)) * math.log(1 + n / df[t]) for t, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs.append({t: x / norm for t, x in v.items()})
    return vecs


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(t, 0.0) for t, x in a.items())


def nearest(target: Agent, corpus: list[Agent], k: int = 3) -> list[tuple[Agent, float]]:
    others = [a for a in corpus if a.path != target.path]
    vecs = _vectors([target] + others)
    scored = [(a, cosine(vecs[0], v)) for a, v in zip(others, vecs[1:])]
    scored.sort(key=lambda x: -x[1])
    return scored[:k]
