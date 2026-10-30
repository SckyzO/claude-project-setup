# CLAUDE.md — what goes where

## Placement

| Content | Location |
|---|---|
| Facts needed in almost every session of this repo | `CLAUDE.md` (or `.claude/CLAUDE.md` — one of the two, never both) |
| Instructions for some files only (CI, Dockerfile, migrations, a package) | `.claude/rules/<topic>.md` with `paths:` (subfolders allowed; patterns stay relative to the directory holding `.claude`) |
| Instructions for one package of a monorepo | `<package>/CLAUDE.md`, loaded when Claude works in that subtree |
| Multi-step procedures used occasionally (release, deploy) | a project skill `.claude/skills/<name>/` |
| Rules that must never be broken | a hook (`.claude/settings.json`) — prose is not enforcement |
| Style a linter/formatter can check | the linter config, not CLAUDE.md |
| Personal preferences for this repo | `CLAUDE.local.md` or `.claude/settings.local.json` |
| Current status, decisions log, next steps | `docs/STATE.md` (read on demand, never imported) |
| How to contribute (setup, commands, PR rules) | `CONTRIBUTING.md` — CLAUDE.md links to it |
| Anything already in the user's `~/.claude/CLAUDE.md` | nowhere — don't repeat it |

`@imports` organise but do not reduce context: imported files load in full.

## AGENTS.md

Claude Code loads `AGENTS.md` natively only when no `CLAUDE.md`,
`.claude/CLAUDE.md` or `CLAUDE.local.md` exists. So when a repo has an
AGENTS.md:
- keep it as the shared source for every agent; refresh it like a CLAUDE.md;
- create a CLAUDE.md only for Claude-specific additions, starting with the line
  `@AGENTS.md` so the shared rules keep loading;
- never copy AGENTS.md content into CLAUDE.md.

## Keep a line only if

- it is a command needed to verify work, or the one allowed way to run things;
- the code is misleading without it (intentional oddity, trap, legacy path);
- it records a decision not visible in the repo;
- the user had to correct it at least once (mined or stated).

Remove: generic engineering advice, architecture tours derivable by reading
the tree, code snippets (use `path:line` pointers), changelogs, task lists,
anything stale.

## Template (≤80 lines target)

```markdown
# <Project> — <one-line purpose>

## Commands
- Build: `…`  · Test: `…`  · Lint: `…`   (the only supported entry points)

## Done means
- <checks that must pass before claiming done>

## Never
- <forbidden actions, files never edited, prod targets>

## Compatibility
- <what must not change silently, and for whom>

## Gotchas
- <intentional oddities and past bugs, one line each, with path:line>

## Pointers
- Contributing: `CONTRIBUTING.md` · Architecture: `docs/…`
- When resuming work, read `docs/STATE.md`; update it when a milestone completes.
```

Omit any empty section.

## Review rubric (refresh mode, /100)

Adapted from the official claude-md-improver: commands 20, gotchas/traps 20,
conciseness 20, currency (every path/command verified to exist) 20,
actionability 20. Report the score, the line count, and the 3 biggest cuts.
