import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "project-setup" / "scripts"

FAKE_CLAUDE = f"""#!{sys.executable}
import json, os, sys
fx = json.load(open(os.environ["FAKE_CLAUDE"]))
args = sys.argv[1:]
if fx.get("mode") == "garbage":
    print("A new version is available\\n[not json")
    sys.exit(0)
if args[:3] == ["plugin", "list", "--json"]:
    print(json.dumps(fx.get("by_cwd", {{}}).get(os.getcwd(), fx.get("list", []))))
elif args[:2] == ["plugin", "details"]:
    print(fx.get("details", {{}}).get(args[2], ""))
else:
    sys.exit(1)
"""


class Sandbox:
    """Temp HOME and XDG config, and a PATH holding only git (plus an optional fake claude CLI)."""

    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix="ps-test-")).resolve()
        self.home = self.root / "home"
        self.home.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        (self.bin / "git").symlink_to(shutil.which("git"))
        self.extra_env = {}

    def env(self) -> dict:
        return {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.home / ".config"),
                "PATH": str(self.bin), "GIT_CONFIG_NOSYSTEM": "1", "PYTHONDONTWRITEBYTECODE": "1",
                "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
                "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com", **self.extra_env}

    def run(self, script: str, *args, cwd=None) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-I", str(SCRIPTS / script), *map(str, args)],
                              capture_output=True, text=True, env=self.env(), cwd=cwd)

    def git(self, *args):
        subprocess.run(["git", *map(str, args)], check=True, capture_output=True, env=self.env())

    def repo(self, name: str, files: dict, git: bool = True) -> Path:
        path = self.root / "work" / name
        path.mkdir(parents=True)
        for rel, content in files.items():
            f = path / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(content)
        if git:
            self.git("init", "-q", path)
        return path

    def user_config(self, data):
        cfg = self.home / ".config" / "project-setup" / "config.json"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(data if isinstance(data, str) else json.dumps(data))
        return cfg

    def fake_claude(self, fixture: dict):
        """Install a claude CLI answering `plugin list --json` (optionally per cwd) and `plugin details`."""
        fx = self.root / "fake_claude.json"
        fx.write_text(json.dumps(fixture))
        script = self.bin / "claude"
        script.write_text(FAKE_CLAUDE)
        script.chmod(0o755)
        self.extra_env["FAKE_CLAUDE"] = str(fx)

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)
