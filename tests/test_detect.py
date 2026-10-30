import json
import unittest

from helpers import Sandbox

GO_EXPORTER = {"go.mod": "module x\nrequire github.com/prometheus/client_golang v1.20.0\n"}
GRAFANA_PANEL = {"package.json": '{"dependencies": {"@grafana/ui": "12.0.0", "react": "19"}}',
                 "src/plugin.json": '{"type": "panel", "id": "x-panel"}'}
GITIGNORED = {".gitignore": ".claude/settings.local.json\n"}
EXPORTER_PLUGINS = ["gopls-lsp@claude-plugins-official", "cc-skills-golang@samber",
                    "prometheus-exporter@prometheus-exporter-marketplace"]


class DetectTest(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()

    def tearDown(self):
        self.sb.cleanup()

    def detect(self, path, *extra):
        r = self.sb.run("detect.py", path, *extra)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    # modes
    def test_empty_directory_is_empty_mode(self):
        self.assertEqual(self.detect(self.sb.repo("empty", {}))["mode"], "empty")

    def test_editor_and_os_files_do_not_make_a_directory_non_empty(self):
        repo = self.sb.repo("junk", {".DS_Store": "", ".vscode/settings.json": "{}"})
        self.assertEqual(self.detect(repo)["mode"], "empty")

    def test_root_claude_md_is_framed_and_measured(self):
        info = self.detect(self.sb.repo("framed", {"CLAUDE.md": "# x\nline"}))
        self.assertEqual(info["mode"], "framed")
        self.assertEqual(info["claude_md"]["lines"], 2)
        self.assertEqual(info["claude_md"]["path"], "CLAUDE.md")

    def test_dot_claude_claude_md_is_framed_too(self):
        info = self.detect(self.sb.repo("framed", {".claude/CLAUDE.md": "# x\n"}))
        self.assertEqual(info["mode"], "framed")
        self.assertEqual(info["claude_md"]["path"], ".claude/CLAUDE.md")

    def test_readme_licence_gitignore_only_is_still_empty(self):
        repo = self.sb.repo("gh", {"README.md": "# x", "LICENSE": "MIT", ".gitignore": "bin/"})
        self.assertEqual(self.detect(repo)["mode"], "empty")

    def test_code_without_claude_md_is_unframed(self):
        self.assertEqual(self.detect(self.sb.repo("u", GO_EXPORTER))["mode"], "unframed")

    def test_local_files_ignore_state_is_reported(self):
        info = self.detect(self.sb.repo("i", {".gitignore": "CLAUDE.local.md\n"}))
        self.assertIs(info["claude_local_md_ignored"], True)
        self.assertIs(info["local_settings_ignored"], False)

    def test_agents_md_is_reported(self):
        self.assertTrue(self.detect(self.sb.repo("a", {"AGENTS.md": "# a\n"}))["agents_md"])

    def test_missing_directory_is_an_error_not_an_empty_project(self):
        r = self.sb.run("detect.py", self.sb.root / "typo")
        self.assertEqual(r.returncode, 2)
        self.assertIn("not a directory", r.stderr)

    def test_directory_inside_another_repo_is_flagged(self):
        parent = self.sb.repo("mono", {"README.md": "x"})
        (parent / "newpkg").mkdir()
        info = self.detect(parent / "newpkg")
        self.assertTrue(info["inside_repo"])
        self.assertEqual(info["git_root"], str(parent))

    # signals
    def test_go_exporter_by_name(self):
        info = self.detect(self.sb.repo("snmp_exporter", GO_EXPORTER))
        self.assertEqual(info["signals"], ["go", "prometheus-exporter"])
        self.assertIn("cc-skills-golang@samber", info["plugins"])
        self.assertIn("gopls-lsp@claude-plugins-official", info["plugins"])

    def test_go_exporter_by_collector_code_without_exporter_in_name(self):
        info = self.detect(self.sb.repo("redfish_mon", {**GO_EXPORTER, "collector/c.go":
                                                        'd := prometheus.NewDesc("x", "", nil, nil)'}))
        self.assertIn("prometheus-exporter", info["signals"])

    def test_go_tool_using_client_golang_is_plain_go(self):
        self.assertEqual(self.detect(self.sb.repo("tool", GO_EXPORTER))["signals"], ["go"])

    def test_grafana_panel(self):
        self.assertEqual(self.detect(self.sb.repo("panel", GRAFANA_PANEL))["signals"], ["frontend", "grafana-plugin"])

    def test_faro_sdk_user_is_not_a_grafana_plugin(self):
        info = self.detect(self.sb.repo("app", {"package.json": '{"dependencies": {"@grafana/faro-web-sdk": "1"}}'}))
        self.assertNotIn("grafana-plugin", info["signals"])

    def test_non_grafana_src_plugin_json_is_ignored(self):
        info = self.detect(self.sb.repo("babel", {"src/plugin.json": '{"name": "x"}'}))
        self.assertNotIn("grafana-plugin", info["signals"])

    def test_language_markers(self):
        info = self.detect(self.sb.repo("poly", {"pyproject.toml": "", "Cargo.toml": "", "tsconfig.json": "{}",
                                                 "pom.xml": "", "composer.json": "{}", "Gemfile": "",
                                                 "CMakeLists.txt": ""}))
        for signal in ("python", "rust", "typescript", "java", "php", "ruby", "c-cpp"):
            self.assertIn(signal, info["signals"])
        self.assertIn("pyright-lsp@claude-plugins-official", info["plugins"])

    def test_gradle_kotlin_dsl_alone_is_java_not_kotlin(self):
        info = self.detect(self.sb.repo("j", {"build.gradle.kts": ""}))
        self.assertIn("java", info["signals"])
        self.assertNotIn("kotlin", info["signals"])
        info = self.detect(self.sb.repo("k", {"build.gradle.kts": "", "src/Main.kt": ""}))
        self.assertIn("kotlin", info["signals"])

    def test_observability_k6_docs_and_app_sdk_signals(self):
        info = self.detect(self.sb.repo("o", {"config/pipeline.alloy": "", "load/smoke.js": "import http from 'k6/http'",
                                              "mkdocs.yml": "", "go.mod": "module x\nrequire github.com/grafana/grafana-app-sdk v0.1\n"}))
        for signal in ("observability-stack", "k6", "docs-site", "grafana-app-sdk"):
            self.assertIn(signal, info["signals"])

    def test_provisioning_dir_is_observability_except_in_grafana_plugins(self):
        stack = self.detect(self.sb.repo("stack", {"provisioning/datasources/ds.yml": ""}))
        self.assertIn("observability-stack", stack["signals"])
        plugin = self.detect(self.sb.repo("plugin", {**GRAFANA_PANEL, "provisioning/datasources/ds.yml": ""}))
        self.assertNotIn("observability-stack", plugin["signals"])

    def test_vendored_and_hidden_dirs_are_not_scanned(self):
        info = self.detect(self.sb.repo("v", {"node_modules/x/loadtest.js": "import http from 'k6/http'",
                                              ".cache/a.alloy": ""}))
        self.assertEqual(info["signals"], [])

    # declared stacks and config
    def test_declared_stacks_give_plugins_to_an_empty_repo(self):
        info = self.detect(self.sb.repo("new", {}), "--stack", "go,Python,rust")
        self.assertEqual(info["mode"], "empty")
        self.assertEqual(info["signals"], ["go", "python", "rust"])
        self.assertIn("rust-analyzer-lsp@claude-plugins-official", info["plugins"])

    def test_unknown_declared_stack_is_reported(self):
        self.assertEqual(self.detect(self.sb.repo("new", {}), "--stack", "go,cobol")["unknown_stacks"], ["cobol"])

    def test_user_config_overrides_one_signal_and_keeps_others(self):
        self.sb.user_config({"plugin_map": {"frontend": ["mine@market"]}})
        info = self.detect(self.sb.repo("panel", GRAFANA_PANEL))
        self.assertIn("mine@market", info["plugins"])
        self.assertNotIn("frontend-design@claude-plugins-official", info["plugins"])
        self.assertIn("grafana-plugins@grafana-skills", info["plugins"])

    def test_stack_signals_override_and_xdg_config_home_are_honoured(self):
        elsewhere = self.sb.root / "xdg"
        cfg = elsewhere / "project-setup" / "config.json"
        cfg.parent.mkdir(parents=True)
        cfg.write_text(json.dumps({"stack_signals": {"cobol": ["go"]}}))
        self.sb.extra_env["XDG_CONFIG_HOME"] = str(elsewhere)
        info = self.detect(self.sb.repo("legacy", {}), "--stack", "cobol")
        self.assertEqual((info["signals"], info["unknown_stacks"]), (["go"], []))

    def test_invalid_user_config_is_a_clear_error(self):
        cfg = self.sb.user_config("{broken")
        r = self.sb.run("detect.py", self.sb.repo("x", {}))
        self.assertEqual(r.returncode, 2)
        self.assertIn(str(cfg), r.stderr)

    # installed-plugin filtering
    def test_without_claude_cli_filtering_is_skipped_and_said(self):
        r = self.sb.run("detect.py", self.sb.repo("snmp_exporter", GO_EXPORTER))
        info = json.loads(r.stdout)
        self.assertEqual(info["installed_check"], "skipped")
        self.assertEqual(info["not_installed"], [])
        self.assertIn("claude CLI not found", r.stderr)

    def test_not_installed_plugins_get_install_hints_and_are_not_proposed(self):
        self.sb.fake_claude({"list": [{"id": "gopls-lsp@claude-plugins-official", "enabled": True}]})
        info = self.detect(self.sb.repo("tool", GO_EXPORTER))
        self.assertEqual(info["installed_check"], "ok")
        self.assertEqual(info["plugins"], ["gopls-lsp@claude-plugins-official"])
        self.assertEqual(info["not_installed"], ["cc-skills-golang@samber"])
        self.assertEqual(info["install_hints"],
                         ["claude plugin marketplace add samber/cc && claude plugin install cc-skills-golang@samber"])

    def test_unreadable_cli_output_does_not_crash(self):
        self.sb.fake_claude({"mode": "garbage"})
        r = self.sb.run("detect.py", self.sb.repo("tool", GO_EXPORTER))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["installed_check"], "skipped")
        self.assertIn("unreadable output", r.stderr)


class BatchTest(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.repo = self.sb.repo("snmp_exporter", {**GO_EXPORTER, **GITIGNORED})
        self.settings = self.repo / ".claude" / "settings.local.json"
        self.sb.fake_claude({"list": [{"id": p, "enabled": False} for p in EXPORTER_PLUGINS]})

    def tearDown(self):
        self.sb.cleanup()

    def batch(self, *extra):
        return self.sb.run("detect.py", "--batch", self.sb.root / "work", *extra)

    def write_settings(self, data):
        self.settings.parent.mkdir(exist_ok=True)
        self.settings.write_text(data if isinstance(data, str) else json.dumps(data))

    def test_dry_run_reports_and_writes_nothing(self):
        self.assertIn("would write", self.batch().stdout)
        self.assertFalse(self.settings.exists())

    def test_apply_adds_plugins_and_preserves_other_keys(self):
        self.write_settings({"permissions": {"allow": ["x"]}, "enabledPlugins": {"other@m": False}})
        self.assertIn("written", self.batch("--apply").stdout)
        data = json.loads(self.settings.read_text())
        self.assertEqual(data["permissions"], {"allow": ["x"]})
        self.assertIs(data["enabledPlugins"]["other@m"], False)
        self.assertIs(data["enabledPlugins"]["cc-skills-golang@samber"], True)
        self.assertEqual([p.name for p in self.settings.parent.iterdir()], ["settings.local.json"])

    def test_explicit_false_from_the_user_is_kept(self):
        self.write_settings({"enabledPlugins": {"cc-skills-golang@samber": False}})
        out = self.batch("--apply").stdout
        self.assertIs(json.loads(self.settings.read_text())["enabledPlugins"]["cc-skills-golang@samber"], False)
        self.assertIn("kept off by you: cc-skills-golang@samber", out)

    def test_first_apply_creates_the_file_and_second_is_unchanged(self):
        self.batch("--apply")
        self.assertTrue(self.settings.exists())
        self.assertIn("unchanged", self.batch("--apply").stdout)

    def test_apply_backs_up_an_existing_file_outside_the_repo(self):
        self.write_settings({"permissions": {"allow": ["x"]}})
        self.batch("--apply")
        backups = list((self.sb.home / ".cache" / "project-setup" / "backups").rglob("*settings.local.json"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(json.loads(backups[0].read_text()), {"permissions": {"allow": ["x"]}})

    def test_apply_is_refused_when_installed_plugins_cannot_be_listed(self):
        (self.sb.bin / "claude").unlink()
        r = self.batch("--apply")
        self.assertEqual(r.returncode, 2)
        self.assertIn("refusing to write", r.stderr)
        self.assertFalse(self.settings.exists())

    def test_not_installed_plugins_are_reported_and_not_written(self):
        self.sb.fake_claude({"list": [{"id": EXPORTER_PLUGINS[0], "enabled": False}]})
        out = self.batch("--apply").stdout
        self.assertIn("not installed: cc-skills-golang@samber", out)
        self.assertEqual(list(json.loads(self.settings.read_text())["enabledPlugins"]), [EXPORTER_PLUGINS[0]])

    def test_repo_where_local_settings_are_not_ignored_is_skipped(self):
        (self.repo / ".gitignore").write_text("")
        self.assertIn("not gitignored", self.batch("--apply").stdout)
        self.assertFalse(self.settings.exists())

    def test_invalid_json_is_never_overwritten(self):
        self.write_settings("{broken")
        self.assertIn("invalid JSON", self.batch("--apply").stdout)
        self.assertEqual(self.settings.read_text(), "{broken")

    def test_unexpected_structure_is_never_overwritten(self):
        self.write_settings({"enabledPlugins": ["not", "a", "dict"]})
        self.assertIn("unexpected settings structure", self.batch("--apply").stdout)

    def test_batch_exclude_skips_directories(self):
        self.sb.user_config({"batch_exclude": ["snmp_exporter"]})
        self.assertNotIn("snmp_exporter", self.batch().stdout)

    def test_worktree_with_git_file_is_found(self):
        wt = self.sb.repo("wt_exporter", {**GO_EXPORTER, **GITIGNORED}, git=False)
        (wt / ".git").write_text(f"gitdir: {self.repo}/.git\n")
        self.assertIn("wt_exporter", self.batch().stdout)

    def test_plugins_already_enabled_at_user_level_are_not_written(self):
        self.sb.fake_claude({"list": [{"id": EXPORTER_PLUGINS[0], "enabled": True}] +
                                     [{"id": p, "enabled": False} for p in EXPORTER_PLUGINS[1:]]})
        self.batch("--apply")
        written = json.loads(self.settings.read_text())["enabledPlugins"]
        self.assertNotIn(EXPORTER_PLUGINS[0], written)
        self.assertEqual(sorted(written), sorted(EXPORTER_PLUGINS[1:]))

    def test_apply_without_batch_is_a_usage_error(self):
        self.assertEqual(self.sb.run("detect.py", self.repo, "--apply").returncode, 2)


if __name__ == "__main__":
    unittest.main()
