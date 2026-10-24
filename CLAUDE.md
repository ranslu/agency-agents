# CLAUDE.md

## Toolbox

This repo has a vetted AI toolbox. Use it without being asked: when a task
touches one of the areas below, reach for the matching tool first, and check
the shortlist before suggesting or installing anything new.

**Where it lives**
- Shortlist (162 picks by division, with reasons): `catalogs/ai-plugins/SHORTLIST.md`,
  also in Google Drive: https://docs.google.com/spreadsheets/d/1xJrGovgrQiqYwYLguzkw2u3UirmrWRPhRy1aRqT6JWQ
  (folder: https://drive.google.com/drive/folders/1-UhVIRf5SSeqfjSDoGoGfTJrel4YcGJi)
- Full catalog (20,805 plugins, vetted into tiers): `catalogs/ai-plugins/plugins.csv`;
  filter on `tier` and ignore `likely-junk`.
- Installed plugins: `enabledPlugins` in `.claude/settings.json`.
  MCP servers: `.mcp.json`.

**MCP servers in `.mcp.json`**

| Server | Use it for | Needs |
|---|---|---|
| `agency` | Search this repo's agents, recommend a team, recall memory | nothing |
| `mermaid` | Render Mermaid diagrams (flowcharts, sequence, ER) | nothing |
| `excalidraw` | Architecture diagrams as editable Excalidraw files | nothing |
| `brave-search` | Independent web search | `BRAVE_API_KEY` |
| `apify` | Ready-made scrapers (Apify Actors) | `APIFY_TOKEN` |
| `google-maps` | Places, reviews and local data | `HASDATA_API_KEY` |
| `shodan` | Internet exposure and CVE lookups | `SHODAN_API_KEY` |
| `currents` | Debug failing or flaky Playwright tests | `CURRENTS_API_KEY` |
| `xero` | Accounting data | `XERO_CLIENT_ID`, `XERO_CLIENT_SECRET` |
| `neo4j` | Graph database queries | `NEO4J_URI`, `NEO4J_PASSWORD` |
| `dbt` | dbt models, lineage and runs | `DBT_TOKEN`, `DBT_PROD_ENV_ID` |
| `fhir` | Clinical (FHIR) records | `FHIR_SERVER_BASE_URL`, `FHIR_SERVER_ACCESS_TOKEN` |

If a server's key or network access is missing, say so in one line, name the
environment variable or host it needs, and carry on with what works. Never ask
for a key in chat; keys go in the cloud environment's secrets.

**Go-to plugins by task** (enabled in `.claude/settings.json`)
- Code: `feature-dev`, `code-review`, `pr-review-toolkit`, `code-simplifier`, `commit-commands`
- Security: `security-guidance`, `claude-security`, `semgrep`
- Research and web data: `exa`, `firecrawl`, `tavily`, `context7` for library docs
- Business work: Anthropic's `sales`, `marketing`, `finance`, `legal`, `human-resources`,
  `customer-support`, `product-management`, `operations` and `design` plugins
- Diagrams: the `mermaid` and `excalidraw` servers above

**Keeping it current**
- Re-scrape the catalog: `python3 scripts/plugin-scraper.py`
- Change the shortlist: edit `catalogs/ai-plugins/shortlist.json`, then run
  `python3 scripts/build-shortlist.py`
- Tests: `python3 scripts/test-plugin-scraper.py`
