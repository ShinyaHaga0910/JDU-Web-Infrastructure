# 教師用：Web演習の正式配布

教師の採点受付と非公開教材を先に起動し、学生は本人の別AWS accountで5台を使います。教師adminは教師CloudShellにだけ保持します。現在の配布は初期環境と62素点checkerの正式入口で、授業本文のD12は次工程です。

## 配布前に確認する

1. 署名archiveを展開前に独立fingerprintで検証する。展開後は`python3 -B student.py verify --trusted-fingerprint "$FINGERPRINT"`を実行し、Class/教師/期限/全ファイルと内側の署名を確認する。
2. 採点受付のHTTPS/教師画面、対象Classの非公開payload、初期環境の価格台帳の有効性を確認する。教師のLabも授業中は稼働させる。
3. 学生ごとに匿名Lab IDと本人AWS accountを照合する。初回発行・既存認証での再配布は同梱の[初期環境教師手順](foundation/TEACHER.md)を使う。その手順の作業フォルダは`jdu-web-course/foundation`。既存Labへnewで認証を発行し直さない。
4. 共通配布物はソフトウェア3ファイルとこの学生手順。個別の採点認証・大容量payloadの短期URLは、既存の暗号化個別受渡しを使う。

## 共通配布物を非公開S3へ保存する

```bash
python3 -B teacher.py publish --trusted-fingerprint "$FINGERPRINT" \
  --archive "$HOME/jdu-web-course.tar.gz" --output "$HOME/course-publication.public.json"
```

同じ教師の既存bucketの`distributions/<配布ID>/`へarchive/署名/公開鍵/publication.jsonを保存します。全GETを照合し、公開禁止・AES256を維持します。新しいIAM/ACL/EC2/認証は作りません。既存objectは同一なら確認だけ、異なる場合は上書きせず停止します。

必要な時だけ、公開ソフトウェア3ファイルの1時間の取得リンクを作れます。

```bash
python3 -B teacher.py software-links --trusted-fingerprint "$FINGERPRINT" \
  --output "$HOME/course-software-links.private.json"
```

このprivateファイルはソフトウェア取得用URLだけで、学生tokenや教師adminは含みません。共通ソフトウェア自体はLMS等で配布できます。今回の作業でLMSへの投稿や学生への送信は行っていません。

## 学生が新規/更新で行うこと

- 新規学生: 共通署名確認→foundationの個別受信/新規5台/閉鎖/SSM/SSH/登録→D11 install→表示されたactivate.sh→M0確認。
- 既存学生: 共通署名確認→本人の元command-stateでD11 install→activate.sh→M0確認。create/鍵生成/採点登録を繰り返さない。
- 初期状態から課題を実行する。教師の完成fixtureやテスト用の管理者password/学生identityは共通配布へ含めない。
- D11用binは配布ID/Lab IDごとに別保存。元のコマンドを上書きしない。PATHに最後に加えた版が使われる。

## 授業Labと検証Labを分ける

新しい登録Labの初期値はunassignedで、成績exportから除外されます。本人account/登録deploymentを確認してから教師が明示します。

```bash
python3 -B teacher.py context --trusted-fingerprint "$FINGERPRINT" \
  --lab-id "$LAB_ID" --deployment-id "$DEPLOYMENT_ID" --context course \
  --output "$HOME/student-context-receipt.private.json"
```

試験用Labは`--context verification`を使います。既存class193548-test1はverificationのまま保持し、授業の実成績へ変えません。成績出力は次のとおりです。

```bash
python3 -B teacher.py export --trusted-fingerprint "$FINGERPRINT" \
  --output "$HOME/web-raw-grades.private.json"
python3 -B teacher.py export --trusted-fingerprint "$FINGERPRINT" --csv \
  --output "$HOME/web-raw-grades.private.csv"
```

満点は固定62。最新の評価可能な提出の素点を参照し、現在のUNKNOWNとは分けます。練習・検証Lab・未割当Labを実成績に加えず、25点への換算は教師が行います。

## 期限と次版

配布版は初期環境と署名鍵の期限を超えません。今回の期限は**2026-10-27 14:24:57 UZT**です。授業前に署名と価格台帳の期限を点検します。期限切れを無視する設定はありません。

次版は元の受入済みfoundationと承認済みassessmentのbyteを検査して別の配布IDで制作します。実装差分・teacherのAPI/registry整合・既存stateでの移行を受入してから案内します。今の版は元5台/state/root/SSH/RDP/採点認証を保持した更新を対象とし、別Classへprivate設定を流用しません。

## 次工程

D12の授業本文と母語校閲、成功passwordを学生が手入力する通し試験、app導入後の全5台停止/再開は別途記録します。Lambda Web Functionsによる固定ブラウザ入口はWEB-PORTAL-001で最後の改善課題として保持。Learner Labでのサービス利用は本人確認済みで、本人認証/学生accountへの権限連携を今後設計します。
