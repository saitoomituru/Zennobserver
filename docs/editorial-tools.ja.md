# 編集用Toolセット

Python 3.11以上の標準ライブラリーで動作する。初回にrootのAGENTS、明示Manifest、SphereDOSを読み、
`python3 scripts/editorial.py magi-context`が返すsourceを確認する。

| コマンド | 入力→出力 | 副作用・停止 |
|---|---|---|
| `collect` | 親gitlinkと参照元HEAD→文書差分・全変更一覧 | INBOXと台帳・foldlogへ保存。networkなし |
| `collect --update` | 登録されたorigin・branch→新revisionの差分 | 登録公開リポだけfetch。差分保存後にdetach checkoutと台帳更新。dirtyなら停止 |
| `fetch-issue URL` | 明示Issue→本文・コメントsnapshot | 公開確認、全コメントをページ取得。取得済み本文は途中失敗時も残す |
| `import-issue FILE` | connector取得の公開snapshot→INBOX | URL・コメント出所を検査。未取得コメントを取得済みと表示しない |
| `magi-context` | 固定Atlantis・Manifest→4slotのsource deck | 既存resolverを明示profileで再利用。source解決は意味監査の合格ではない |
| `route ID DEST --audit FILE` | 資料と三Positionの監査receipt→振分状態 | hash・定規revision・時間receiptを検査。不明・不合格ならIssue起票して終了 |
| `block ID --reason REASON` | 判定不能資料→例外Issueと状態票 | INBOX原本を残し終了2。投稿失敗は本文を保持し終了3 |
| `record-issue ID URL` | connector投稿済みIssue→受領状態 | 宛先と本文markerをAPIで確認して終了2 |
| `list` | INBOX→資料IDと処理状態 | 一覧表示のみ |

`DEST`: `neetrunner` / `infoton-engineering` / `lab-debugging`。
`route`は編集先の割当までで、原稿の生成・移動・公開を行わない。原本は割当後もINBOXに残す。
振分先の指示は`config/editorial.json`から辿る。Zenn記事の本文は`articles/`へ出力する。

上表は取得・MAGI監査を行うlegacy Toolである。JSON-LD素材の配置は別の決定論的Toolを使う。

| コマンド | 入力→出力 | 副作用 |
|---|---|---|
| `editorial_router.py build --dry-run` | JSON-LD→検証済み移動計画 | なし |
| `editorial_router.py build` | JSON-LD→folder配置・NDJSON索引 | 許可root内の素材folder移動と索引更新 |
| `editorial_router.py reindex` | metadata→NDJSON索引 | 索引だけ再生成 |
| `editorial_router.py reindex --check` | metadataと索引の比較 | なし。不一致で終了2 |
| `editorial_router.py ctl QUERY` | NDJSON索引→小さなJSON | なし。本文を読まない |

`QUERY`: `pending` / `unarticleized` / `unresolved` / `archived` / `stats`。
詳細は[Actionサーバー契約](editorial-action-server.ja.md)を参照する。

## 更新の実行

```bash
git submodule update --init
python3 scripts/editorial.py magi-context
python3 scripts/editorial.py collect --update --repo saitoomituru/FQuery
python3 scripts/editorial.py fetch-issue https://github.com/saitoomituru/FQuery/issues/NUMBER
python3 scripts/editorial.py list
```

`NUMBER`はエージェントが根拠を確認して選んだ実在番号へ置き換える。
`--repo`を省略した更新は台帳20件と制御用2件を対象にする。指定リポ以外の探索・取得、内部submoduleの
再帰取得、LFS payload取得、上流install・buildはしない。依存更新はGitサブモジュールを対象とし、npm依存の
無条件なupgradeは含めない。制御用リポが更新されたら、新しいAGENTS・MAGI sourceを再読する。

文書は`.md/.mdx/.rst/.txt`の追加・変更・削除をdiffで保存し、renameは削除＋追加として保持する。
試験コード等の変更は全変更一覧とコミット参照を残す。全ソース・画像・モデルはINBOXへ複製しない。
初回も既存gitlinkを基準にする。全Docsを既読・記事化済みとする初期化ではない。

INBOXは資料単位のSHA256 IDを使い、同一入力の再実行でblocked状態をpendingへ戻さない。
更新は資料保存後にだけ進め、元・新コミットをlocal refへ保持する。親gitlink・台帳・INBOX・foldlogを
同じcheckpointへcommitする。ツール自体はGit commit・pushしない。

## Issueと認証

自動起票先は`config/editorial.json`で指定した`saitoomituru/Zennobserver`だけ。
`GH_TOKEN`または`GITHUB_TOKEN`に当該リポのIssues書込権限を付ける。tokenをファイルへ保存しない。
起票前に公開Issueの本文markerを確認して重複を避ける。closedの既存票も再利用し、勝手にreopenしない。
closed票で未解決状態が再発した場合はエージェントが経緯を確認する。

認証・networkが使えなければ`exception-request.json`を残して終了3になる。接続済みGitHub connectorで
その`repository/title/body`を投稿し、`record-issue`へ実際のURLを渡して終了する。
connector取込のJSONは次の形とし、公開リポのmetadataを確認した資料だけ渡す。

```json
{"url":"https://github.com/OWNER/REPO/issues/1","issue":{"html_url":"https://github.com/OWNER/REPO/issues/1","title":"題名","body":"本文","state":"open","created_at":"元時刻","updated_at":"元時刻"},"comments":[{"html_url":"https://github.com/OWNER/REPO/issues/1#issuecomment-1","body":"コメント","created_at":"元時刻","updated_at":"元時刻"}]}
```

不足ページ、サイズ上限、dirty参照元、取得エラーを成功や無変更へ変換しない。単一実行ロックがある。
中断後のロック解除は、記録PIDの処理が終了したことを確認してから行う。

## MAGI receiptと再利用

receipt書式は`templates/magi-audit.json`。エージェントが三Position Skillを読み、同じ資料について独立した
first passを行い、その結果を記入する。テンプレートは`observe`と未記入が既定で、そのままでは通らない。
資料hash・出力先・Atlantis/Manifest revisionが一致し、三Positionと合成判定がpass、未解決・対立・確認要求が
空である場合だけ振分可能。これは記載された監査の機械検査であり、文章の真理認証や実機再試験ではない。

Meaning: 一次資料を保持し、エージェントの整理指示を短くし、判断不能を人間へ返す。
Vessel: `scripts/editorial.py`、設定、INBOX、状態票、試験。
Bridge: 既存SphereDOS wrapper、MAGI resolver・時間検査器、GitHub REST/connector。
Supply: 台帳revision、元license、Tool索引、foldlog、異常系の試験。

既存のAtlantis `atlantis_cli/note.py`・`workspace.py`、`scripts/validate_note_pr.py`、Manifestのproject作成scriptを
調査した。Note提出・workspace展開は今回の差分INBOX／Issue取込と入出力・副作用が違うため再実装せず、
編集アダプターを追加した。MAGI resolverと時間検査器はcopyせず固定submoduleへ委譲する。

検証: `npm run check`。GitHubへの実際の起票はテストで行わず、重複・認証失敗・INBOX保持を模擬APIで検証する。
外部送信と同時実行はrepository-local lockの範囲で制御し、別clone同士の同時起票を完全に排他する保証はない。
