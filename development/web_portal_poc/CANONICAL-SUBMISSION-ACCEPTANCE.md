# ブラウザ確認結果の成績原本への自動保存

**2026-10-30 AWS配備・実ブラウザ受入完了。** 新M1は追加保存操作なしで自動反映。元M1/M5保存と旧request再送も確認。詳細は[実受入記録](verification/2026-10-30-canonical-submission-accepted.public.json)。全ポータルの別残件は本受入に含めない。

2026-10-29本人指示で制作。今回の完成条件は、ブラウザの確認完了後に元report/request IDを既存成績DBへ自動保存し、画面と保存済み成績で確認できること。GitHub反映とAWS配備・実受入まで行う。新しいサーバー、table、role、認証情報は追加しない。

## 保存する内容

- 教師側の非公開checkerがGoogle本人登録・教師承認を確認し、登録済み学生Lambdaから元reportをIAM経路で取得する。ブラウザからreport/点数/宛先を受けず、元Bearer tokenを取り出さない。
- 既存D11 APIの`assessment_attempt`と`AssessmentStore.submission_writes`を共用する。素点62、P/M0成績外、最新の確定可能なM結果を選択する既存規則を維持する。最高点や項目の和集合へ変えない。
- 原本へREQUEST/最新確認/METAを保存し、確定可能なMだけGRADEも更新する。未確認がある場合は最新確認と受付記録を保存し、選択済みGRADEを保持する。M3/M5/M6の特殊確認を実装したことにはしない。
- 本人binding・教師承認と元metadataを同じDynamoDB transactionで確認する。保存したREQUESTには元reportそのものとjob/本人HMACの対応を付ける。生の学校ID、メール、password、鍵を追加保存しない。
- 同じrequest IDの再送は最初の受付を返し、新しい確認や成績の並べ直しをしない。GETは原本に書かず保存状態だけを表示する。未保存時の再試行も同じreportを使いSSMを再実行しない。

## 受入

| 条件 | 現在 |
| --- | --- |
| 確定可能なMを原本へ自動保存し選択成績と表示へ反映 | Motoと実AWSで合格。新M1 8/8→完了POST自動保存→保存日時/選択成績を実表示 |
| 未確認Mは最新記録へ保存し確定済み点数を保持 | Motoと実AWSでM5 9/13＋未確認4の記録、選択13点・合計62点保持を合格 |
| P/M0は成績外、元62点方式を維持 | 新9件と既存API14件合格。今回新しいP/M0の実AWS実行はしていない |
| 切断・同request再送・GETで二重保存や再実行なし | Motoと実AWSで旧request再送の原受付・全partition不変を合格。M5保存応答の一時失敗後もGETで回収し、SSM再送なし |
| 本人・task・run・元report不一致、保存直前の失効を拒否 | Motoで合格。新しい認証方式や権限基盤は追加しない |
| 画面で保存済み/未保存/未確認/P成績外を区別 | Node51件合格。実JA/RU/UZで保存日時、M5未確認を確認。P成績外の新実画面試験は未実施 |
| AWS配備・元5台/96GiB/認証と元REQUEST保持 | 既存2 Lambda CodeとWebのUPDATE_COMPLETE、原本75→78行/旧行・登録保持、元5台/96GiB照合と停止を実確認 |

教師CloudShell内だけの更新前75行控えを使い、verify_canonical_submission.pyで今回の新REQUEST3件と最新/選択/METAだけの期待差分、元REQUESTと登録情報の保持を実照合した。成績DB全体不変は今回の合格条件にしない。受入対象は既存の検証Labで、一般学生配布や教師一覧の完成とは分ける。
