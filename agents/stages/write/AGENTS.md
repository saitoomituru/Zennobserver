# 執筆・配信前確認段階の差分指示

共通入口: rootのAGENTSと`agents/UPDATE.md`。assignedの資料と振分先のAGENTSを読む。

1. 人間の指示、参照した前提、実行、結果、次の判断の接続を保つ。
   人間が都度出した切り分け指示を、無人で判断した履歴へ置換しない。
2. 原稿を`published: false`で作る。既存公開記事への変更は更新指示の対象と範囲を確認する。
3. 元Issue、ファイル、commit、実験条件、著者、licenseへの参照を置く。
4. 語りは中性的な「私」を軸にし、現場の問い・ユーモア・固有概念を保持する。
   トラ技寄りの操作・測定・切り分け密度を高める。生ログを全量貼って解説の代わりにしない。
5. 執筆後の主張もMAGI三Positionで再確認し、引用・結論と元資料の対応を`foldlog/`へ残す。
   内容を変えたら、資料振分時の監査だけで本文も合格したと表示しない。
6. `npm run check`とZenn CLIのプレビューを行う。Bookは設定・章順・表紙も確認する。
7. `templates/article-sources.jsonld`から`articles/<slug>.sources.jsonld`を作り、使用素材URNを記録する。
   各素材MDXにも同じ記事URN、`archive`、`archiveMonth`、`complete: true`を記録する。
8. `python3 scripts/editorial_router.py build --dry-run`で相互参照と移動計画を確認する。
   素材を手動移動せず、原稿・宣言・関連receiptを日本語でcommitしpushする。
   公開指示がある原稿だけ公開状態へ進める。

ZennobserverのmainはZennと連携済み（2026-10-03の本人提示画面）。pushは同期を起動する。
CIは同期を止めるgateではないため、公開フラグを変更する前に検証する。
判定不能なら原稿もINBOXの参照も保持し、元資料IDについて`block`して終了する。
新形式素材では`editorial:transition: unresolved`と具体的理由を記録し、archive宣言を付けない。
