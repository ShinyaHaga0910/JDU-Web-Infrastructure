# WEB-PORTAL-001：完了（合意した範囲・指定検証環境）

2026-11-03追記：本人の「教師・学生の最初のコマンドから本当に課題へ進めるか」という追加確認を[初回ワークフロー](../../course/labs/INITIAL-WORKFLOW.md)で管理する。以下の機能受入は保持するが、期限切れの正式署名r2とP0の配布ID固定があるため、新規学生の初回手順まで今日そのまま通るという意味ではない。新規配布の通し受入は未完。旧R1の全自動Web化を再開する指示ではない。

2026-10-30最新本人決定：**初期設定は既存CloudFormationを使う。構築後、学生がブラウザで課題を確認し、本人の成績を見て、教師が進捗を追えるところを完成させる。** 初回5台作成を全自動Web化する旧R1は今回の必須条件から外す。旧候補コード・署名物は保持するが、新12資源やworker配布許可を追加しない。旧repoを含む既存5台の削除・置換も行わない。

## 完成の判定

1. 初期構築は既存CloudFormationと、その初期接続・採点登録手順を利用する。学生がサーバー内でWeb/DNS/DB/アプリを設定する課題は維持する。
2. 構築・登録後は学校Googleでログインし、P0〜P6/M0〜M6の課題確認から結果表示・成績原本保存までブラウザで行える。課題確認のコマンドや結果URLのコピーを要求しない。
3. P3/M3の停止前記録→同じWebの停止観測→再開後保持、P5/M5の既存passwordを使う実ログイン/作成/編集/公開反映/logout、P6/M6の許可・拒否まで既存checkerの条件で確認する。
4. 本人の保存成績と教師の担当学生進捗が表示され、学生EC2停止中・学生End Lab後も保存成績を見られる。教師Labは開始中で使う。
5. 固定62素点、P/M0成績外、未確認時の確定点保持と同report再送を維持する。既存5台/root96GiB/認証/SSM/原本を保持し、表示だけでサーバーを起動・停止しない。GitHub/AWS/最小の学生・教師手順が一致する。

## 既にAWSで確認済み

| 操作 | 実確認 |
| --- | --- |
| 学校Googleと本人AWS/Labの連携 | 指定された先生を学生役とした実Google/学生AWSの実STS、登録、logout/再login。[証拠](verification/2026-10-29-authenticated-student-portal.public.json) |
| 保存成績・5台状態 | 62点、学生5台停止、学生End Lab後の62点表示。教師Lab開始が条件。[証拠](verification/2026-10-29-authenticated-student-portal.public.json) |
| 通常の課題確認・原本保存 | 実M1/M2/M5、元report、未確認M5で選択13/合計62維持、再送・停止後閲覧。[確認](verification/2026-10-29-browser-checks-accepted.public.json)・[原本](verification/2026-10-30-canonical-submission-accepted.public.json) |
| 教師一覧・学生別画面 | 担当の検証Labだけの62点/M5未確認、授業/検証分離、3言語、担当外/logout拒否。[証拠](verification/2026-10-30-teacher-progress-accepted.public.json) |

## 今回の完了記録

| 旧ID | 作業 | 結果 |
| --- | --- | --- |
| R1 | 初回5台の全自動Web化 | 今回対象外。既存CloudFormation・個別の初期登録を使用。旧5台の削除・置換や新12資源は実施しない |
| R2 | P3/M3停止前後のブラウザ確認 | done。実M3で同じWebの停止・元volume/marker保持・boot ID変化、3/3と原本保存 |
| R3/R4 | P5/M5・P6/M6の機能/権限確認 | done。M5ブラウザ誤password経路と点数保持、EC2内の既存fixtureでM5 13/13・M6 16/16、ブラウザ結果表示/同report保存 |
| R5 | 最小手順と配布入口 | done。[ブラウザ手順](BROWSER-CHECKS.md)、教材ZIP内のJA/RU/UZ追補。元P/M本文・署名物は保持し、採点CLIを追補で置き換える |
| R6 | 指定環境の不足操作の受入 | done。原本78→82行、旧受付/登録不変、62/62、本人/教師最新表示、元5台/暗号化96GiB/全SSM Online、同画面へのGoogle再ログイン |

[今回の詳細な実受入・試験方法・未実施](verification/2026-10-30-browser-special-checks-accepted.public.json)。正規passwordの成功試験は秘密をEC2内に保持するfixture経路、ブラウザのpassword送信は誤password canaryによる実経路で検証した。人による正規passwordフォームの成功を確認済みとは報告しない。旧R1は再開作業に戻さない。今回の制作・AWS反映は完了し、追加実装は新しい依頼を待つ。

独立した学生Googleでの試読・通し試験は未実施と明記する。本人は別環境を用意できないため、新しいGoogle/AWSアカウントを今回の実装完了の条件に追加しない。一般学生への展開済みと、指定された検証環境での受入を区別する。

初回構築Web化・教師End Lab中の閲覧・監視/負荷/追加可用性対策・25点換算・本人実演・ブラウザ内RDPは今回に追加しない。新しい要求がなければ上の完成条件を増やさない。報告は「学生ができる操作/まだできない操作」を基準にする。
