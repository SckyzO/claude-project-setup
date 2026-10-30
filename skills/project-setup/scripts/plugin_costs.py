#!/usr/bin/env python3
"""Installed plugins with their always-on token cost, user-level and in one repo.

Usage: plugin_costs.py [--repo PATH] [--json]

Cost comes from `claude plugin details` (skill and agent descriptions loaded in
every session; MCP tool schemas are deferred and not counted). The "user"
column is the state outside any project; "repo" is the state in effect in PATH
(default: current directory), after its .claude/settings*.json overrides.
Each cost is cached for a day in ~/.cache/project-setup/plugin_costs.json;
failed lookups are not cached.
"""
import argparse
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.dont_write_bytecode = True  # never write __pycache__ into an installed plugin
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ConfigError, cache_dir, load_config, plugin_list, user_level_plugin_list  # noqa: E402

TTL = 86400
COST = re.compile(r"Always-on:\s+~?([\d,]+)\s*tok")
KINDS = re.compile(r"^\s+(Skills|Agents|Hooks|MCP servers|LSP servers) \((\d+)\)", re.M)


def details(pid: str) -> dict:
    try:
        out = subprocess.run(["claude", "plugin", "details", pid], capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        out = ""
    m = COST.search(out)
    return {"always_on": int(m.group(1).replace(",", "")) if m else None,
            "components": {k: int(n) for k, n in KINDS.findall(out) if int(n)}}


def load_cache(path: Path) -> dict:
    """Fresh entries only; a missing or corrupt cache is simply rebuilt."""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    now = time.time()
    return {k: v for k, v in data.items()
            if isinstance(v, dict) and now - v.get("at", 0) < TTL} if isinstance(data, dict) else {}


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo", default=".", help="repository whose effective plugin state to show")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        print(f"error: {repo} is not a directory", file=sys.stderr)
        return 2
    try:
        keep = set(load_config().get("always_keep", []))
    except ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    in_repo, reason = plugin_list(cwd=repo)
    at_user, reason_user = user_level_plugin_list()
    if in_repo is None or at_user is None:
        print(f"error: {reason or reason_user}", file=sys.stderr)
        return 2
    user_state = {p["id"]: p.get("enabled", False) for p in at_user}

    cache_file = cache_dir() / "plugin_costs.json"
    cache = load_cache(cache_file)
    key = lambda p: f"{p['id']}@{p.get('version')}"  # noqa: E731
    todo = [p for p in in_repo if key(p) not in cache]
    found = {}
    with ThreadPoolExecutor(8) as pool:
        for p, d in zip(todo, pool.map(lambda p: details(p["id"]), todo)):
            found[key(p)] = d
            if d["always_on"] is not None:
                cache[key(p)] = {**d, "at": time.time()}
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(cache))

    rows = []
    for p in in_repo:
        d = cache.get(key(p)) or found[key(p)]
        rows.append({"id": p["id"], "user": user_state.get(p["id"], False), "repo": p.get("enabled", False),
                     "always_on": d["always_on"], "components": d["components"],
                     "keep": p["id"] in keep, "lsp_only": set(d["components"]) == {"LSP servers"}})
    rows.sort(key=lambda r: (-(r["always_on"] or 0), r["id"]))
    totals = {col: sum(r["always_on"] or 0 for r in rows if r[col]) for col in ("user", "repo")}
    if args.json:
        print(json.dumps({"repo": str(repo), "totals": totals, "plugins": rows}, indent=2))
        return 0
    print(f"{'user':<5} {'repo':<5} {'tokens':>7}  plugin  (components) [flags]")
    for r in rows:
        comps = ", ".join(f"{k} {n}" for k, n in r["components"].items())
        cost = "?" if r["always_on"] is None else f"{r['always_on']:,}"
        flags = " ".join(f for f, on in (("keep", r["keep"]), ("lsp", r["lsp_only"])) if on)
        print(f"{'on' if r['user'] else 'off':<5} {'on' if r['repo'] else 'off':<5} {cost:>7}  "
              f"{r['id']}  ({comps}){f' [{flags}]' if flags else ''}")
    print(f"\nAlways-on total: user level ~{totals['user']:,} tok, in {repo} ~{totals['repo']:,} tok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
