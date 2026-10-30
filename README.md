# claude-project-setup

A Claude Code plugin that sets a repository up for Claude Code: a new empty
folder, an existing repo without a `CLAUDE.md`, or a repo whose `CLAUDE.md` or
`AGENTS.md` has grown stale. It asks only what the code can't answer, decides which plugins are
loaded in that repo, and proposes every file before writing it.

## What it does

- **Detects the stack** from manifests and sources (Go, Python, Rust,
  TypeScript, Java, Kotlin, PHP, Ruby, Swift, C/C++, C#, Lua, frontend
  frameworks, Grafana plugins, Prometheus exporters, observability configs, k6
  scripts…) and picks one of three modes: `empty`, `unframed`, `framed`. It
  warns when the folder sits inside another git repository.
- **Mines your past sessions** in `~/.claude/projects/` for corrections you
  already gave in this repo and its worktrees: rejected tool calls with
  feedback, messages right after an interrupt, "no / don't / je t'ai dit…"
  phrasing. Only messages you typed count — subagent, SDK, scheduled and
  auto-mode entries are ignored — and secrets are redacted. Each proposed rule
  is backed by a dated quote.
- **Asks the gaps only**: one open question about the project's purpose, then
  at most two rounds of up to four multiple-choice questions built from your
  answer. Stacks, external systems and optional files can be combined.
- **Budgets the session**: lists installed plugins with their always-on token
  cost (from `claude plugin details`), their state at user level and in this
  repo, proposes which ones to enable or disable here, and shows the
  before/after total. Missing plugins come with the install command.
- **Generates the frame**, after your approval:
  - `README.md`, `CLAUDE.md` (target ≤80 lines), `CONTRIBUTING.md`, `CHANGELOG.md`
  - `docs/STATE.md` (read on demand, never imported)
  - `.claude/settings.json` (team permissions)
  - `.claude/settings.local.json` (your plugins and skills for this repo)
  - path-scoped `.claude/rules/`
  - for public repos: `LICENSE`, `SECURITY.md`, issue/PR templates
  - on request: CI, dependency updates, `.editorconfig`, linter config, MCP config
- **Refreshes** an existing `CLAUDE.md`: scores it, drops stale or generic
  lines, moves file-specific blocks into `.claude/rules/`, reports size
  before/after. With an `AGENTS.md`, it keeps that file as the shared source
  and imports it instead of duplicating it.

## Install

```text
/plugin marketplace add SckyzO/claude-plugins
/plugin install project-setup@sckyzo-plugins
```

Start a new session, then in any directory:

```text
/project-setup:project-setup
```

Or just say "set this project up for Claude Code". The skill triggers on that
kind of request.

## Batch plugin scoping

To enable the right domain plugins across many existing repos, run the
detector without the skill. Nothing is written without `--apply`:

```sh
python3 -I skills/project-setup/scripts/detect.py --batch ~/Dev          # dry run
python3 -I skills/project-setup/scripts/detect.py --batch ~/Dev --apply  # write
```

Batch mode only adds `true` entries to `enabledPlugins` in
`.claude/settings.local.json`; a plugin you set to `false` there stays off. It
skips any repo where that file is not gitignored or not valid JSON, refuses
`--apply` when the installed plugins cannot be listed, backs up each file it
changes under `~/.cache/project-setup/backups/`, and prints each repo's
`CLAUDE.md` size so you can refresh the largest first.

In a session, the skill applies your approved choices with
`skills/project-setup/scripts/apply_settings.py`, which follows the same rules
for a single repo.

## Configuration

Stack-to-plugin mapping lives in
[`skills/project-setup/data/defaults.json`](skills/project-setup/data/defaults.json).
Override it per signal in `~/.config/project-setup/config.json` (honours
`XDG_CONFIG_HOME`):

```json
{
  "plugin_map": {
    "frontend": ["frontend-design@claude-plugins-official", "ui-ux-pro-max@ui-ux-pro-max-skill"]
  },
  "always_keep": ["superpowers@claude-plugins-official", "context7@context7-marketplace"]
}
```

| Key | Merge | Purpose |
|---|---|---|
| `plugin_map` | per signal | Signal → plugins to enable |
| `stack_signals` | per stack | Declared stack (`--stack`) → signals |
| `marketplaces` | per name | Marketplace name → GitHub repo, for install hints |
| `always_keep` | replaced | Plugins the skill never proposes to disable |
| `batch_exclude` | replaced | Directory names batch mode does not descend into |

Mapped plugins that are not installed are reported with an install command and
never written to settings.

## Requirements

Python 3.10+ (standard library only) and git. The `claude` CLI is used, when
available, for plugin costs and the installed-plugin list.

## Privacy

Transcript mining runs locally, but the excerpts it finds become part of your
current Claude Code conversation. Secrets are redacted on a best-effort basis.
See [SECURITY.md](SECURITY.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Licensed under [MIT](LICENSE).
