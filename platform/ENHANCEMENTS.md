# Reverse-engineering notes & enhancement roadmap

## How the upstream project works

| Layer | Files | Role |
|---|---|---|
| Corpus | `<division>/*.md` (282 agents, 18 divisions) | YAML frontmatter (`name`, `description`, `color`, `emoji`, `vibe`, optional `tools`) + a markdown system prompt |
| Catalogs | `divisions.json`, `tools.json`, `strategy/runbooks.json` | Single sources of truth for divisions, target tools and team rosters; consumed by the desktop app |
| Converters | `scripts/convert.sh`, `scripts/lib.sh` | Render each agent into 15+ tool formats (Cursor rules, Copilot, Gemini, Aider roster, Codex, Hermes plugin…) under `integrations/` |
| Installer | `scripts/install.sh` | Detects installed tools and copies/links rendered files |
| Guards | `scripts/check-*.sh`, `scripts/test-*.sh`, `.github/workflows/` | Keep catalogs, converters and directories in sync; lint frontmatter |
| Doctrine | `strategy/` | NEXUS playbooks, runbooks and handoff templates — prose only |

**Key observation:** everything stops at *distribution*. Agents are static prompts copied into
other tools. Nothing in the repo searches them, picks them for a task, measures their quality,
runs them together, or remembers anything between runs. `integrations/mcp-memory` describes a
memory contract but tells you to bring your own server.

## Gaps found → what the platform adds

| Gap | Evidence | Added |
|---|---|---|
| No way to find the right agent among 282 without reading the README tables | README roster | `agency search` (BM25, hyphen-insensitive, field-weighted) |
| Team assembly is manual; runbooks are prose | `strategy/runbooks/*.md` | `agency team` router (clause-aware, division caps, orchestrator lead) + `agency runbook` |
| Quality varies across agents | 24 agents grade D, 26 grade C; most often missing *Deliverables* (63), *Communication* (37), *Success Metrics* (36); weakest divisions: gis, specialized, paid-media, spatial-computing | `agency score` with `--min` for CI gating |
| Multi-agent workflows are copy-paste | `strategy/coordination/handoff-templates.md` | `agency run` — sequential pipeline with structured handoffs via the Claude API |
| Memory server is BYO | `integrations/mcp-memory/README.md` | Built-in SQLite `remember/recall/search/rollback` |
| Agents only reach tools via file conversion | `scripts/convert.sh` | MCP server: every agent is a live prompt + 9 tools, works in any MCP client with no conversion |
| No browsable UI outside the paid desktop app | README | `agency serve` dashboard |
| No machine-readable full index | app builds its own | `agency catalog` |

## Tools worth adding to your setup

`agency doctor` checks for these and prints install commands:

- **Claude Code** + this repo's MCP server — agents as prompts, team routing and memory inside your sessions.
- **promptfoo** — regression-test agent prompts (pair it with `agency run --dry-run` output as fixtures).
- **uv** — fast Python env/tool management for running the platform anywhere.
- **Gemini CLI / Codex CLI / Aider / OpenCode** — already supported by `scripts/convert.sh`; doctor shows which you lack.
- Community **agency-orchestrator** (upstream discussion #461) — a YAML workflow engine; complementary to `agency run`.

## Roadmap (not yet built)

1. Parallel fan-out + reviewer agent (orchestrator → N specialists → Reality Checker gate).
2. Embedding search (optional, when an embeddings endpoint is configured) for paraphrase matching.
3. LLM-as-judge evals per agent (`agency eval <slug>`) with stored scores in the catalog.
4. Auto-fix PRs for D-grade agents: generate the missing template sections, human review.
5. Run runbooks end-to-end: `agency run --runbook startup-mvp` honoring `activation` phases.

## Disadvantages → strengths

Each disadvantage from the original review, the fix researched for it, and what now ships.

### 1. "Agent quality varies; missing sections and frontmatter fixes still landing"
- **Fix researched:** treat prompts like code — measurable quality bar, automated gates, assisted repair.
- **Shipped:** `agency score` grades all 282 agents; `agency fix` repairs missing sections (offline scaffold
  or `--ai` in the agent's voice); `agency triage --strict` blocks invalid files in CI.
- **Strength:** the only agent library with a published, enforced quality grade per agent and a one-command
  path from D to A. Current baseline: A 190 · B 42 · C 26 · D 24.

### 2. "Agents are prompts, so results depend on the model and how you invoke them"
- **Fix researched:** LLM-as-judge rubric evals (promptfoo `llm-rubric` pattern) and a fixed invocation contract.
- **Shipped:** `agency eval` builds each agent's rubric from its *own* Success Metrics + Critical Rules,
  generates scenarios from its Core Mission, and runs them across several models (`--models a,b,c`)
  to produce a portability matrix. `--promptfoo` exports the same suite for any provider.
  Every run (`agency run`, evals) wraps the task in one standard brief: assumptions, deliverable, risks, handoff.
- **Strength:** "model-agnostic" stops being a claim and becomes a measured, per-model score.

### 3. "Using them outside Claude Code may take adaptation"
- **Fix researched:** the Agent Skills open standard (SKILL.md, published Dec 2025, agentskills.io),
  AGENTS.md (agents.md), and MCP.
- **Shipped:** `agency export skills` (spec-compliant names/descriptions), `agency export agents-md`,
  `json`, `txt`; plus the MCP server, which serves every agent as a prompt to any MCP client.
- **Strength:** one source, every runtime — native files for 15+ tools via `convert.sh`, open standards
  for everything else, and a live server for anything MCP-capable.

### 4. "142 open PRs; maintainer review looks backlogged"
- **Fix researched:** CI triage bots with duplicate detection and completeness checks (GitHub Continuous AI,
  PR Triage Bot pattern).
- **Shipped:** `agency triage` + `.github/workflows/agent-triage.yml`: every PR touching agent files gets a
  sticky comment with verdict (ready / needs-work / possible-duplicate / invalid), grade, missing sections
  and the nearest existing agents (TF-IDF cosine). Fork-safe: read-only token, report in the job summary.
  `agency overlaps` audits the whole corpus for near-duplicates.
- **Strength:** contributors self-correct before a human looks; maintainers review only "ready" PRs.
