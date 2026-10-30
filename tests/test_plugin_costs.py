import json
import unittest

from helpers import Sandbox

DETAILS = {
    "big@m": "Component inventory\n  Skills (3)\n\nProjected token cost\n  Always-on:   ~1,200 tok   added",
    "lsp@m": "Component inventory\n  LSP servers (1)\n\nProjected token cost\n  Always-on:   ~0 tok   added",
}
USER_LEVEL = [{"id": "big@m", "version": "1", "enabled": True}, {"id": "lsp@m", "version": "1", "enabled": True}]


class PluginCostsTest(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.repo = self.sb.repo("r", {})
        repo_view = [{"id": "big@m", "version": "1", "enabled": False}, {"id": "lsp@m", "version": "1", "enabled": True}]
        self.sb.fake_claude({"list": USER_LEVEL, "by_cwd": {str(self.repo): repo_view}, "details": DETAILS})

    def tearDown(self):
        self.sb.cleanup()

    def costs(self):
        r = self.sb.run("plugin_costs.py", "--repo", self.repo, "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_user_and_repo_states_and_totals_differ(self):
        data = self.costs()
        big = next(p for p in data["plugins"] if p["id"] == "big@m")
        self.assertEqual((big["user"], big["repo"], big["always_on"]), (True, False, 1200))
        self.assertEqual(data["totals"], {"user": 1200, "repo": 0})

    def test_lsp_only_and_always_keep_are_flagged(self):
        self.sb.user_config({"always_keep": ["big@m"]})
        rows = {p["id"]: p for p in self.costs()["plugins"]}
        self.assertTrue(rows["lsp@m"]["lsp_only"])
        self.assertTrue(rows["big@m"]["keep"])
        self.assertFalse(rows["lsp@m"]["keep"])

    def test_missing_cli_is_a_clear_error(self):
        (self.sb.bin / "claude").unlink()
        r = self.sb.run("plugin_costs.py", "--repo", self.repo)
        self.assertEqual(r.returncode, 2)
        self.assertIn("claude CLI not found", r.stderr)

    def test_failed_lookups_are_not_cached(self):
        self.sb.fake_claude({"list": USER_LEVEL, "details": {"big@m": DETAILS["big@m"]}})
        rows = {p["id"]: p for p in self.costs()["plugins"]}
        self.assertIsNone(rows["lsp@m"]["always_on"])
        cache = json.loads((self.sb.home / ".cache" / "project-setup" / "plugin_costs.json").read_text())
        self.assertEqual(list(cache), ["big@m@1"])

    def test_stale_entries_are_refetched(self):
        cache = self.sb.home / ".cache" / "project-setup" / "plugin_costs.json"
        cache.parent.mkdir(parents=True)
        cache.write_text(json.dumps({"big@m@1": {"always_on": 999, "components": {}, "at": 0}}))
        self.assertEqual(self.costs()["totals"]["user"], 1200)

    def test_a_plugin_installed_in_two_scopes_is_counted_once(self):
        twice = USER_LEVEL + [{"id": "big@m", "version": "1", "enabled": False, "scope": "project"}]
        self.sb.fake_claude({"list": twice, "details": DETAILS})
        data = self.costs()
        self.assertEqual([p["id"] for p in data["plugins"]].count("big@m"), 1)
        self.assertEqual(data["totals"]["user"], 1200)

    def test_corrupt_cache_is_rebuilt(self):
        cache = self.sb.home / ".cache" / "project-setup" / "plugin_costs.json"
        cache.parent.mkdir(parents=True)
        cache.write_text("{corrupt")
        self.assertEqual(self.costs()["totals"]["user"], 1200)


if __name__ == "__main__":
    unittest.main()
