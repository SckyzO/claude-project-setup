"""Shared helpers for the project-setup scripts: configuration, the claude CLI, safe writes.

The scripts run with `python3 -I`, which keeps the script directory off
sys.path; each script adds this directory explicitly before importing.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

DEFAULTS = Path(__file__).resolve().parent.parent / "data" / "defaults.json"
MERGED_KEYS = ("plugin_map", "stack_signals", "marketplaces")  # merged per entry
REPLACED_KEYS = ("always_keep", "batch_exclude")                # replaced as a whole


class ConfigError(Exception):
    """The user configuration file exists but cannot be used."""


def config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "project-setup" / "config.json"


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "project-setup"


def load_config() -> dict:
    """Shipped defaults overridden by the user config; raises ConfigError on a bad file."""
    cfg = json.loads(DEFAULTS.read_text())
    user = config_path()
    if not user.exists():
        return cfg
    try:
        override = json.loads(user.read_text())
    except json.JSONDecodeError as e:
        raise ConfigError(f"{user}: invalid JSON ({e.msg}, line {e.lineno})") from e
    if not isinstance(override, dict):
        raise ConfigError(f"{user}: the top level must be a JSON object")
    for key in MERGED_KEYS:
        value = override.get(key, {})
        if not isinstance(value, dict):
            raise ConfigError(f"{user}: `{key}` must be an object")
        cfg[key] = {**cfg.get(key, {}), **value}
    for key in REPLACED_KEYS:
        if key in override:
            if not isinstance(override[key], list):
                raise ConfigError(f"{user}: `{key}` must be a list")
            cfg[key] = override[key]
    return cfg


def plugin_list(cwd=None):
    """`claude plugin list --json` run in `cwd`; returns (plugins, None) or (None, reason).

    `enabled` in the result is the state in effect for that directory: local
    and project settings of `cwd` override the user settings. A plugin
    installed in several scopes appears once per installation; this function
    returns one entry per id, enabled if any installation is.
    """
    try:
        r = subprocess.run(["claude", "plugin", "list", "--json"], cwd=cwd,
                           capture_output=True, text=True, timeout=120)
    except FileNotFoundError:
        return None, "claude CLI not found"
    except (OSError, subprocess.SubprocessError) as e:
        return None, f"claude CLI could not run ({e.__class__.__name__})"
    if r.returncode != 0:
        return None, f"`claude plugin list --json` exited with {r.returncode}"
    try:
        plugins = json.loads(r.stdout)
        if not isinstance(plugins, list) or not all(isinstance(p, dict) and "id" in p for p in plugins):
            raise ValueError("unexpected structure")
    except ValueError as e:
        return None, f"`claude plugin list --json` returned unreadable output ({e})"
    by_id = {}
    for p in plugins:
        seen = by_id.setdefault(p["id"], dict(p))
        seen["enabled"] = bool(seen.get("enabled")) or bool(p.get("enabled"))
    return list(by_id.values()), None


def user_level_plugin_list():
    """Plugin list as seen from an empty directory, i.e. without any project override."""
    with tempfile.TemporaryDirectory(prefix="project-setup-") as neutral:
        return plugin_list(cwd=neutral)


def git(root: Path, *args) -> str:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def ignored_by_git(root: Path, rel: str):
    """True/False when root is in a git work tree, None when it is not."""
    if not git(root, "rev-parse", "--is-inside-work-tree"):
        return None
    r = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", str(root / rel)], capture_output=True)
    return r.returncode == 0


def backup(path: Path, repo: Path) -> Path:
    """Copy `path` under the cache dir, never inside the repository; returns the copy."""
    stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{time.time_ns() % 1_000_000_000:09d}"
    dest = cache_dir() / "backups" / re.sub(r"[^A-Za-z0-9]", "-", str(repo)) / f"{stamp}-{path.name}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)
    return dest


def write_json(target: Path, data: dict) -> None:
    """Atomic replace, so Claude Code never reads a half-written settings file."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(data, indent=2) + "\n")
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def read_settings(target: Path):
    """(settings dict, None) or (None, reason) for a .claude/settings*.json file."""
    if not target.exists():
        return {}, None
    try:
        data = json.loads(target.read_text())
    except json.JSONDecodeError as e:
        return None, f"invalid JSON ({e.msg}, line {e.lineno})"
    if not isinstance(data, dict):
        return None, "unexpected settings structure"
    for key in ("enabledPlugins", "skillOverrides"):
        if not isinstance(data.get(key, {}), dict):
            return None, "unexpected settings structure"
    return data, None
