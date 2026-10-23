# Scoring rubric

`skill_scraper.py` scores every `SKILL.md` it finds on a 0–100 scale. The score
rewards skills that are **comprehensive** (they ship real resources, not just a
prompt) and **dynamic** (they use the runtime features that make a skill adapt
to its input and environment). Four capped categories (15 + 30 + 35 + 20) add up to 100; a small
popularity bonus and penalties adjust the total.

Run `skill_scraper.py --features` to print every key below, and pass any of them
to `--require` (e.g. `--require scripts,shell-context-injection`).

## Frontmatter & metadata (cap 15)

| Key | Pts | Detects |
|---|---:|---|
| `valid-name` | 2 | `name` is lowercase-hyphenated, ≤ 64 chars |
| `description` | ≤ 3 | 1 pt per ~80 chars of description |
| `trigger-phrasing` | 3 | description says *when* to use it ("Use when…", "when the user…") |
| `allowed-tools` | 3–4 | pre-approved tools; +1 when scoped like `Bash(git:*)` |
| `argument-hint` | 2 | autocomplete hint for arguments |
| `forked-context` | 3 | `context: fork` or `agent:` runs the skill in a subagent |
| `skill-hooks` | 3 | lifecycle hooks declared in frontmatter |
| `model-control` | 1 | `model:` or `effort:` override |
| `invocation-control` | 1 | `disable-model-invocation` / `user-invocable` |
| `license` | 1 | license in frontmatter or a LICENSE file nearby |
| `metadata` | 1 | `version`, `metadata`, or `compatibility` |

## Bundled resources (cap 30)

| Key | Pts | Detects |
|---|---:|---|
| `scripts` | 4–9 | executable helpers (`.py .sh .js .ts …`), log-scaled by count |
| `reference-docs` | 2–6 | extra docs for progressive disclosure, log-scaled |
| `assets` | 1–3 | templates, fonts, images, schemas, data files |
| `tests-or-evals` | 4 | `tests/`, `evals/`, `test_*.py`, `*.test.ts`, `evals.json` |
| `bundled-hooks` | 3 | `hooks/` or `hooks.json` inside the skill |
| `progressive-disclosure` | 2–5 | SKILL.md links to bundled files that exist |

## Dynamic runtime features (cap 35)

Dynamic features carry the most weight. Positional `$1` and `` !`cmd` `` are only
counted in prose, not inside fenced code, so an `awk '{print $1}'` example or a
MATLAB `` `!` `` escape doesn't count as a runtime feature.

| Key | Pts | Detects |
|---|---:|---|
| `arguments` | 5 | `$ARGUMENTS`, `$ARGUMENTS[N]`, `$0`–`$9` |
| `shell-context-injection` | 7 | `` !`cmd` `` or ` ```! ` blocks that inject live output on load |
| `env-substitution` | 4 | `${CLAUDE_SKILL_DIR}`, `${CLAUDE_PLUGIN_ROOT}`, `${CLAUDE_SESSION_ID}` |
| `executes-bundled-code` | 5 | body tells Claude to run `python scripts/…`, `bash scripts/…`, etc. |
| `mcp-tools` | 4 | references `mcp__server__tool` names |
| `subagent-orchestration` | 5 | delegates to subagents / Task / Agent tool / parallel agents |
| `tool-choreography` | 3 | names specific tools (AskUserQuestion, TodoWrite, WebFetch…) |
| `file-mentions` | 2 | `@path/to/file` references |
| `thinking-trigger` | 1 | `ultrathink` / extended-thinking cues |

## Guidance depth (cap 20)

| Key | Pts | Detects |
|---|---:|---|
| `workflow-steps` | ≤ 4 | ≥ 3 numbered steps or Step/Phase headings |
| `checklists` | 3 | `- [ ]` items Claude can track |
| `validation-loop` | 3 | an explicit loop: re-run/iterate until it passes, or what to do if a check fails |
| `examples` | 3 | Example/Usage sections, `<example>` tags |
| `code-blocks` | ≤ 3 | fenced code blocks |
| `decision-logic` | 2 | if/then branches, decision tables |
| `pitfalls` | 2 | Troubleshooting / Common mistakes / Anti-patterns section |
| `structure` | ≤ 2 | ≥ 4 headings |

## Popularity bonus (uncapped by category, max +8)

| Key | Pts | Detects |
|---|---:|---|
| `mirrored` | ≤ 3 | identical body found in other repos (it gets copied because it's good) |
| `repo-stars` | ≤ 5 | `log10(stars)`, only with `--discover` or `--stars` |

## Penalties

| Key | Pts | Trigger |
|---|---:|---|
| `no-frontmatter` | −8 | no YAML frontmatter |
| `no-description` | −10 | Claude cannot auto-select a skill without one |
| `invalid-name` | −2 | name not lowercase-hyphenated |
| `description-too-long` | −2 | > 1024 chars (spec limit) |
| `broken-links` | −2 each, max −10 | markdown links to bundled files that don't exist |
| `too-thin` | −10 | < 15 body lines |
| `bloated-body` | −5 | > 800 body lines (guideline is < 500; move detail to references/) |
| `risk-flags` | −10 each, max −20 | see below |

## Risk flags

Scanned in SKILL.md and up to 40 bundled scripts. Flagged skills are marked ⚠️,
listed in their own report section, and skipped by `--harvest` unless
`--allow-risky`. A flag is a prompt to read the file, not proof of malice — a
README-style `curl … | sh` install line trips `pipe-to-shell` too.

| Flag | Pattern |
|---|---|
| `pipe-to-shell` | `curl …  \| sh`, `wget … \| bash` |
| `base64-exec` | `base64 -d … \| sh` |
| `destructive-rm` | `rm -rf /`, `rm -rf ~`, `rm -rf $HOME` |
| `skip-permissions` | `--dangerously-skip-permissions` |
| `prompt-injection` | "ignore previous instructions" |
| `embedded-secret` | AWS/GitHub/Anthropic/Slack tokens, private keys |
| `credential-read` | `~/.ssh/id_*`, `~/.aws/credentials`, `.netrc` |

## Mirror dedupe

Bodies are whitespace-normalised and hashed. Identical skills collapse to one
entry (the copy in the most-starred repo, then the richest), and the others are
listed as mirrors.
