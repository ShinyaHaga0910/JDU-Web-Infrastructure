# WEB-PORTAL-001：学生の環境準備・採点確認をブラウザへ集約する

更新：2026-10-30。**全体は未完了。残件はR1〜R6の6項目に固定する。** 完了条件・実行順・証拠は[全体完了表](../web_portal_poc/PORTAL-ACCEPTANCE.md)を正本とする。

## 受入済み

- 学校Googleと本人AWS/Labの連携（先生を学生役にも用いた検証）。
- 本人の保存成績、学生EC2停止中/学生End Lab後の閲覧（教師Lab開始が条件）。
- 通常の課題確認→成績原本の自動保存、未確認時の選択点数保持と同request再送。
- 担当教師の一覧/学生別画面、授業/検証分離、3言語、担当外/ログアウト後の拒否。

[本人連携](../web_portal_poc/verification/2026-10-29-authenticated-student-portal.public.json)・[原本保存](../web_portal_poc/verification/2026-10-30-canonical-submission-accepted.public.json)・[教師画面](../web_portal_poc/verification/2026-10-30-teacher-progress-accepted.public.json)。元5台・暗号化root96GiB・認証・常設SSM・原本を保持。検証用1件の成功を一般学生への配布完了と数えない。

R1の[画面・worker・作成後処理・採点登録](../web_portal_poc/INITIAL-PREPARATION.md)を接続。基盤検査/S3閉鎖/内部SSH/暗号化した個別登録/本人bindingに加え、公開教材配置と同じ5台専用status/checkerを候補接続した。関連Python97・Node73・Web package3とWSL Ubuntuの実filesystem4件が合格。実課題実行・新ready画面のChrome確認・12資源候補のAWS検査/配備は未実施。有効新署名配布/設定/timeout更新/実受入は残る。[教材接続候補](../web_portal_poc/verification/2026-10-30-initial-teaching.public.json)。本人は別Labを用意できないため、元5台の保持併設または具体的な再利用案を実制限/予算から検討する。停止中も数える9台guardを実quotaと断定せず、削除/guard変更は未承認。独立学生identityの受入も未完。初期自動準備は基盤のみで、学生自身が各サーバーで行う導入・設定変更・反映を代行しない。

## 残り6項目

- [ ] **R1 ブラウザから初回5台を準備**：割当/本人AWS確認/資源確認→5台初期化/SSM/内部SSH/採点登録。学生にコマンド転記を要求せず、再読込みで重複作成しない。署名・期限の有効な資材を用いる。
- [ ] **R2 M3/P3 停止前後確認**：同じWebの停止前記録/停止観測/再開後保持をブラウザ手順で確認する。
- [ ] **R3 M5/P5 アプリ機能確認**：本人の非表示password入力から実ログイン/専用架空データ登録・編集/反映/logoutを確認し原本へ保存する。
- [ ] **R4 M6/P6 権限確認**：匿名/誤password/管理入口の許可・拒否を既存条件で確認し原本へ保存する。
- [ ] **R5 一般学生への配布・割当**：検証1件固定を外し、教師が指定した学校identity/AWS/Labだけへ配布・登録・担当許可を行う。正規署名版/固定入口/学生・教師手順を揃える。
- [ ] **R6 最終の通し受入**：別の学生identity/対応Labで構築→確認→原本→本人/教師画面、稼働・停止・再開/学生End Lab後、他人データ拒否と元環境保持を照合し、AWS/GitHub/手順を揃える。

**6項目の合格で全体を終了する。** 非機能面の追加強化、教師End Lab中の閲覧、25点換算、ブラウザ内RDPは今回に追加しない。初回5台準備は候補実装・未受入で、完成間近とは報告しない。

進捗は完了ID/残りID/障害で報告し、同じ検査を理由なく繰り返さない。新しい要望は別Issueへ分ける。過去の経過はGit履歴とverification/の証拠を参照し、現在の完了表に矛盾する履歴を積み重ねない。
