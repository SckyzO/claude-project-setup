---
name: project-setup
description: Frame a project for Claude Code — new empty folder, existing repo without CLAUDE.md, or refresh of an existing CLAUDE.md/AGENTS.md. Detects the stack, mines past sessions for the user's corrections, asks only what the code cannot answer, proposes the plugin/skill set loaded in this repo with its token cost, then generates git, CLAUDE.md, CONTRIBUTING.md, CHANGELOG.md, docs/STATE.md and .claude/ config — writing nothing before approval. Use when the user says "nouveau projet", "cadrer ce projet", "project setup", "init this repo for Claude", "mets à jour le CLAUDE.md", "quels plugins pour ce repo", or starts work in an empty directory. Not for product specs or end-user documentation.
---

# project-setup

Goal: give future sessions in this repo the few facts they cannot derive from the
code, and load only what this repo needs. Every always-on line (CLAUDE.md,
plugin skill descriptions) costs context in every session — the bar is "would a
session fail or be corrected without it?"

Scripts (run with `python3 -I`, paths relative to this skill's base directory):
- `scripts/detect.py PATH [--stack go,python]` — mode, signals (detected + declared), proposed and missing plugins with install hints, existing files, git facts.
- `scripts/detect.py --batch ROOT [--apply]` — plugin scoping for every git repo under ROOT (dry run without `--apply`).
- `scripts/mine_corrections.py PATH [--since YYYY-MM-DD]` — the user's past corrections in this project and its worktrees.
- `scripts/plugin_costs.py --repo PATH [--json]` — installed plugins: user-level and in-repo state, always-on tokens, `keep`/`lsp` flags.
- `scripts/apply_settings.py PATH --enable … --disable … --skill-off … [--dry-run]` — the only way this skill writes `.claude/settings.local.json`.

Configuration: `data/defaults.json`, overridden by `~/.config/project-setup/config.json`
(`plugin_map`, `stack_signals`, `marketplaces` merged per entry; `always_keep`,
`batch_exclude` replaced). A script exiting with code 2 prints the reason — report
it to the user instead of guessing around it.

References — read the one a step points to, when it points to it:
- `references/questions.md` — question bank (step 3)
- `references/claude-md.md` — placement rules, template, AGENTS.md, refresh rubric (step 5)
- `references/scaffold.md` — file tiers, templates, best-practice checklist (step 5)

## Rules for every dialog

- Ask in the user's conversation language; files committed to a public repo stay in English.
- AskUserQuestion takes 1–4 questions, 2–4 options each, and always adds a free-text
  "Other". It cannot pre-select: put recommended options first and suffix their
  label with "(Recommended)". Use `multiSelect: true` whenever answers can combine.
- A list longer than 4 options is split across questions, or shown in chat with
  the 3–4 most relevant as options. Open-ended topics (traps, compatibility)
  are asked in chat, not forced into options.
- If AskUserQuestion is unavailable (headless run, tool denied), ask the same
  questions in chat as numbered lists and wait for the answer.
- Approval is an explicit yes from the user. A dismissed or timed-out dialog,
  silence, or an answer to a different question is not approval.

## Step 1 — Detect

Run `detect.py` on the target directory, then branch:

| Result | Flow |
|---|---|
| `mode: empty` (also README/LICENSE/.gitignore only) | 3 → 4 → 5 → 6 → 7 |
| `mode: unframed` | 2 → 3 → 4 → 5 → 6 |
| `mode: framed`, or `agents_md: true` | 2 → 3 (mined rules and contradictions only) → 4 → 5b → 6 |
| `inside_repo: true` | First ask: frame the enclosing repo (`git_root`) or this directory as a package of it (nested CLAUDE.md, no `git init`) |

`installed_check: skipped` means the plugin list could not be read: say so,
and do not present `plugins` as verified installed.

## Step 2 — Gather evidence (existing repo)

Before asking anything; each fact found here is a question not asked.
- Read `CONTRIBUTING.md` in full if present, plus README, task runner, CI
  workflows, `.claude/`, `CLAUDE.md`/`AGENTS.md`, `docs/STATE.md`.
- Run `mine_corrections.py`. Group hits, discard one-offs, keep what recurs or
  reveals a project rule (tooling, forbidden actions, language, workflow order).
  Keep dates as evidence for the user. In committed files, rules are rephrased
  as instructions: no quotes, no hostnames, internal URLs, client or people's
  names, and never anything near a `[REDACTED]` marker.
- Note doc/code contradictions (README says `npm test`, CI runs `make test`) —
  they become questions.

## Step 3 — Ask (only the gaps)

1. **Open pitch first** (empty mode, or when the README doesn't say what the
   project is). Ask in plain chat: "Describe in one or two sentences what this
   project should do, for whom, anything already decided — and its name, if it
   has one." Never guess the purpose from the folder name. If there is no name
   yet, propose two or three in the first dialog round (the folder name among
   them): the name lands in README, CLAUDE.md, LICENSE and config paths, so it
   is settled before any file is drafted.
2. **Tailored dialogs**, built from the pitch and the detection, at most two
   rounds (see `references/questions.md` for the bank and the empty-mode rounds).
   Skip anything already established.
3. Declared stacks: re-run `detect.py PATH --stack <choices>` so an empty repo
   gets its plugins before any code exists. Report `unknown_stacks`.

## Step 4 — Session budget: plugins and skills for this repo

Run `plugin_costs.py --repo PATH`. Show one table, including plugins currently
off in this repo, so a wrong earlier choice is visible:

| Plugin | Always-on tok | User level | In this repo | Proposed | Why |
|---|---|---|---|---|---|

Inputs: detected signals, declared stacks, the pitch, and — when it exists — a
spec or plan (`docs/specs/`, `docs/plans/`, a brainstorming output). A spec that
introduces a frontend, a dashboard or a new language is a reason to enable a plugin.

Proposals:
- **Enable** the plugins `detect.py` proposes, plus any the user named.
- **Disable here** plugins on at user level with no use in this repo and a real
  cost — e.g. browser-automation MCPs in a repo without a web UI, design or
  productivity bundles in a backend repo, any skill pack >500 tok unrelated to
  the stack. Plugins whose hooks run on every tool call cost latency, not
  tokens — say so.
- **Never disable** rows flagged `keep` (the user's `always_keep`) or `lsp`. If
  the user has no config file yet, ask which plugins they rely on everywhere and
  offer to save them as `always_keep`.
- **Not installed**: show `install_hints`; never write them to settings.
- User-level skills (`~/.claude/skills/*`) can be switched per repo with
  `skillOverrides` (`"off"` / `"name-only"`); plugin skills only through their plugin.
- MCP servers: list the ones this repo needs; propose `claude mcp add --scope local`
  for repo-specific servers instead of user scope.

Show the before/after always-on total. Offer: proposed set (Recommended),
minimal (proposed plugins only, everything optional off), custom (then a
multiSelect over the debatable rows). The result is `enabledPlugins`
(`true`/`false` per id) and `skillOverrides` in `.claude/settings.local.json`.

Repo-specific guard rails do **not** go in auto-mode settings: Claude Code reads
`autoMode` only from user and managed settings, never from a repository. Use the
CLAUDE.md "Never" section, `permissions.deny` in `.claude/settings.json`, or a
hook. If the user wants auto mode to know about this repo, propose an entry for
`~/.claude/settings.json` that names the repo explicitly — it applies everywhere.

## Step 5 — Propose files

Read `references/scaffold.md` and `references/claude-md.md`. Show the complete
proposal: new files in full, existing files as diffs.
- `empty`: Core tier, Public tier if the repo is or will be public, and the
  Quality items the user picked. If the stack is "to be decided", only the
  stack-independent files (git, generic `.gitignore`, README from the pitch,
  a minimal CLAUDE.md, `docs/STATE.md`); commands, task runner, CI and linters
  wait for the refresh after the spec — never write placeholders.
- CLAUDE.md never gets a status, progress or roadmap section: that is
  `docs/STATE.md`.
- `unframed`: CLAUDE.md, `.claude/` config, and only the missing items; never
  rewrite an existing CONTRIBUTING.md or README — propose a diff.
- If `local_settings_ignored` is not `true`, the proposal includes the
  `.gitignore` entry for `.claude/settings.local.json` before that file is written.

### 5b — Refresh (`framed` or AGENTS.md)

Score the existing file with the rubric in `references/claude-md.md`; propose a
diff: drop stale lines (verify each path/command), generic advice, duplicates of
the user's global CLAUDE.md, code snippets; move file-specific blocks to
`.claude/rules/` with `paths:`; move status/history to `docs/STATE.md`; add the
mined rules the user kept. Report bytes/lines before→after. Over 200 lines the
refresh is mandatory. With only an AGENTS.md, follow the AGENTS.md section of
`references/claude-md.md` — creating a CLAUDE.md without importing it would stop
Claude Code from loading AGENTS.md.

## Step 6 — Apply

Every write of this skill goes through this step — including plugins-only mode
and the re-budget after a spec — and only after explicit approval of what was shown.
- `.claude/settings.local.json`: run `apply_settings.py` with the approved
  choices (first with `--dry-run` if anything changed since the proposal).
  Never hand-edit it: it usually holds the user's permissions too.
- Other files: before overwriting, if git tracks the file with no local changes,
  git is the backup; otherwise copy it to
  `~/.cache/project-setup/backups/<repo>/<timestamp>-<file>`. Never leave
  backup files inside the repository.
- No commit unless the user asks. Finish with `git status` and remind the user
  that plugin changes apply from the next session (`/context` to check).

## Step 7 — Empty project hand-off

If the stack was "to be decided" or the product is not specified yet, hand off
to a brainstorming/spec skill if one is installed. Before handing off, add to
`docs/STATE.md` → Next: "Re-run the plugin budget (`/project-setup`, plugins
only) once the spec exists" — the reminder survives the other skill's flow and
the session. When the spec is written, run steps 4 and 6 again with it as input.
`claude plugin enable <id> --scope local` (or `/plugin`) re-enables a plugin in
this repo at any time. Rerun this skill in refresh mode once real code exists.

## Plugins-only mode

When the user asks "which plugins for this repo" or says a plugin is missing:
steps 1, 4 and 6 (settings only).

## Batch mode

To scope plugins across many repos: `detect.py --batch ROOT` (dry run), show the
output, wait for approval, then `--apply`. Batch only adds `true` entries to
`enabledPlugins` in `.claude/settings.local.json` for plugins not already on at
user level, keeps the user's explicit `false`, skips repos where that file is
not gitignored or not valid JSON, and refuses `--apply` without a readable
plugin list.
Never write CLAUDE.md in batch — offer refreshes repo by repo, largest CLAUDE.md
first (sizes are in the batch output).
