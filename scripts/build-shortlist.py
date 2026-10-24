#!/usr/bin/env python3
"""Render catalogs/ai-plugins/shortlist.json into SHORTLIST.md.

Each pick names a catalog entry exactly (plus an optional URL substring when
several entries share a name). Links, tiers and descriptions come from
plugins.json, so nothing in the shortlist is typed by hand. Exits non-zero if
any pick is missing or ambiguous, which catches renames after a re-scrape.

Usage:
  python3 scripts/build-shortlist.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalogs" / "ai-plugins"


def resolve(entries, pick):
    hits = [e for e in entries if e["name"] == pick["name"]]
    if pick.get("match"):
        hits = [e for e in hits if pick["match"] in e["url"]]
    return hits


def md_cell(text):
    return (text or "").replace("|", "\\|")


def main():
    entries = json.loads((CATALOG / "plugins.json").read_text())
    spec = json.loads((CATALOG / "shortlist.json").read_text())
    errors, total = [], 0
    lines = [f"# {spec['title']}", "", spec["intro"], ""]
    toc = []
    body = []
    for div in spec["divisions"]:
        rows = []
        for pick in div["picks"]:
            hits = resolve(entries, pick)
            if len(hits) != 1:
                errors.append(f"{div['division']}: {pick['name']!r} matched {len(hits)} entries")
                continue
            e = hits[0]
            kind = "Claude Code plugin" if e["type"] == "claude-code-plugin" else "MCP server"
            rows.append(f"| [{md_cell(e['name'])}]({e['url']}) | {kind} | {e['tier']} | {md_cell(pick['why'])} |")
        total += len(rows)
        anchor = re.sub(r"[^a-z0-9 -]", "", div["division"].lower()).replace(" ", "-")
        toc.append(f"- [{div['division']}](#{anchor}) ({len(rows)})")
        body += ["", f"## {div['division']}", "", "| Plugin | Type | Tier | Why |", "|---|---|---|---|", *rows]
    if errors:
        print("Shortlist picks that did not resolve to exactly one catalog entry:", file=sys.stderr)
        print("\n".join("  " + x for x in errors), file=sys.stderr)
        return 1
    lines += [f"{total} picks across {len(spec['divisions'])} groups. Tier is the catalog's heuristic vetting tier.", ""]
    lines += toc + body
    (CATALOG / "SHORTLIST.md").write_text("\n".join(lines) + "\n")
    print(f"{total} picks written to {CATALOG / 'SHORTLIST.md'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
