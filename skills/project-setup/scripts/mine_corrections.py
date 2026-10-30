#!/usr/bin/env python3
"""Extract likely user corrections from past Claude Code sessions of one project.

Usage: mine_corrections.py PROJECT_PATH [--limit N] [--since YYYY-MM-DD]

Reads $CLAUDE_CONFIG_DIR/projects (default ~/.claude/projects)/<encoded path>*/*.jsonl
and keeps entries whose `cwd` is the project, one of its git worktrees, or a
subdirectory of either — except subdirectories that are git repositories of
their own. Sibling projects sharing the encoded prefix are excluded. Only messages the human typed count: subagent,
SDK, peer, scheduled and system-injected turns are skipped, and only tool
denials made by the user (not by the auto-mode classifier) are reported.
Secrets matching common token formats are redacted. Output is evidence for
proposed CLAUDE.md rules, not rules themselves.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

PATTERNS = re.compile(
    r"^\s*(non|no|nope|stop|arr[eê]te|attends|wait|wrong|faux|pas comme [çc]a|"
    r"je (t'|te )?(l')?ai (d[ée]j[aà] )?dit|je t'avais dit|pourquoi (tu|as-tu)|"
    r"ne (fais|touche|modifie|lance|supprime) (pas|jamais)|jamais|toujours|"
    r"utilise (plut[oô]t|uniquement|seulement)|il faut (pas|toujours)|"
    r"tu (dois|ne dois)|n'utilise pas|tu as oubli[ée]|c'est pas|ce n'est pas|pas [çc]a|"
    r"[çc]a (ne )?marche pas|parle|relis|lis (le|la|les)|"
    r"don't|never|always|instead|rather)(?![\w-])",
    re.IGNORECASE,
)
# A real denial is a tool_result with is_error=true whose text starts with this wrapper.
REJECTION = re.compile(r"\s*The user doesn't want to proceed with this tool use\..*?the user said:\s*(.+)",
                       re.IGNORECASE | re.DOTALL)
NOT_FEEDBACK = re.compile(r"The user wants to clarify these questions")  # AskUserQuestion "Chat about this"
NOISE = re.compile(r"^(<|\[|/|\(Re-invocation of|Caveat:|Base directory for this skill:|"
                   r"This session is being continued|Another Claude session sent a message)")
NON_HUMAN_SOURCES = {"sdk", "system"}
NON_HUMAN_TURNS = {"sdk", "peer", "task_notification", "scheduled"}
SECRETS = [
    re.compile(r"\b(sk-ant-[\w-]{16,}|sk-[\w-]{20,}|ctx7sk-[\w-]{16,}|gh[pousr]_\w{30,}|github_pat_\w{30,}|"
               r"glpat-[\w-]{16,}|xox[abprs]-[\w-]{10,}|AKIA[0-9A-Z]{16}|"
               r"eyJ[\w-]{10,}\.[\w-]{10,}\.[\w-]{10,})"),
    re.compile(r"(?i)\b(bearer\s+)[\w.~+/-]{16,}=*"),
]
KEY_VALUE = re.compile(r"(?i)\b(password|passwd|pwd|token|secret|api[_-]?key)(\s*[:=]\s*)(\S+)")


def encode(path: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def redact(text: str) -> str:
    text = SECRETS[0].sub("[REDACTED]", text)
    text = SECRETS[1].sub(r"\1[REDACTED]", text)
    return KEY_VALUE.sub(r"\1\2[REDACTED]", text)


def project_roots(project: str) -> list:
    """The project plus its git worktrees, which belong to the same project."""
    try:
        out = subprocess.run(["git", "-C", project, "worktree", "list", "--porcelain"],
                             capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        out = ""
    roots = {project} | {l[len("worktree "):] for l in out.splitlines() if l.startswith("worktree ")}
    return sorted(r.rstrip("/") for r in roots)


@lru_cache(maxsize=4096)
def in_nested_repo(cwd: str, root: str) -> bool:
    """True when a directory between root (excluded) and cwd (included) is its own git repo."""
    path = Path(cwd)
    while str(path) != root and str(path).startswith(root + "/"):
        if (path / ".git").exists():
            return True
        path = path.parent
    return False


def in_project(entry: dict, roots: list, exact_dir: bool) -> bool:
    cwd = entry.get("cwd")
    if cwd:
        cwd = cwd.rstrip("/")
        return any(cwd == r or (cwd.startswith(r + "/") and not in_nested_repo(cwd, r)) for r in roots)
    return exact_dir  # older transcripts without cwd: trust only the project's own directory


def human_session(entry: dict) -> bool:
    return not entry.get("isSidechain") and entry.get("userType", "external") == "external" \
        and not str(entry.get("entrypoint", "")).startswith("sdk")


def typed_by_human(entry: dict) -> bool:
    if entry.get("isMeta") or entry.get("isCompactSummary") or not human_session(entry):
        return False
    if entry.get("promptSource") in NON_HUMAN_SOURCES or entry.get("turnOrigin") in NON_HUMAN_TURNS:
        return False
    origin = entry.get("origin")
    return not (isinstance(origin, dict) and origin.get("kind") not in (None, "human"))


def user_text(entry: dict) -> str:
    content = entry.get("message", {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
    return ""


def rejection_text(entry: dict) -> str:
    if entry.get("toolDenialKind") not in (None, "user-rejected") or not human_session(entry):
        return ""
    content = entry.get("message", {}).get("content")
    if not isinstance(content, list):
        return ""
    for c in content:
        if isinstance(c, dict) and c.get("type") == "tool_result" and c.get("is_error"):
            body = c.get("content")
            if isinstance(body, list):
                body = " ".join(x.get("text", "") for x in body if isinstance(x, dict))
            m = REJECTION.match(body if isinstance(body, str) else "")
            if m and not NOT_FEEDBACK.match(m.group(1).strip()):
                return m.group(1).strip()
    return ""


def scan(path: Path, roots: list, exact_dir: bool, since: str):
    """Yield (date, session, kind, text) for one transcript; also report whether it belongs to the project."""
    interrupted, matched = False, False
    with path.open(errors="ignore") as f:
        for line in f:
            if '"user"' not in line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("type") != "user" or not in_project(e, roots, exact_dir):
                continue
            matched = True
            date = str(e.get("timestamp", ""))[:10]
            if since and date and date < since:
                continue
            rejected = rejection_text(e)
            if rejected:
                yield date, path.stem[:8], "tool-rejected", rejected
                continue
            if not typed_by_human(e):
                continue
            text = user_text(e).strip()
            if not text:
                continue
            if text.startswith("[Request interrupted by user"):
                interrupted = True
                continue
            if not NOISE.match(text) and len(text) <= 1500 and (PATTERNS.match(text) or interrupted):
                yield date, path.stem[:8], "after-interrupt" if interrupted else "pattern", text
            interrupted = False
    yield None, matched, None, None


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project")
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--since", default="", help="ignore entries before this date (YYYY-MM-DD)")
    args = ap.parse_args(argv)
    if args.limit < 0:
        ap.error("--limit must be >= 0")
    project = str(Path(args.project).expanduser().resolve())
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "projects"
    roots = project_roots(project)
    exact = {encode(r) for r in roots}
    dirs = sorted({d for r in roots for d in base.glob(encode(r) + "*") if d.is_dir()})
    hits, seen, sessions = [], set(), 0
    for d in dirs:
        for f in sorted(d.glob("*.jsonl")):
            for date, sess, kind, text in scan(f, roots, d.name in exact, args.since):
                if date is None:
                    sessions += 1 if sess else 0
                    continue
                key = re.sub(r"\W+", " ", text.lower())[:80]
                if key not in seen:
                    seen.add(key)
                    hits.append((date, sess, kind, text))
    hits.sort(reverse=True)
    print(f"# {len(hits)} candidate corrections from {sessions} sessions\n")
    for date, sess, kind, text in hits[:args.limit]:
        print(f"- {date} [{sess}] ({kind}) {redact(' '.join(text.split()))[:300]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
