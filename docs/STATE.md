# State — claude-project-setup
_Last updated: 2026-10-30_

## Now
- 0.1.0 audited and hardened locally; not yet pushed. Distribution via the
  shared `SckyzO/claude-plugins` marketplace (created locally, not pushed).

## Decisions
| Date | Decision | Why |
|---|---|---|
| 2026-10-30 | stdlib-only Python, unittest | No install step for users; CI without deps |
| 2026-10-30 | Personal plugin choices in `~/.config/project-setup/config.json` | Shipped defaults stay generic |
| 2026-10-30 | Batch adds only `true` entries, keeps explicit `false` | Re-running batch never undoes a user's choice |
| 2026-10-30 | Transcript mining filters by `cwd` and human-typed fields | Encoded directory names collide across sibling projects; SDK/peer turns are not the user |
| 2026-10-30 | No `autoMode` in generated repo settings | Claude Code ignores it outside user/managed settings |

## Next
- Fold in the findings of the first live test (empty folder).
- Dogfood on an existing repo with history.
- Create the GitHub repos and push.
- Add `claude plugin eval` cases for triggering and the approval gate.

## Open questions
- Icon for the plugin directory listing.
