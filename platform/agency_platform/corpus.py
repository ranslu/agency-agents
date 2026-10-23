"""Load the agent corpus: frontmatter, sections and division metadata."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.M)
_EMOJI_PREFIX_RE = re.compile(r"^[^\w]+", re.U)


@dataclass
class Agent:
    slug: str
    name: str
    description: str
    division: str
    path: str
    color: str = ""
    emoji: str = ""
    vibe: str = ""
    tools: str = ""
    body: str = ""
    sections: dict[str, str] = field(default_factory=dict)

    def summary(self) -> dict:
        d = asdict(self)
        d.pop("body")
        d.pop("sections")
        d["section_titles"] = list(self.sections)
        return d

    @property
    def prompt(self) -> str:
        """The system prompt this agent runs with (the markdown body)."""
        return self.body.strip()


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        inner = value[1:-1]
        return inner.replace('\\"', '"') if value[0] == '"' else inner.replace("''", "'")
    return value


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse the flat YAML subset the corpus uses (scalars, quoted and folded/literal blocks).

    Returns (fields, body). A file without frontmatter yields ({}, text).
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return {}, text
    fields: dict[str, str] = {}
    i = 1
    while i < end:
        line = lines[i]
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not m:
            i += 1
            continue
        key, value = m.group(1), m.group(2)
        if value.strip() in {">", ">-", "|", "|-", ">+", "|+"}:
            block = []
            i += 1
            while i < end and (lines[i].startswith((" ", "\t")) or not lines[i].strip()):
                block.append(lines[i].strip())
                i += 1
            joiner = "\n" if value.strip().startswith("|") else " "
            fields[key] = joiner.join(b for b in block if b).strip()
            continue
        fields[key] = _unquote(value)
        i += 1
    return fields, "\n".join(lines[end + 1 :])


def split_sections(body: str) -> dict[str, str]:
    """Map normalized `## ` headings (emoji stripped) to their content."""
    sections: dict[str, str] = {}
    matches = list(_SECTION_RE.finditer(body))
    for idx, m in enumerate(matches):
        title = _EMOJI_PREFIX_RE.sub("", m.group(1)).strip()
        start = m.end()
        stop = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        sections[title] = body[start:stop].strip()
    return sections


def load_divisions(root: Path = REPO_ROOT) -> dict[str, dict]:
    return json.loads((root / "divisions.json").read_text())["divisions"]


def load_runbooks(root: Path = REPO_ROOT) -> list[dict]:
    path = root / "strategy" / "runbooks.json"
    return json.loads(path.read_text())["runbooks"] if path.exists() else []


def load_agent(path: Path, division: str, root: Path = REPO_ROOT) -> Agent | None:
    fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    if not fm.get("name") or not fm.get("description"):
        return None
    return Agent(
        slug=path.stem,
        name=fm["name"],
        description=fm["description"],
        division=division,
        path=str(path.relative_to(root)),
        color=fm.get("color", ""),
        emoji=fm.get("emoji", ""),
        vibe=fm.get("vibe", ""),
        tools=fm.get("tools", ""),
        body=body,
        sections=split_sections(body),
    )


@lru_cache(maxsize=4)
def load_corpus(root: Path = REPO_ROOT) -> tuple[Agent, ...]:
    agents = []
    for division in sorted(load_divisions(root)):
        for path in sorted((root / division).rglob("*.md")):
            agent = load_agent(path, division, root)
            if agent:
                agents.append(agent)
    return tuple(agents)


def by_slug(root: Path = REPO_ROOT) -> dict[str, Agent]:
    return {a.slug: a for a in load_corpus(root)}
