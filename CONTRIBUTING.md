# Contributing to claude-project-setup

## Development setup

Python 3.10+ and git. No virtualenv needed: the scripts and tests use the
standard library only. To try the plugin from your checkout:

```sh
claude --plugin-dir .
```

## Everyday commands

| Task | Command |
|---|---|
| Test | `python3 -m unittest discover -s tests -v` |
| Validate the plugin | `claude plugin validate . --strict` and `claude plugin validate . --profile directory` |
| Run the detector on a repo | `python3 -I skills/project-setup/scripts/detect.py PATH` |

## Layout

| Path | Role |
|---|---|
| `skills/project-setup/SKILL.md` | The workflow Claude follows |
| `skills/project-setup/references/` | Loaded on demand by the skill: questions, CLAUDE.md rules, scaffold templates |
| `skills/project-setup/scripts/` | Deterministic helpers: detection, transcript mining, plugin costs, settings writer (`apply_settings.py`); `_common.py` holds config loading, the `claude` CLI calls and safe writes |
| `skills/project-setup/data/defaults.json` | Default stack signal → plugin mapping |
| `tests/` | Subprocess tests in a sandboxed `HOME`, with a fake `claude` CLI (`tests/helpers.py`) |

## Making a change

1. Branch from `main`: `<type>/<short-description>`.
2. Bug fix → add a test that fails before the fix and passes after.
3. New detection signal → add it to `detect.py`, map it in `defaults.json`
   only if the plugin is public (add its marketplace to `marketplaces` for the
   install hint), and cover it — positive and negative — in `tests/test_detect.py`.
4. New correction pattern → add a positive and a negative case in
   `tests/test_mine_corrections.py`. Patterns must stay cheap and
   language-tagged (FR/EN today).
5. Run the commands above; CI must be green before merge.
6. Commits follow Conventional Commits with a scope: `feat(detect): …`,
   `fix(mine): …`, `docs(skill): …`.

## Compatibility

`detect.py --batch --apply` writes to users' repositories. Its contract must
not change silently: dry run by default, only adds `true` entries to
`enabledPlugins`, keeps explicit `false`, skips non-gitignored files and
unexpected content, refuses to write without a verified plugin list, backs up
outside the repo, writes atomically. `apply_settings.py` shares the same rules.
Changing any of these is a breaking change and goes in the CHANGELOG.

## Pull requests

Describe the problem, the change, and how you verified it. Keep one logical
change per PR.
