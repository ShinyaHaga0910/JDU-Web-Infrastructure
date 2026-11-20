# WEB-PORTAL-001：完了 — CloudFormation初期設定後のブラウザ課題確認

最新本人指定の範囲を実装し、GitHubと既存AWSへ反映しました。初期5台は既存CloudFormation・個別登録を使います。学生はサーバーに入り、P/MのWeb・DNS・保存・DB・アプリ・権限を自分で設定します。その後の課題確認・原本保存・本人の成績閲覧・教師の進捗確認をブラウザから行えます。

- [x] R2：停止前記録→同じWeb停止の観測→再開後保持。実M3 3/3。
- [x] R3/R4：既存passwordを使うM5機能・M6権限確認。実M5 13/13、M6 16/16。ブラウザの誤password送信・未確認時の点数保持も検証。
- [x] R5：CloudFormationからブラウザ利用へ進むJA/RU/UZの最小手順を教材ZIPへ同梱。
- [x] R6：指定環境で原本78→82行・旧受付/登録の保持・62/62・本人/教師表示・元5台/96GiB/SSM・Google再ログインから同画面復帰を確認。

[完成条件と実受入の詳細](../web_portal_poc/PORTAL-ACCEPTANCE.md)、[試験方法と未実施](../web_portal_poc/verification/2026-10-30-browser-special-checks-accepted.public.json)。

正規passwordの成功試験では、既存の架空fixtureの秘密をEC2内で暗号化し、ブラウザで結果と原本保存を確認しました。ブラウザのpasswordフォーム自体は誤password canaryで検証しました。独立した学生Google/AWSの通し試験と母語校閲は未実施です。一般学生の個別割当・有効版の発行は各授業の運用として行います。

初回5台の全自動Web化は本人の最新指定で対象外。教師Labは開始中で使用します。教師End Lab中の閲覧、追加非機能基盤、新12資源/worker許可/旧環境削除は今回実施しません。
