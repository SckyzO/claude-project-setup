#!/usr/bin/env python3
"""Apply approved plugin and skill choices to a repo's .claude/settings.local.json.

Usage:
  apply_settings.py PATH [--enable a@m,b@m] [--disable c@m] [--skill-off x] [--skill-name-only y] [--dry-run]

Sets exactly the given `enabledPlugins` and `skillOverrides` entries and keeps
every other key (permissions, hooks, …). Refuses when the file is not
gitignored in a git work tree, or holds invalid or unexpected content. The
previous file is backed up under ~/.cache/project-setup/backups/. The write is
atomic. Prints each changed entry as `key: before -> after`.
"""
import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # never write __pycache__ into an installed plugin
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import backup, ignored_by_git, read_settings, write_json  # noqa: E402


def items(value: str) -> list:
    return [v.strip() for v in value.split(",") if v.strip()]


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("path")
    ap.add_argument("--enable", default="", help="plugin ids to set to true")
    ap.add_argument("--disable", default="", help="plugin ids to set to false")
    ap.add_argument("--skill-off", default="", help="user-level skill names to set to \"off\"")
    ap.add_argument("--skill-name-only", default="", help="user-level skill names to set to \"name-only\"")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    repo = Path(args.path).expanduser().resolve()
    if not repo.is_dir():
        print(f"error: {repo} is not a directory", file=sys.stderr)
        return 2
    enable, disable = items(args.enable), items(args.disable)
    if set(enable) & set(disable):
        print(f"error: both enabled and disabled: {', '.join(sorted(set(enable) & set(disable)))}", file=sys.stderr)
        return 2
    if ignored_by_git(repo, ".claude/settings.local.json") is False:
        print("error: .claude/settings.local.json is not gitignored here; add it to .gitignore first",
              file=sys.stderr)
        return 2
    target = repo / ".claude" / "settings.local.json"
    data, problem = read_settings(target)
    if problem:
        print(f"error: {target}: {problem}; fix it by hand, nothing was written", file=sys.stderr)
        return 2

    wanted = {("enabledPlugins", p): True for p in enable}
    wanted.update({("enabledPlugins", p): False for p in disable})
    wanted.update({("skillOverrides", s): "off" for s in items(args.skill_off)})
    wanted.update({("skillOverrides", s): "name-only" for s in items(args.skill_name_only)})
    changes = [(section, name, data.get(section, {}).get(name), value)
               for (section, name), value in wanted.items() if data.get(section, {}).get(name) != value]
    if not changes:
        print("unchanged")
        return 0
    for section, name, before, after in changes:
        print(f"{section}.{name}: {'(unset)' if before is None else before} -> {after}")
    if args.dry_run:
        return 0
    if target.exists():
        print(f"backup: {backup(target, repo)}")
    for section, name, _, after in changes:
        data.setdefault(section, {})[name] = after
    write_json(target, data)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
