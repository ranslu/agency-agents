# 🧩 Agency Platform

A zero-dependency (Python 3.10+ stdlib) platform layer on top of The Agency's agent corpus.
The repository ships agents as markdown and converts them per tool; this adds the pieces
that turn the roster into something you can **query, route, audit, orchestrate and serve**.

| Feature | Command | What it adds |
|---|---|---|
| Ranked search | `agency search react performance` | BM25 over name/description/vibe/body with field weights |
| Team router | `agency team "mobile app with tiktok marketing and HIPAA compliance"` | Picks one specialist per need, caps per division, adds the orchestrator for 4+ |
| Runbook rosters | `agency runbook startup-mvp` | Reads `strategy/runbooks.json` |
| Quality audit | `agency score -n 20` | Grades every agent A–D against the house template (sections, examples, depth) |
| Pipeline runner | `agency run "Plan a SaaS launch" --agents a,b,c` | Runs agents in sequence via the Claude API with structured handoffs |
| Project memory | `agency memory remember/recall/search/rollback` | Built-in SQLite implementation of the `integrations/mcp-memory` contract |
| MCP server | `agency mcp` | Every agent as an MCP **prompt** + tools for search, teams, scoring and memory |
| Web dashboard | `agency serve` | Browse, team builder, run pipelines, quality table, runbooks at http://127.0.0.1:8787 |
| JSON catalog | `agency catalog -o catalog.json` | One machine-readable index for other apps |
| Doctor | `agency doctor` | Shows which AI CLIs you have, which you're missing, and how to install them |
| Auto-fix | `agency fix --grade D [--ai] --write` | Adds missing template sections: offline scaffold, or written by Claude in the agent's voice |
| Behavioural evals | `agency eval <slug> --models a,b` | Grades real outputs against the agent's *own* success metrics and rules; compares models |
| promptfoo suite | `agency eval --grade A --promptfoo suite.json` | Exports `llm-rubric` tests for any providers promptfoo supports |
| Open-format export | `agency export skills\|agents-md\|json\|txt -o dist` | Agent Skills (`SKILL.md`), `AGENTS.md`, JSON or plain prompts — no per-tool adaptation |
| PR triage | `agency triage --base origin/main` | First-pass review of changed agents: grade, missing sections, near-duplicates |
| Overlap finder | `agency overlaps --threshold 0.45` | Near-duplicate pairs across the whole corpus |

## Quick start

```bash
alias agency="python3 $(pwd)/platform/agency.py"
agency doctor
agency search "kubernetes cost optimization"
agency team "B2B SaaS launch with SEO and paid ads" -n 6
agency serve
```

### Run a multi-agent pipeline

```bash
export ANTHROPIC_API_KEY=sk-ant-...
agency run "Design and launch a habit-tracking app" -n 4 --memory --project habits --out runs/habits
```

Without a key (or with `--dry-run`) it prints the exact prompts each agent would receive.
`AGENCY_MODEL` overrides the model; `--memory` feeds each agent its past outputs for the project
and checkpoints every step (`agency memory rollback --checkpoint step-1 --project habits`).

### Use it from Claude Code (or any MCP client)

Opening Claude Code inside this repo connects it automatically: the root `.mcp.json` registers
the server for the project (Claude Code asks you to approve it the first time). To use it from
any directory, register it globally instead:

```bash
claude mcp add agency -- python3 /absolute/path/to/agency-agents/platform/agency.py mcp
```

Tools: `search_agents`, `get_agent`, `recommend_team`, `list_runbooks`, `score_agent`,
`remember`, `recall`, `search_memory`, `rollback`. Prompts: one per agent slug, with an optional
`task` argument. Memory lives in `~/.agency/memory.db` (override with `AGENCY_MEMORY_DB`).

## Tests

```bash
python3 -m unittest discover -s platform/tests -v
```

CI runs them in `.github/workflows/platform.yml`; `.github/workflows/agent-triage.yml` posts the
triage report on every PR that touches agent files. See [ENHANCEMENTS.md](ENHANCEMENTS.md) for the
reverse-engineering notes and the roadmap.
