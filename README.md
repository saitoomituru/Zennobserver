# Zennobserver

**ふさもふを観測して、Zennに届ける。**

ZeroRoomLabのドキュメント、コード、実験ログを、元資料へ辿れる記事に育てる編集・配信母艦です。
Manifestを共有文脈、SphereDOSを開発足場として埋め込みます。
原稿の作成・検証・プレビューに加え、資料回収・MAGI監査・振分・例外IssueのToolセットを備えています。
記事・Bookの分け方は[編集メタルール](docs/editorial-rules.ja.md)に記録しています。
更新の入口は[日本語の更新指示](agents/UPDATE.md)、コマンドと停止条件は[Tool索引](docs/editorial-tools.ja.md)です。

## 構成

| パス | 役割 |
|---|---|
| `articles/` | Zenn記事のMarkdown（現在は記事未作成） |
| `books/` | Zenn本の配置先（lab-debuggingは非公開の空の編集骨格） |
| `magazines/` | マガジン別の差分指示・記事索引（本文はarticlesへ） |
| `agents/` | 回収・監査・振分・執筆の段階別指示 |
| `INBOX/` | 文書差分・Issue原本・振分と例外の状態票 |
| `OUTLINES/` | 複数素材を束ねた記事アウトラインと機械生成索引 |
| `BACKNUMBERS/` | 記事化済み素材MDX。将来の探索にも再利用する |
| `foldlog/` | 更新操作とMAGI監査の記録 |
| `templates/` | 公開対象外の原稿テンプレート |
| `scripts/` | 原稿検証とSphereDOSへの薄い接続 |
| `.vendor/ZeroRoomLab-manifest/` | 明示Manifestの固定revision |
| `.vendor/SphereOS-Atlantis/` | SphereDOSの固定revision |
| `sources/<owner>/<repository>/` | 記事素材として追加した公開リポのサブモジュール |
| `sources/catalog.json` | 取得revision・参照根拠・ライセンス表示場所の台帳 |
| `.github/workflows/` | 原稿検証CI |
| `docs/` | 構築記録と次段階の未決定事項 |

## 開発環境の初期化

Node.js 24、Python 3.11以上、Gitを使用します。Node.jsの検証環境は`.node-version`に記録します。

```bash
git clone https://github.com/saitoomituru/Zennobserver.git
cd Zennobserver
git submodule update --init
npm ci
python3 scripts/sphere-dos.py bootstrap
python3 scripts/sphere-dos.py boot
python3 scripts/sphere-dos.py status
```

`git submodule update --init`は親リポに記録されたコミットを再現します。
更新には`python3 scripts/editorial.py collect --update`を使い、差分を保存してから登録先のrevisionを進めます。
Atlantisの`workspace init`による他component取得は行いません。
`sources/`のトップレベルサブモジュールも同じコマンドで初期化します。
各参照元の内部サブモジュールはrecursive初期化しません。Manifest内の`vendor/FQuery`・`vendor/IBD`も
未初期化のままです。FQueryとIBDの資料は`sources/saitoomituru/`に独立して配置しています。

SphereDOS wrapperはAtlantisの既存bootstrap・CLIへ委譲します。boot receiptは
Atlantis側の無視対象`.atlantis/`へ保存されます。
Atlantisのcomponent workspaceを追加展開しないため、bootは`development-shell-partial`になり得ます。
今回の明示Manifestは上のサブモジュールを参照します。bootだけでAtlantis内部のcomponent registryへ
登録・mountしたことにはなりません。
VS Codeを使う場合は[Zennobserver.code-workspace](Zennobserver.code-workspace)を開けます。

## 記事の作成と確認

```bash
npm run new:article -- --slug example-article-001
npm run validate
npm run preview
```

`templates/article.md`も執筆の入口に使えます。新規原稿は`published: false`で作成します。
Zennのslugは小文字英数字・`-`・`_`からなる12〜50文字です。更新時は同じslugを維持します。
記事のメタ情報はZenn公式`zenn-model`で検証し、YAMLの破損や公開設定の型違いを検出します。
本文の見た目・埋め込み・リンク先の確認はZenn CLIのプレビューで行います。
本の作成・プレビューは`npm run new:book`と`npm run preview`を使用します。
この初期段階のCI検証対象は記事で、本の設定・章・表紙の検証は今後の拡張対象です。

## Zennへの配信

2026-10-03のユーザー提示画面で、Zenn側と**`saitoomituru/Zennobserver`の`main`**の連携を確認しました。
配信にはこの既存のZenn公式連携を使います。

連携後は`articles/*.md`を`main`へpushするとZennが同期します。
`published: false`は下書き、`true`は公開対象です。Zenn CLIはプレビュー・原稿作成用で、
GitHub Actionsから独自のZenn deploy APIを呼ぶ構成にはしていません。

Actionsはpush・PR・手動実行で`npm ci`、検証テスト、記事メタ情報検証を行います。
**push後のActions検証は、Zennの同期を待機・阻止する公開ゲートではありません。**
公開ブランチ・公開判断・必要な保護設定は運用ルールを決める段階で選定します。
配信結果はZennダッシュボードのデプロイ履歴で確認します。

公式資料:

- [ZennとGitHubリポジトリの連携](https://zenn.dev/zenn/articles/connect-to-github)
- [Zenn CLIの導入](https://zenn.dev/zenn/articles/install-zenn-cli)
- [記事・本の管理方法](https://zenn.dev/zenn/articles/zenn-cli-guide)

## 更新と編集の実行

公開リポの資料集合は[取得元一覧](docs/source-repositories.ja.md)に記録しています。
これは記事素材の配置であり、Atlantis内部workspaceのcomponent登録や実装依存を追加するものではありません。
大きな参照元は浅い履歴で取得し、LFS素材の実体取得・再帰的な依存取得・install・buildは行っていません。

登録先の更新と差分回収、明示Issueの本文・コメント取得、MAGI receipt検査、編集先の割当をToolで実行します。
初回はManifest・SphereDOS・MAGI Skillを読み、各段階と出力先の日本語AGENTSへ分岐します。
判定不能は資料をINBOXに保持したままZennobserverへIssueを起票し終了します。投稿失敗も未送信票を保持します。

原稿の判断・執筆はエージェントが担当し、新規原稿は下書きで開始します。週次scheduler、無人runner、
自動公開は設定していません。[次段階の未決定事項](docs/next-decisions.ja.md)に残りの運用選択を記録しています。

素材の残留確認と配置は本文をLLMへ再読込せず実行できます。

```bash
python3 scripts/editorial_router.py ctl stats
python3 scripts/editorial_router.py ctl unarticleized
python3 scripts/editorial_router.py build --dry-run
```

素材MDXのJSON-LDへ遷移を宣言すると、main上のActionサーバーが相互参照を検証し、
BACKNUMBERSへの移動と索引再生成だけを行います。Action内でLLMは起動しません。

読者需要・記事の粒度・初回の題材・導線・計測は
[Zennマーケティング計画案](docs/zenn-marketing-plan.ja.md)にまとめています。
調査から作った未採用の提案で、公開日程や自動運用を設定するものではありません。

## ライセンス

コード・機械可読設定は既存の[Apache License 2.0](LICENSE)。
新規文章・コンテンツは[CC BY 4.0](LICENSE-CONTENT.md)。
サブモジュールと取り込む資料は各参照元のライセンスを保持します。
帰属表示: ふさもふ / Mitsuru Saitō / ZeroRoomLab。
