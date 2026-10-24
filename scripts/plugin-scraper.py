#!/usr/bin/env python3
"""Scrape public catalogs of AI plugins (MCP servers and Claude Code plugins).

Sources:
  - The official MCP Registry API (registry.modelcontextprotocol.io)
  - Claude Code plugin marketplaces (marketplace.json files)
  - Community awesome-lists of MCP servers and Claude Code extensions

Every entry is normalised to {name, type, category, description, url, sources},
de-duplicated by repository/homepage URL, given a topic category when its source
has none (plugin_categories.py), vetted with a heuristic quality tier
(plugin_vetting.py), and written as JSON, CSV and Markdown. Standard library only.

Usage:
  python3 scripts/plugin-scraper.py --out catalogs/ai-plugins
  python3 scripts/plugin-scraper.py --skip registry --min 1000
  python3 scripts/plugin-scraper.py --from-json catalogs/ai-plugins/plugins.json
"""
import argparse
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plugin_categories import GENERIC, categorise  # noqa: E402
from plugin_vetting import vet  # noqa: E402

USER_AGENT = "agency-agents-plugin-scraper/1.0"
REGISTRY_URL = "https://registry.modelcontextprotocol.io/v0/servers"

MARKETPLACES = {
    "anthropics/claude-plugins-official": "https://raw.githubusercontent.com/anthropics/claude-plugins-official/main/.claude-plugin/marketplace.json",
    "anthropics/knowledge-work-plugins": "https://raw.githubusercontent.com/anthropics/knowledge-work-plugins/main/.claude-plugin/marketplace.json",
    "anthropics/claude-code": "https://raw.githubusercontent.com/anthropics/claude-code/main/.claude-plugin/marketplace.json",
}

# (source label, raw README URL, entry type)
AWESOME_LISTS = [
    ("punkpeye/awesome-mcp-servers", "https://raw.githubusercontent.com/punkpeye/awesome-mcp-servers/main/README.md", "mcp-server"),
    ("wong2/awesome-mcp-servers", "https://raw.githubusercontent.com/wong2/awesome-mcp-servers/main/README.md", "mcp-server"),
    ("appcypher/awesome-mcp-servers", "https://raw.githubusercontent.com/appcypher/awesome-mcp-servers/main/README.md", "mcp-server"),
    ("modelcontextprotocol/servers", "https://raw.githubusercontent.com/modelcontextprotocol/servers/main/README.md", "mcp-server"),
    ("hesreallyhim/awesome-claude-code", "https://raw.githubusercontent.com/hesreallyhim/awesome-claude-code/main/README.md", "claude-code-extension"),
]

# Headings whose links are navigation or meta, not plugins.
SKIP_HEADINGS = re.compile(
    r"content|contributing|license|star history|tutorial|community|legend|"
    r"what is|getting started|resources|related|sponsor|table of",
    re.I,
)
LIST_ITEM = re.compile(r"^\s*[-*]\s+(?:\*\*)?\[([^\]]+)\]\((https?://[^)\s]+)\)(?:\*\*)?(.*)$")
HEADING = re.compile(r"^(#{2,4})\s+(.*)$")
BADGE = re.compile(r"\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)|!\[[^\]]*\]\([^)]*\)")
MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")


def fetch(url, retries=4):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** (attempt + 1))


def clean_text(text):
    text = BADGE.sub("", text)
    text = MD_LINK.sub(r"\1", text)
    text = re.sub(r"[^\w\s.,;:!?()'\"/&+%#@$-]", "", text)  # drop emoji markers
    text = re.sub(r"^\s*[-–—:]+\s*", "", text.strip())
    return re.sub(r"\s+", " ", text).strip()


def clean_heading(text):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>|[^\w\s&/,+.-]", "", text)).strip()


def norm_url(url):
    if not url:
        return ""
    url = url.strip().lower().rstrip("/")
    url = re.sub(r"\.git$", "", url)
    url = re.sub(r"^https?://(www\.)?", "", url)
    m = re.match(r"github\.com/([^/]+/[^/#?]+)", url)
    return "github.com/" + m.group(1) if m else url.split("#")[0]


def scrape_registry(max_pages):
    latest = {}
    cursor = None
    for _ in range(max_pages):
        params = {"limit": "100"}
        if cursor:
            params["cursor"] = cursor
        data = json.loads(fetch(REGISTRY_URL + "?" + urllib.parse.urlencode(params)))
        for item in data.get("servers", []):
            srv = item.get("server", {})
            meta = item.get("_meta", {}).get("io.modelcontextprotocol.registry/official", {})
            if meta.get("status", "active") != "active" or not srv.get("name"):
                continue
            # Later versions overwrite earlier ones; isLatest wins outright.
            if meta.get("isLatest") or srv["name"] not in latest or not latest[srv["name"]][1]:
                latest[srv["name"]] = (srv, bool(meta.get("isLatest")))
        cursor = data.get("metadata", {}).get("nextCursor")
        if not cursor:
            break
    out = []
    for name, (srv, _) in latest.items():
        repo = (srv.get("repository") or {}).get("url", "")
        remote = next((r.get("url") for r in srv.get("remotes", []) if r.get("url")), "")
        url = repo or srv.get("websiteUrl") or remote
        out.append({
            "name": srv.get("title") or name,
            "id": name,
            "type": "mcp-server",
            "category": "remote" if srv.get("remotes") else "package",
            "description": clean_text(srv.get("description", "")),
            "url": url or f"https://registry.modelcontextprotocol.io/v0/servers?search={urllib.parse.quote(name)}",
            "sources": ["mcp-registry"],
        })
    return out


def plugin_source_url(label, src):
    """Link to a plugin's own folder, not just the marketplace or monorepo root."""
    if isinstance(src, str) and not src.startswith("http"):
        return f"https://github.com/{label}/tree/main/{src.lstrip('./')}".rstrip("/")
    if isinstance(src, dict):
        base = src.get("url") or (f"https://github.com/{src['repo']}" if src.get("repo") else "")
        if base and not base.startswith("http"):
            base = f"https://github.com/{base}"
        base = re.sub(r"\.git$", "", base)
        if base and src.get("path"):
            return f"{base}/tree/{src.get('ref') or 'main'}/{src['path'].strip('/')}"
        if base:
            return base
    return f"https://github.com/{label}"


def scrape_marketplace(label, url):
    data = json.loads(fetch(url))
    out = []
    for p in data.get("plugins", []):
        link = p.get("homepage") or plugin_source_url(label, p.get("source"))
        out.append({
            "name": p.get("name", ""),
            "id": p.get("name", ""),
            "type": "claude-code-plugin",
            "category": p.get("category", "") or "uncategorized",
            "description": clean_text(p.get("description", "")),
            "url": link,
            "sources": [label],
        })
    return out


def scrape_awesome(label, url, entry_type):
    out = []
    heading = ""
    skipping = False
    for line in fetch(url).splitlines():
        h = HEADING.match(line)
        if h:
            heading = clean_heading(h.group(2))
            skipping = bool(SKIP_HEADINGS.search(heading))
            continue
        if skipping:
            continue
        m = LIST_ITEM.match(line)
        if not m:
            continue
        name, link, rest = m.groups()
        if "glama.ai/mcp/servers" in link and "badge" in link:
            continue
        out.append({
            "name": clean_text(name) or link,
            "id": norm_url(link),
            "type": entry_type,
            "category": heading or "uncategorized",
            "description": clean_text(rest),
            "url": link,
            "sources": [label],
        })
    return out


def merge(entries):
    merged = {}
    for e in entries:
        # Many plugins share one marketplace repo or vendor homepage, so plugins
        # are keyed by name; everything else by repo/homepage URL.
        if e["type"] == "claude-code-plugin":
            key = "plugin:" + e["name"].lower()
        else:
            key = norm_url(e["url"]) or e["id"].lower()
        if key in merged:
            cur = merged[key]
            cur["sources"] = sorted(set(cur["sources"]) | set(e["sources"]))
            if len(e["description"]) > len(cur["description"]):
                cur["description"] = e["description"]
            if cur["category"] in GENERIC and e["category"] not in GENERIC:
                if cur["category"] in ("remote", "package"):
                    cur["hosting"] = cur["category"]
                cur["category"] = e["category"]
            if cur["type"] == "mcp-server" and e["type"] == "claude-code-plugin":
                cur["type"] = e["type"]
        else:
            merged[key] = dict(e)
    return sorted(merged.values(), key=lambda e: (e["type"], e["category"].lower(), e["name"].lower()))


def md_cell(text, limit=160):
    text = text.replace("|", "\\|")
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def write_outputs(entries, outdir, errors):
    outdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    (outdir / "plugins.json").write_text(json.dumps(entries, indent=1, ensure_ascii=False) + "\n")
    with open(outdir / "plugins.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "type", "category", "category_source", "tier", "quality_score", "flags",
                    "hosting", "description", "url", "sources"])
        for e in entries:
            w.writerow([e["name"], e["type"], e["category"], e.get("category_source", ""), e.get("tier", ""),
                        e.get("quality_score", ""), ";".join(e.get("flags", [])), e.get("hosting", ""),
                        e["description"], e["url"], ";".join(e["sources"])])

    by_type, by_source, by_tier = {}, {}, {}
    for e in entries:
        by_type[e["type"]] = by_type.get(e["type"], 0) + 1
        by_tier[e.get("tier", "")] = by_tier.get(e.get("tier", ""), 0) + 1
        for s in e["sources"]:
            by_source[s] = by_source.get(s, 0) + 1

    lines = [
        "# AI Plugin Catalog",
        "",
        f"{len(entries):,} unique AI plugins scraped on {stamp} with `scripts/plugin-scraper.py`.",
        "Machine-readable copies: [plugins.json](plugins.json), [plugins.csv](plugins.csv).",
        "",
        "| Type | Count |", "|---|---|",
        *[f"| {t} | {n:,} |" for t, n in sorted(by_type.items())],
        "",
        "| Source | Entries |", "|---|---|",
        *[f"| {s} | {n:,} |" for s, n in sorted(by_source.items(), key=lambda x: -x[1])],
        "",
        "## Vetting",
        "",
        "Each entry has a heuristic `tier` and `quality_score` (see `scripts/plugin_vetting.py`).",
        "Tiers measure who vouches for a plugin, not whether its code is good: check the repo",
        "and the permissions it asks for before installing anything.",
        "",
        "| Tier | Meaning | Count |", "|---|---|---|",
        *[f"| {t} | {TIER_MEANING[t]} | {by_tier.get(t, 0):,} |" for t in TIER_MEANING],
        "",
    ]
    if errors:
        lines += ["Sources that failed this run: " + ", ".join(errors), ""]

    # README stays small enough for GitHub to render: summary, top MCP
    # categories, and the full Claude Code tables. plugins.md has everything.
    mcp_cats = {}
    for e in entries:
        if e["type"] == "mcp-server":
            row = mcp_cats.setdefault(e["category"], {"all": 0, "recommended": 0, "likely-junk": 0})
            row["all"] += 1
            row[e.get("tier")] = row.get(e.get("tier"), 0) + 1
    readme = lines + [
        "The complete list of every entry is in [plugins.md](plugins.md). Categories marked",
        "`inferred` in the CSV were assigned from the plugin's description (`scripts/plugin_categories.py`).",
        "", "## MCP server categories", "", "| Category | All | Recommended | Likely junk |", "|---|---|---|---|",
        *[f"| {md_cell(c, 60)} | {r['all']:,} | {r['recommended']:,} | {r['likely-junk']:,} |"
          for c, r in sorted(mcp_cats.items(), key=lambda x: -x[1]["all"])],
    ]

    def table(title, rows):
        out = ["", f"## {title} ({len(rows):,})", "", "| # | Name | Category | Tier | Description |", "|---|---|---|---|---|"]
        return out + [
            f"| {i} | [{md_cell(e['name'], 60)}]({e['url']}) | {md_cell(e['category'], 40)} | {e.get('tier', '')} | {md_cell(e['description'])} |"
            for i, e in enumerate(rows, 1)
        ]

    full = list(lines)
    for e_type in sorted(by_type):
        rows = [e for e in entries if e["type"] == e_type]
        full += table(e_type, rows)
        if e_type != "mcp-server":
            readme += table(e_type, rows)
    picks = sorted(
        (e for e in entries if e["type"] == "mcp-server" and e.get("tier") == "recommended"),
        key=lambda e: (e["category"].lower(), -e.get("quality_score", 0), e["name"].lower()),
    )
    readme += table("Recommended MCP servers", picks)
    (outdir / "README.md").write_text("\n".join(readme) + "\n")
    (outdir / "plugins.md").write_text("\n".join(full) + "\n")


TIER_MEANING = {
    "recommended": "Anthropic-curated, or human-curated and cross-listed",
    "ok": "vouched for by one human-curated list",
    "unvetted": "self-published to a registry; nobody else vouches for it",
    "likely-junk": "temporary hosting, template text, bulk spam or duplicates",
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="catalogs/ai-plugins", help="output directory")
    ap.add_argument("--skip", default="", help="comma list of: registry,marketplaces,awesome")
    ap.add_argument("--max-pages", type=int, default=500, help="MCP Registry page cap (100 per page)")
    ap.add_argument("--from-json", help="re-categorise and re-vet an existing plugins.json instead of scraping")
    ap.add_argument("--min", type=int, default=0, help="exit non-zero if fewer unique plugins are found")
    args = ap.parse_args()
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}

    entries, errors = [], []
    if args.from_json:
        entries = json.loads(Path(args.from_json).read_text())
        for e in entries:
            if e.get("category_source") == "inferred":
                e["category"] = e.get("hosting", "uncategorized")
        skip = {"registry", "marketplaces", "awesome"}

    def run(label, fn, *a):
        try:
            got = fn(*a)
            print(f"  {label}: {len(got)}", file=sys.stderr)
            entries.extend(got)
        except Exception as exc:
            print(f"  {label}: FAILED ({exc})", file=sys.stderr)
            errors.append(label)

    if "registry" not in skip:
        run("mcp-registry", scrape_registry, args.max_pages)
    if "marketplaces" not in skip:
        for label, url in MARKETPLACES.items():
            run(label, scrape_marketplace, label, url)
    if "awesome" not in skip:
        for label, url, kind in AWESOME_LISTS:
            run(label, scrape_awesome, label, url, kind)

    merged = vet(categorise(merge(entries)))
    write_outputs(merged, Path(args.out), errors)
    print(f"{len(entries)} raw entries -> {len(merged)} unique plugins written to {args.out}", file=sys.stderr)
    return 1 if len(merged) < args.min else 0


if __name__ == "__main__":
    sys.exit(main())
