# 更新指示の入口

今回の更新対象・期間・目的を人間の指示から受け取る。このファイルはschedulerではない。
rootのAGENTSを最初に読み、以後のファイルは共通指示の全文複製でなく段階ごとの差分として読む。

## 初回と参照元更新後

1. `Zennobserver.code-workspace`で登録した3メンバーを確認する。資料リポ一覧と開発workspaceを混同しない。
2. `.vendor/ZeroRoomLab-manifest/AGENTS.md`と必要な運用正本を読む。
3. `.vendor/SphereOS-Atlantis/AGENTS.md`、`SPHERE-DOS.ja.md`を読む。
4. `python3 scripts/editorial.py magi-context`を実行し、返されたbundle・定規・三Position Skillを読む。
5. `docs/editorial-rules.ja.md`、`docs/editorial-tools.ja.md`を読む。

## 段階的な指示分岐

- 回収: [stages/collect/AGENTS.md](stages/collect/AGENTS.md)
- ログ監査: [stages/audit/AGENTS.md](stages/audit/AGENTS.md)
- 問いの抽出と振分: [stages/route/AGENTS.md](stages/route/AGENTS.md)
- 執筆と配信前確認: [stages/write/AGENTS.md](stages/write/AGENTS.md)

ツールの終了2は判定不能Issueを残して停止、終了3はIssue送信失敗などを保持して停止である。
非ゼロを成功として後段へ進めない。本文の不足を想像で埋めず、INBOXに残してIssueへ返す。

GitHub connectorを使う場合も同じ状態票を使う。CLIの例外Issue送信が失敗しても
`exception-request.json`から投稿できれば、`record-issue`へURLを渡してこの実行を終了する。
投稿自体が不可能なら未送信の事実と票の場所を報告する。Issue URLを捏造しない。

実行が問題なく完了した段階ごとに、日本語で小さくcommitしremoteへpushする。
上流リポのcode・Issueへ変更を送る権限は、この更新指示から導出しない。
週次日時、利用モデル、token予算、無人実行runnerはこの指示から推定しない。
