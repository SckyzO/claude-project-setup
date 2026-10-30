#!/usr/bin/env python3
"""Detect a repo's stack and propose per-project Claude Code plugins.

Usage:
  detect.py PATH [--stack go,python]   JSON report for one directory
  detect.py --batch ROOT               dry run: what --apply would change in each git repo under ROOT
  detect.py --batch ROOT --apply       write the change into each repo's .claude/settings.local.json

Batch only adds `"<plugin>": true` entries to `enabledPlugins` in
.claude/settings.local.json, for plugins not already enabled at user level.
Other keys and explicit `false` entries are kept.
Repos where that file is not gitignored, or holds unexpected content, are skipped.
`--apply` refuses to run when the installed plugins cannot be listed, and backs
up every file it changes under ~/.cache/project-setup/backups/.

Signal -> plugin mapping: data/defaults.json, overridden per entry by
$XDG_CONFIG_HOME/project-setup/config.json (default ~/.config/project-setup/).
Mapped plugins that are not installed are reported with an install hint, never written.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # never write __pycache__ into an installed plugin
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (ConfigError, backup, git, ignored_by_git, load_config,  # noqa: E402
                     plugin_list, read_settings, user_level_plugin_list, write_json)

SKIP_DIRS = {"node_modules", "vendor", "dist", "build", "target", "venv", "__pycache__"}
NOT_CONTENT = {".git", ".claude", ".DS_Store", "Thumbs.db", ".idea", ".vscode"}
# what `gh repo create --add-readme --license … --gitignore …` leaves: still an empty project
SCAFFOLD_ONLY = re.compile(r"(README|LICENSE|LICENCE|COPYING|NOTICE)(\.\w+)?|\.gitignore|\.gitattributes", re.I)
WALK_DEPTH = 3
MAX_SCANNED = 300  # content-scanned files per kind (k6 scripts, Go sources)

# signal -> marker files at the repo root
ROOT_MARKERS = {
    "python": ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile"),
    "rust": ("Cargo.toml",),
    "java": ("pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"),
    "php": ("composer.json", "wp-config.php"),
    "ruby": ("Gemfile",),
    "swift": ("Package.swift",),
    "c-cpp": ("CMakeLists.txt", "meson.build", "compile_commands.json"),
    "docs-site": ("mkdocs.yml", "docusaurus.config.js", "docusaurus.config.ts", "hugo.toml", "antora.yml"),
    "docker": ("Dockerfile", "compose.yaml", "compose.yml", "docker-compose.yml", "docker-compose.yaml"),
    "helm": ("Chart.yaml",),
    "ansible": ("ansible.cfg",),
}
# signal -> (file-name regex, max directory depth)
FILE_PATTERNS = {
    "csharp": (r".*\.(csproj|sln)", 1),
    "kotlin": (r".*\.kt", 3),
    "lua": (r".*\.lua", 2),
    "terraform": (r".*\.tf", 2),
    "observability-stack": (r".*\.alloy|(prometheus|loki|alertmanager|tempo|mimir)[\w.-]*\.ya?ml", 2),
}
FRONTEND_DEPS = re.compile(r'"(react|vue|svelte|next|vite|@angular/core|solid-js|astro)"\s*:')
GRAFANA_PLUGIN_DEPS = re.compile(r'"@grafana/(data|ui|runtime|scenes|create-plugin|plugin-e2e|toolkit)"\s*:')
GRAFANA_PLUGIN_JSON = re.compile(r'"grafanaDependency"|"type"\s*:\s*"(panel|datasource|app|renderer|secretsmanager)"')
EXPORTER_CODE = re.compile(r"prometheus\.NewDesc\(|MustNewConstMetric\(")
K6_IMPORT = re.compile(r"""(from\s+|require\()\s*['"]k6""")


def read(p: Path) -> str:
    try:
        return p.read_text(errors="ignore")
    except OSError:
        return ""


def walk(root: Path, depth: int = WALK_DEPTH) -> list:
    """(directory depth, path) of files up to `depth` levels, skipping hidden, vendored and build dirs."""
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        level = len(Path(dirpath).relative_to(root).parts)
        dirnames[:] = [d for d in dirnames if level < depth and d not in SKIP_DIRS and not d.startswith(".")]
        files += [(level, Path(dirpath) / f) for f in filenames]
    return files


def detect_signals(root: Path) -> set:
    signals = set()
    files = walk(root)
    for signal, markers in ROOT_MARKERS.items():
        if any((root / m).exists() for m in markers):
            signals.add(signal)
    for signal, (pattern, max_level) in FILE_PATTERNS.items():
        if any(level <= max_level and re.fullmatch(pattern, p.name) for level, p in files):
            signals.add(signal)
    if (root / "wp-content").is_dir():
        signals.add("php")

    gomod = read(root / "go.mod")
    if gomod:
        signals.add("go")
        if "grafana/grafana-app-sdk" in gomod:
            signals.add("grafana-app-sdk")
        if "prometheus/client_golang" in gomod:
            module = next((l.split()[1] for l in gomod.splitlines() if l.startswith("module ") and len(l.split()) > 1), "")
            go_files = [p for _, p in files if p.suffix == ".go"][:MAX_SCANNED]
            if "exporter" in (root.name + module).lower() or any(EXPORTER_CODE.search(read(p)) for p in go_files):
                signals.add("prometheus-exporter")

    pkg = read(root / "package.json")
    if (root / "tsconfig.json").exists() or '"typescript"' in pkg:
        signals.add("typescript")
    if FRONTEND_DEPS.search(pkg):
        signals.add("frontend")
    plugin_jsons = [p for _, p in files if p.name == "plugin.json" and p.parent.name == "src"]
    if GRAFANA_PLUGIN_DEPS.search(pkg) or any(GRAFANA_PLUGIN_JSON.search(read(p)) for p in plugin_jsons):
        signals.add("grafana-plugin")
    # Grafana plugin scaffolds ship provisioning/ for their dev server: not an observability stack
    if "grafana-plugin" not in signals and any((root / "provisioning" / d).is_dir() for d in ("datasources", "dashboards")):
        signals.add("observability-stack")
    scripts = [p for _, p in files if p.suffix in (".js", ".ts", ".mjs")][:MAX_SCANNED]
    if any(K6_IMPORT.search(read(p)[:4000]) for p in scripts):
        signals.add("k6")
    return signals


def install_hints(missing: list, cfg: dict) -> list:
    hints = []
    for plugin in missing:
        market = plugin.split("@", 1)[1] if "@" in plugin else ""
        repo = cfg.get("marketplaces", {}).get(market, "")
        add = f"claude plugin marketplace add {repo} && " if repo else ""
        hints.append(f"{add}claude plugin install {plugin}")
    return hints


def detect(root: Path, cfg: dict, installed, stacks=()) -> dict:
    signal_map = cfg.get("stack_signals", {})
    signals = detect_signals(root)
    for s in stacks:
        signals.update(signal_map.get(s, []))
    wanted = {p for s in signals for p in cfg["plugin_map"].get(s, [])}
    missing = sorted(wanted - installed) if installed is not None else []

    claude_md = next((p for p in (root / "CLAUDE.md", root / ".claude" / "CLAUDE.md") if p.is_file()), None)
    has_content = any(e.name not in NOT_CONTENT and not SCAFFOLD_ONLY.fullmatch(e.name) for e in root.iterdir())
    git_root = git(root, "rev-parse", "--show-toplevel")
    md = None
    if claude_md:
        text = read(claude_md)
        md = {"path": str(claude_md.relative_to(root)), "bytes": claude_md.stat().st_size,
              "lines": text.count("\n") + (0 if text.endswith("\n") or not text else 1),
              "est_tokens": claude_md.stat().st_size // 4}
    return {
        "path": str(root),
        "mode": "framed" if claude_md else ("unframed" if has_content else "empty"),
        "git_root": git_root or None,
        "inside_repo": bool(git_root) and Path(git_root) != root,  # git init here would nest a repo
        "signals": sorted(signals),
        "plugins": sorted(wanted - set(missing)),
        "not_installed": missing,
        "install_hints": install_hints(missing, cfg),
        "unknown_stacks": [s for s in stacks if s not in signal_map],
        "installed_check": "ok" if installed is not None else "skipped",
        "claude_md": md,
        "agents_md": (root / "AGENTS.md").is_file(),
        "present": sorted(f for f in ("README.md", "CONTRIBUTING.md", "CHANGELOG.md", "LICENSE", "SECURITY.md",
                                      "Makefile", "Taskfile.yml", "justfile", ".mcp.json", "docs/STATE.md",
                                      ".gitignore", ".editorconfig") if (root / f).exists()),
        "ci": sorted(p.name for p in (root / ".github" / "workflows").glob("*.y*ml")),
        "claude_dir": sorted(e.name for e in (root / ".claude").iterdir()) if (root / ".claude").is_dir() else [],
        "local_settings_ignored": ignored_by_git(root, ".claude/settings.local.json"),
        "claude_local_md_ignored": ignored_by_git(root, "CLAUDE.local.md"),
        "remote": git(root, "remote", "get-url", "origin") or None,
    }


def plan(root: Path, plugins: list):
    """What --apply would do: (status, new settings or None, plugins kept off by the user)."""
    data, problem = read_settings(root / ".claude" / "settings.local.json")
    if problem:
        return f"skip: {problem}", None, []
    current = data.get("enabledPlugins", {})
    kept_off = [p for p in plugins if current.get(p) is False]
    to_add = [p for p in plugins if p not in current]
    if not to_add:
        return "unchanged", None, kept_off
    return "write", {**data, "enabledPlugins": {**current, **{p: True for p in to_add}}}, kept_off


def find_repos(root: Path, exclude: set, depth: int = 5) -> list:
    repos = []
    for dirpath, dirnames, filenames in os.walk(root):
        level = len(Path(dirpath).relative_to(root).parts)
        if ".git" in dirnames or ".git" in filenames:  # a file for worktrees and submodules
            repos.append(Path(dirpath))
        dirnames[:] = [d for d in dirnames if level < depth and d not in SKIP_DIRS
                       and d not in exclude and not d.startswith(".")]
    return sorted(repos)


def batch(root: Path, cfg: dict, installed, user_enabled: set, do_apply: bool) -> int:
    for repo in find_repos(root, set(cfg.get("batch_exclude", []))):
        info = detect(repo, cfg, installed)
        info["plugins"] = [p for p in info["plugins"] if p not in user_enabled]  # already on everywhere
        if not info["plugins"] and not info["not_installed"]:
            continue
        kept_off = []
        if not info["local_settings_ignored"]:
            status = "skip: settings.local.json not gitignored"
        else:
            status, data, kept_off = plan(repo, info["plugins"])
            if status == "write":
                if do_apply:
                    target = repo / ".claude" / "settings.local.json"
                    if target.exists():
                        backup(target, repo)
                    write_json(target, data)
                status = "written" if do_apply else "would write"
        notes = [f"kept off by you: {', '.join(kept_off)}"] if kept_off else []
        if info["not_installed"]:
            notes.append(f"not installed: {', '.join(info['not_installed'])}")
        md = f"  CLAUDE.md {info['claude_md']['bytes'] // 1024} KB" if info["claude_md"] else ""
        short = ", ".join(p.split("@")[0] for p in info["plugins"]) or "-"
        print(f"{status:<14} {repo}  [{', '.join(info['signals'])}] -> {short}{md}"
              + "".join(f"\n{'':<15}{n}" for n in notes))
    return 0


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("path", nargs="?", help="directory to inspect")
    ap.add_argument("--stack", default="", help="declared stacks, comma-separated (see stack_signals)")
    ap.add_argument("--batch", metavar="ROOT", help="scan every git repo under ROOT")
    ap.add_argument("--apply", action="store_true", help="with --batch: write the changes")
    args = ap.parse_args(argv)
    if bool(args.path) == bool(args.batch) or (args.apply and not args.batch):
        ap.print_usage(sys.stderr)
        return 2
    target = Path(args.batch or args.path).expanduser().resolve()
    if not target.is_dir():
        print(f"error: {target} is not a directory", file=sys.stderr)
        return 2
    try:
        cfg = load_config()
    except ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    plugins, reason = plugin_list()
    installed = {p["id"] for p in plugins} if plugins is not None else None
    if reason:
        print(f"warning: {reason}; installed-plugin filtering skipped", file=sys.stderr)
    if args.batch:
        if args.apply and installed is None:
            print("error: cannot verify which plugins are installed; refusing to write. "
                  "Run the dry run, or fix the claude CLI first.", file=sys.stderr)
            return 2
        at_user, _ = user_level_plugin_list() if installed is not None else (None, None)
        user_enabled = {p["id"] for p in at_user or [] if p.get("enabled")}
        return batch(target, cfg, installed, user_enabled, args.apply)
    stacks = [s.strip().lower() for s in args.stack.split(",") if s.strip()]
    print(json.dumps(detect(target, cfg, installed, stacks), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
