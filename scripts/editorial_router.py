#!/usr/bin/env python3
"""素材MDXのJSON-LD宣言を検証し、配置・索引・CTLへ機械的にコンパイルする。"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parent.parent
MATERIAL_ID = re.compile(r"^[0-9a-f]{64}$")
ARTICLE_SLUG = re.compile(r"^[a-z0-9_-]{12,50}$")
ARCHIVE_MONTH = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$")
MATERIAL_URN = "urn:zennobserver:material:"
ARTICLE_URN = "urn:zennobserver:article:"


class RouterError(Exception):
    """意味判断を補わず、配置を一件も進めずに停止する。"""


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def strict_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise RouterError(f"JSON keyが重複しています: {key}")
        value[key] = item
    return value


def parse_json(text):
    return json.loads(text, object_pairs_hook=strict_object)


def read_json(path):
    return parse_json(Path(path).read_text(encoding="utf-8-sig"))


def atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Router:
    def __init__(self, root=ROOT):
        self.root = Path(root).resolve()
        self.config = read_json(self.root / "config/editorial-router.json")

    def inside(self, relative):
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root):
            raise RouterError("リポ外のパスは扱えません。")
        return path

    @contextmanager
    def lock(self):
        path = self.inside(".editorial-router.lock")
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise RouterError("Actionサーバーは別実行で使用中です。") from None
        try:
            with os.fdopen(fd, "w") as stream:
                stream.write(str(os.getpid()))
            yield
        finally:
            path.unlink(missing_ok=True)

    def relative(self, path):
        return Path(path).resolve().relative_to(self.root).as_posix()

    def material_fence(self, text):
        label = re.escape(self.config["material_fence"])
        pattern = re.compile(rf"^```{label}[ \t]*\r?\n(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)
        matches = pattern.findall(text)
        if len(matches) != 1:
            raise RouterError("素材MDXには専用JSON-LD fenceが一つだけ必要です。")
        try:
            value = parse_json(matches[0])
        except json.JSONDecodeError as error:
            raise RouterError(f"素材JSON-LDが不正です: line={error.lineno}") from None
        if not isinstance(value, dict):
            raise RouterError("素材JSON-LDはobjectでなければなりません。")
        return value

    def read_material(self, directory, location):
        directory = Path(directory)
        if directory.is_symlink() or not MATERIAL_ID.fullmatch(directory.name):
            raise RouterError("素材folder名は64桁SHA256で、symlinkは禁止です。")
        path = directory / "material.mdx"
        if path.is_symlink() or not path.is_file():
            raise RouterError(f"material.mdxがありません: {self.relative(directory)}")
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise RouterError("素材MDXはUTF-8でなければなりません。") from None
        value = self.material_fence(text)
        item_id = directory.name
        urn = MATERIAL_URN + item_id
        types = value.get("@type")
        types = [types] if isinstance(types, str) else types
        if value.get("@id") != urn or not isinstance(types, list) or "editorial:Material" not in types:
            raise RouterError(f"素材IDまたは@typeがfolderと一致しません: {item_id}")
        transition = value.get("editorial:transition", "hold")
        if transition not in self.config["transitions"]:
            raise RouterError(f"未登録transitionです: {transition}")
        complete = value.get("editorial:complete", False)
        if not isinstance(complete, bool):
            raise RouterError("editorial:completeはbooleanです。")
        used_by = value.get("editorial:usedBy", [])
        unresolved = value.get("editorial:unresolved", [])
        if not isinstance(used_by, list) or not all(isinstance(row, str) for row in used_by):
            raise RouterError("editorial:usedByはURN文字列の配列です。")
        if not isinstance(unresolved, list) or not all(isinstance(row, str) and row.strip() for row in unresolved):
            raise RouterError("editorial:unresolvedは非空文字列の配列です。")
        if transition == "unresolved" and not unresolved:
            raise RouterError("unresolved遷移には判定不能理由が必要です。")
        return {
            "id": item_id,
            "urn": urn,
            "format": "mdx-jsonld",
            "location": location,
            "path": self.relative(directory),
            "transition": transition,
            "complete": complete,
            "article_slug": value.get("editorial:articleSlug"),
            "archive_month": value.get("editorial:archiveMonth"),
            "used_by": used_by,
            "unresolved": unresolved,
            "content_sha256": digest(raw),
        }

    def material_directories(self):
        inbox_root = self.inside(self.config["material_root"])
        inbox = sorted(p for p in inbox_root.glob("*") if p.is_dir()) if inbox_root.exists() else []
        archive_root = self.inside(self.config["backnumber_root"])
        archived = sorted(p.parent for p in archive_root.glob("*/*/*/material.mdx")) if archive_root.exists() else []
        return inbox, archived

    def scan_materials(self):
        inbox, archived = self.material_directories()
        records = [self.read_material(path, "inbox") for path in inbox]
        records += [self.read_material(path, "backnumbers") for path in archived]
        ids = [row["id"] for row in records]
        if len(ids) != len(set(ids)):
            raise RouterError("同じ素材IDが複数の配置に存在します。")
        for record in records:
            if record["location"] == "backnumbers":
                if record["transition"] != "archive" or not record["complete"] or record["unresolved"]:
                    raise RouterError(f"BACKNUMBERSに未完了素材があります: {record['id']}")
                slug, month = self.article_binding(record)
                expected = f"{self.config['backnumber_root']}/{month}/{slug}/{record['id']}"
                if record["path"] != expected:
                    raise RouterError(f"BACKNUMBERSの配置がtagと一致しません: {record['id']}")
        return records

    def article_binding(self, record):
        slug = record["article_slug"]
        month = record["archive_month"]
        if not isinstance(slug, str) or not ARTICLE_SLUG.fullmatch(slug):
            raise RouterError(f"archiveの記事slugが不正です: {record['id']}")
        if not isinstance(month, str) or not ARCHIVE_MONTH.fullmatch(month):
            raise RouterError(f"archiveMonthが不正です: {record['id']}")
        article = self.inside(f"{self.config['article_root']}/{slug}.md")
        sidecar = self.inside(f"{self.config['article_root']}/{slug}.sources.jsonld")
        if not article.is_file() or article.is_symlink() or not sidecar.is_file() or sidecar.is_symlink():
            raise RouterError(f"記事または素材逆参照がありません: {slug}")
        value = read_json(sidecar)
        expected_article = ARTICLE_URN + slug
        refs = value.get("editorial:usesMaterial") if isinstance(value, dict) else None
        if value.get("@id") != expected_article or not isinstance(refs, list) or record["urn"] not in refs:
            raise RouterError(f"記事側の素材逆参照が一致しません: {record['id']}")
        if expected_article not in record["used_by"]:
            raise RouterError(f"素材側のusedByが記事と一致しません: {record['id']}")
        return slug, month

    def plan(self):
        records = self.scan_materials()
        plans = []
        targets = set()
        for record in records:
            if record["location"] != "inbox" or record["transition"] != "archive":
                continue
            if not record["complete"] or record["unresolved"]:
                raise RouterError(f"未完了・未解決素材はarchiveできません: {record['id']}")
            slug, month = self.article_binding(record)
            source = self.inside(record["path"])
            target = self.inside(f"{self.config['backnumber_root']}/{month}/{slug}/{record['id']}")
            if target.exists() or target in targets:
                raise RouterError(f"移動先が衝突します: {self.relative(target)}")
            targets.add(target)
            plans.append({"id": record["id"], "from": self.relative(source), "to": self.relative(target)})
        return plans

    def legacy_records(self):
        root = self.inside(self.config["legacy_root"])
        rows = []
        if not root.exists():
            return rows
        for directory in sorted(root.glob("*")):
            if not directory.is_dir() or not (directory / "item.json").is_file():
                continue
            metadata = read_json(directory / "item.json")
            state = read_json(directory / "state.json")
            item_id = metadata.get("id", directory.name)
            if item_id != directory.name or not MATERIAL_ID.fullmatch(item_id):
                raise RouterError("legacy素材IDが不正です。")
            rows.append({
                "id": item_id,
                "urn": MATERIAL_URN + item_id,
                "format": "legacy-bundle",
                "location": "inbox",
                "path": self.relative(directory),
                "transition": state.get("status", "pending"),
                "complete": False,
                "used_by": [],
                "unresolved": [state.get("reason")] if state.get("status") == "blocked" and state.get("reason") else [],
                "content_sha256": digest(encoded(metadata.get("payloads", {}))),
            })
        return rows

    def outline_records(self):
        root = self.inside(self.config["outline_root"])
        if not root.exists():
            return []
        return [{"id": path.stem, "format": "outline-md", "location": "outlines",
                 "path": self.relative(path)}
                for path in sorted(root.rglob("*.md")) if path.name != "AGENTS.md"]

    def index_rows(self):
        materials = self.scan_materials()
        inbox = sorted([*self.legacy_records(), *(row for row in materials if row["location"] == "inbox")],
                       key=lambda row: (row["id"], row["path"]))
        archived = sorted((row for row in materials if row["location"] == "backnumbers"),
                          key=lambda row: (row["id"], row["path"]))
        outlines = sorted(self.outline_records(), key=lambda row: (row["id"], row["path"]))
        return {"inbox": inbox, "backnumbers": archived, "outlines": outlines}

    def index_bytes(self):
        return {name: b"".join(encoded(row) for row in rows) for name, rows in self.index_rows().items()}

    def reindex(self, check=False):
        values = self.index_bytes()
        changed = []
        for name, data in values.items():
            path = self.inside(self.config["indexes"][name])
            current = path.read_bytes() if path.exists() else None
            if current != data:
                changed.append(self.relative(path))
                if not check:
                    atomic(path, data)
        if check and changed:
            raise RouterError("索引がmetadataと一致しません: " + ", ".join(changed))
        return changed

    def build(self, dry_run=False):
        plans = self.plan()  # 全件を先に検査し、途中の意味エラーによる部分移動を避ける。
        if dry_run:
            return {"dry_run": True, "moves": plans, "indexes": "not-written"}
        for plan in plans:
            source = self.inside(plan["from"])
            target = self.inside(plan["to"])
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)
        changed = self.reindex()
        return {"dry_run": False, "moves": plans, "indexes": changed}

    def ctl(self, query):
        rows = []
        for name in ("inbox", "backnumbers", "outlines"):
            path = self.inside(self.config["indexes"][name])
            if not path.is_file():
                raise RouterError("索引がありません。先にbuildまたはreindexを実行してください。")
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rows.append(parse_json(line))
        if query == "pending":
            result = [row for row in rows if row.get("location") == "inbox" and not row.get("unresolved")]
        elif query == "unarticleized":
            result = [row for row in rows if row.get("location") == "inbox" and not row.get("used_by")]
        elif query == "unresolved":
            result = [row for row in rows if row.get("unresolved") or row.get("transition") == "unresolved"]
        elif query == "archived":
            result = [row for row in rows if row.get("location") == "backnumbers"]
        elif query == "stats":
            counts = {"inbox": 0, "backnumbers": 0, "outlines": 0, "unarticleized": 0, "unresolved": 0}
            for row in rows:
                if row.get("location") in counts:
                    counts[row["location"]] += 1
                if row.get("location") == "inbox" and not row.get("used_by"):
                    counts["unarticleized"] += 1
                if row.get("unresolved") or row.get("transition") == "unresolved":
                    counts["unresolved"] += 1
            return counts
        else:
            raise RouterError("未登録CTL queryです。")
        return sorted(result, key=lambda row: (row.get("id", ""), row.get("path", "")))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="operation", required=True)
    build = sub.add_parser("build", help="遷移を検証・適用して索引を再生成")
    build.add_argument("--dry-run", action="store_true")
    reindex = sub.add_parser("reindex", help="metadataから索引を再生成")
    reindex.add_argument("--check", action="store_true")
    ctl = sub.add_parser("ctl", help="本文を読まず索引へ問い合わせる")
    ctl.add_argument("query", choices=("pending", "unarticleized", "unresolved", "archived", "stats"))
    args = parser.parse_args(argv)
    try:
        router = Router(args.root)
        with router.lock():
            if args.operation == "build":
                result = router.build(args.dry_run)
            elif args.operation == "reindex":
                result = {"changed": router.reindex(args.check), "check": args.check}
            else:
                result = router.ctl(args.query)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (RouterError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
