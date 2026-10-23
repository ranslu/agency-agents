#!/usr/bin/env python3
"""Claude Skill Scraper: find, score, and harvest the most comprehensive Agent Skills.

Sources skills (directories containing a SKILL.md) from GitHub repositories,
awesome-lists, GitHub search, and local folders, then ranks each one on how
comprehensive and dynamic it is: bundled scripts and references, frontmatter
controls (allowed-tools, argument-hint, context: fork, hooks...), runtime
features ($ARGUMENTS, !`shell` context injection, ${CLAUDE_SKILL_DIR}, MCP and
subagent orchestration), and guidance depth (workflows, checklists, validation
loops, examples).

Scraped content is treated as untrusted data: nothing it contains is ever
executed. Risky patterns (piping downloads into a shell, embedded secrets,
prompt-injection phrasing) are flagged, penalised, and excluded from harvests by default.

Standard library only. Python 3.9+.
"""
from __future__ import annotations

import argparse
import concurrent.futures as futures
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

VERSION = "1.0.0"
HERE = Path(__file__).resolve().parent
DEFAULT_SOURCES = HERE.parent / "sources.txt"
DEFAULT_CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "skill-scraper"

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next"}
SCRIPT_EXTS = {".py", ".sh", ".bash", ".zsh", ".js", ".mjs", ".cjs", ".ts", ".rb", ".go",
               ".ps1", ".pl", ".lua", ".rs", ".swift", ".kt", ".r", ".R"}
DOC_EXTS = {".md", ".mdx", ".txt", ".rst"}
MAX_SCAN_BYTES = 400_000          # per file, for risk scanning
MAX_HARVEST_FILE = 5 * 1024 * 1024
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# Category caps sum to 100. See references/scoring.md for the rubric.
CATEGORY_CAPS = {"frontmatter": 15, "resources": 30, "dynamic": 35, "guidance": 20}


# --------------------------------------------------------------------------- #
# Frontmatter
# --------------------------------------------------------------------------- #

def parse_frontmatter(text: str) -> tuple[dict, str, bool]:
    """Return (frontmatter, body, had_frontmatter). PyYAML if present, else a tolerant mini-parser."""
    if not text.startswith("---"):
        return {}, text, False
    lines = text.splitlines()
    end = next((i for i in range(1, len(lines)) if lines[i].strip() in ("---", "...")), None)
    if end is None:
        return {}, text, False
    raw = "\n".join(lines[1:end])
    body = "\n".join(lines[end + 1:])
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(raw)
        if isinstance(data, dict):
            return data, body, True
    except Exception:
        pass
    return mini_yaml(raw), body, True


def _scalar(v: str):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    if v.startswith("[") and v.endswith("]"):
        return [_scalar(x) for x in v[1:-1].split(",") if x.strip()]
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    return v


def mini_yaml(raw: str) -> dict:
    """Top-level keys only: scalars, inline lists, block lists, block scalars, nested maps (kept raw)."""
    out: dict = {}
    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", lines[i])
        i += 1
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        block = []
        while i < len(lines) and (lines[i].startswith((" ", "\t")) or not lines[i].strip()):
            block.append(lines[i])
            i += 1
        content = [b.strip() for b in block if b.strip()]
        if val in ("|", ">", "|-", ">-", "|+", ">+"):
            out[key] = ("\n" if val.startswith("|") else " ").join(content)
        elif val:
            out[key] = _scalar(val)
        elif content and all(c.startswith("- ") for c in content):
            out[key] = [_scalar(c[2:]) for c in content]
        elif content:
            out[key] = {"_raw": "\n".join(block)}
        else:
            out[key] = ""
    return out


def tool_list(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        value = ", ".join(str(v) for v in value)
    return re.findall(r"[A-Za-z_][\w.*-]*(?:\([^)]*\))?", str(value))


# --------------------------------------------------------------------------- #
# Sources
# --------------------------------------------------------------------------- #

@dataclass
class Source:
    kind: str                 # "git" | "local"
    label: str                # owner/repo or local path
    url: str = ""
    ref: str = ""
    subpath: str = ""
    stars: int | None = None
    via: str = "seed"
    path: Path | None = None  # checkout location once fetched
    commit: str = ""
    error: str = ""


def parse_spec(spec: str, via: str = "seed") -> Source | None:
    spec = spec.strip()
    if not spec or spec.startswith("#"):
        return None
    spec = spec.split()[0]
    if spec.startswith((".", "/", "~")):
        p = Path(os.path.expanduser(spec)).resolve()
        return Source("local", str(p), path=p, via=via)
    m = re.match(r"^https?://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?(?:/tree/([^/]+)(?:/(.*))?)?/?$", spec)
    if m:
        owner, repo, ref, sub = m.groups()
        return Source("git", f"{owner}/{repo}", f"https://github.com/{owner}/{repo}.git", ref or "", sub or "", via=via)
    m = re.match(r"^([\w.-]+)/([\w.-]+?)(?:@([^:]+))?(?::(.+))?$", spec)
    if m:
        owner, repo, ref, sub = m.groups()
        return Source("git", f"{owner}/{repo}", f"https://github.com/{owner}/{repo}.git", ref or "", sub or "", via=via)
    if spec.startswith(("http://", "https://", "git@", "ssh://")):
        label = re.sub(r"(\.git)?/?$", "", spec).rsplit("/", 2)
        return Source("git", "/".join(label[-2:]), spec, via=via)
    return None


def load_sources(path: Path) -> list[Source]:
    if not path or not path.exists():
        return []
    return [s for s in (parse_spec(line) for line in path.read_text(encoding="utf-8").splitlines()) if s]


def gh_api(path: str, token: str | None, timeout: int = 20):
    url = f"https://api.github.com/{path.lstrip('/')}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": f"skill-scraper/{VERSION}"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


DISCOVERY_QUERIES = [
    "topic:claude-skills",
    "topic:agent-skills",
    "topic:claude-code-skills",
    "topic:anthropic-skills",
    "claude skills in:name,description",
    "SKILL.md in:readme claude",
]


def discover(limit: int, token: str | None, extra_queries: list[str]) -> list[Source]:
    found: dict[str, Source] = {}
    for q in DISCOVERY_QUERIES + extra_queries:
        try:
            data = gh_api(f"search/repositories?q={urllib.parse.quote(q)}&sort=stars&order=desc&per_page=50", token)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            log(f"  discover: '{q}' failed ({exc}); skipping")
            continue
        for item in data.get("items", []):
            if item.get("fork") or item.get("archived"):
                continue
            label = item["full_name"]
            if label not in found:
                found[label] = Source("git", label, item["clone_url"], stars=item.get("stargazers_count"), via=f"search:{q}")
    ranked = sorted(found.values(), key=lambda s: s.stars or 0, reverse=True)
    return ranked[:limit]


def fill_stars(sources: list[Source], token: str | None) -> None:
    for s in sources:
        if s.kind != "git" or s.stars is not None or "github.com" not in s.url:
            continue
        try:
            s.stars = gh_api(f"repos/{s.label}", token).get("stargazers_count")
        except (urllib.error.URLError, OSError, ValueError):
            pass


def git(args: list[str], cwd: Path | None = None, timeout: int = 180) -> subprocess.CompletedProcess:
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_LFS_SKIP_SMUDGE="1")
    return subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)


def fetch(src: Source, cache: Path, offline: bool) -> Source:
    if src.kind == "local":
        return src
    dest = cache / re.sub(r"[^\w.-]+", "__", src.label)
    try:
        if (dest / ".git").exists():
            if not offline:
                ref = src.ref or "HEAD"
                r = git(["fetch", "--depth", "1", "origin", ref], dest)
                if r.returncode == 0:
                    git(["reset", "--hard", "-q", "FETCH_HEAD"], dest)
                else:
                    log(f"  {src.label}: fetch failed, using cached copy")
        elif offline:
            src.error = "not cached (offline)"
            return src
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            args = ["clone", "--depth", "1", "--single-branch", "-q"]
            if src.ref:
                args += ["--branch", src.ref]
            r = git(args + [src.url, str(dest)])
            if r.returncode != 0:
                src.error = (r.stderr.strip().splitlines() or ["clone failed"])[-1]
                shutil.rmtree(dest, ignore_errors=True)
                return src
        src.path = dest
        rev = git(["rev-parse", "HEAD"], dest)
        src.commit = rev.stdout.strip() if rev.returncode == 0 else ""
    except subprocess.TimeoutExpired:
        src.error = "git timed out"
    return src


GITHUB_LINK = re.compile(r"github\.com/([\w.-]+)/([\w.-]+)")


def expand_awesome(src: Source, limit: int) -> list[Source]:
    """Pull repo links out of an awesome-list README (one level, no recursion)."""
    if not src.path:
        return []
    readmes = sorted(src.path.glob("README*.md")) + sorted(src.path.glob("readme*.md"))
    seen, out = {src.label.lower()}, []
    for readme in readmes[:1]:
        for owner, repo in GITHUB_LINK.findall(readme.read_text(encoding="utf-8", errors="replace")):
            repo = re.sub(r"\.git$", "", repo).rstrip(".")
            label = f"{owner}/{repo}"
            if owner.lower() in {"sponsors", "orgs", "topics", "features", "apps", "marketplace", "user-attachments", "settings", "login"} or label.lower() in seen:
                continue
            seen.add(label.lower())
            out.append(Source("git", label, f"https://github.com/{label}.git", via=f"awesome:{src.label}"))
            if len(out) >= limit:
                return out
    return out


# --------------------------------------------------------------------------- #
# Skill analysis
# --------------------------------------------------------------------------- #

RISK_PATTERNS = [
    ("pipe-to-shell", re.compile(r"(curl|wget)\b[^\n|]*\|\s*(sudo\s+)?(ba|z|da)?sh\b")),
    ("base64-exec", re.compile(r"base64\s+(-d|--decode)[^\n]*\|\s*(ba)?sh\b")),
    ("destructive-rm", re.compile(r"rm\s+-[a-zA-Z]*r[a-zA-Z]*f?\s+(/|~|\$HOME)(\s|$|\*)")),
    ("skip-permissions", re.compile(r"--dangerously-skip-permission[s]")),
    ("prompt-injection", re.compile(r"(?i)ignore (all )?(the )?(previous|prior|above) instructions")),
    ("embedded-secret", re.compile(r"AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|sk-ant-[A-Za-z0-9_-]{20,}|xox[bp]-[A-Za-z0-9-]{20,}"
                                   r"|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("credential-read", re.compile(r"\.ssh/id_(rsa|ed25519)|\.aws/credential[s]|\.netr[c]\b")),
]

MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCED = re.compile(r"^(`{3,}|~{3,})[^\n]*\n.*?^\1[ \t]*$", re.M | re.S)
INLINE_PATH = re.compile(r"`(?:\$\{CLAUDE_SKILL_DIR\}/|\./)?((?:scripts|references|reference|assets|templates|examples|docs|resources|lib)/[\w./-]+)`")


@dataclass
class Skill:
    id: str
    name: str
    description: str
    source: str
    source_url: str
    commit: str
    rel_path: str
    abs_path: str
    license: str
    stars: int | None
    lines: int
    words: int
    files: dict
    features: list = field(default_factory=list)      # [category, key, points, evidence]
    penalties: list = field(default_factory=list)     # [key, points, evidence]
    risks: list = field(default_factory=list)
    categories: dict = field(default_factory=dict)
    score: float = 0.0
    content_hash: str = ""
    mirrors: list = field(default_factory=list)

    @property
    def feature_keys(self) -> set[str]:
        return {f[1] for f in self.features}


def find_skill_files(root: Path) -> list[Path]:
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.lower() == "skill.md":
                out.append(Path(dirpath) / fn)
    return sorted(out)


def bundled_files(skill_dir: Path) -> list[Path]:
    """Files belonging to this skill, excluding nested skills and junk."""
    out = []
    for dirpath, dirnames, filenames in os.walk(skill_dir):
        d = Path(dirpath)
        keep = []
        for name in dirnames:
            sub = d / name
            if name in SKIP_DIRS or any((sub / n).exists() for n in ("SKILL.md", "skill.md")):
                continue
            keep.append(name)
        dirnames[:] = keep
        for fn in filenames:
            p = d / fn
            if p.is_symlink() or (d == skill_dir and fn.lower() == "skill.md"):
                continue
            out.append(p)
    return sorted(out)


def classify(files: list[Path], skill_dir: Path) -> dict:
    scripts, docs, assets, tests, lic = [], [], [], [], []
    for f in files:
        rel = f.relative_to(skill_dir).as_posix()
        low = rel.lower()
        if Path(low).name.startswith(("license", "licence", "copying")):
            lic.append(rel)
        elif re.search(r"(^|/)(tests?|evals?)/|(^|/)test_[^/]+\.py$|\.(test|spec)\.[jt]sx?$|(^|/)evals?\.json$", low):
            tests.append(rel)
        elif f.suffix in SCRIPT_EXTS:
            scripts.append(rel)
        elif f.suffix.lower() in DOC_EXTS:
            docs.append(rel)
        else:
            assets.append(rel)
    return {"scripts": scripts, "docs": docs, "assets": assets, "tests": tests, "license": lic}


def detect_license(fm: dict, skill_dir: Path, repo_root: Path) -> str:
    if fm.get("license"):
        return str(fm["license"])[:80]
    for base in (skill_dir, repo_root):
        for cand in sorted(base.glob("LICEN[CS]E*")) + sorted(base.glob("COPYING*")):
            head = cand.read_text(encoding="utf-8", errors="replace")[:1500]
            for spdx, pat in (("MIT", r"MIT License|Permission is hereby granted, free of charge"),
                              ("Apache-2.0", r"Apache License,?\s+Version 2\.0"),
                              ("GPL-3.0", r"GNU GENERAL PUBLIC LICENSE\s+Version 3"),
                              ("BSD", r"Redistribution and use in source and binary forms"),
                              ("CC-BY-4.0", r"Creative Commons Attribution 4\.0"),
                              ("MPL-2.0", r"Mozilla Public License,? v(ersion)?\.? ?2\.0")):
                if re.search(pat, head, re.I):
                    return spdx
            return f"see {cand.name}"
    return "unknown"


def add(skill: Skill, cat: str, key: str, pts: float, evidence: str = "") -> None:
    skill.features.append([cat, key, round(pts, 2), evidence[:120]])


def penalise(skill: Skill, key: str, pts: float, evidence: str = "") -> None:
    skill.penalties.append([key, -abs(round(pts, 2)), evidence[:120]])


def count(pattern: str, text: str, flags=re.I | re.M) -> int:
    return len(re.findall(pattern, text, flags))


def analyse(skill_md: Path, src: Source, repo_root: Path) -> Skill:
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    fm, body, had_fm = parse_frontmatter(text)
    skill_dir = skill_md.parent
    rel = skill_dir.relative_to(repo_root).as_posix() if skill_dir != repo_root else "."
    name = str(fm.get("name") or skill_dir.name)
    desc = fm.get("description") or ""
    desc = " ".join(str(desc).split()) if not isinstance(desc, dict) else ""
    files = bundled_files(skill_dir)
    cls = classify(files, skill_dir)
    sid = re.sub(r"[^\w.-]+", "-", f"{src.label}/{rel}".strip("/")).strip("-").lower()
    sk = Skill(
        id=sid, name=name, description=desc, source=src.label,
        source_url=src.url.removesuffix(".git") if src.kind == "git" else src.label,
        commit=src.commit, rel_path=rel, abs_path=str(skill_dir), license=detect_license(fm, skill_dir, repo_root),
        stars=src.stars, lines=len(body.splitlines()), words=len(body.split()), files=cls,
        content_hash=hashlib.sha256(re.sub(r"\s+", " ", body).strip().encode()).hexdigest()[:16],
    )

    # -- frontmatter (cap 20) ------------------------------------------------
    if not had_fm:
        penalise(sk, "no-frontmatter", 8, "SKILL.md has no YAML frontmatter")
    if fm.get("name") and NAME_RE.match(str(fm["name"])) and len(str(fm["name"])) <= 64:
        add(sk, "frontmatter", "valid-name", 2, str(fm["name"]))
    elif fm.get("name"):
        penalise(sk, "invalid-name", 2, f"name '{fm['name']}' is not lowercase-hyphenated")
    if not desc:
        penalise(sk, "no-description", 10, "missing description: Claude cannot auto-select it")
    else:
        add(sk, "frontmatter", "description", min(3, len(desc) / 80), f"{len(desc)} chars")
        if re.search(r"\b(use (this|it)? ?(skill )?(when|whenever|for|if)|trigger|when (the )?user|invoke)", desc, re.I):
            add(sk, "frontmatter", "trigger-phrasing", 3, "description states when to use it")
        if len(desc) > 1024:
            penalise(sk, "description-too-long", 2, f"{len(desc)} chars > 1024 spec limit")
    tools = tool_list(fm.get("allowed-tools") or fm.get("allowed_tools") or fm.get("tools"))
    if tools:
        scoped = [t for t in tools if "(" in t]
        add(sk, "frontmatter", "allowed-tools", 3 + (1 if scoped else 0), ", ".join(tools[:6]))
    if fm.get("argument-hint"):
        add(sk, "frontmatter", "argument-hint", 2, str(fm["argument-hint"]))
    if fm.get("context") == "fork" or fm.get("agent"):
        add(sk, "frontmatter", "forked-context", 3, f"context={fm.get('context')} agent={fm.get('agent')}")
    if fm.get("hooks"):
        add(sk, "frontmatter", "skill-hooks", 3, "frontmatter hooks")
    if fm.get("model") or fm.get("effort"):
        add(sk, "frontmatter", "model-control", 1, str(fm.get("model") or fm.get("effort")))
    if "disable-model-invocation" in fm or "user-invocable" in fm:
        add(sk, "frontmatter", "invocation-control", 1, "explicit invocation policy")
    if fm.get("license") or sk.license != "unknown":
        add(sk, "frontmatter", "license", 1, sk.license)
    if fm.get("version") or fm.get("metadata") or fm.get("compatibility"):
        add(sk, "frontmatter", "metadata", 1, "version/metadata/compatibility")

    # -- bundled resources (cap 30) -----------------------------------------
    if cls["scripts"]:
        langs = sorted({Path(s).suffix for s in cls["scripts"]})
        add(sk, "resources", "scripts", 4 + min(5, 2 * math.log2(1 + len(cls["scripts"]))),
            f"{len(cls['scripts'])} scripts ({' '.join(langs)})")
    if cls["docs"]:
        add(sk, "resources", "reference-docs", 2 + min(4, 1.5 * math.log2(1 + len(cls["docs"]))), f"{len(cls['docs'])} docs")
    if cls["assets"]:
        add(sk, "resources", "assets", 1 + min(2, math.log2(1 + len(cls["assets"]))), f"{len(cls['assets'])} assets/templates")
    if cls["tests"]:
        add(sk, "resources", "tests-or-evals", 4, f"{len(cls['tests'])} test/eval files")
    if (skill_dir / "hooks").is_dir() or (skill_dir / "hooks.json").exists():
        add(sk, "resources", "bundled-hooks", 3, "hooks/ shipped with the skill")

    linked, broken = set(), []
    for target in MD_LINK.findall(body):
        if re.match(r"^(https?:|mailto:|#|<)", target):
            continue
        t = target.split("#", 1)[0].replace("${CLAUDE_SKILL_DIR}/", "")
        if not t:
            continue
        if (skill_dir / t).exists():
            linked.add(t)
        else:
            broken.append(t)
    for t in INLINE_PATH.findall(body):
        if (skill_dir / t.rstrip(".")).exists():
            linked.add(t.rstrip("."))
    if linked:
        add(sk, "resources", "progressive-disclosure", 2 + min(3, len(linked)), f"{len(linked)} bundled files referenced")
    if broken:
        penalise(sk, "broken-links", min(10, 2 * len(broken)), ", ".join(broken[:4]))

    # -- dynamic runtime features (cap 35) -----------------------------------
    prose = FENCED.sub("", body)
    n = count(r"\$\{?ARGUMENTS\b", body, re.M) + count(r"(?<![\w$\\])\$[0-9](?![\d.,])", prose, re.M)
    if n:
        add(sk, "dynamic", "arguments", 5, f"{n} $ARGUMENTS/positional refs")
    n = count(r"(?<![`\w])!`[A-Za-z$./~][^`\n]*`", prose, re.M) + count(r"^```!", body, re.M)
    if n:
        add(sk, "dynamic", "shell-context-injection", 7, f"{n} !`cmd` injections")
    n = count(r"\$\{?CLAUDE_(SKILL_DIR|PLUGIN_ROOT|PROJECT_DIR|SESSION_ID)\}?", body, re.M)
    if n:
        add(sk, "dynamic", "env-substitution", 4, f"{n} ${{CLAUDE_*}} refs")
    if re.search(r"\b(python3?|bash|sh|node|npx|uv run|deno|bun|ruby|go run)\s+[\"']?(\$\{?CLAUDE_\w+\}?/|\./)?"
                 r"(scripts|bin|tools|lib)/", body):
        add(sk, "dynamic", "executes-bundled-code", 5, "body runs bundled scripts")
    n = count(r"\bmcp__\w+", body, re.M)
    if n:
        add(sk, "dynamic", "mcp-tools", 4, f"{n} MCP tool refs")
    if re.search(r"\b(Task|Agent) tool\b|\bsub-?agents?\b|\bparallel agents\b|subagent_type|spawn (an? )?agent", body, re.I):
        add(sk, "dynamic", "subagent-orchestration", 5, "delegates to subagents")
    if re.search(r"\bAskUserQuestion\b|\bTodoWrite\b|\bTaskCreate\b|\bWebFetch\b|\bWebSearch\b|\bNotebookEdit\b", body):
        add(sk, "dynamic", "tool-choreography", 3, "names specific Claude tools")
    if re.search(r"(^|\s)@[\w./-]+\.(md|py|json|ya?ml|ts|js)\b", body):
        add(sk, "dynamic", "file-mentions", 2, "@file references")
    if re.search(r"\b(ultrathink|think hard|extended thinking)\b", body, re.I):
        add(sk, "dynamic", "thinking-trigger", 1, "thinking keyword")

    # -- guidance depth (cap 20) ---------------------------------------------
    steps = count(r"^\s*(\d+\.|#{2,4}\s*(step|phase)\b)", body)
    if steps >= 3:
        add(sk, "guidance", "workflow-steps", min(4, 1 + steps / 4), f"{steps} ordered steps")
    n = count(r"^\s*[-*] \[[ xX]\]", body)
    if n:
        add(sk, "guidance", "checklists", 3, f"{n} checklist items")
    if re.search(r"\b(re-?run|run (it )?again|repeat|iterate|loop)\b[^\n]{0,80}\b(until|if|when)\b|\buntil [^\n]{0,40}\b(pass|succeed|clean|green)"
                 r"|\bif [^\n]{0,40}(validation|check|test)s? fail", body, re.I):
        add(sk, "guidance", "validation-loop", 3, "validate/verify feedback loop")
    n = count(r"^#{1,4}\s*(examples?|usage|sample)\b|<example>|^\*\*(input|output|example)", body)
    if n:
        add(sk, "guidance", "examples", 3, f"{n} example sections")
    blocks = count(r"^```", body) // 2
    if blocks:
        add(sk, "guidance", "code-blocks", min(3, 1 + blocks / 4), f"{blocks} code blocks")
    if re.search(r"\b(if|when)\b[^\n]{0,80}\b(then|otherwise|else)\b|decision tree|\|\s*(situation|case|if)\s*\|", body, re.I):
        add(sk, "guidance", "decision-logic", 2, "conditional branches")
    if re.search(r"^#{1,4}\s*(troubleshoot\w*|common (mistakes|pitfalls|errors)|gotchas|anti-?patterns|don'?ts?)\b", body, re.I | re.M):
        add(sk, "guidance", "pitfalls", 2, "troubleshooting/pitfalls section")
    headings = count(r"^#{1,4}\s", body)
    if headings >= 4:
        add(sk, "guidance", "structure", min(2, headings / 6), f"{headings} headings")

    # -- size sanity ---------------------------------------------------------
    if sk.lines < 15:
        penalise(sk, "too-thin", 10, f"{sk.lines} body lines")
    elif sk.lines > 800:
        penalise(sk, "bloated-body", 5, f"{sk.lines} lines; split into references/ (>500 is the guideline)")

    # -- security --------------------------------------------------------------
    scan_targets = [("SKILL.md", text)]
    for rel_f in cls["scripts"][:40]:
        try:
            scan_targets.append((rel_f, (skill_dir / rel_f).read_text(encoding="utf-8", errors="replace")[:MAX_SCAN_BYTES]))
        except OSError:
            pass
    for key, pat in RISK_PATTERNS:
        for fname, content in scan_targets:
            m = pat.search(content)
            if m:
                sk.risks.append([key, fname, m.group(0)[:80]])
                break
    if sk.risks:
        penalise(sk, "risk-flags", min(20, 10 * len(sk.risks)), ", ".join(r[0] for r in sk.risks))
    return sk


def finalise(skills: list[Skill]) -> list[Skill]:
    """Dedupe mirrors (same body), compute capped category totals and final score."""
    by_hash: dict[str, list[Skill]] = {}
    for s in skills:
        by_hash.setdefault(s.content_hash, []).append(s)
    unique = []
    for group in by_hash.values():
        group.sort(key=lambda s: (-(s.stars or 0), -len(s.feature_keys), s.source, s.rel_path))
        keep = group[0]
        keep.mirrors = [f"{g.source}:{g.rel_path}" for g in group[1:]]
        unique.append(keep)
    for s in unique:
        cats = {c: 0.0 for c in CATEGORY_CAPS}
        for cat, _key, pts, _ev in s.features:
            cats[cat] += pts
        s.categories = {c: round(min(v, CATEGORY_CAPS[c]), 1) for c, v in cats.items()}
        bonus = 0.0
        if s.mirrors:
            bonus += min(3, len(s.mirrors))
            s.features.append(["popularity", "mirrored", min(3, len(s.mirrors)), f"{len(s.mirrors)} copies elsewhere"])
        if s.stars:
            sb = min(5, math.log10(1 + s.stars))
            bonus += sb
            s.features.append(["popularity", "repo-stars", round(sb, 2), f"{s.stars} stars"])
        total = sum(s.categories.values()) + bonus + sum(p[1] for p in s.penalties)
        s.score = round(max(0.0, min(100.0, total)), 1)
    return unique


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #

def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def highlights(s: Skill, k: int = 5) -> str:
    feats = sorted((f for f in s.features if f[0] != "popularity"), key=lambda f: -f[2])
    return ", ".join(f[1] for f in feats[:k])


def md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def write_report(skills: list[Skill], all_features: list[str], out: Path, meta: dict, detail: int) -> None:
    L = [f"# Claude Skill Scraper Report", "",
         f"_Generated {meta['generated']} by skill-scraper {VERSION}_", "",
         f"- Sources scanned: **{meta['sources_ok']}** ok, {meta['sources_failed']} failed",
         f"- SKILL.md files found: **{meta['found']}**; unique after mirror dedupe: **{meta['unique']}**; shown: **{len(skills)}**",
         f"- Filters: {meta['filters'] or 'none'}", "",
         "Score = frontmatter (15) + bundled resources (30) + dynamic features (35) + guidance (20) "
         "+ popularity bonus − penalties. See `references/scoring.md`.", "",
         "## Leaderboard", "",
         "| # | Skill | Source | Score | Dyn | Res | Scripts | Highlights |",
         "|---:|---|---|---:|---:|---:|---:|---|"]
    for i, s in enumerate(skills, 1):
        warn = " ⚠️" if s.risks else ""
        link = f"{s.source_url}/tree/{s.commit or 'HEAD'}/{s.rel_path}" if s.source_url.startswith("http") else s.abs_path
        L.append(f"| {i} | [{md_escape(s.name)}]({link}){warn} | {s.source} | **{s.score}** | {s.categories['dynamic']} "
                 f"| {s.categories['resources']} | {len(s.files['scripts'])} | {md_escape(highlights(s))} |")

    L += ["", "## Feature prevalence", "", "How many of the listed skills use each feature.", "",
          "| Feature | Skills | Share |", "|---|---:|---:|"]
    total = max(1, len(skills))
    for key in all_features:
        n = sum(1 for s in skills if key in s.feature_keys)
        if n:
            L.append(f"| `{key}` | {n} | {100 * n / total:.0f}% |")

    L += ["", f"## Top {min(detail, len(skills))} in detail", ""]
    for i, s in enumerate(skills[:detail], 1):
        L += [f"### {i}. {s.name} — {s.score}", "",
              f"> {md_escape(s.description[:400]) or '_no description_'}", "",
              f"- **Source:** `{s.source}` → `{s.rel_path}`" + (f" @ `{s.commit[:10]}`" if s.commit else ""),
              f"- **License:** {s.license} · **Stars:** {s.stars if s.stars is not None else 'n/a'} · "
              f"**Body:** {s.lines} lines / {s.words} words",
              f"- **Bundle:** {len(s.files['scripts'])} scripts, {len(s.files['docs'])} docs, "
              f"{len(s.files['assets'])} assets, {len(s.files['tests'])} tests",
              f"- **Categories:** " + ", ".join(f"{c} {v}/{CATEGORY_CAPS[c]}" for c, v in s.categories.items())]
        if s.mirrors:
            L.append(f"- **Mirrors:** {', '.join(s.mirrors[:5])}")
        L += ["", "| Category | Feature | Pts | Evidence |", "|---|---|---:|---|"]
        for cat, key, pts, ev in s.features:
            L.append(f"| {cat} | `{key}` | {pts} | {md_escape(ev)} |")
        for key, pts, ev in s.penalties:
            L.append(f"| penalty | `{key}` | {pts} | {md_escape(ev)} |")
        L.append("")

    risky = [s for s in skills if s.risks]
    if risky:
        L += ["## ⚠️ Risk flags", "", "Review these by hand before installing. Harvest skips them unless `--allow-risky`.", "",
              "| Skill | Source | Flag | File | Match |", "|---|---|---|---|---|"]
        for s in risky:
            for key, fname, match in s.risks:
                L.append(f"| {md_escape(s.name)} | {s.source} | `{key}` | {fname} | `{md_escape(match)}` |")
        L.append("")
    if meta.get("errors"):
        L += ["## Source errors", ""] + [f"- `{lbl}`: {err}" for lbl, err in meta["errors"]] + [""]
    (out / "report.md").write_text("\n".join(L), encoding="utf-8")


def write_data(skills: list[Skill], out: Path, meta: dict) -> None:
    records = []
    for s in skills:
        d = {k: v for k, v in s.__dict__.items()}
        d["highlights"] = highlights(s, 8)
        records.append(d)
    (out / "skills.json").write_text(json.dumps({"meta": meta, "skills": records}, indent=2), encoding="utf-8")
    with (out / "skills.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["rank", "score", "name", "source", "path", "dynamic", "resources", "frontmatter", "guidance",
                    "scripts", "docs", "assets", "tests", "license", "stars", "risks", "features", "description"])
        for i, s in enumerate(skills, 1):
            c = s.categories
            w.writerow([i, s.score, s.name, s.source, s.rel_path, c["dynamic"], c["resources"], c["frontmatter"],
                        c["guidance"], len(s.files["scripts"]), len(s.files["docs"]), len(s.files["assets"]),
                        len(s.files["tests"]), s.license, s.stars or "", ";".join(r[0] for r in s.risks),
                        ";".join(sorted(s.feature_keys)), s.description[:300]])


def harvest(skills: list[Skill], dest: Path, allow_risky: bool) -> list[tuple[Skill, Path]]:
    """Copy skill folders (no symlinks, no huge files, never executed) with a PROVENANCE.md."""
    dest.mkdir(parents=True, exist_ok=True)
    done = []
    for s in skills:
        if s.risks and not allow_risky:
            log(f"  harvest: skipping {s.name} (risk flags: {', '.join(r[0] for r in s.risks)})")
            continue
        base = re.sub(r"[^\w.-]+", "-", s.name.lower()).strip("-") or "skill"
        target = dest / base
        if target.exists():
            target = dest / f"{base}--{s.source.split('/')[0].lower()}"
        if target.exists():
            shutil.rmtree(target)
        src_dir = Path(s.abs_path)
        target.mkdir(parents=True)
        shutil.copy2(next(p for p in src_dir.iterdir() if p.name.lower() == "skill.md"), target / "SKILL.md")
        for f in bundled_files(src_dir):
            if f.stat().st_size > MAX_HARVEST_FILE:
                continue
            out = target / f.relative_to(src_dir)
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, out)
        (target / "PROVENANCE.md").write_text("\n".join([
            f"# Provenance: {s.name}", "",
            f"- Source: {s.source_url}", f"- Path: {s.rel_path}", f"- Commit: {s.commit or 'n/a'}",
            f"- License: {s.license}", f"- Score: {s.score} ({', '.join(f'{c} {v}' for c, v in s.categories.items())})",
            f"- Harvested: {datetime.now(timezone.utc).isoformat(timespec='seconds')} by skill-scraper {VERSION}", "",
            "Harvested as untrusted third-party content. Read SKILL.md and every script before enabling it.", ""]),
            encoding="utf-8")
        done.append((s, target))
    (dest / "INDEX.md").write_text("\n".join(
        ["# Harvested skills", "", "| Skill | Score | Source | License |", "|---|---:|---|---|"] +
        [f"| [{s.name}]({t.name}/SKILL.md) | {s.score} | {s.source} | {s.license} |" for s, t in done]) + "\n",
        encoding="utf-8")
    return done


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="skill_scraper.py", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog="""
examples:
  %(prog)s                                   # curated sources.txt, top 25
  %(prog)s --discover --discover-limit 30    # + GitHub search (set GITHUB_TOKEN)
  %(prog)s --repo anthropics/skills --require scripts,arguments
  %(prog)s --local ~/.claude/skills --top 50 # audit your installed skills
  %(prog)s --query pdf,excel --harvest 5     # copy the 5 best matches with provenance
""")
    g = p.add_argument_group("sources")
    g.add_argument("--sources", type=Path, default=DEFAULT_SOURCES, help="seed list (owner/repo[@ref][:subpath] per line)")
    g.add_argument("--no-seeds", action="store_true", help="ignore the sources file")
    g.add_argument("--repo", action="append", default=[], help="extra GitHub repo or git URL (repeatable)")
    g.add_argument("--local", action="append", default=[], type=Path, help="local folder to scan (repeatable)")
    g.add_argument("--discover", action="store_true", help="find more repos via GitHub search API")
    g.add_argument("--discover-limit", type=int, default=25)
    g.add_argument("--search", action="append", default=[], help="extra GitHub repository search query")
    g.add_argument("--expand-awesome", action="store_true", help="follow repo links inside awesome-* lists")
    g.add_argument("--expand-limit", type=int, default=40, help="max repos taken from each awesome list")
    g.add_argument("--stars", action="store_true", help="fetch star counts for seeded repos (GitHub API)")
    g.add_argument("--cache", type=Path, default=DEFAULT_CACHE, help=f"clone cache (default {DEFAULT_CACHE})")
    g.add_argument("--offline", action="store_true", help="use cached clones only")
    g.add_argument("--jobs", type=int, default=6, help="parallel clones")

    f = p.add_argument_group("filter & rank")
    f.add_argument("--top", type=int, default=25, help="how many to list (0 = all)")
    f.add_argument("--min-score", type=float, default=0)
    f.add_argument("--require", default="", help="comma list of feature keys every result must have")
    f.add_argument("--query", default="", help="comma list of keywords; match name/description/path")
    f.add_argument("--sort", choices=["score", "dynamic", "resources", "guidance", "stars"], default="score")
    f.add_argument("--exclude-risky", action="store_true", help="drop skills with risk flags from results")

    o = p.add_argument_group("output")
    o.add_argument("--out", type=Path, default=Path("skill-scraper-out"), help="output folder")
    o.add_argument("--detail", type=int, default=10, help="detail cards in report.md")
    o.add_argument("--harvest", type=int, default=0, metavar="N", help="copy the top N skill folders")
    o.add_argument("--harvest-dir", type=Path, help="where to copy (default <out>/harvest)")
    o.add_argument("--allow-risky", action="store_true", help="let harvest copy risk-flagged skills")
    o.add_argument("--json", action="store_true", help="print results JSON to stdout instead of a table")
    o.add_argument("--features", action="store_true", help="list scoreable feature keys and exit")
    p.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return p


FEATURE_KEYS = [
    "valid-name", "description", "trigger-phrasing", "allowed-tools", "argument-hint", "forked-context", "skill-hooks",
    "model-control", "invocation-control", "license", "metadata",
    "scripts", "reference-docs", "assets", "tests-or-evals", "bundled-hooks", "progressive-disclosure",
    "arguments", "shell-context-injection", "env-substitution", "executes-bundled-code", "mcp-tools",
    "subagent-orchestration", "tool-choreography", "file-mentions", "thinking-trigger",
    "workflow-steps", "checklists", "validation-loop", "examples", "code-blocks", "decision-logic", "pitfalls", "structure",
    "mirrored", "repo-stars",
]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.features:
        print("\n".join(FEATURE_KEYS))
        return 0
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    sources: list[Source] = [] if args.no_seeds else load_sources(args.sources)
    sources += [s for s in (parse_spec(r, "cli") for r in args.repo) if s]
    sources += [Source("local", str(p.expanduser().resolve()), path=p.expanduser().resolve(), via="cli") for p in args.local]
    if args.discover:
        log(f"Discovering repos via GitHub search{' (authenticated)' if token else ' (unauthenticated, rate limited)'}...")
        sources += discover(args.discover_limit, token, args.search)

    def dedupe(items: list[Source]) -> list[Source]:
        seen, out = set(), []
        for s in items:
            k = (s.label.lower(), s.subpath)
            if k not in seen:
                seen.add(k)
                out.append(s)
        return out

    sources = dedupe(sources)
    if not sources:
        log("No sources. Add repos to sources.txt, or pass --repo/--local/--discover.")
        return 2

    def fetch_all(items: list[Source]) -> list[Source]:
        remote = sum(1 for s in items if s.kind == "git")
        log(f"Fetching {remote} repo(s) into {args.cache} ..." if remote else f"Scanning {len(items)} local folder(s) ...")
        with futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as ex:
            done = list(ex.map(lambda s: fetch(s, args.cache, args.offline), items))
        for s in done:
            log(f"  {'✗' if s.error else '✓'} {s.label}{' — ' + s.error if s.error else ''}")
        return done

    sources = fetch_all(sources)
    if args.expand_awesome:
        extra = []
        for s in sources:
            if s.path and "awesome" in s.label.lower():
                extra += expand_awesome(s, args.expand_limit)
        known = {s.label.lower() for s in sources}
        extra = [e for e in dedupe(extra) if e.label.lower() not in known]
        if extra:
            log(f"Expanding awesome lists: +{len(extra)} repos")
            sources += fetch_all(extra)
    if args.stars:
        fill_stars(sources, token)

    found: list[Skill] = []
    for s in sources:
        if not s.path:
            continue
        root = s.path / s.subpath if s.subpath else s.path
        if not root.exists():
            s.error = f"subpath '{s.subpath}' not found"
            continue
        for skill_md in find_skill_files(root):
            try:
                found.append(analyse(skill_md, s, s.path))
            except Exception as exc:  # one malformed skill must not sink the run
                log(f"  ! {skill_md}: {exc}")
    unique = finalise(found)

    required = {r.strip() for r in args.require.split(",") if r.strip()}
    unknown = required - set(FEATURE_KEYS)
    if unknown:
        log(f"Unknown --require feature(s): {', '.join(sorted(unknown))}. See --features.")
        return 2
    words = [w.strip().lower() for w in args.query.split(",") if w.strip()]

    def relevance(s: Skill) -> int:
        """2 = keyword in name/path, 1 = only in description, 0 = no match."""
        if not words:
            return 1
        if any(w in f"{s.name} {s.rel_path}".lower() for w in words):
            return 2
        return 1 if any(w in s.description.lower() for w in words) else 0

    results = [s for s in unique
               if s.score >= args.min_score
               and required <= s.feature_keys
               and not (args.exclude_risky and s.risks)
               and relevance(s)]
    metric = {"score": lambda s: s.score, "stars": lambda s: (s.stars or 0, s.score)}.get(
        args.sort, lambda s: (s.categories[args.sort], s.score))
    results.sort(key=lambda s: (relevance(s), metric(s)), reverse=True)
    shown = results if args.top == 0 else results[:args.top]

    args.out.mkdir(parents=True, exist_ok=True)
    meta = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "version": VERSION,
        "sources_ok": sum(1 for s in sources if s.path and not s.error),
        "sources_failed": sum(1 for s in sources if s.error),
        "errors": [(s.label, s.error) for s in sources if s.error],
        "found": len(found), "unique": len(unique), "matched": len(results),
        "filters": " ".join(filter(None, [f"min-score={args.min_score}" if args.min_score else "",
                                          f"require={','.join(sorted(required))}" if required else "",
                                          f"query={args.query}" if words else "",
                                          "exclude-risky" if args.exclude_risky else "",
                                          f"sort={args.sort}" if args.sort != "score" else ""])),
        "sources": [{"label": s.label, "via": s.via, "commit": s.commit, "stars": s.stars, "error": s.error}
                    for s in sources],
    }
    write_report(shown, FEATURE_KEYS, args.out, meta, args.detail)
    write_data(shown, args.out, meta)

    harvested = []
    if args.harvest:
        harvested = harvest(shown[:args.harvest], args.harvest_dir or args.out / "harvest", args.allow_risky)

    if args.json:
        print(json.dumps([{"rank": i, "score": s.score, "name": s.name, "source": s.source, "path": s.rel_path,
                           "categories": s.categories, "highlights": highlights(s, 8), "risks": s.risks}
                          for i, s in enumerate(shown, 1)], indent=2))
    else:
        width = max([len(s.name) for s in shown] + [5])
        width = min(width, 34)
        print(f"\n{'#':>3}  {'SCORE':>5}  {'DYN':>4}  {'RES':>4}  {'SKILL':<{width}}  SOURCE / HIGHLIGHTS")
        for i, s in enumerate(shown, 1):
            flag = " ⚠" if s.risks else ""
            print(f"{i:>3}  {s.score:>5.1f}  {s.categories['dynamic']:>4.1f}  {s.categories['resources']:>4.1f}  "
                  f"{s.name[:width]:<{width}}  {s.source}{flag}  [{highlights(s, 4)}]")
        print(f"\n{len(found)} SKILL.md found, {len(unique)} unique, {len(results)} matched filters. "
              f"Report: {args.out / 'report.md'}")
        if harvested:
            print(f"Harvested {len(harvested)} skill(s) to {(args.harvest_dir or args.out / 'harvest')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
