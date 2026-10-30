# 教師用の進捗一覧

**10/30教師用進捗一覧をAWSへ実配備・受入完了。** 本人の適用直前承認後、既存非公開2 Codeと同じWebを更新し、先生の既存学校identityへ検証Lab1件だけの独立した教師閲覧許可を設定した。実Google→教師リンク→授業用0件/検証用1件→学生別62点/M5未確認をJA/RU/UZで表示し、担当外Lab・ログアウト後を拒否、再ログインで同じ許可を再利用した。既存学生の5台停止表示と保存M1の元受付日時も保持。05:04:37 UTCの検査で元成績78行全体・学生binding/承認は不変、教師EC2は停止。新資源/IAM/credentialなし。[実受入記録](verification/2026-10-30-teacher-progress-accepted.public.json)。全goalは未完了で、新規5台のブラウザ準備、特殊checker、一般学生配布を続ける。以下の準備中記述は適用前の履歴。

2026-10-30、全体目標の継続指示を受けて実装。学生の確認→原本自動保存はf902844で実受入済み。この次工程では、教師が担当Labの原本成績を一覧と学生別画面で読む。新しい環境構築や特殊checkerはこの一覧の実装とは別の残件。

## 授業での動作

- 学校Googleの通常ログイン後、教師用の閲覧許可がある場合だけトップに「教師用の進捗」を表示する。
- 一覧は匿名Lab ID、M1〜M6の選択済み素点、合計62素点、最新の未確認課題、最終提出日時を表示する。各Labから同じ選択成績/最新確認/日時の詳細へ進む。
- 授業用と検証用を明示的に分ける。verificationの点数を授業用一覧へ混ぜず、25点換算や最高点選択はしない。
- 未確認の最新結果と保存済み点数を区別する。未提出は記録なし、読み取り不能は取得不可と表示し、0点を作らない。元CLIの教師exportは引き続き利用できる。
- 一覧は10件ずつ。50件までの初期担当指定を計画可能。許可された名前付きLabのMETA/LATEST/GRADEだけを読み、全成績tableのscan、EC2/SSM操作、原本書込みは行わない。

## 閲覧許可と配備

既存の非公開GradeReaderにteacher_access/list/detailを追加し、同じWeb入口に/teacherと/teacher/studentを追加する。GradeReaderと本人登録処理は既存の共通ZIPを使うため、2 LambdaのCodeとWeb Revision/Endpointを更新する。新規resource、IAM policy、secret、passwordは追加しない。既存LabRole自体は広いLab権限を持つが、今回の教師操作は読取り専用。

教師は自己申告roleや学校domainだけでは認めない。Googleの検証済みsubject/emailから、教師CloudShellで作った独立したTEACHER/ACCESS行を読む。現在の発行helperは、既に本人確認・承認済みの学校identityからemail HMACとsubject pinを引き継ぎ、担当Lab/deployment/contextを固定する。元の学生binding・承認・原本を教師許可へ書き換えない。

prepare_teacher_access.pyのplanは読取りだけで、applyは独立した操作。元承認/本人対応/元METAと変更前teacher revision/許可内容を同じtransactionで確認し、新たな閲覧許可だけを保存する。担当外Lab、許可失効、元deployment/contextの差替えを拒否する。実適用前には新しい教師閲覧許可として本人確認を受ける。

今回の実機候補は、本人指定済みの先生Google identityとClass193548、学生AWS965244652544の既存class193548-test1（verification）だけ。授業用一覧が空で検証区分にだけ62点が出ることを確かめる。一般学生や他の教師への割当は、対象を具体化した別の許可変更で行う。

## 検証の現在地

| 条件 | 現在 |
| --- | --- |
| 元62点とM5未確認/選択13点保持 | Python/Nodeのcanonical projectionで合格、実AWSで62点/M5未確認・選択13点保持を確認 |
| 学校ログインだけでは教師にならず、担当外を拒否 | 新Python8件/Node8件で合格 |
| 許可取消し/元Lab変更/同時scope変更で権限付与や読取りを拒否 | 新Moto5件とread-only検査で合格 |
| 授業用/検証用分離、未提出/取得失敗の表示 | Python/Nodeで合格、架空データのChrome画面確認済み |
| JA/RU/UZ、一覧→詳細、言語切替時のLab保持 | Nodeと実JA/RU/UZ・一覧/詳細で合格 |
| 既存学生用ログイン/成績/状態/確認/自動保存を保持 | Node全59件、Pythonの既存受入周辺を確認 |
| 配布ZIP/元registry/計画の範囲 | Python package3件/更新計画3件など合格。元registry byteを保持 |
| 実教師許可・AWS配備・EC2停止時の原本不変 | Code/Web UPDATE_COMPLETE、元原本78行全体不変・元binding/承認保持、教師EC2停止を実照合 |

Web更新の準備は未適用の非公開サービスCode計画を参照できる。実applyは、先に非公開2関数が期待する新しいCode hashになったことを照合してから行う。新しい権限の有効化を準備完了と取り違えない。

再開時は教師CloudShellのjdu-web-teacher-progress-20261030-r1にある保存receipt/計画の実行状態を先に読む。既存の更新を重ねて作り直したり、本人登録・鍵・元5台を初期化したりしない。元成績の全partition控えは教師CloudShell内だけに保持する。

## 実際の未実行計画

教師CloudShellのservices-v2.ready.private.jsonはEnrollmentService/GradeReaderのCodeだけ2 Modify、web/enrollment-web.ready.private.jsonは既存Revision/Endpointの2 Modifyで、双方CREATE_COMPLETE/AVAILABLE。teacher-access.ready.private.jsonは現在の先生identityに既存検証Lab1件だけを許可する下書きで、ACCESS行はまだ存在しない。実成績78行の控えを教師CloudShell内に保存した。元原本/5台/認証を保持し、新しい教師用許可の適用直前確認を受けてから、非公開Code→教師ACCESS→Webの順に進める。

[計画の検査結果](verification/2026-10-30-teacher-progress-plan.public.json)。元のサービスreceiptはaccountフィールドを持たないため、未適用Code計画のteacher accountは完全なCloudFormation Stack ARNで照合する。計画準備に使う形式と実applyのlive code hash確認を分ける。準備ツールの初回停止ではWeb計画自体はまだ作られておらず、下書き/原本を変更していない。

## 今回の実機範囲と残件

対象はClass193548の既存検証Lab1件と本人指定の先生Google identityで、roleは匿名Lab/deployment/contextと学校subject HMACに固定した。授業用一覧は空、検証用に62点/M5未確認を表示する。12件の分割、未提出/取得不能、並行権限変更/取消しはMoto/架空応答で確認し、複数の実学生の授業成績や別の実教員identityの受入とは数えない。これらの境界を含む全goalの残件はPORTAL-ACCEPTANCE.mdで継続管理する。

実際のサービスCodeは386f68fdbfa2d2e94af12d304131c60eab2f21a85a3d2e84d8ee4cf593b1ed3f、Webは00a4cce72be52c9c2fe79d1b17805c73b477233451464dcf2f61c520a83cc40e。services-v2.updated.private.json、teacher-access.applied.private.json、web/enrollment-web.updated.private.jsonは教師CloudShell内に保存済み。再開時にapplyを繰り返さない。原本控えはAWS外へ出さない。
