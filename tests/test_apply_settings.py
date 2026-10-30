import json
import unittest

from helpers import Sandbox


class ApplySettingsTest(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.repo = self.sb.repo("r", {".gitignore": ".claude/settings.local.json\n"})
        self.settings = self.repo / ".claude" / "settings.local.json"

    def tearDown(self):
        self.sb.cleanup()

    def apply(self, *args):
        return self.sb.run("apply_settings.py", self.repo, *args)

    def write_settings(self, data):
        self.settings.parent.mkdir(exist_ok=True)
        self.settings.write_text(data if isinstance(data, str) else json.dumps(data))

    def backups(self):
        return list((self.sb.home / ".cache" / "project-setup" / "backups").rglob("*"))

    def test_sets_entries_keeps_other_keys_and_backs_up_outside_the_repo(self):
        self.write_settings({"permissions": {"allow": ["Bash(make test *)"]}, "enabledPlugins": {"a@m": False}})
        r = self.apply("--enable", "a@m", "--disable", "b@m", "--skill-off", "slidev")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("enabledPlugins.a@m: False -> True", r.stdout)
        data = json.loads(self.settings.read_text())
        self.assertEqual(data["permissions"], {"allow": ["Bash(make test *)"]})
        self.assertEqual(data["enabledPlugins"], {"a@m": True, "b@m": False})
        self.assertEqual(data["skillOverrides"], {"slidev": "off"})
        self.assertEqual(len([p for p in self.backups() if p.is_file()]), 1)
        self.assertEqual([p.name for p in self.settings.parent.iterdir()], ["settings.local.json"])

    def test_refuses_when_not_gitignored(self):
        (self.repo / ".gitignore").write_text("")
        r = self.apply("--enable", "a@m")
        self.assertEqual(r.returncode, 2)
        self.assertIn("not gitignored", r.stderr)
        self.assertFalse(self.settings.exists())

    def test_plain_directory_without_git_is_allowed(self):
        folder = self.sb.repo("plain", {}, git=False)
        r = self.sb.run("apply_settings.py", folder, "--enable", "a@m")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((folder / ".claude" / "settings.local.json").exists())

    def test_invalid_json_is_refused_and_untouched(self):
        self.write_settings("{broken")
        self.assertEqual(self.apply("--enable", "a@m").returncode, 2)
        self.assertEqual(self.settings.read_text(), "{broken")

    def test_dry_run_and_unchanged_write_nothing(self):
        self.assertIn("(unset) -> True", self.apply("--enable", "a@m", "--dry-run").stdout)
        self.assertFalse(self.settings.exists())
        self.apply("--enable", "a@m")
        self.assertEqual(self.apply("--enable", "a@m").stdout.strip(), "unchanged")
        self.assertEqual(self.backups(), [])

    def test_conflicting_enable_and_disable_is_an_error(self):
        self.assertEqual(self.apply("--enable", "a@m", "--disable", "a@m").returncode, 2)


if __name__ == "__main__":
    unittest.main()
