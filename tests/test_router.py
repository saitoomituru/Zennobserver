"""JSON-LD routerの全件先行検査、lossless移動、冪等性、CTLを検証する。"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("editorial_router", ROOT / "scripts/editorial_router.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RouterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        (self.root / "config/editorial-router.json").write_bytes((ROOT / "config/editorial-router.json").read_bytes())
        self.router = module.Router(self.root)

    def material(self, char, transition="hold", complete=False, slug=None, month=None,
                 used_by=None, unresolved=None, unknown=True):
        item_id = char * 64
        directory = self.root / "INBOX/materials" / item_id
        directory.mkdir(parents=True)
        value = {
            "@context": {"editorial": "https://zeroroomlab.dev/ns/editorial#"},
            "@id": module.MATERIAL_URN + item_id,
            "@type": "editorial:Material",
            "editorial:complete": complete,
            "editorial:transition": transition,
            "editorial:source": [],
            "editorial:usedBy": used_by or [],
            "editorial:unresolved": unresolved or [],
        }
        if slug is not None:
            value["editorial:articleSlug"] = slug
        if month is not None:
            value["editorial:archiveMonth"] = month
        if unknown:
            value["unknown:must-survive"] = {"nested": [1, 2, 3]}
        text = "# 素材\n\n本文\n\n```jsonld zennobserver-material\n" + json.dumps(value, ensure_ascii=False, indent=2) + "\n```\n"
        (directory / "material.mdx").write_text(text)
        return item_id, directory

    def article(self, slug, ids):
        root = self.root / "articles"
        root.mkdir(parents=True, exist_ok=True)
        (root / f"{slug}.md").write_text("---\ntitle: test\npublished: false\n---\n")
        (root / f"{slug}.sources.jsonld").write_text(json.dumps({
            "@id": module.ARTICLE_URN + slug,
            "@type": "editorial:ZennArticle",
            "editorial:usesMaterial": [module.MATERIAL_URN + item_id for item_id in ids],
        }))

    def test_hold_and_unresolved_stay_in_inbox_and_ctl_uses_index(self):
        hold, hold_path = self.material("a")
        unresolved, unresolved_path = self.material("b", transition="unresolved", unresolved=["分類不能"])
        result = self.router.build()
        self.assertEqual(result["moves"], [])
        self.assertTrue(hold_path.exists())
        self.assertTrue(unresolved_path.exists())
        self.assertEqual([row["id"] for row in self.router.ctl("pending")], [hold])
        self.assertEqual([row["id"] for row in self.router.ctl("unresolved")], [unresolved])
        self.assertEqual(self.router.ctl("stats")["unarticleized"], 2)

    def test_archive_is_lossless_and_idempotent(self):
        slug = "buddy-permission-case"
        item_id, source = self.material("c", "archive", True, slug, "2026-10",
                                        [module.ARTICLE_URN + slug])
        self.article(slug, [item_id])
        before = (source / "material.mdx").read_bytes()
        dry = self.router.build(dry_run=True)
        self.assertEqual(len(dry["moves"]), 1)
        self.assertTrue(source.exists())
        result = self.router.build()
        target = self.root / "BACKNUMBERS/2026-10" / slug / item_id
        self.assertEqual(len(result["moves"]), 1)
        self.assertFalse(source.exists())
        self.assertEqual((target / "material.mdx").read_bytes(), before)
        self.assertIn('"unknown:must-survive"', (target / "material.mdx").read_text())
        self.assertEqual(self.router.build()["moves"], [])
        self.assertEqual([row["id"] for row in self.router.ctl("archived")], [item_id])

    def test_all_plans_are_validated_before_any_move(self):
        slug = "two-material-article"
        first, first_path = self.material("d", "archive", True, slug, "2026-10",
                                          [module.ARTICLE_URN + slug])
        second, second_path = self.material("e", "archive", True, slug, "2026-10",
                                            [module.ARTICLE_URN + slug])
        self.article(slug, [first])  # secondの逆参照を意図的に欠落させる。
        with self.assertRaises(module.RouterError):
            self.router.build()
        self.assertTrue(first_path.exists())
        self.assertTrue(second_path.exists())

    def test_path_injection_is_rejected(self):
        self.material("f", "archive", True, "../../outside", "2026-10",
                      [module.ARTICLE_URN + "../../outside"])
        with self.assertRaises(module.RouterError):
            self.router.build(dry_run=True)

    def test_incomplete_archive_is_rejected_even_with_valid_binding(self):
        slug = "incomplete-material"
        item_id, source = self.material("4", "archive", False, slug, "2026-10",
                                        [module.ARTICLE_URN + slug])
        self.article(slug, [item_id])
        with self.assertRaises(module.RouterError):
            self.router.build()
        self.assertTrue(source.exists())

    def test_legacy_is_indexed_but_never_moved(self):
        item_id = "1" * 64
        directory = self.root / "INBOX/items" / item_id
        directory.mkdir(parents=True)
        (directory / "item.json").write_text(json.dumps({"id": item_id, "payloads": {"x": "y"}}))
        (directory / "state.json").write_text(json.dumps({"status": "pending"}))
        self.router.build()
        self.assertTrue(directory.exists())
        self.assertEqual([row["id"] for row in self.router.ctl("unarticleized")], [item_id])

    def test_index_check_detects_manual_drift(self):
        self.material("2")
        self.router.build()
        (self.root / "INBOX/index.ndjson").write_text("tampered\n")
        with self.assertRaises(module.RouterError):
            self.router.reindex(check=True)

    def test_archived_path_must_keep_matching_tags(self):
        slug = "archive-path-check"
        item_id, source = self.material("5", "archive", True, slug, "2026-10",
                                        [module.ARTICLE_URN + slug])
        self.article(slug, [item_id])
        wrong = self.root / "BACKNUMBERS/2026-11" / slug / item_id
        wrong.parent.mkdir(parents=True)
        source.rename(wrong)
        with self.assertRaises(module.RouterError):
            self.router.reindex()

    def test_duplicate_json_key_is_rejected(self):
        _, directory = self.material("6")
        path = directory / "material.mdx"
        text = path.read_text().replace('"editorial:complete": false,',
                                        '"editorial:complete": false,\n  "editorial:complete": true,')
        path.write_text(text)
        with self.assertRaises(module.RouterError):
            self.router.build(dry_run=True)

    def test_multiple_metadata_blocks_and_id_mismatch_are_rejected(self):
        item_id, directory = self.material("3")
        path = directory / "material.mdx"
        path.write_text(path.read_text() + "\n```jsonld zennobserver-material\n{}\n```\n")
        with self.assertRaises(module.RouterError):
            self.router.build(dry_run=True)


if __name__ == "__main__":
    unittest.main()
