"""INBOXの保持・再実行・異常終了・監査bindingを実リポfixtureで確かめる。"""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("editorial", ROOT / "scripts/editorial.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class API:
    def __init__(self, fail=False):
        self.fail = fail
        self.issues = {}
        self.posts = 0

    def public_repo(self, name):
        pass

    def ensure_exception(self, repository, marker, title, body):
        if self.fail:
            raise module.EditorialError("認証できません")
        if marker not in self.issues:
            self.posts += 1
            self.issues[marker] = f"https://github.com/{repository}/issues/{self.posts}"
        return self.issues[marker]


class EditorialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        self.config = json.loads((ROOT / "config/editorial.json").read_text())
        (self.root / "config/editorial.json").write_text(json.dumps(self.config))
        self.api = API()
        self.editor = module.Editor(self.root, self.api)

    def material(self):
        return self.editor.save("document-diff", {"repository": "test/source"}, {"documents.patch": b"original"})

    def test_block_retains_source_and_is_idempotent(self):
        item = self.material()
        self.assertEqual(self.editor.block(item, "分類不能"), 2)
        self.assertEqual(self.editor.block(item, "分類不能"), 2)
        path, _ = self.editor.item(item)
        self.assertEqual((path / "documents.patch").read_bytes(), b"original")
        self.assertEqual(self.api.posts, 1)
        self.assertEqual(module.read_json(path / "state.json")["status"], "blocked")

    def test_auth_failure_preserves_retry_request_and_never_claims_success(self):
        item = self.material()
        self.api.fail = True
        self.assertEqual(self.editor.block(item, "unknown"), 3)
        path, _ = self.editor.item(item)
        self.assertTrue((path / "exception-request.json").exists())
        self.assertEqual(module.read_json(path / "state.json")["issue_status"], "failed")
        self.api.fail = False
        self.assertEqual(self.editor.block(item, "unknown"), 2)

    def test_payload_tampering_and_escape_are_rejected(self):
        item = self.material()
        path, _ = self.editor.item(item)
        (path / "documents.patch").write_bytes(b"changed")
        with self.assertRaises(module.EditorialError):
            self.editor.item(item)
        with self.assertRaises(module.EditorialError):
            self.editor.inside("../outside")

    def test_duplicate_input_does_not_reset_blocked_state(self):
        item = self.material()
        self.editor.block(item, "判断待ち")
        self.assertEqual(item, self.material())
        path, _ = self.editor.item(item)
        self.assertEqual(module.read_json(path / "state.json")["status"], "blocked")

    def test_lock_prevents_parallel_mutation(self):
        with self.editor.lock():
            with self.assertRaises(module.EditorialError):
                with self.editor.lock():
                    pass

    def test_partial_issue_fetch_keeps_body_and_received_comments(self):
        module.write_json(self.root / "sources/catalog.json", {"repositories": []})
        url = "https://github.com/saitoomituru/SphereOS-Atlantis/issues/24"
        self.api.request = lambda path: {"html_url": url, "title": "原本", "body": "本文"}
        def comments(path):
            yield {"html_url": url + "#issuecomment-1", "body": "取得済み"}
            raise module.EditorialError("次ページの取得失敗")
        self.api.pages = comments
        item, code = self.editor.fetch_issue(url)
        self.assertEqual(code, 2)
        path, _ = self.editor.item(item)
        data = module.read_json(path / "issue.json")
        self.assertEqual(data["issue"]["body"], "本文")
        self.assertEqual(data["comments"][0]["body"], "取得済み")
        self.assertEqual(module.read_json(path / "state.json")["status"], "blocked")

    def git(self, path, *args):
        return subprocess.check_output(["git", *args], cwd=path, stderr=subprocess.DEVNULL).decode().strip()

    def test_real_diff_preserves_deletion_and_rename_before_checkout(self):
        self.git(self.root, "init")
        self.git(self.root, "config", "user.email", "test@example.invalid")
        self.git(self.root, "config", "user.name", "test")
        source = self.root / "sources/test/source"
        source.mkdir(parents=True)
        self.git(source, "init")
        self.git(source, "config", "user.email", "test@example.invalid")
        self.git(source, "config", "user.name", "test")
        self.git(source, "remote", "add", "origin", "https://github.com/test/source.git")
        (source / "old.md").write_text("before\n")
        self.git(source, "add", ".")
        self.git(source, "commit", "-m", "before")
        old = self.git(source, "rev-parse", "HEAD")
        self.git(self.root, "update-index", "--add", "--cacheinfo", f"160000,{old},sources/test/source")
        self.git(self.root, "commit", "-m", "pin")
        (source / "old.md").rename(source / "new.md")
        (source / "new.md").write_text("after\n")
        self.git(source, "add", ".")
        self.git(source, "commit", "-m", "after")
        new = self.git(source, "rev-parse", "HEAD")
        self.config["control_sources"] = []
        module.write_json(self.root / "config/editorial.json", self.config)
        module.write_json(self.root / "sources/catalog.json", {"repositories": [
            {"name": "test/source", "path": "sources/test/source", "branch": "main", "revision": old}]})
        editor = module.Editor(self.root, self.api)
        ids, code = editor.collect()
        self.assertEqual(code, 0)
        self.assertEqual(len(ids), 1)
        path, metadata = editor.item(ids[0])
        diff = (path / "documents.patch").read_text()
        self.assertIn("-before", diff)
        self.assertIn("+after", diff)
        self.assertEqual(metadata["source"]["before"], old)
        self.assertEqual(metadata["source"]["after"], new)
        self.assertEqual(editor.collect()[0], ids)
        # fetch済みの新revisionを模擬し、INBOX保存がcheckoutより先であることを確認する。
        self.git(source, "checkout", "--detach", old)
        self.git(source, "fetch", ".", new)
        real_git = editor.git
        events = []
        real_save = editor.save
        def save(*args, **kwargs):
            result = real_save(*args, **kwargs)
            events.append("saved")
            return result
        def git(path, *args):
            if args[0] == "fetch":
                return b""
            if args[0] == "checkout":
                self.assertIn("saved", events)
                events.append("checkout")
            return real_git(path, *args)
        with patch.object(editor, "git", side_effect=git), patch.object(editor, "save", side_effect=save):
            self.assertEqual(editor.collect(update=True), (ids, 0))
        self.assertEqual(events, ["saved", "checkout"])
        self.assertEqual(self.git(source, "rev-parse", "HEAD"), new)
        (source / "new.md").write_text("unsaved\n")
        ids, code = editor.collect()
        self.assertEqual(code, 2)
        self.assertEqual((source / "new.md").read_text(), "unsaved\n")

    def test_route_requires_all_positions_exact_hash_and_current_rulers(self):
        item = self.material()
        _, metadata = self.editor.item(item)
        target = self.root / "magazines/neetrunner/AGENTS.md"
        target.parent.mkdir(parents=True)
        target.write_text("差分規約")
        vendor = self.root / module.ATLANTIS
        (vendor / "magi/0.2.1").mkdir(parents=True)
        for name in ("validate_temporal_receipt.py", "oae-temporal-policy.json"):
            (vendor / "magi/0.2.1" / name).write_bytes((ROOT / module.ATLANTIS / "magi/0.2.1" / name).read_bytes())
        audit = {"item_id": item, "payloads": metadata["payloads"], "destination": "neetrunner",
                 "source_revisions": {"atlantis": "a", "manifest": "b"},
                 "action_gate": "pass", "unresolved": [], "disagreements": [], "human_confirmation_required": [],
                 "positions": {s: {"gate": "pass", "finding": "条件と観測を確認"} for s in ("maxwell", "uriel", "raphael")},
                 "temporal": {"version": "0.2.1", "observation_mode": "current-interpretation-of-history",
                     "observed_at": module.now(), "historical_oae_status": "historical-oae-unavailable",
                     "historical_role_attribution": "none", "retroactive_backfill": False,
                     "same_worldline_mutation": False, "claims_physical_time_travel": False,
                     "last_order": {"code": "OAE-HISTORY-UNKNOWN", "action": "stop-retroactive-backfill"}}}
        for key in ("observer", "declared_position", "position_talk_risk", "claim_scope", "ruler_provenance"):
            audit[key] = "明示した監査位置"
        with patch.object(self.editor, "magi_context", return_value={"source_revisions": audit["source_revisions"]}):
            self.assertEqual(self.editor.route(item, "neetrunner", audit), 0)
            audit["positions"]["uriel"]["gate"] = "bottom"
            self.assertEqual(self.editor.route(item, "neetrunner", audit), 2)
            audit["positions"]["uriel"]["gate"] = "pass"
            audit["payloads"] = {}
            self.assertEqual(self.editor.route(item, "neetrunner", audit), 2)
            audit["payloads"] = metadata["payloads"]
            audit["temporal"]["retroactive_backfill"] = True
            self.assertEqual(self.editor.route(item, "neetrunner", audit), 2)


if __name__ == "__main__":
    unittest.main()
