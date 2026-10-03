# 記事素材の参照リポジトリ

2026-10-03: ユーザー指定5リポを起点に、ManifestのREADME・workspace台帳・project文書、39件のIssue、90件のコメント、1件のマイルストーンを確認しました。

新規20リポを`sources/<owner>/<repository>/`へ配置しました。既存のManifest・Atlantisと合わせて22サブモジュールです。取得コミットと個別の発見根拠は[台帳](../sources/catalog.json)に記録しています。

| リポジトリ | 固定revision | 主な発見元 |
|---|---|---|
| [saitoomituru/FQuery](https://github.com/saitoomituru/FQuery) | `95b0eab17c7d` | Manifest文書・Issueコメント・ユーザー指定 |
| [saitoomituru/Sphere-aae](https://github.com/saitoomituru/Sphere-aae) | `f67fa20df0ad` | Manifest文書・ユーザー指定 |
| [saitoomituru/OpenRVC](https://github.com/saitoomituru/OpenRVC) | `865b337ca214` | ユーザー指定 |
| [saitoomituru/OND800](https://github.com/saitoomituru/OND800) | `553ed3965c20` | Manifest文書・Issueコメント・ユーザー指定 |
| [HIPSTAR-IScompany/quantaril_cloud_QAtlantis](https://github.com/HIPSTAR-IScompany/quantaril_cloud_QAtlantis) | `39a67f2ed68c` | Manifest文書・Issue・Issueコメント・ユーザー指定 |
| [saitoomituru/fold-nic](https://github.com/saitoomituru/fold-nic) | `44b5d8bb7525` | Manifest文書・Issueコメント |
| [saitoomituru/IBD](https://github.com/saitoomituru/IBD) | `4e2d02b16854` | Manifest文書・Issue |
| [saitoomituru/DVE800](https://github.com/saitoomituru/DVE800) | `dd705e1f3555` | Manifest文書 |
| [saitoomituru/FAN800](https://github.com/saitoomituru/FAN800) | `053d68a14981` | Manifest文書 |
| [saitoomituru/SAO800](https://github.com/saitoomituru/SAO800) | `14797473e2c4` | Manifest文書 |
| [saitoomituru/PSYCHO-Py800MCP](https://github.com/saitoomituru/PSYCHO-Py800MCP) | `54cb3f94c755` | Manifest文書 |
| [saitoomituru/SphereASTRO](https://github.com/saitoomituru/SphereASTRO) | `6ed62aa0a6fa` | Manifest文書 |
| [saitoomituru/commonsATX](https://github.com/saitoomituru/commonsATX) | `6773ccd02fa2` | Manifest文書 |
| [HIPSTAR-IScompany/astro.quantaril.cloud](https://github.com/HIPSTAR-IScompany/astro.quantaril.cloud) | `5158caec172b` | Manifest文書 |
| [saitoomituru/pain-scouter-assessment](https://github.com/saitoomituru/pain-scouter-assessment) | `4c6d21f751e0` | Manifest文書 |
| [saitoomituru/OpenSourcePITETO](https://github.com/saitoomituru/OpenSourcePITETO) | `baea1ba33bba` | Manifest文書 |
| [HIPSTAR-IScompany/FMS24GTP_driver](https://github.com/HIPSTAR-IScompany/FMS24GTP_driver) | `93cac4155526` | Manifest文書 |
| [saitoomituru/saitoomituru](https://github.com/saitoomituru/saitoomituru) | `203b2049923f` | Manifest文書 |
| [saitoomituru/KUMA800](https://github.com/saitoomituru/KUMA800) | `edf56b3fef1a` | Issueコメント |
| [HIPSTAR-IScompany/SphereOS-synthesizer](https://github.com/HIPSTAR-IScompany/SphereOS-synthesizer) | `c6b7248b9955` | 関連README |

## 名称・重複の確認

- `HIPSTAR-IScompany/quantaril_cloud_Q3`はGitHub metadataでQAtlantisと同じrepository IDと確認したため、QAtlantisのみを追加しました。
- Manifest READMEにある`HIPSTAR-IScompany/OND800`・`FAN800`・`SAO800`は今回の参照で404でした。ユーザー指定とManifest workspace台帳で確認できた`saitoomituru`側を採用しています。
- `KUMA800`はManifest Issue #10のコメントから、`SphereOS-synthesizer`はPSYCHO-Py800MCPのREADMEから確認しました。

## 配置と未実施範囲

- 上流はすべて公開リポです。各リポの既定ブランチから取得したコミットを親Gitのgitlinkで固定しています。
- 新規リポは浅い履歴で取得し、`.gitmodules`にも`shallow = true`を記録しました。
- 内部サブモジュールの再帰取得、LFS payloadの明示取得、依存install、build、モデル・実機テストは行っていません。
- 配置成功は各componentの動作確認やライセンスの再許諾を意味しません。参照元のlicense・著者表示を保持しています。
- Zennobserverの開発workspace descriptorは従来の3メンバーを維持しています。この台帳は記事資料集合であり、別の開発workspaceや実装依存を作る宣言ではありません。
- 自動追従、定時fetch、記事生成、分類、Issue起票、公開判断の運用は引き続き未実装です。
