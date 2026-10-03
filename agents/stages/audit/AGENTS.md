# ログ監査段階の差分指示

共通入口: rootのAGENTSと`agents/UPDATE.md`。本文を作る前に監査する。

1. 対象INBOX原本とhash、前後revision、Issue URL、観測時刻を確認する。
2. `magi-context`が返す全必須sourceを読む。source欠損はSOURCE-BLOCKとして`block`する。
3. 同じsource・問い・媒体・claim scopeをMaxwell、Uriel、RaphaelのSkillへ独立に適用する。
4. Maxwellは目的・固有概念・未採用branchの保持、Urielは指示・操作・観測・責務の接続、
   Raphaelは素材から記事/Bookへの意味経路と差分保持を確認する。
5. `templates/magi-audit.json`を原本としてreceiptを作り、資料ID・payload hash・定規revision・
   振分候補・現在の監査時刻・監査者を埋める。三Positionのfindingとgateを別々に残す。
6. 時間receiptは過去資料への現在解釈を明示する。当時のOAE参照が不明なら
   `historical-oae-unavailable`とLast Orderを保持する。これは資料そのものの不在を意味しない。
7. 結論に必要なログ、意味、因果、分類が判定不能なら、unresolvedへ具体的な理由を書き、
   `block ID --reason ...`を実行して終了する。多数決や「たぶん」でpassにしない。

source resolver成功、lint成功、過去のCI成功を今回の意味監査・実機再試験の合格へ置換しない。
receiptは`foldlog/`へ置き、取得したINBOX原本を上書きしない。
