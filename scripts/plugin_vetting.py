"""Heuristic quality vetting for scraped AI plugins.

No one can hand-review 20,000 plugins, so each entry gets a 0-100 score from
signals that separate maintained plugins from throwaway listings, plus the
flags that explain it. A tier is derived from the score:

  recommended  >= 60   Anthropic-curated, or human-curated and cross-listed
  ok           40-59   vouched for by one human-curated list
  unvetted     20-39   self-published to a registry; nobody else vouches for it
  likely-junk  < 20    temporary hosting, template text, bulk spam or duplicates

These are signals, not proof: a "recommended" plugin can still be abandoned
and an "unvetted" one can be excellent. GitHub stars and recent commits are
not used (the API rate limit makes them impractical at this scale).
"""
import re
from collections import Counter

BASE = 20

CURATED = {"anthropics/claude-plugins-official", "anthropics/knowledge-work-plugins", "anthropics/claude-code"}
COMMUNITY_LISTS = {
    "punkpeye/awesome-mcp-servers", "wong2/awesome-mcp-servers", "appcypher/awesome-mcp-servers",
    "modelcontextprotocol/servers", "hesreallyhim/awesome-claude-code",
}

# Hosting services that mirror other people's servers are not spam publishers.
MIRROR_PUBLISHERS = {"ai.smithery"}
BULK_THRESHOLD = 40

TEMP_HOST = re.compile(r"trycloudflare\.com|ngrok|loca\.lt|localhost|127\.0\.0\.1|localtunnel|serveo\.net", re.I)
PLACEHOLDER = re.compile(
    r"^(?:an? )?mcp server(?: for [\w .-]+)?$|\bmcp server by\b|hello.?world|\b(?:test|demo|example|sample|template|my first|todo)\b(?: (?:mcp|server|app))?\s*$",
    re.I,
)


def publisher(e):
    m = re.match(r"io\.github\.([^/]+)/", e.get("id", ""))
    if m:
        return m.group(1).lower()
    if "mcp-registry" in e.get("sources", []) and "/" in e.get("id", ""):
        return e["id"].split("/")[0].lower()
    m = re.match(r"https?://github\.com/([^/]+)/", e.get("url", ""))
    return m.group(1).lower() if m else ""


def _desc_key(text):
    return re.sub(r"\W+", " ", (text or "").lower()).strip()


def vet(entries):
    """Add quality_score, tier and flags to each entry, in place."""
    pubs = Counter(publisher(e) for e in entries)
    descs = Counter(_desc_key(e.get("description")) for e in entries)

    for e in entries:
        score, flags = BASE, []
        sources = set(e.get("sources", []))
        desc = (e.get("description") or "").strip()
        ident = e.get("id", "")
        pub = publisher(e)

        if sources & CURATED:
            score += 45
            flags.append("+anthropic-marketplace")
        listed = sources & COMMUNITY_LISTS
        if listed:
            score += 20
            flags.append("+community-list")
        if len(sources) >= 2:
            score += 10 * (len(sources) - 1)
            flags.append(f"+in-{len(sources)}-sources")
        # Registry namespaces other than io.github.* require the publisher to
        # prove ownership of the domain.
        if "mcp-registry" in sources and not ident.startswith("io.github.") and pub not in MIRROR_PUBLISHERS:
            score += 5
            flags.append("+verified-domain")
        if re.match(r"https?://github\.com/[^/]+/[^/]+", e.get("url", "")):
            score += 5
            flags.append("+open-source")
        if 40 <= len(desc) <= 400:
            score += 5

        if TEMP_HOST.search(e.get("url", "")) or TEMP_HOST.search(ident):
            score -= 40
            flags.append("-temporary-tunnel-url")
        if not desc:
            score -= 20
            flags.append("-no-description")
        elif len(desc) < 25 or PLACEHOLDER.search(desc) or _desc_key(desc) == _desc_key(e.get("name")):
            score -= 25
            flags.append("-placeholder-description")
        if pub and pub not in MIRROR_PUBLISHERS and pubs[pub] > BULK_THRESHOLD and not sources & CURATED:
            score -= 20
            flags.append(f"-bulk-publisher({pubs[pub]})")
        if desc and descs[_desc_key(desc)] >= 3:
            score -= 20
            flags.append("-duplicate-description")
        if e.get("category") == "Archived":
            score -= 30
            flags.append("-archived")
        if re.search(r"\bx402\b|usdc|pay[- ]per[- ]call", desc, re.I):
            flags.append("paid-per-call")

        score = max(0, min(100, score))
        e["quality_score"] = score
        e["tier"] = (
            "recommended" if score >= 60 else
            "ok" if score >= 40 else
            "unvetted" if score >= 20 else
            "likely-junk"
        )
        e["flags"] = flags
    return entries
