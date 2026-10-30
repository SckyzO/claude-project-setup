# claude-project-setup — Claude Code plugin that frames repositories

## Commands
- Test: `python3 -m unittest discover -s tests -v` (stdlib only, no pytest)
- Validate plugin: `claude plugin validate . --strict` and `claude plugin validate . --profile directory`

## Done means
- Tests pass, including a test that fails before any bug fix.
- Both validations pass; CI green before merge.

## Never
- Add third-party Python dependencies or network calls to `scripts/`.
- Write to a user's repo or settings from a script without an explicit flag (`--apply`).
- Ship maintainer-specific assumptions (plugin names, paths, preferences) in
  `SKILL.md`, `references/` or `scripts/`. Personal choices go in
  `~/.config/project-setup/config.json`; public plugin ids go in `data/defaults.json`.
- Commit anything mined from real transcripts; test fixtures are synthetic.
- Tell the skill to put `autoMode` in repo settings: Claude Code only reads it
  from user and managed settings.

## Language
English for everything shipped. The skill asks questions in the user's language.

## Gotchas
- `claude plugin list --json` reports `enabled` for the directory it runs in
  (local > project > user). `_common.user_level_plugin_list()` runs it from an
  empty temp dir to get the user-level view.
- Scripts run with `python3 -I`, which drops the script dir from `sys.path`;
  each script inserts its own directory before `import _common`.
- A real tool denial is a `tool_result` with `is_error: true` whose text starts
  with "The user doesn't want to proceed with this tool use."; tool output that
  merely quotes that sentence (reading this repo's own scripts) must not match.
- Transcript filtering relies on entry fields `cwd`, `isSidechain`, `isMeta`,
  `isCompactSummary`, `entrypoint`, `promptSource`, `turnOrigin`, `origin`,
  `toolDenialKind`. Check them against a real transcript when Claude Code
  changes its format; tests in `tests/test_mine_corrections.py` encode the
  expected semantics.
- Without the `claude` CLI (CI, tests), `detect.py` reports
  `installed_check: skipped` and does not filter plugins.
- Tests run scripts as subprocesses with a sandboxed `HOME`, a `PATH` holding
  only git, and an optional fake `claude` (`tests/helpers.py`); keep it that way
  so they never touch real config.

## Pointers
- Contributing: `CONTRIBUTING.md` · Skill entry point: `skills/project-setup/SKILL.md`
- When resuming work, read `docs/STATE.md`; update it when a milestone completes.
