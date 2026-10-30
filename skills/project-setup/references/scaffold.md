# Scaffold — files and best-practice checklist

Propose only what is missing. Templates are skeletons: fill from detection and
answers, delete empty sections, never leave placeholders in written files.

## Tiers

**Core** is proposed by default; **Public** when the repo is or will be public;
**Quality** is a multiSelect where the items the stack makes obvious come first,
labelled "(Recommended)" — the dialog cannot pre-check options.

### Core

| Item | Committed | Notes |
|---|---|---|
| `git init`, default branch `main` | — | Skip if `.git` exists |
| `.gitignore` | yes | Stack ignores + `CLAUDE.local.md`, `.claude/settings.local.json` |
| `README.md` | yes | What, why, quick start — short; use a docs skill if available |
| `CLAUDE.md` | yes | See `claude-md.md`; ≤80 lines target |
| `CONTRIBUTING.md` | yes | Humans and Claude read it; CLAUDE.md points to it, never duplicates it |
| `CHANGELOG.md` | yes | Keep a Changelog format, `## [Unreleased]` section; SemVer |
| `docs/STATE.md` | yes (or local if private notes) | Current status; **not** imported into CLAUDE.md |
| Task runner (`Makefile` / `Taskfile.yml` / `justfile`) | yes | One entry point per task (build, test, lint, fmt); the commands CLAUDE.md lists |
| `.claude/settings.json` | yes | Team-shared: `permissions.allow` for the repo's build/test/lint commands, `permissions.deny` for forbidden ones (the repo's guard rails), hooks if agreed |
| `.claude/settings.local.json` | no | `enabledPlugins`, `skillOverrides`. Not `autoMode`: Claude Code ignores it outside user/managed settings |
| `.claude/rules/*.md` | yes | Only when a file-scoped instruction exists |
| MCP | `.mcp.json` (yes, `${ENV}` placeholders) or `claude mcp add --scope local` (no) | Only servers the repo needs |
| Commit convention | — | Conventional Commits, stated in CONTRIBUTING.md |

### Public

| Item | Notes |
|---|---|
| `LICENSE` | Ask which (MIT / Apache-2.0 / dual / GPL…) and the copyright holder (default: `git config user.name`). Take the canonical text from `gh api /licenses/<spdx-id> --jq .body` when available rather than writing it from memory |
| `SECURITY.md` | How to report privately (GitHub private vulnerability reporting) |
| `.github/ISSUE_TEMPLATE/` (bug, feature) + `pull_request_template.md` | Short; ask for repro steps and verification |
| `CODE_OF_CONDUCT.md` | Only if the user wants community contributions. It needs a contact method: ask; never put the user's personal e-mail in a public file without explicit consent |

### Quality (multiSelect)

| Item | Notes |
|---|---|
| CI `.github/workflows/ci.yml` | Runs the same entry points as "Done means"; explicit `on:` branches/events; `permissions: contents: read` |
| Dependency updates (`.github/dependabot.yml` or `renovate.json`) | Ecosystems from the declared stacks + `github-actions` |
| `.editorconfig` | Indentation/charset/EOL per file type |
| Linter/formatter config per stack | e.g. `.golangci.yml`, `ruff` in `pyproject.toml`, `rustfmt.toml`, `eslint`/`prettier` |
| `.pre-commit-config.yaml` | Only if the user uses pre-commit; mirrors the linters above |
| `CODEOWNERS` | Team repos only |
| `.gitattributes` | When line endings or LFS matter |

## CONTRIBUTING.md (English skeleton)

```markdown
# Contributing to <project>

## Development setup
<prerequisites and the one command to get a working dev env>

## Everyday commands
| Task | Command |
|---|---|
| Build | `…` |
| Test | `…` |
| Lint | `…` |

## Making a change
1. Branch from `main`: `<type>/<short-description>`.
2. Bug fix → add a test that fails before the fix and passes after.
3. Run the checks above; CI must be green before merge.
4. Commits follow Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`).

## Compatibility
<defaults and interfaces that must not change without a documented breaking change>

## Pull requests
<review expectations, template location>
```

## docs/STATE.md

Purpose: let a fresh session (or a human) resume work without re-reading
history. Rules that keep it useful:
- ≤60 lines; overwrite sections, don't append a diary — git keeps history.
- Link to plan, spec and ADR files; don't copy them.
- Update at the end of each milestone, not every turn.
- CLAUDE.md contains one line: "When resuming work, read `docs/STATE.md`;
  update it when a milestone completes." It is read on demand, so it costs
  nothing in sessions that don't need it.

```markdown
# State — <project>
_Last updated: YYYY-MM-DD_

## Now
- <current goal / branch / plan link>

## Decisions
| Date | Decision | Why |
|---|---|---|

## Next
- <top 3 items>

## Open questions
- <blocking unknowns>
```

## .claude/settings.json (team-shared skeleton)

```json
{
  "permissions": {
    "allow": ["Bash(make test *)", "Bash(make lint *)"],
    "deny": ["Bash(pnpm install *)"]
  }
}
```

`Bash(cmd *)` matches the command with any arguments (the older `Bash(cmd:*)`
form is equivalent). Fill `allow` with the repo's real read-only/verification
entry points so sessions don't prompt for them. `deny` carries the repo's guard
rails — e.g. the package manager when the task runner is the only supported
entry point; leave destructive or publishing commands prompting at least.
Suggest `/fewer-permission-prompts`, when available, after a few sessions to
extend the list from real usage.
