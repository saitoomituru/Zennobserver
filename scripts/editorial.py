#!/usr/bin/env python3
"""資料差分とIssueをINBOXへ保存し、MAGI監査・振分・判定不能の終了を接続する。"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
ATLANTIS = ".vendor/SphereOS-Atlantis"
MANIFEST = ".vendor/ZeroRoomLab-manifest"
SHA = re.compile(r"^[0-9a-f]{40}$")
ISSUE_URL = re.compile(r"^https://github\.com/([\w.-]+/[\w.-]+)/issues/([1-9][0-9]*)$")


class EditorialError(Exception):
    """処理を継続せず、資料と例外票を保持する。"""


def now():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def write_json(path, value):
    atomic(path, encoded(value))


def command(argv, cwd):
    # stderrはcredentialやリモート本文を含み得るため例外票へ転載しない。
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_LFS_SKIP_SMUDGE="1")
    result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, timeout=120)
    if result.returncode:
        raise EditorialError(f"コマンド失敗: {argv[0]} {argv[1]} (exit={result.returncode})")
    return result.stdout


class GitHub:
    """公開リポの資料取得と、指定したZennobserverの例外Issueだけを扱う。"""
    def __init__(self, max_pages=100):
        self.max_pages = max_pages

    def request(self, path, value=None):
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "Zennobserver",
                   "X-GitHub-Api-Version": "2026-03-10"}
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = "Bearer " + token
        if value is not None and not token:
            raise EditorialError("Issue起票にはGH_TOKENまたはGITHUB_TOKENが必要です。")
        data = encoded(value) if value is not None else None
        try:
            with urlopen(Request("https://api.github.com" + path, data=data, headers=headers), timeout=30) as r:
                raw = r.read(16 * 1024 * 1024 + 1)
                if len(raw) > 16 * 1024 * 1024:
                    raise EditorialError("API応答サイズ上限に達しました。")
                return json.loads(raw)
        except HTTPError as e:
            raise EditorialError(f"GitHub API HTTP {e.code}") from None
        except (URLError, TimeoutError) as e:
            raise EditorialError("GitHub APIへ到達できません。") from None

    def pages(self, path):
        separator = "&" if "?" in path else "?"
        for page in range(1, self.max_pages + 1):
            batch = self.request(f"{path}{separator}per_page=100&page={page}")
            if not isinstance(batch, list):
                raise EditorialError("ページ応答が配列ではありません。")
            yield from batch
            if len(batch) < 100:
                return
        raise EditorialError("ページ上限に達しました。未取得分を完了扱いにしません。")

    def public_repo(self, name):
        if self.request(f"/repos/{name}").get("private") is not False:
            raise EditorialError("公開リポと確認できない資料は取得しません。")

    def get_issue(self, url):
        match = ISSUE_URL.fullmatch(url)
        if not match:
            raise EditorialError("GitHub Issueの正規URLを指定してください。")
        name, number = match.groups()
        self.public_repo(name)
        issue = self.request(f"/repos/{name}/issues/{number}")
        if "pull_request" in issue:
            raise EditorialError("PRはIssue素材と別に扱ってください。")
        # 名前・メール等の余分な個人metadataは保存しない。
        def excerpt(row):
            return {key: row.get(key) for key in ("html_url", "title", "body", "state", "created_at", "updated_at")}
        return {"url": url, "repository": name, "issue": excerpt(issue),
                "comments": [excerpt(c) for c in self.pages(f"/repos/{name}/issues/{number}/comments")]}

    def ensure_exception(self, repository, marker, title, body):
        self.public_repo(repository)
        # search索引の遅延を避け、closedを含め本文markerで重複を確認する。
        for issue in self.pages(f"/repos/{repository}/issues?state=all"):
            if "pull_request" not in issue and marker in (issue.get("body") or ""):
                return issue["html_url"]
        return self.request(f"/repos/{repository}/issues", {"title": title, "body": body})["html_url"]


class Editor:
    def __init__(self, root=ROOT, api=None):
        self.root = Path(root).resolve()
        self.config = read_json(self.root / "config/editorial.json")
        self.api = api or GitHub(self.config["max_api_pages"])

    def inside(self, name):
        path = (self.root / name).resolve()
        if not path.is_relative_to(self.root):
            raise EditorialError("リポ外のパスは扱えません。")
        return path

    @contextmanager
    def lock(self):
        path = self.inside("INBOX/.editorial.lock")
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise EditorialError("INBOXは別実行で使用中です。停止済みならロックを確認してください。") from None
        try:
            with os.fdopen(fd, "w") as stream:
                stream.write(str(os.getpid()))
            yield
        finally:
            path.unlink()

    def git(self, path, *args):
        return command(["git", "--literal-pathspecs", *args], self.inside(path))

    def revision(self, path):
        return self.git(path, "rev-parse", "HEAD").decode().strip()

    def item(self, item_id):
        if not re.fullmatch(r"[0-9a-f]{64}", item_id):
            raise EditorialError("INBOX IDは64桁のSHA256です。")
        path = self.inside(f"INBOX/items/{item_id}")
        metadata = read_json(path / "item.json")
        for name, expected in metadata["payloads"].items():
            if Path(name).name != name or name in (".", ".."):
                raise EditorialError("INBOX payload名が不正です。")
            if digest((path / name).read_bytes()) != expected:
                raise EditorialError("INBOX素材のhashが一致しません。")
        return path, metadata

    def save(self, kind, source, payloads):
        hashes = {name: digest(data) for name, data in payloads.items()}
        identity = {"kind": kind, "source": source, "payloads": hashes}
        item_id = digest(encoded(identity))
        directory = self.inside(f"INBOX/items/{item_id}")
        if (directory / "item.json").exists():
            self.item(item_id)
            return item_id
        directory.mkdir(parents=True, exist_ok=True)
        for name, data in payloads.items():
            if len(data) > self.config["max_payload_bytes"]:
                raise EditorialError("資料がサイズ上限を超えました。revisionを保持して停止します。")
            atomic(directory / name, data)
        write_json(directory / "item.json", dict(identity, id=item_id, collected_at=now(),
                                                 source_license="source-side-notices-retained"))
        write_json(directory / "state.json", {"status": "pending"})
        return item_id

    def fetch_issue(self, url):
        match = ISSUE_URL.fullmatch(url)
        if not match:
            raise EditorialError("GitHub Issueの正規URLを指定してください。")
        name, number = match.groups()
        _, sources = self.sources()
        if name not in {s["name"] for s in sources}:
            raise EditorialError("資料台帳外のIssueです。")
        self.api.public_repo(name)
        issue = self.api.request(f"/repos/{name}/issues/{number}")
        value = {"url": url, "issue": issue, "comments": []}
        # ページ途中の通信失敗時にも、取得した本文・コメントを保持する。
        item_id = self.import_issue(value)
        try:
            for comment in self.api.pages(f"/repos/{name}/issues/{number}/comments"):
                value["comments"].append(comment)
            return self.import_issue(value), 0
        except (EditorialError, OSError, ValueError) as e:
            item_id = self.import_issue(value)
            return item_id, self.block(item_id, "Issue取得が未完了: " + str(e))

    def log(self, event):
        payload = dict(event, observed_at=now())
        name = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        write_json(self.inside(f"foldlog/{name}__editorial.json"), payload)

    def sources(self):
        catalog = read_json(self.inside(self.config["catalog"]))
        return catalog, catalog["repositories"] + self.config["control_sources"]

    def collect(self, names=None, update=False):
        catalog, sources = self.sources()
        selected = [s for s in sources if not names or s["name"] in names]
        if names and set(names) - {s["name"] for s in selected}:
            raise EditorialError("台帳にないリポは取得しません。")
        ids = []
        for source in selected:
            name, path = source["name"], source["path"]
            try:
                if not (self.inside(path) / ".git").exists():
                    raise EditorialError("先に記録revisionのサブモジュールを初期化してください。")
                if self.git(path, "status", "--porcelain"):
                    raise EditorialError("参照元に未保存の変更があります。上書きしません。")
                expected = "https://github.com/" + name + ".git"
                remote = self.git(path, "remote", "get-url", "origin").decode().strip()
                if remote.removesuffix(".git") != expected.removesuffix(".git"):
                    raise EditorialError("originが登録URLと一致しません。")
                # 親の記録と作業HEADとの差も回収し、前回途中停止から再開できる。
                old = self.git(".", "rev-parse", f"HEAD:{path}").decode().strip()
                current = self.revision(path)
                new = current
                if update:
                    self.api.public_repo(name)
                    branch = source["branch"]
                    if not re.fullmatch(r"[A-Za-z0-9_./-]+", branch) or branch.startswith("-"):
                        raise EditorialError("追従branchが不正です。")
                    self.git(path, "fetch", "--depth=1", "origin", "refs/heads/" + branch)
                    new = self.git(path, "rev-parse", "FETCH_HEAD").decode().strip()
                if old == new:
                    continue
                if not SHA.fullmatch(old) or not SHA.fullmatch(new):
                    raise EditorialError("revisionが不正です。")
                changes = self.git(path, "diff", "--name-status", "--no-renames", old, new).decode().splitlines()
                files = [row.split("\t", 1)[1] for row in changes
                         if Path(row.split("\t", 1)[1]).suffix.lower() in self.config["document_suffixes"]]
                patch = self.git(path, "diff", "--no-ext-diff", "--no-textconv", "--no-renames", old, new, "--", *files) if files else b""
                item_id = self.save("document-diff", {"repository": name, "path": path,
                                    "before": old, "after": new, "url": f"https://github.com/{name}/compare/{old}...{new}"},
                                    {"changes.json": encoded({"all_changes": changes, "document_paths": files}),
                                     "documents.patch": patch})
                ids.append(item_id)
                # INBOX保存後にだけrevisionを進める。古いobjectもGCから保護する。
                self.git(path, "update-ref", f"refs/zennobserver/{old}", old)
                self.git(path, "update-ref", f"refs/zennobserver/{new}", new)
                if update and current != new:
                    self.git(path, "checkout", "--detach", new)
                for row in catalog["repositories"]:
                    if row["name"] == name:
                        row["revision"] = new
                write_json(self.inside(self.config["catalog"]), catalog)
                self.log({"operation": "collect", "item": item_id, "source": name, "update": update})
            except (EditorialError, OSError, ValueError, subprocess.TimeoutExpired) as e:
                failure = self.save("collection-error", {"repository": name, "path": path},
                                    {"failure.json": encoded({"reason": str(e)})})
                return ids + [failure], self.block(failure, str(e))
        return ids, 0

    def import_issue(self, value):
        url = value.get("url", "")
        match = ISSUE_URL.fullmatch(url)
        if not match or not isinstance(value.get("issue"), dict) or not isinstance(value.get("comments"), list):
            raise EditorialError("Issue snapshotのurl・issue・commentsが不正です。")
        _, sources = self.sources()
        if match[1] not in {s["name"] for s in sources}:
            raise EditorialError("資料台帳外のIssueです。先に収集対象を明示してください。")
        if value["issue"].get("html_url") != url or "pull_request" in value["issue"]:
            raise EditorialError("Issue URLと本文の出所が一致しません。")
        clean = {"url": url, "repository": match[1], "issue": {}, "comments": []}
        for source, target in [(value["issue"], clean["issue"])]:
            target.update({k: source.get(k) for k in ("html_url", "title", "body", "state", "created_at", "updated_at")})
        for comment in value["comments"]:
            if not (comment.get("html_url") or "").startswith(url + "#issuecomment-"):
                raise EditorialError("コメントの出所が一致しません。")
            clean["comments"].append({k: comment.get(k) for k in ("html_url", "body", "created_at", "updated_at")})
        item_id = self.save("github-issue", {"url": url, "repository": match[1]}, {"issue.json": encoded(clean)})
        self.log({"operation": "import-issue", "item": item_id, "source": url})
        return item_id

    def block(self, item_id, reason):
        path, metadata = self.item(item_id)
        state = read_json(path / "state.json")
        marker = f"<!-- zennobserver-inbox:{item_id} -->"
        body = (f"{marker}\n## 判定不能・処理停止\n\n理由: {reason}\n\n"
                f"INBOX: `INBOX/items/{item_id}/`\n元資料: " +
                json.dumps(metadata["source"], ensure_ascii=False) +
                "\n\n資料をINBOXに保持し、この実行を終了しました。分類・公開・資料削除はしていません。\n")
        request = {"repository": self.config["issue_repository"], "title": "[INBOX] 判定不能: " + item_id[:12], "body": body}
        write_json(path / "exception-request.json", request)
        state.update(status="blocked", reason=reason, issue_status="pending")
        write_json(path / "state.json", state)
        try:
            url = state.get("issue_url") or self.api.ensure_exception(request["repository"], marker, request["title"], body)
            match = ISSUE_URL.fullmatch(url)
            if not match or match[1] != self.config["issue_repository"]:
                raise EditorialError("例外Issueの投稿先が一致しません。")
            state.update(issue_status="created", issue_url=url)
            code = 2
        except (EditorialError, OSError, ValueError) as e:
            state.update(issue_status="failed", issue_error=str(e))
            code = 3
        write_json(path / "state.json", state)
        self.log({"operation": "block", "item": item_id, "reason": reason,
                  "issue_status": state["issue_status"], "issue_url": state.get("issue_url")})
        return code

    def magi_context(self):
        output = {}
        for slot in ("composite", "maxwell", "uriel", "raphael"):
            argv = [sys.executable, "-B", str(self.inside(ATLANTIS + "/magi/0.2.1/resolve_sources.py")),
                    "--slot", slot, "--profile", "zeroroomlab", "--repo-root",
                    "ZeroRoomLab-manifest=" + str(self.inside(MANIFEST)), "--require-local"]
            output[slot] = json.loads(command(argv, self.root))
        return {"source_revisions": {"atlantis": self.revision(ATLANTIS), "manifest": self.revision(MANIFEST)},
                "decks": output, "semantic_audit_performed": False}

    def route(self, item_id, destination, audit):
        path, metadata = self.item(item_id)
        problems = []
        try:
            context = self.magi_context()
        except (EditorialError, OSError, ValueError, subprocess.TimeoutExpired) as e:
            return self.block(item_id, "MAGI source解決不能: " + str(e))
        if not isinstance(audit, dict):
            return self.block(item_id, "監査receiptがobjectではありません。")
        if destination not in self.config["destinations"]:
            problems.append("振分先が未登録")
        if audit.get("item_id") != item_id or audit.get("payloads") != metadata["payloads"]:
            problems.append("監査対象のhash不一致")
        if audit.get("source_revisions") != context["source_revisions"]:
            problems.append("監査定規のrevision不一致")
        if audit.get("destination") != destination:
            problems.append("監査と振分先が不一致")
        for key in ("observer", "declared_position", "position_talk_risk", "claim_scope", "ruler_provenance"):
            if not isinstance(audit.get(key), str) or not audit[key].strip():
                problems.append(key + "未記入")
        positions = audit.get("positions")
        if not isinstance(positions, dict):
            positions = {}
        for slot in ("maxwell", "uriel", "raphael"):
            result = positions.get(slot, {})
            if not isinstance(result, dict):
                result = {}
            if result.get("gate") != "pass" or not isinstance(result.get("finding"), str) or not result["finding"].strip():
                problems.append(slot + "未完了・不合格")
        if audit.get("action_gate") != "pass" or any(audit.get(k) != [] for k in ("unresolved", "disagreements", "human_confirmation_required")):
            problems.append("未解決・判定不能が残存")
        temporal = audit.get("temporal", {})
        validator = self.inside(ATLANTIS + "/magi/0.2.1/validate_temporal_receipt.py")
        result = subprocess.run([sys.executable, "-B", str(validator)], input=encoded(temporal),
                                capture_output=True, timeout=30)
        if result.returncode:
            problems.append("MAGI時間receipt不合格")
        audit_id = digest(encoded(audit))
        write_json(self.inside(f"foldlog/audit-{audit_id}.json"), audit)
        if problems:
            return self.block(item_id, " / ".join(problems))
        instructions = self.config["destinations"][destination]["instructions"]
        if not self.inside(instructions).is_file():
            return self.block(item_id, "振分先のAGENTS.mdがありません。")
        state = read_json(path / "state.json")
        state.update(status="assigned", destination=destination, instructions=instructions,
                     audit_ref=f"foldlog/audit-{audit_id}.json", assigned_at=now())
        write_json(path / "state.json", state)
        self.log({"operation": "route", "item": item_id, "destination": destination, "audit_ref": state["audit_ref"]})
        return 0

    def record_issue(self, item_id, url):
        """connector経由で起票した場合も、公開本文markerを確認して受領する。"""
        path, _ = self.item(item_id)
        match = ISSUE_URL.fullmatch(url)
        if not match or match[1] != self.config["issue_repository"]:
            raise EditorialError("例外Issueの投稿先が一致しません。")
        issue = self.api.request(f"/repos/{match[1]}/issues/{match[2]}")
        marker = f"<!-- zennobserver-inbox:{item_id} -->"
        if marker not in (issue.get("body") or "") or "pull_request" in issue:
            raise EditorialError("例外IssueのINBOX markerが一致しません。")
        state = read_json(path / "state.json")
        if state.get("status") != "blocked":
            raise EditorialError("判定不能票として停止した資料ではありません。")
        state.update(issue_status="created", issue_url=url)
        write_json(path / "state.json", state)
        self.log({"operation": "record-issue", "item": item_id, "issue_url": url})
        return 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="実行するZennobserver checkout")
    sub = parser.add_subparsers(dest="operation", required=True)
    c = sub.add_parser("collect", help="登録資料の差分を保存。--update時だけoriginをfetchする")
    c.add_argument("--repo", action="append")
    c.add_argument("--update", action="store_true")
    i = sub.add_parser("fetch-issue", help="明示Issueと全コメントを取得")
    i.add_argument("url")
    i = sub.add_parser("import-issue", help="connectorで取得した公開Issue snapshotを取り込む")
    i.add_argument("file", type=Path)
    sub.add_parser("magi-context", help="必読sourceを解決する。意味監査自体はエージェントが行う")
    r = sub.add_parser("route", help="三Position監査済み資料を振り分ける。本文の公開はしない")
    r.add_argument("item")
    r.add_argument("destination")
    r.add_argument("--audit", required=True, type=Path)
    b = sub.add_parser("block", help="INBOXを保持し例外Issueを起票して終了")
    b.add_argument("item")
    b.add_argument("--reason", required=True)
    b = sub.add_parser("record-issue", help="connector起票後のURLとINBOX markerを確認し終了")
    b.add_argument("item")
    b.add_argument("url")
    sub.add_parser("list", help="INBOXの状態を一覧する")
    args = parser.parse_args(argv)
    try:
        editor = Editor(args.root)
        with editor.lock():
            if args.operation == "collect":
                ids, code = editor.collect(args.repo, args.update)
                print(json.dumps({"items": ids, "exit_code": code}, ensure_ascii=False))
                return code
            if args.operation == "fetch-issue":
                item, code = editor.fetch_issue(args.url)
                print(json.dumps({"item": item, "exit_code": code}, ensure_ascii=False))
                return code
            elif args.operation == "import-issue":
                print(editor.import_issue(read_json(args.file)))
            elif args.operation == "magi-context":
                print(json.dumps(editor.magi_context(), ensure_ascii=False, indent=2))
            elif args.operation == "route":
                return editor.route(args.item, args.destination, read_json(args.audit))
            elif args.operation == "block":
                return editor.block(args.item, args.reason)
            elif args.operation == "record-issue":
                return editor.record_issue(args.item, args.url)
            elif args.operation == "list":
                print(json.dumps([dict(read_json(p / "state.json"), id=p.name)
                      for p in sorted(editor.inside("INBOX/items").glob("*")) if (p / "item.json").is_file()], ensure_ascii=False, indent=2))
        return 0
    except (EditorialError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as e:
        # 素材IDがない失敗にもINBOX票を作る。CLI構文エラーはargparseがネットワークなしで終了する。
        try:
            with editor.lock():
                item = editor.save("operation-error", {"operation": args.operation, "item": getattr(args, "item", None),
                                   "url": getattr(args, "url", None)}, {"failure.json": encoded({"reason": str(e)})})
                return editor.block(item, str(e))
        except Exception:
            print("処理停止。例外票を保存できませんでした。既存INBOXは削除していません。", file=sys.stderr)
            return 3


if __name__ == "__main__":
    sys.exit(main())
