# JSON-LDタグ駆動のActionサーバー契約

要件: [Issue #1](https://github.com/saitoomituru/Zennobserver/issues/1)。

## 責務

LLMは探索・意味判断・アウトライン・執筆を担当する。ActionサーバーはLLMを起動せず、
素材MDXのJSON-LDを検証して配置とNDJSON索引へ決定論的にコンパイルする。
JSON-LDが正本、フォルダー位置が処理段階、索引は再生成可能な派生物である。

## 三つの成果物

| 層 | 形式 | 配置 |
|---|---|---|
| 素材 | MDX＋専用JSON-LD fence | `INBOX/materials/<SHA256>/material.mdx` |
| アウトライン | Markdown | `OUTLINES/` |
| Zenn原稿 | Zenn準拠Markdown | `articles/<slug>.md` |

素材MDXは末尾に一つだけ ``jsonld zennobserver-material`` fenceを持つ。routerはJSONとして読み、
JSXや任意codeを実行しない。未知entity・fieldは拒否も削除もせず、素材フォルダーをバイト単位で移す。
FAM化は必須ではない。将来必要になった形式だけFQueryの追加pluginで解釈する。

## 遷移

| `editorial:transition` | 動作 |
|---|---|
| `hold`または完了前 | INBOXへ保持 |
| `unresolved` | INBOXへ保持し、別の滞留監視対象にする |
| `archive` | 記事と相互参照を検査後、BACKNUMBERSへ移動 |

`archive`には`editorial:complete: true`、`editorial:articleSlug`、`editorial:archiveMonth`、
`editorial:usedBy`が必要である。記事側は`articles/<slug>.sources.jsonld`の
`editorial:usesMaterial`から同じURNを参照する。実パスは宣言させず、routerが次の規則で作る。

```text
BACKNUMBERS/<archiveMonth>/<articleSlug>/<materialId>/
```

不正tag、許可外値、重複ID、記事・逆参照の欠落、移動先衝突では一件も移動しない。
既存`INBOX/items/`はlegacy素材として索引するが、明示移行なしに移動しない。

## CTL

CTLは本文をAIへ読ませず、生成済みNDJSONから`pending`、`unarticleized`、`unresolved`、
`archived`、`stats`をJSONで返す。索引が疑わしい場合はActionサーバーがmetadataから再構築する。

## 実行原則

- dry-runは検証と移動計画だけを返し、ファイルを書き換えない。
- applyは全計画を先に検証し、素材フォルダー単位でrenameする。
- 同じ入力の再実行で追加変更を作らない。
- Actionのbot commitを意味判断・記事内容の承認として表示しない。
- `published`の決定、LLM実行、週次日時、FAM正規化はこのToolの責務外とする。
