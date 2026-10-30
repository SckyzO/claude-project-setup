# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-10-30

### Added
- `project-setup` skill with three modes (`empty`, `unframed`, `framed`), a
  plugins-only mode and a batch mode.
- `detect.py`: stack detection (Go, Python, Rust, TypeScript, Java, Kotlin,
  PHP, Ruby, Swift, C/C++, C#, Lua, frontend frameworks, Grafana plugins,
  Prometheus exporters, observability configs, k6), declared stacks via
  `--stack`, nested-repository warning, `.claude/CLAUDE.md` and `AGENTS.md`
  awareness, install hints for missing plugins, batch dry run and `--apply`.
- `mine_corrections.py`: past-session corrections for a project and its git
  worktrees (rejected tool calls, post-interrupt messages, FR/EN phrasing),
  limited to messages the human typed, with `--since` and secret redaction.
- `plugin_costs.py`: installed plugins with always-on token cost, user-level
  and in-repo state, `always_keep` and LSP flags, per-entry cache expiry.
- `apply_settings.py`: deterministic writer for approved `enabledPlugins` and
  `skillOverrides` choices, with gitignore guard, backup outside the repo and
  atomic write; batch `--apply` follows the same rules.
- Configuration in `data/defaults.json`, overridable in
  `~/.config/project-setup/config.json` (`plugin_map`, `stack_signals`,
  `marketplaces`, `always_keep`, `batch_exclude`).
- Scaffold in three tiers (core, public, quality) with templates for
  `CLAUDE.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `docs/STATE.md` and
  `.claude/settings.json`.
