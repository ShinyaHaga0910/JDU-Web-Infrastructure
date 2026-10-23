# 学生用：Web演習の配布物と採点コマンド

自分のAWS Academyの指定ClassからLabを開始し、CloudShellを使います。Windowsの共有アカウントに秘密鍵・採点認証を保存する手順はありません。

## 1. 配布物の署名を確かめる

教師から、jdu-web-course.tar.gz、同名の.asc、package-signing-public.asc、Class・教師AWS・匿名Lab ID・有効期限の案内を受け取ります。公開のソフトウェアは3ファイルとも同じCloudShell専用フォルダに置きます。ソフトウェア取得リンクは1時間で失効するため、期限切れなら教師から新しいリンクを受け取ります。

教師が別途示す署名fingerprintを確認します。現行の正しい値は **65EC6784750CCFA703BA7179519284E45155EC2A** です。ダウンロードした公開鍵だけから信用する値を決めません。

**展開前**に次を実行します。検証フォルダが既にある場合は新しい専用名を選び、前回のファイルを削除・上書きしません。

```bash
umask 077
mkdir -m 700 "$HOME/web-course-signature-check"
gpg --no-options --homedir "$HOME/web-course-signature-check" --batch --no-autostart \
  --import package-signing-public.asc
gpg --no-options --homedir "$HOME/web-course-signature-check" --batch --no-autostart \
  --status-fd 1 --verify jdu-web-course.tar.gz.asc jdu-web-course.tar.gz
```

署名成功と、VALIDSIGの完全なfingerprintが教師案内と一致することを確認します。期限切れ・失効・不一致の場合は展開せず教師へ連絡します。確認できた場合だけ次へ進みます。

```bash
tar -xzf jdu-web-course.tar.gz
cd jdu-web-course
FINGERPRINT='65EC6784750CCFA703BA7179519284E45155EC2A'
python3 -B student.py verify --trusted-fingerprint "$FINGERPRINT"
```

表示されたClass・教師AWS・期限が教師案内と一致するか確認します。この検査では署名、全ファイル、初期環境と採点機能の内側の署名も調べます。

## 2. 初めて5台を準備する学生

まだ自分のstate/5台がない学生は、同梱の[初期環境の学生手順](foundation/STUDENT.md)を順に実施します。その手順の作業フォルダは`jdu-web-course/foundation`です。本人用の暗号化受信、新規5台、RDP・SSM・内部SSH・採点登録まで進めます。初期化用の大容量教材と本人用の採点認証は、教師から個別に受け取ります。

すでに自分の5台を持つ学生は新規構築を繰り返さず、手順3へ進みます。今回のD11更新は自分の5台・ディスク・作業・鍵・RDP/採点認証を保持します。

## 3. 既存の5台に採点コマンドを対応付ける

`jdu-web-course`へ戻ります。`LAB_ID`には教師から受け取った自分の匿名IDを入れます。初期環境手順で全5台と登録を確認し、Labが動いている状態で実行します。

```bash
LAB_ID='教師から指定された自分の匿名ID'
COURSE_ID='署名確認で表示された配布ID'
python3 -B student.py install --trusted-fingerprint "$FINGERPRINT" \
  --command-state "$HOME/.jdu-web-student/$LAB_ID/command-state.json"
```

`D11_STUDENT_COMMANDS_READY`が出たら、続いて表示された`source .../activate.sh`の1行をそのまま実行します。同じ設定での再実行は確認だけを行います。違う内容がある場合は上書きせず停止します。

導入時は、自分のCloudShellホームを本人専用の権限700へ保護します。Windowsやサーバーの権限は変更しません。

```bash
jdu-web-check --help
jdu-web-check M0 --no-submit
```

新しい入口はP0〜P6/M0〜M6とbootstrapを扱います。旧D08のコマンドは別の場所に残ります。以降は今回のactivate.shを読み込んだ端末で実行します。

## 4. 課題を確認する

通常確認は現在状態を読み取り、結果を教師へ送信します。まず自己確認だけをしたい場合は`--no-submit`を付けます。

```bash
jdu-web-check P2 --no-submit
jdu-web-check P2
jdu-web-check M2
jdu-web-check M4
```

M1〜M6はHTTP8・DNS13・保存3・DB9・アプリ13・権限16、計62素点です。Pは練習、M0/準備は成績に加えません。25点への換算は教師が行います。UNKNOWNは未確認を表し、勝手に0点や合格にはしません。

アプリのログイン・登録・編集・logoutと認証拒否は対話確認を使います。

```bash
jdu-web-check P5 --functional
jdu-web-check P6 --functional
jdu-web-check M5 --functional
jdu-web-check M6 --functional
```

本物のSSM端末が開いたら、対象profileの**既存アプリ管理者パスワード**を非表示欄へ入力します。RDPのパスワードとは別です。自分で構築したアプリのパスワードを使い、教師への報告や会話には書きません。確認処理は専用CK-P/CK-M架空備品だけを登録・編集します。通常の読取り確認だけでは機能確認はUNKNOWNのままです。

保存課題は次の順です。停止・起動そのものは学生がAWSコンソールで行います。

```bash
jdu-web-check M3 --prepare-stop
# AWSで同じWebを停止し、stoppedになってから
jdu-web-check M3 --observe-stopped
# AWSで同じWebを再開し、SSMがOnlineになってから
jdu-web-check M3
```

練習ではP3を使います。別のインスタンスへ置き換えません。

## 5. 点数の確認・未送信の再送

初期環境で導入した本人用の進捗コマンドを使います。

```bash
jdu-web-my-progress
```

生成された本人用URLをブラウザで開きます。本人以外へURLを配らず、教師の管理用URLは使いません。固定のブラウザ入口への集約は後工程です。

送信が`PENDING --retry ...`なら、表示されたIDと元の課題で再送します。

```bash
jdu-web-check M2 --retry '表示されたrequest-id'
```

新しい結果を作り直す必要はありません。STOREDなら教師へ受領済みです。自己確認の`--no-submit`には受領証が付きません。

## 6. 次回の再開と更新

自分のLabを再開し、同じ5台の状態を確認します。新しいCloudShell端末では、保存済みのD11 activate.shを読み込みます。配布IDは署名確認時に表示された値、Lab IDは自分のIDです。

```bash
export PATH="$HOME/.local/share/jdu-web/student-bin:$PATH"
source "$HOME/.local/share/jdu-web/courses/$COURSE_ID/$LAB_ID/activate.sh"
jdu-web-check M0 --no-submit
```

署名期限が切れたら教師から新しい正式版を受け取り、同じcommand-stateを指定して別の配布IDへ導入します。元state/5台/認証/未送信結果を消しません。今回の版の期限はcourse-release.jsonと教師案内で確認します。

旧入口へ戻す必要がある場合は、新しい端末で初期環境用のPATHだけを有効にします。旧入口はbootstrap/P1/M1のみ対応します。全課題の採点へ使い続ける場合はD11の更新確認を教師へ依頼してください。
