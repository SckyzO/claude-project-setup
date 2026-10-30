# Question bank

Order: open pitch in chat → tailored dialogs. Ask only what detection and the
pitch did not establish. Each entry says when to skip it and whether answers
combine (`multi`).

## 0. Pitch (plain chat, not a dialog)

"Describe in one or two sentences what this project should do, for whom,
anything already decided (language, where it runs, who uses it) — and its name,
if it has one."

Never infer the purpose from the folder name. Derive from the answer: project
kind, likely stacks, visibility hints, external systems. Use these to order and
pre-select options below.

## Always relevant (unless established)

1. **Visibility** — public OSS / private / client repo. *Skip if* the remote is
   a known public repo (`gh repo view --json visibility`). Drives CLAUDE.md
   language, "every push publishes" rule, the Public scaffold tier.
2. **The one true way to build/test/lint** — e.g. `make` only, Docker only,
   never call the package manager directly. *Skip if* Makefile/CI make it
   unambiguous and no mined correction contradicts it.
3. **Definition of done** (`multi`) — which checks must pass locally before
   claiming done, and whether CI must be green before merge. Offer the 3–4
   checks relevant to the stack (tests, lint, typecheck, e2e, build, docs check).
4. **Forbidden / dangerous** — prod targets, generated/vendored files, applied
   migrations, publishing steps.
5. **Compatibility contract** — who consumes this; what must not change
   silently. Open question: ask in chat.
6. **Known traps** — intentional oddities, past bugs that must not come back.
   Open question: ask in chat, offering the mined candidates if any.

## Empty project

7. **Stacks** (`multi`) — the 3 most likely from the pitch plus "to be decided"
   (→ brainstorming); the free-text "Other" covers the rest. Map choices
   through `stack_signals`.
8. **Project kind** — derived from the pitch (CLI, library, service, Grafana
   plugin, Prometheus exporter, IaC, docs site…); ask only if the pitch is
   ambiguous, with options specific to it — never a generic list.
9. **Tooling** — task runner (make / Taskfile / just), Docker dev env, CI provider.
10. **External systems** (`multi`) — MCP servers or APIs needed, and where.
11. **Optional files** (`multi`) — the Quality tier of `scaffold.md`: the 4
    most relevant to the stack as options, the obvious ones first labelled
    "(Recommended)"; name the others in the question so "Other" can pick them.

Empty-mode rounds. Questions 4–6 have no answer yet in an empty repo: don't ask
them. Instead, derive "Never" rules and compatibility constraints from the pitch
(and any research it needed) and put them in the CLAUDE.md draft, where the user
reviews them in step 5. Ask 4–6 in the refresh, once code exists.
- Round 1: Stacks (7), Visibility + licence (1), Tooling (9), and the project
  name if the pitch gave none (otherwise External systems (10)).
- Round 2: Optional files (11), Definition of done (3), External systems (10)
  if not asked yet, Project kind (8) only if the pitch left it ambiguous.

## Optional (only if signals suggest it)

- Monorepo: which packages are in scope?
- Client/work repo: can content leave the machine (gists, external services)?
- Commit/PR/docs language if it differs from the user's defaults.
