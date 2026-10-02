# Zennobserverの作業入口

人間向けの文書・コメント・コミットは日本語を既定とします。
コミットは`[layer] scope: 日本語の説明`で、意味のまとまった小単位に分けて反映します。

## 文脈の入口

1. [README](README.md)と依頼された作業範囲
2. 明示Manifest: [.vendor/ZeroRoomLab-manifest/AGENTS.md](.vendor/ZeroRoomLab-manifest/AGENTS.md)
3. SphereDOS: [.vendor/SphereOS-Atlantis/SPHERE-DOS.ja.md](.vendor/SphereOS-Atlantis/SPHERE-DOS.ja.md)
4. Atlantisのtoolを使う場合、その[AGENTS.md](.vendor/SphereOS-Atlantis/AGENTS.md)と対象toolの契約
5. [コンテンツライセンス](LICENSE-CONTENT.md)

workspaceの構成は[Zennobserver.code-workspace](Zennobserver.code-workspace)で明示します。
サブモジュールの存在は、上流への変更権限や周辺リポジトリの取得命令を意味しません。
MAGIのZeroRoomLab追加定規を解決するときは`--profile zeroroomlab`と明示Manifestパスを渡します。
source resolverの成功を、記事の意味監査・分類・公開判断の合格と表示しません。

## 初期化段階の境界

現段階はZenn執筆・検証・配信連携の足場までです。運用ルールは未決定です。
週次scheduler、上流自動追従、他リポのfetch、記事分類・自動生成、自動Issue起票、
自動公開判断は、別途依頼と運用ルールの確定があるまで追加しません。
思想・信仰・構想と、実装・観測・追試のレジスターを無断で相互置換しません。
元資料のrevision、著者、明示ライセンス、変更内容を保持します。
