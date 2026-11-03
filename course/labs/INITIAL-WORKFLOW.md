# 教師・学生の初回手順と課題開始の確認

更新：2026-11-03。対象はClass193548の既存教師AWSと学生ごとの別AWS。実行場所は各自のCloudShell（us-east-1）。Windowsの共有アカウントには秘密鍵や採点認証を保存しない。

**更新版r3 `web-course-class193548-20261103-r3` を正規署名し、教師の非公開S3へ保存済みです。有効期限は2027年1月31日末（UZT）。** 元のcore実行物・template・payload・採点処理は全byte保持。実学生の元stateを変更せず新courseへ導入し、Web/DBへ公開教材資源を配置できました。旧r2は期限切れの参照として保存しています。新規構築からの初回通し確認はまだ未実施であり、下記手順をその証拠に読み替えません。

## 全体の順序

| 順 | 操作者 | 操作 | 次へ進む条件 |
| --- | --- | --- | --- |
| 1 | 教師 | 教師Labを開始し、採点受付・Web入口・有効な配布物を確認 | 教師AWSが正しく、受付・画面が利用可能 |
| 2 | 学生 | 共通配布物を検証し、本人CloudShellで受取先を作る | 署名・期限一致、公開requestを教師に渡す |
| 3 | 教師 | 学生AWS・受取先を照合して個別配布 | 本人だけが復号できる暗号文を渡す |
| 4 | 学生 | CloudFormationで5台作成、初期化後の閉鎖・SSH・採点登録 | 同じ5台・96GiB・SSM・GUI・登録を確認 |
| 5 | 学生/教師 | 採点コマンドの初期導入と公開教材資源の配置、ブラウザ接続の設定 | 学生の学校Google・AWS・Labが一致し、課題画面が使える |
| 6 | 学生 | Pの手順に沿ってサーバーを設定し、Mを自力で構築 | ブラウザの課題確認に実設定が反映される |
| 7 | 教師/学生 | 結果・成績原本・教師一覧を照合 | 同じ課題の結果と保存時刻が一致 |

CloudFormationは5台の土台を作る操作です。初回の受渡し・採点登録・Google/AWS連携も必要です。課題を解くWeb/DNS/DB/アプリ設定は学生自身が行います。

## A. 既存の検証環境を再開する場合（新規作成しない）

Edgeの教師Academy、Chromeの学生Academyで、それぞれClass193548からStart Lab → 緑のAWSを開きます。ブラウザ名でなく、次の出力でAWSを区別します。

教師CloudShell：

```bash
aws sts get-caller-identity --query Account --output text
# この検証の教師は170126527713
aws cloudformation describe-stacks --region us-east-1 \
  --stack-name jdu-web-progress-2026 \
  --query 'Stacks[0].[StackName,StackStatus]' --output table
```

学生CloudShell：

```bash
aws sts get-caller-identity --query Account --output text
# この検証の学生は965244652544
aws ec2 describe-instances --region us-east-1 \
  --instance-ids i-0488d26e69614e096 i-0c43b73c9a75c41eb \
    i-0f4cfc066e59488a6 i-0ccc3e9206d30867b i-08f8a40fdaa5bb240 \
  --query 'Reservations[].Instances[].[InstanceId,State.Name,PrivateIpAddress,PublicIpAddress]' \
  --output table
aws ssm describe-instance-information --region us-east-1 \
  --filters 'Key=InstanceIds,Values=i-0488d26e69614e096,i-0c43b73c9a75c41eb,i-0f4cfc066e59488a6,i-0ccc3e9206d30867b,i-08f8a40fdaa5bb240' \
  --query 'InstanceInformationList[].[InstanceId,PingStatus]' --output table
```

5台がrunning、SSMが5台ともOnlineになったら、Webへの接続は次です。

```bash
aws ssm start-session --region us-east-1 --target i-0c43b73c9a75c41eb
# Webのssm-userに入ったら
hostname
whoami
exit
```

この5 IDは検証用の固定値です。一般学生へこのまま配りません。学生は自分のCloudFormationのIDを使います。既存環境ではcreate・鍵生成・採点認証発行・本人連携を繰り返しません。

[課題画面](https://d9r6gn83y8wkl4xl.gpb.lambda-web.us-east-1.on.aws)で学校Googleログイン → 課題の確認 → M0を実行します。既に完成済みの検証環境ならM1等も実行し、保存済み成績と教師一覧を確認できます。未構築の学生環境が初めから満点になることは期待しません。

## B. 新規学生の初回構築（有効な更新版を受領後）

以下は既存CLIの実際の引数に対応した実行順です。更新版r3を使い、`LAB_ID`・学生AWS・fingerprint・各SHA256は教師の個別案内で確定します。署名期限とは別に、起動計画で使う教師価格台帳は7日以内が必要です。

### 1. 学生：共通配布物の検証

教師が渡す公開3ファイルを本人CloudShellの同じ専用フォルダへ置きます。署名鍵は別経路で示された完全なfingerprintと照合します。

```bash
umask 077
FINGERPRINT='65EC6784750CCFA703BA7179519284E45155EC2A'
mkdir -m 700 "$HOME/web-course-signature-check"
gpg --no-options --homedir "$HOME/web-course-signature-check" --batch --no-autostart \
  --import package-signing-public.asc
gpg --no-options --homedir "$HOME/web-course-signature-check" --batch --no-autostart \
  --status-fd 1 --verify jdu-web-course.tar.gz.asc jdu-web-course.tar.gz
```

署名成功、VALIDSIGの完全なfingerprint、失効・期限を確認してから、次を実行します。

```bash
tar -xzf jdu-web-course.tar.gz
cd jdu-web-course
python3 -B student.py verify --trusted-fingerprint "$FINGERPRINT"
LAB_ID='教師から受け取った自分の匿名Lab ID'
cd foundation
python3 -B distribution.py recipient --trusted-fingerprint "$FINGERPRINT" \
  --lab-id "$LAB_ID" --workspace "$HOME/web-delivery-01"
```

`web-delivery-01/recipient-request.public.json`と、そこにあるcertificate_sha256を教師へ渡します。`recipient.key`は渡しません。

### 2. 教師：学生ごとの配布

教師も同じ有効な共通配布物を検証し、`jdu-web-course/foundation`で実行します。学生AWSとcertificate SHA256は本人との別の確認手段でも照合します。以下のrequestは学生から受け取った公開ファイルです。

```bash
STUDENT_ACCOUNT='学生本人の12桁AWSアカウント'
RECIPIENT_SHA256='本人と照合したcertificate_sha256'
python3 -B distribution.py plan --trusted-fingerprint "$FINGERPRINT" \
  --request "$HOME/student-001-recipient.public.json" \
  --student-account "$STUDENT_ACCOUNT" --recipient-sha256 "$RECIPIENT_SHA256" \
  --mode new --plan "$HOME/student-001-plan.private.json"
```

計画のClass・教師・学生・Lab ID・期限が正しいことを確認し、教師が実行します。

```bash
python3 -B distribution.py send --trusted-fingerprint "$FINGERPRINT" \
  --plan "$HOME/student-001-plan.private.json" --student-account "$STUDENT_ACCOUNT" \
  --recipient-sha256 "$RECIPIENT_SHA256" \
  --teacher-config "$HOME/.jdu-web-teacher/teacher.credentials.json" \
  --workspace "$HOME/student-001-issued" --confirmed-access
```

学生へ渡すのは`student-delivery.encrypted.cms`とSHA256・有効期限です。教師adminは渡しません。既存学生なら`new`でなく[reuse手順](../../development/01_roles/cyber_security/tools/web_lab_distribution/TEACHER.md)を使い、認証を発行し直しません。

### 3. 学生：本人用情報の受信・CloudFormationで5台作成

本人CloudShellの`jdu-web-course/foundation`で実行します。

```bash
RECIPIENT_SHA256='本人と教師で照合したcertificate_sha256'
CIPHERTEXT_SHA256='教師から受け取った暗号文のSHA256'
python3 -B distribution.py receive --trusted-fingerprint "$FINGERPRINT" \
  --workspace "$HOME/web-delivery-01" --ciphertext "$HOME/student-delivery.encrypted.cms" \
  --recipient-sha256 "$RECIPIENT_SHA256" --ciphertext-sha256 "$CIPHERTEXT_SHA256" \
  --confirmed-access
bash core/jdu-web-lab plan --lab-id "$LAB_ID" \
  --output "$HOME/web-plan.private.json" \
  --price-catalog "$HOME/teacher-price-catalog.json"
```

計画は5台・暗号化96GiB・指定CIDR限定RDP・公開HTTP80・全台SSMです。計画確認後、学生本人が実行し、RDPパスワードを非表示で2回入力します。

```bash
bash core/jdu-web-lab create --plan "$HOME/web-plan.private.json" \
  --state "$HOME/web-state.private.json" --confirmed-access \
  --bootstrap-url-file "$HOME/web-delivery-01/received/bootstrap-url.private.txt"
STATE="$HOME/web-state.private.json"
OWN="$HOME/web-delivery-01/received/own-student.credentials.json"
bash core/jdu-web-lab status --state "$STATE"
```

createは内部でCloudFormationを実行します。別途テンプレートを重ねて作成しません。初期化中ならstatusで確認し、作成を繰り返しません。

### 4. 学生：初期化後の閉鎖・SSH・採点登録

初期化完了後、同じstateのまま順に実行します。

```bash
bash core/jdu-web-lab lock-prepare --state "$STATE"
bash core/jdu-web-lab lock-review --state "$STATE"
bash core/jdu-web-lab lock-apply --state "$STATE"
bash core/jdu-web-lab status --state "$STATE"
bash core/jdu-web-lab ssh-plan --state "$STATE"
bash core/jdu-web-lab ssh-apply --state "$STATE"
```

短期鍵の失効を62秒以上待った後：

```bash
bash core/jdu-web-lab ssh-verify --state "$STATE"
bash core/jdu-web-lab register-plan --state "$STATE" --student-config "$OWN"
bash core/jdu-web-lab register-apply --state "$STATE" --student-config "$OWN"
bash core/jdu-web-lab register-verify --state "$STATE" --student-config "$OWN"
bash core/jdu-web-lab install-commands --state "$STATE" --student-config "$OWN" \
  --bin-directory "$HOME/.local/share/jdu-web/student-bin"
```

RDPで現在の踏み台IPへ`labuser`と自分のRDPパスワードで入り、デスクトップ・Firefoxを確認します。

```bash
bash core/jdu-web-lab preflight --state "$STATE" --gui-confirmed
cd ..
python3 -B student.py install --trusted-fingerprint "$FINGERPRINT" \
  --command-state "$HOME/.jdu-web-student/$LAB_ID/command-state.json"
```

表示された`source .../activate.sh`を実行します。CloudShellからのサーバー管理は次です。

```bash
cd foundation
bash core/jdu-web-lab ssm --state "$STATE" --role web
# 接続先ではssm-user。終了時はexit
```

### 5. 公開教材資源とブラウザへの初回連携

ここは初期配備の外にある重要な工程です。

- P0の`stage_resources.py --installation ...`で、Web/DBへ公開アプリ・SQL/helperを配置します。サービス・DB・パスワード・完成解答は作りません。r3用release-mapへ更新し、実学生での配置・同一再実行を確認済みです。
- 学生AWSには、その学生Labの状態取得・課題確認用Lambda/結果保存先と、指定教師からの呼出し許可が必要です。既存の検証学生では配備済みです。`prepare_checker.py`等の配備補助には検証アカウント固定値があるため、任意学生向けの共通1コマンドとして配りません。
- 教師は学校Googleメール・学生AWS・登録済みLabを対応付けます。既存の`approve_portal_student.py`は教師CloudShellで実行し、学校メールは非表示入力です。秘密鍵保管先ARNやtable名は教師の実配備から取得し、秘密値そのものを渡しません。
- 学生は学校Googleでポータルへログインし「本人AWSとの連携」から指定学生AWSのCloudFormation確認画面を開きます。これは本人確認用3資源で、5台作成とは別です。完了後に元のポータルへ戻ります。
- 教師は授業用/検証用contextと担当一覧へ追加します。既存検証Labのcontextはverificationのままです。

手動で必要な上記設定が終わる前に「create成功＝ブラウザ課題も準備完了」と案内しません。新規学生向け一連の実機確認はまだ未完です。

## C. 課題が実行できることの判定

1. SSMで自分のWeb/DNS/DBに入り、P/M教材の指定ファイル・サービスを操作できる。
2. ポータルが本人のLabを表示し、M0の準備確認を実行できる。
3. P1でNginxと指定練習ページを設定し、ブラウザでP1の結果を見る。練習だけではM1の指定ページは合格しない。
4. M1の指定ページを構築し、ブラウザでM1の8点と原本への自動保存を確認する。
5. 教師一覧で同じ学生・課題・保存結果を確認する。

この順序で新規配布から実行した証拠が揃ったとき、今回の「最初のコマンドから課題へ進める」を合格とします。既存完成環境の62/62は新規学生の通し確認の代わりにしません。既存完成環境をこの確認のために初期化・削除・降点しません。

## 2026-11-03の監査とその後の対応

- 完了：正式r3を2027-01-31末まで正規更新。元state/設定を保持した実installを確認。
- 完了：教材P0をr3へ対応させ、Web/DBに公開教材資源を配置。3言語教材も同期。
- 残る：学生ごとのブラウザ接続設定を含む初回手順の通し受入。本人の追加指示により、この確認も対象へ含める。

## 今回の実機確認結果

同日その後の①②：r3は2027-01-31末まで全層の署名検証に合格し、教師の既存private S3へ新しい配布IDで保存済み。実学生で元state/command-state/baseline/SSH情報4fileのhash不変を確認して更新導入。P0の5つの公開資源をWeb/DBへ配置し、同一再実行も合格。さらに両台の公開アプリ展開とWeb用の署名wheel7点の検証まで完了した。アプリサービス・DB・パスワードは作成していない。[更新と配置の実測](../../development/web_portal_poc/verification/2026-11-03-renewal-and-material-assets.public.json)。

③の新規状態からの確認用には、新Lab `class193548-retest1` の実作成前計画を準備済み。5台を残すと合計10台で現ツール9台guardを超えるため、元root96GiB/原本を保持して検証5台を置き換える案は、適用前確認待ち。以下の表は更新前に発見した状態とブラウザ動作の記録として保持する。

| 確認 | 結果 |
| --- | --- |
| 教師/学生AWS | Edge教師170126527713、Chrome学生965244652544を実STSで照合 |
| 元5台・SSM・root | 全running/SSM Online、元5 volume・暗号化96GiB保持 |
| CloudShellからWebへ | `aws ssm start-session`で接続し、`whoami`がssm-user、`hostname`がip-10-20-1-20 |
| Webサービス/課題ファイル | Nginx active、practice.txt/mission.txtあり |
| P0の新しい教材資源 | `/var/lib/jdu-web/lesson-resources-r1`なし。教材helperの配置工程は実施済みと扱えない |
| ブラウザM0 | 3項目合格、04:43:00 UTCに成績外の原本記録を自動保存 |
| ブラウザM1 | 8/8、04:44:46 UTCに自動保存。学生保存成績62/62・教師一覧の同時刻反映 |
| 原本の独立照合 | 82→84行、M0/M1のREQUESTのみ2行追加。本文hash/receipt一致、元受付・登録metadata・無関係な行は保持 |
| 旧正式配布を実verify | 実Linux/GPG経路で期限切れ拒否。時計変更や検証の無効化なし |

[実測JSON](../../development/web_portal_poc/verification/2026-11-03-initial-workflow-audit.public.json)。今回は新規5台の構築を再実施していません。既存5台の設定・SSH/RDP/採点認証は保持し、M0/M1の正規検証記録だけ追加しました。アプリへの秘密入力を含む全課題の再受入ではありません。

10/30の[ブラウザ機能の完了記録](../../development/web_portal_poc/PORTAL-ACCEPTANCE.md)は維持します。今回の初回手順監査は、その先の一般学生配布まで無条件に合格したという報告を訂正するものです。新規5台の全自動Web化、追加の非機能要件、教師End Lab中の利用を完了条件へ加えません。
