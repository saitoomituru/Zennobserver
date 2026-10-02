# 初期構築・検証記録

実施日: 2026-10-03（JST）

## 依頼と実装範囲

指定のManifestとAtlantisをサブモジュールとして導入し、コンテンツライセンス、README、
SphereDOSの初期化、Zennの執筆・検証・配信連携の足場を構築しました。
他リポの収集・週次処理・分類・生成・Issue起票・公開判断の運用ルールは未採用です。

| 参照元 | 固定コミット |
|---|---|
| ZeroRoomLab-manifest | `e5fc0be592d7216b2e7bd059a4518db73a2a118e` |
| SphereOS-Atlantis | `ab36617865145403078cec193b539971534f3547` |

両サブモジュールを初期化しました。Manifest配下のFQuery・IBDサブモジュールは未初期化です。
両上流リポの追跡ファイルに変更を加えていません。

## 再利用の判断とtool索引

Atlantisの`SPHERE-DOS.ja.md`、`scripts/bootstrap_venv.py`、`atlantis_cli/sphere_dos.py`、
`scripts/`、`atlantis_cli/`、`.github/workflows/`とManifestの運用文書を確認しました。
Zenn原稿の生成・分類toolは今回確認した範囲では見つからず、Zenn専用検証は公式packageを利用しました。

| tool | 入力・出力 | 副作用・依存・license | 選択理由・検証 |
|---|---|---|---|
| `scripts/sphere-dos.py` | bootstrap/boot/status/doctor → Atlantis CLIのJSONと終了コード | bootstrapはルート`.venv/`、bootはAtlantisの`.atlantis/`へ保存。Python 3.11以上、Apache-2.0 | 既存実装へ委譲するadapter。bootstrap・boot・statusを実行 |
| `scripts/validate-articles.mjs` | `articles/*.md` → メタ情報の検証結果・終了コード | 原稿変更・network・収集なし。yaml 2.9.1、zenn-model 0.5.4、Apache-2.0 | Zenn公式validatorを再利用し、YAMLとファイル配置だけ接続。4テスト合格 |
| Zenn CLI 0.5.4 | 原稿作成・ローカルプレビュー | 新規原稿を書き、previewはローカルHTTP serverを起動。MIT | 独自プレビューを作らず公式CLIを使用。HTTP 200確認 |
| `validate.yml` | push/PR/手動実行 → 検証job | contents:read。Zennobserverとnpm依存のみ取得。サブモジュール取得・書き込みなし。Apache-2.0 | 既存Atlantis CIのread-only構成を参照し、Node.js用にadapt |

ローカル実行環境: Node.js 24.19.0、npm 11.9.0、Python 3.12.14。
`npm ci`による依存再構築、`npm run check`、`git diff --check`を確認しました。
空のarticles構成を検証し、公開対象の記事は作成していません。

## SphereDOSと文脈の確認

SphereDOS bootstrap・boot・statusを実行しました。状態は`development-shell-partial`です。
Atlantis内部workspaceのManifest、IBD、Sphere-aae、SphereASTROは追加展開していません。
Zennobserverの明示Manifestは`.vendor/ZeroRoomLab-manifest`に配置し、親workspace descriptorで参照します。
この配置をAtlantis内部の固定component registryへの登録成功とは表示しません。

MAGI source resolverは`--slot composite --profile zeroroomlab`、明示Manifest root、
`--require-local`で実行し、必要な参照元をローカル解決できました。
これは参照経路の検証であり、三Positionによる記事の意味監査・分類や公開合格ではありません。

## 未試験・未実装範囲

- Zennアカウント側のGitHub連携状態と実サービスのデプロイは未確認。
- 本のメタ情報・章・表紙のCI検証は未実装。公式CLIで作成・プレビュー可能。
- 記事本文の描画、全リンク先、実験再実行はメタ情報検証の対象外。
- doctorは入口を提供したが今回の受入確認としては未実行。
- Windows、macOS、SphereOSのcomponent runtime、model実行は未試験。
- 週次更新・分類・生成・Issue起票・他リポ取得・自動公開判断は未実装。

次の判断は[未決定事項一覧](next-decisions.ja.md)に残しました。
