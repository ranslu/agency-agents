"""`agency` command-line interface."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from .corpus import REPO_ROOT, by_slug, load_corpus, load_runbooks
from .memory import Memory
from .quality import score_agent
from .search import Index


def _line(a, extra: str = "") -> str:
    return f"{a.emoji or '•'} {a.slug:<48} {a.name}{extra}"


def cmd_list(args):
    for a in load_corpus():
        if not args.division or a.division == args.division:
            print(_line(a))


def cmd_search(args):
    for a, s in Index().search(" ".join(args.query), args.limit, args.division):
        print(_line(a, f"  ({s:.1f})"))
        print(f"    {a.description[:140]}")


def cmd_show(args):
    a = by_slug().get(args.slug)
    if not a:
        sys.exit(f"unknown agent {args.slug!r}")
    print(a.prompt if args.prompt else json.dumps(a.summary(), indent=2))


def cmd_team(args):
    team = Index().recommend_team(" ".join(args.task), args.size)
    for a, _ in team:
        print(_line(a, f"  [{a.division}]"))
    if args.slugs:
        print(",".join(a.slug for a, _ in team))


def cmd_runbook(args):
    books = load_runbooks()
    if not args.slug:
        for b in books:
            print(f"{b['slug']:<24} {b['title']} — {b['mode']}")
        return
    book = next((b for b in books if b["slug"] == args.slug), None)
    if not book:
        sys.exit(f"unknown runbook {args.slug!r}")
    for g in book["roster"]:
        print(f"\n## {g['group']} ({g['activation']})")
        for s in g["agents"]:
            print(f"  - {s}")


def cmd_score(args):
    reports = sorted((score_agent(a) for a in load_corpus()), key=lambda r: r.score)
    if args.slug:
        reports = [r for r in reports if r.slug == args.slug]
    if args.json:
        print(json.dumps([{**r.__dict__, "grade": r.grade} for r in reports], indent=2))
        return
    for r in reports[: args.limit or None]:
        issues = ", ".join([f"missing {m}" for m in r.missing] + r.notes)
        print(f"{r.grade} {r.score:>3}  {r.slug:<48} {issues}")
    grades = {g: sum(r.grade == g for r in reports) for g in "ABCD"}
    print(f"\n{len(reports)} agents  " + "  ".join(f"{g}:{n}" for g, n in grades.items()))
    if args.min and any(r.score < args.min for r in reports):
        sys.exit(1)


def cmd_run(args):
    from .runner import run_pipeline

    agents_by = by_slug()
    slugs = args.agents.split(",") if args.agents else [a.slug for a, _ in Index().recommend_team(args.task, args.size)]
    missing = [s for s in slugs if s not in agents_by]
    if missing:
        sys.exit(f"unknown agents: {', '.join(missing)}")
    dry = args.dry_run or not os.environ.get("ANTHROPIC_API_KEY")
    if dry and not args.dry_run:
        print("ANTHROPIC_API_KEY not set — doing a dry run.\n", file=sys.stderr)
    out_dir = Path(args.out) if args.out else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    def on_step(step):
        print(f"\n{'=' * 72}\n{step.agent.emoji} {step.agent.name}\n{'=' * 72}")
        print(step.prompt if dry else step.output)
        if out_dir:
            n = len(list(out_dir.glob("*.md"))) + 1
            (out_dir / f"{n:02d}-{step.agent.slug}.md").write_text(step.output)

    run_pipeline(args.task, [agents_by[s] for s in slugs], model=args.model, dry_run=dry,
                 memory=Memory() if args.memory else None, project=args.project, on_step=on_step)


def cmd_memory(args):
    m = Memory()
    if args.action == "remember":
        print(m.remember(" ".join(args.text), args.project, args.agent or "any", checkpoint=args.checkpoint))
    elif args.action == "recall":
        rows = m.recall(args.project, args.agent)
    elif args.action == "search":
        rows = m.search(" ".join(args.text), args.project)
    elif args.action == "rollback":
        print(f"removed {m.rollback(args.checkpoint, args.project)}")
    if args.action in ("recall", "search"):
        for r in rows:
            print(f"#{r['id']} [{r['agent']}] {r['content'][:200]}")


def cmd_catalog(args):
    data = {"agents": [a.summary() for a in load_corpus()], "runbooks": load_runbooks()}
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text)
        print(f"wrote {len(data['agents'])} agents to {args.out}")
    else:
        print(text)


def _select(args):
    agents = list(load_corpus())
    if getattr(args, "slug", None):
        agents = [a for a in agents if a.slug == args.slug]
        if not agents:
            sys.exit(f"unknown agent {args.slug!r}")
    if getattr(args, "grade", None):
        agents = [a for a in agents if score_agent(a).grade in args.grade.upper()]
    if getattr(args, "division", None):
        agents = [a for a in agents if a.division == args.division]
    return agents


def cmd_fix(args):
    from .fix import fix_agent, unified

    if not (args.slug or args.grade):
        sys.exit("pass a slug or --grade (e.g. --grade D)")
    if args.ai and not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("--ai needs ANTHROPIC_API_KEY")
    changed = 0
    for a in _select(args):
        original, fixed, added = fix_agent(a, use_ai=args.ai)
        if not added:
            continue
        changed += 1
        if args.write:
            (REPO_ROOT / a.path).write_text(fixed, encoding="utf-8")
            print(f"fixed {a.path}: added {', '.join(added)}")
        else:
            print(unified(a, original, fixed))
    print(f"{changed} agent(s) {'updated' if args.write else 'would change (use --write)'}", file=sys.stderr)


def cmd_eval(args):
    from .evals import promptfoo_config, run_eval

    agents = _select(args)
    if args.promptfoo:
        providers = [f"anthropic:messages:{m}" for m in args.models.split(",")]
        Path(args.promptfoo).write_text(promptfoo_config(agents, providers))
        print(f"wrote {args.promptfoo} — run: npx promptfoo eval -c {args.promptfoo}")
        return
    if not args.slug:
        sys.exit("live eval needs a slug (or use --promptfoo for batch)")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("live eval needs ANTHROPIC_API_KEY (or use --promptfoo to export the suite)")
    results = run_eval(agents[0], args.models.split(","), args.n, args.judge)
    by_model: dict[str, list] = {}
    for r in results:
        by_model.setdefault(r.model, []).append(r)
        print(f"{'PASS' if r.passed else 'FAIL'} {r.score:>4.1f}  {r.model:<22} {r.scenario[:70]}")
        for reason in r.reasons:
            print(f"        - {reason}")
    print()
    for model, rs in by_model.items():
        print(f"{model:<24} avg {sum(r.score for r in rs) / len(rs):.1f}/10  pass {sum(r.passed for r in rs)}/{len(rs)}")


def cmd_export(args):
    from .export import export

    agents = _select(args)
    if getattr(args, "slugs", None):
        wanted = [s.strip() for s in args.slugs.split(",") if s.strip()]
        known = {a.slug for a in agents}
        missing = [s for s in wanted if s not in known]
        if missing:
            sys.exit(f"unknown agents: {', '.join(missing)}")
        agents = [a for a in agents if a.slug in wanted]
    n = export(agents, args.format, Path(args.out))
    print(f"exported {n} agents as {args.format} to {args.out}")


def cmd_triage(args):
    from .triage import changed_files, render, review_file

    files = args.files or changed_files(args.base)
    reviews = [r for r in (review_file(f) for f in files) if r]
    text = render(reviews)
    if args.out:
        Path(args.out).write_text(text)
    print(text)
    if args.strict and any(r.verdict in ("invalid", "possible-duplicate") for r in reviews):
        sys.exit(1)


def cmd_overlaps(args):
    from .similarity import _vectors, cosine

    agents = list(load_corpus())
    vecs = _vectors(agents)
    pairs = []
    for i in range(len(agents)):
        for j in range(i + 1, len(agents)):
            s = cosine(vecs[i], vecs[j])
            if s >= args.threshold:
                pairs.append((s, agents[i].slug, agents[j].slug))
    for s, a, b in sorted(pairs, reverse=True)[: args.limit]:
        print(f"{s:.2f}  {a}  <->  {b}")
    print(f"\n{len(pairs)} pair(s) at or above {args.threshold}")


TOOL_HINTS = [
    ("claude", "Claude Code", "npm i -g @anthropic-ai/claude-code"),
    ("cursor", "Cursor", "https://cursor.com"),
    ("gemini", "Gemini CLI", "npm i -g @google/gemini-cli"),
    ("codex", "OpenAI Codex CLI", "npm i -g @openai/codex"),
    ("aider", "Aider", "pip install aider-chat"),
    ("opencode", "OpenCode", "npm i -g opencode-ai"),
    ("promptfoo", "promptfoo (used by `agency eval --promptfoo`)", "npm i -g promptfoo"),
    ("uv", "uv (fast Python tooling)", "curl -LsSf https://astral.sh/uv/install.sh | sh"),
]


def cmd_doctor(args):
    print("AI tooling on this machine:\n")
    for binary, label, how in TOOL_HINTS:
        found = shutil.which(binary)
        print(f"  {'✔' if found else '✘'} {label:<26} {found or 'install: ' + how}")
    claude_dir = Path.home() / ".claude" / "agents"
    installed = {p.stem for p in claude_dir.glob("*.md")} if claude_dir.exists() else set()
    corpus = {a.slug for a in load_corpus()}
    print(f"\nClaude Code agents installed: {len(installed & corpus)}/{len(corpus)} ({claude_dir})")
    print(f"API key for `agency run`: {'set' if os.environ.get('ANTHROPIC_API_KEY') else 'not set'}")
    entry = Path(__file__).resolve().parents[1] / "agency.py"
    print("\nRegister the MCP server with Claude Code:")
    print(f"  claude mcp add agency -- python3 {entry} mcp")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="agency", description="Search, route, score, orchestrate and serve The Agency's agents.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("list", help="list agents"); s.add_argument("--division"); s.set_defaults(fn=cmd_list)
    s = sub.add_parser("search", help="find agents for a need"); s.add_argument("query", nargs="+")
    s.add_argument("-n", "--limit", type=int, default=10); s.add_argument("--division"); s.set_defaults(fn=cmd_search)
    s = sub.add_parser("show", help="show one agent"); s.add_argument("slug")
    s.add_argument("--prompt", action="store_true", help="print the system prompt"); s.set_defaults(fn=cmd_show)
    s = sub.add_parser("team", help="recommend a team for a task"); s.add_argument("task", nargs="+")
    s.add_argument("-n", "--size", type=int, default=5); s.add_argument("--slugs", action="store_true"); s.set_defaults(fn=cmd_team)
    s = sub.add_parser("runbook", help="list runbooks or show a roster"); s.add_argument("slug", nargs="?"); s.set_defaults(fn=cmd_runbook)
    s = sub.add_parser("score", help="quality audit of agent files"); s.add_argument("slug", nargs="?")
    s.add_argument("-n", "--limit", type=int, default=0); s.add_argument("--json", action="store_true")
    s.add_argument("--min", type=int, default=0, help="exit 1 if any agent scores below this"); s.set_defaults(fn=cmd_score)
    s = sub.add_parser("run", help="run a multi-agent pipeline via the Claude API"); s.add_argument("task")
    s.add_argument("--agents", help="comma-separated slugs (default: recommended team)")
    s.add_argument("-n", "--size", type=int, default=3); s.add_argument("--model", default=os.environ.get("AGENCY_MODEL", "claude-sonnet-5-5"))
    s.add_argument("--dry-run", action="store_true"); s.add_argument("--memory", action="store_true", help="read/write project memory")
    s.add_argument("--project", default="default"); s.add_argument("--out", help="write each step's output to this dir"); s.set_defaults(fn=cmd_run)
    s = sub.add_parser("memory", help="persistent project memory"); s.add_argument("action", choices=["remember", "recall", "search", "rollback"])
    s.add_argument("text", nargs="*"); s.add_argument("--project", default="default"); s.add_argument("--agent")
    s.add_argument("--checkpoint"); s.set_defaults(fn=cmd_memory)
    s = sub.add_parser("catalog", help="export a JSON catalog"); s.add_argument("-o", "--out"); s.set_defaults(fn=cmd_catalog)
    s = sub.add_parser("doctor", help="check installed AI tools and setup"); s.set_defaults(fn=cmd_doctor)
    s = sub.add_parser("fix", help="add missing template sections (scaffold, or --ai)"); s.add_argument("slug", nargs="?")
    s.add_argument("--grade", help="fix every agent with these grades, e.g. D or CD"); s.add_argument("--division")
    s.add_argument("--ai", action="store_true", help="write sections with Claude"); s.add_argument("--write", action="store_true")
    s.set_defaults(fn=cmd_fix)
    s = sub.add_parser("eval", help="behavioural eval: rubric from the agent's own metrics/rules"); s.add_argument("slug", nargs="?")
    s.add_argument("--models", default=os.environ.get("AGENCY_MODEL", "claude-sonnet-5-5"), help="comma-separated models to compare")
    s.add_argument("--judge", default=os.environ.get("AGENCY_JUDGE_MODEL", "claude-opus-5-5")); s.add_argument("-n", type=int, default=3)
    s.add_argument("--grade"); s.add_argument("--division")
    s.add_argument("--promptfoo", metavar="FILE", help="export a promptfoo suite instead of running"); s.set_defaults(fn=cmd_eval)
    s = sub.add_parser("export", help="export to open formats (skills, skill-bundle, agents-md, json, txt)")
    s.add_argument("format", choices=["skills", "skill-bundle", "agents-md", "json", "txt"]); s.add_argument("-o", "--out", default="dist")
    s.add_argument("--division"); s.add_argument("--grade")
    s.add_argument("--slugs", help="comma-separated agent slugs to export (default: all)"); s.set_defaults(fn=cmd_export)
    s = sub.add_parser("triage", help="first-pass review of changed agent files (for PRs)"); s.add_argument("files", nargs="*")
    s.add_argument("--base", default="origin/main"); s.add_argument("--out"); s.add_argument("--strict", action="store_true")
    s.set_defaults(fn=cmd_triage)
    s = sub.add_parser("overlaps", help="find near-duplicate agents in the corpus"); s.add_argument("--threshold", type=float, default=0.6)
    s.add_argument("-n", "--limit", type=int, default=25); s.set_defaults(fn=cmd_overlaps)
    s = sub.add_parser("mcp", help="run the MCP server on stdio")
    s.set_defaults(fn=lambda a: __import__("agency_platform.mcp_server", fromlist=["x"]).serve_stdio())
    s = sub.add_parser("serve", help="run the web dashboard"); s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8787)
    s.set_defaults(fn=lambda a: __import__("agency_platform.web", fromlist=["x"]).serve(a.host, a.port))

    args = p.parse_args(argv)
    if args.cmd == "memory" and args.action == "rollback" and not args.checkpoint:
        p.error("rollback needs --checkpoint")
    args.fn(args)
