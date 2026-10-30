import json
import re
import unittest

from helpers import Sandbox


def user(text, ts="2026-10-01T10:00:00Z", **fields):
    return {"type": "user", "timestamp": ts, "message": {"role": "user", "content": text}, **fields}


def rejection(feedback, ts="2026-10-02T10:00:00Z", **fields):
    body = ("The user doesn't want to proceed with this tool use. The tool use was rejected. "
            f"To tell you how to proceed, the user said:\n{feedback}")
    return tool_result(body, ts, is_error=True, **fields)


def tool_result(body, ts="2026-10-02T10:00:00Z", is_error=False, **fields):
    return {"type": "user", "timestamp": ts, **fields, "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "t1", "content": body, "is_error": is_error}]}}


class MineCorrectionsTest(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.project = self.sb.repo("proj", {"README.md": "x"})

    def tearDown(self):
        self.sb.cleanup()

    def write_session(self, entries, name="s1", path=None):
        encoded = re.sub(r"[^A-Za-z0-9]", "-", str(path or self.project))
        d = self.sb.home / ".claude" / "projects" / encoded
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.jsonl").write_text("\n".join(json.dumps(e) for e in entries) + "\n")

    def mine(self, *extra):
        r = self.sb.run("mine_corrections.py", self.project, *extra)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_french_and_english_corrections_are_found(self):
        self.write_session([user("non, utilise make test"), user("don't run pnpm directly"), user("ok merci")])
        out = self.mine()
        self.assertIn("utilise make test", out)
        self.assertIn("don't run pnpm", out)
        self.assertNotIn("ok merci", out)

    def test_rejected_tool_feedback_is_found_once(self):
        self.write_session([rejection("passe par le Makefile"), rejection("passe par le Makefile")])
        out = self.mine()
        self.assertIn("(tool-rejected) passe par le Makefile", out)
        self.assertEqual(out.count("passe par le Makefile"), 1)

    def test_auto_mode_denial_is_not_a_user_correction(self):
        self.write_session([rejection("classifier text", toolDenialKind="automode-blocked")])
        self.assertIn("# 0 candidate", self.mine())

    def test_ask_user_question_clarify_is_not_feedback(self):
        self.write_session([rejection("The user wants to clarify these questions.\n    This means…")])
        self.assertIn("# 0 candidate", self.mine())

    def test_tool_output_quoting_the_wrapper_is_not_a_rejection(self):
        quoted = 'REJECTION = "The user doesn\'t want to proceed with this tool use. ... the user said: x"'
        self.write_session([tool_result("1\t#!/usr/bin/env python3\n2\t" + quoted)])
        self.assertIn("# 0 candidate", self.mine())

    def test_words_glued_to_a_hyphen_are_not_corrections(self):
        self.write_session([user("non-blocking IO is fine here"), user("no-op is expected")])
        self.assertIn("# 0 candidate", self.mine())

    def test_message_after_interrupt_is_found(self):
        self.write_session([user("[Request interrupted by user]"), user("travaille d'abord le design")])
        self.assertIn("(after-interrupt) travaille d'abord le design", self.mine())

    def test_duplicates_are_collapsed(self):
        self.write_session([user("non, pas comme ça"), user("non, pas comme ça")])
        self.assertEqual(self.mine().count("pas comme ça"), 1)

    def test_command_and_tag_noise_is_ignored(self):
        self.write_session([user("/compact"), user("<command-name>/x</command-name> non")])
        self.assertIn("# 0 candidate", self.mine())

    def test_non_human_turns_are_ignored(self):
        self.write_session([
            user("never touch prod", entrypoint="sdk-py"),
            user("never touch prod 2", promptSource="system", turnOrigin="peer"),
            user("never touch prod 3", turnOrigin="scheduled"),
            user("never touch prod 4", isSidechain=True),
            user("never touch prod 5", origin={"kind": "peer", "from": "a1"}),
            user("never touch prod 6", isCompactSummary=True),
        ])
        self.assertIn("# 0 candidate", self.mine())

    def test_typed_and_queued_messages_count(self):
        self.write_session([user("non, en français", promptSource="typed", origin={"kind": "human"}),
                            user("stop, pas de pnpm", promptSource="queued")])
        out = self.mine()
        self.assertIn("en français", out)
        self.assertIn("pas de pnpm", out)

    def test_sibling_project_with_same_prefix_is_excluded(self):
        sibling = self.sb.repo("proj-wt", {"README.md": "x"})
        self.write_session([user("non, sibling rule", cwd=str(sibling))], path=sibling)
        self.assertIn("# 0 candidate", self.mine())

    def test_subdirectory_sessions_are_included(self):
        sub = self.project / "web"
        sub.mkdir()
        self.write_session([user("non, sub rule", cwd=str(sub))], path=sub)
        self.assertIn("sub rule", self.mine())

    def test_sessions_in_a_nested_git_repo_are_excluded(self):
        nested = self.project / "vendor-tool"
        nested.mkdir()
        self.sb.git("init", "-q", nested)
        self.write_session([user("non, nested rule", cwd=str(nested))], path=nested)
        self.assertIn("# 0 candidate", self.mine())

    def test_claude_config_dir_is_honoured(self):
        moved = self.sb.root / "claude-config"
        self.sb.extra_env["CLAUDE_CONFIG_DIR"] = str(moved)
        d = moved / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(self.project))
        d.mkdir(parents=True)
        (d / "s.jsonl").write_text(json.dumps(user("non, moved config")) + "\n")
        self.assertIn("moved config", self.mine())

    def test_limit_is_applied_and_validated(self):
        self.write_session([user("non, a"), user("non, b", ts="2026-10-03T00:00:00Z")])
        self.assertEqual(self.mine("--limit", "1").count("\n- "), 1)
        self.assertEqual(self.sb.run("mine_corrections.py", self.project, "--limit", "-1").returncode, 2)

    def test_git_worktree_sessions_are_included(self):
        self.sb.git("-C", self.project, "commit", "-q", "--allow-empty", "-m", "init")
        wt = self.sb.root / "work" / "proj-feature"
        self.sb.git("-C", self.project, "worktree", "add", "-q", wt)
        self.write_session([user("non, worktree rule", cwd=str(wt))], path=wt)
        self.assertIn("worktree rule", self.mine())

    def test_since_filters_older_entries(self):
        self.write_session([user("non, old", ts="2026-01-01T00:00:00Z"), user("non, new", ts="2026-10-01T00:00:00Z")])
        out = self.mine("--since", "2026-06-01")
        self.assertIn("new", out)
        self.assertNotIn("old", out)

    def test_secrets_are_redacted(self):
        token = "ghp_" + "a" * 36
        self.write_session([user(f"non, utilise {token}"), user("non, password=hunter2 ici")])
        out = self.mine()
        self.assertNotIn(token, out)
        self.assertNotIn("hunter2", out)
        self.assertIn("[REDACTED]", out)

    def test_no_transcripts_is_not_an_error(self):
        self.assertIn("from 0 sessions", self.mine())


if __name__ == "__main__":
    unittest.main()
