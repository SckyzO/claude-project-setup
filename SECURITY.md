# Security

## What the plugin reads and writes

- **Reads** your Claude Code transcripts under `~/.claude/projects/` for the
  current project and its git worktrees (`mine_corrections.py`). The script
  runs locally and sends nothing itself, but its output — short excerpts of
  messages you typed — becomes part of the current Claude Code conversation,
  like any file Claude reads in a session. Common token formats (GitHub,
  Anthropic, AWS, Slack, JWT, `password=`/`token=` values) are redacted first.
  The redaction is best-effort: review the proposed rules before accepting
  them into a committed `CLAUDE.md`.
- **Reads** the output of `claude plugin list` and `claude plugin details`, and
  caches the costs in `~/.cache/project-setup/plugin_costs.json`.
- **Writes** files in your repository only after you approve the proposal in
  the session, or, in batch mode, when you pass `--apply`. Batch mode only
  touches `.claude/settings.local.json`, and only when git ignores it.
- **Backs up** files it overwrites to `~/.cache/project-setup/backups/`, never
  inside the repository, unless git already holds an unmodified copy.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting on this repository
(Security → Report a vulnerability). Please don't open a public issue for
security problems.
