# JDU Web Infrastructure

**日本語** · [Русский](README.ru.md) · [O‘zbekcha](README.uz.md)

[採点ページのURLを確認する](#採点ページのurlを確認する)

JDUのWebインフラストラクチャー構築教材です。今セミスターは`Introduction-CyberSecurity`という統合科目の後半で使用します。将来は、この教材を独立した科目の入口として使用できる構成にします。

学生はAWSのVPC内でEC2上のDNS・Web・DBを構築し、教員提供アプリをWebとDBへ接続します。通信経路、公開範囲、service、port、log、保存と復旧を確認します。学生がアプリケーションをプログラミングする授業ではありません。

## 採点ページのURLを確認する

**教師**は、採点ポータルを構築した教師用Learner LabのCloudShell（`us-east-1`）に、次を貼り付けます。有効化済みで利用期限内の採点ページのURLが1行で表示されます。

```bash
setup=$(mktemp)
curl -q -fsS https://raw.githubusercontent.com/ShinyaHaga0910/JDU-Web-Infrastructure/refs/heads/main/development/setup-classroom.sh -o "$setup" &&
  bash "$setup" portal-url --lang ja
```

AWSの画面からURLを探す場合は、教師用Learner Labの **CloudFormation → Stacks → `jdu-web-infrastructure-portal` → Outputs → `PortalUrl`** を開きます。コマンドでURLが表示されないときは、教師用Learner Labで実行しているか、採点ポータルが有効化されているか、利用期限内かを確認してください。 [教師向けの設定手順](development/web_portal_poc/CLASSROOM-PORTAL.md)

教師用の成績一覧を直接開くには、表示されたURLの末尾に `/teacher?lang=ja` を付け、閲覧権限のある学校Googleアカウントでログインします。学生の課題確認画面は同じポータルの `/checks?lang=ja` にあります。

**学生**は、自分のクラスのLMSで教師が共有した採点ページのURLを開きます。教師側のスタックにあるURLなので、学生用CloudShellでは `portal-url` で取得できません。LMSの案内に見当たらない場合は、教師に確認してください。

## AWS演習環境の構築

### 教師・学生が各1回実行する新手順（ウォークスルー用）

AWS Academyで対象のLearner Labを開始し、米国東部（バージニア北部、`us-east-1`）のCloudShellに次を貼り付けます。開始画面で English・Japanese・Русский・O‘zbekcha を選ぶと、その後の入力案内、進捗、完了結果、エラー案内が選択した言語で表示されます。

#### 教師側のコマンド

```bash
setup=$(mktemp)
curl -q -fsS https://raw.githubusercontent.com/ShinyaHaga0910/JDU-Web-Infrastructure/refs/heads/main/development/setup-classroom.sh -o "$setup" &&
  bash "$setup" teacher
```

新規構築には起動時のGitHub最新版を使います。学生側の構築を再開するときは、開始時の版から必要なファイルを取得します。

構築・採点コードをmainに反映すると、GitHub Actionsが構築スクリプトとブラウザ採点用の配布物を同じ版で作ります。[ビルドと成果物の取得方法](development/README.md#採点を変更したときのビルド)

**教師用Learner Lab** では上記のまま実行します。言語を選び、学期最終日と教師用ポータルで使う学校のGoogleメールアドレス（`@jdu.uz`）を入力します。そのメールアドレスでポータルへログインすると、今回の共通登録コードで参加した学生の成績を確認できます。共通登録コードは受講者だけが見られる場所で共有します。表示されたリダイレクトURIをGoogle Cloudに登録し、採点ポータルを有効にします。

[教師向けの採点ポータル設定（Google Cloud・採点URL）](development/web_portal_poc/CLASSROOM-PORTAL.md)

#### 学生側のコマンド

学生用Learner LabのCloudShell（`us-east-1`）で、次のコマンドをそのまま貼り付けます。

```bash
setup=$(mktemp)
curl -q -fsS https://raw.githubusercontent.com/ShinyaHaga0910/JDU-Web-Infrastructure/refs/heads/main/development/setup-classroom.sh -o "$setup" &&
  bash "$setup" student
```

言語を選び、教師から受け取った共通登録コードをコピー＆ペーストして、後で踏み台サーバーのデスクトップを開くときに使う4〜128文字のパスワードを自分で決めます。貼り付けた登録コードは画面に表示されます。パスワードは確認のため同じものを2回入力します。どちらの入力でも1文字ずつ `*` で表示されます。忘れると踏み台サーバーに接続できず演習を続けられないため、決めたパスワードを忘れないでください。スクリプトはLab IDと採点用トークンを個別に生成し、CloudFormationでEC2 5台を構築します。サーバー構築用ファイルの配置と内部SSHの確認後、踏み台から教師の採点APIに構築結果を試験送信します。

学生用スクリプトは、GitHubに記録した版とSHA-256に基づき、公式配布元から依存パッケージを最大8件ずつ並行して取得・検証します。CloudShellで複数のアーカイブにまとめてAWS Systems Manager経由で最大5本ずつ並行して配布サーバーに転送し、展開後に各ファイルを再検証します。取得済みファイル数と転送済みアーカイブ数は30秒ごとに表示されます。サーバー構築用ファイルを置くS3バケットの作成とClass IDの入力は不要です。

途中で切断した場合は、同じCloudShellで学生用コマンドを再実行します。ホームディレクトリに残ったファイルのSHA-256を照合し、一致したものは再利用します。採点先への試験送信が成功すると、この一時保存を片付けます。

内部パッケージの配布先ができたら、サーバー5台の初期設定と確認を同時に進めます。内部SSHの準備では接続先4台のホスト鍵を同時に取得し、踏み台の公開鍵も4台へ同時に登録します。サーバー構築用ファイルはWebとDBへ同時に配置します。

新規スタックは、教師側が `jdu-web-infrastructure-teacher`、学生側が `jdu-web-infrastructure-student-<Lab ID>` です。

学生側のスクリプトは、CloudFormationで課題確認Lambdaと結果保存先も作成します。初期化後に同じ版の採点コードをLambdaへ転送し、5台への接続状態をLambdaから検査します。教師側では、Google Cloudの設定後に課題画面を有効にし、学生Labとの連携を準備します。学生は教師から案内された課題画面をP0から使います。新手順のLearner Labでの通し確認は未完了です。

#### RDPパスワードを忘れたとき

新手順で構築した踏み台サーバーを起動し、環境構築に使った学生用CloudShell（`us-east-1`）に次を貼り付けます。

```bash
setup=$(mktemp)
curl -q -fsS https://raw.githubusercontent.com/ShinyaHaga0910/JDU-Web-Infrastructure/refs/heads/main/development/setup-classroom.sh -o "$setup" &&
  bash "$setup" reset-rdp
```

言語を選び、対象のLabが複数ある場合は画面で選びます。新しく決めた4〜128文字のパスワードを2回入力すると、入力した文字が `*` で表示されます。以前のパスワードと共通登録コードの入力は不要です。完了後は新しいパスワードで `labuser` として接続します。

## 従来の配布手順（教材用S3を使用）

### 教師側

AWS Academyで対象クラスの**教師用Learner Lab**を開始し、米国東部（バージニア北部、`us-east-1`）のCloudShellで次を実行します。

```bash
url='https://raw.githubusercontent.com/ShinyaHaga0910/JDU-Web-Infrastructure/8b080f940957fe3898e65d5a31978f581aa86dd0/development/01_roles/cyber_security/tools/web_lab_teacher/install_teacher.py'
script=$(mktemp) &&
  curl -fsS "$url" -o "$script" &&
  printf '%s  %s\n' 'f943d815e52f38442e292ffd5f74a15b4327c00618a2b8afa3a0d97ee384a2a6' "$script" |
    sha256sum -c - &&
  python3 -B "$script"
```

スクリプトはCloudShellからAWSアカウントを取得し、CloudFormationで教師用のVPC、EC2、固定IPv4、採点API、DynamoDB、非公開S3を構築します。Class IDやAWSアカウント番号の入力は不要です。構築後に採点APIへのHTTPS接続と保存先の設定を検査します。作成せずに事前確認を行う場合は、最後の行に `--plan` を追加します。

学生へ案内する前に、教材を登録し、新しい採点先に対応する署名済み配布物と学校Googleログイン付き課題画面を準備します。 [教師用スクリプトの詳細](development/01_roles/cyber_security/tools/web_lab_teacher/README.md) · [初回の配布・登録手順](course/labs/INITIAL-WORKFLOW.md)

### 学生側

自分の**学生用Learner Lab**を開始し、同じリージョンのCloudShellを開きます。教師から案内された共通配布物の署名と有効期限を確認し、本人用の暗号化配布を受け取ります。その後、初回手順に沿ってCloudFormationで演習用EC2 5台を作成し、採点登録へ進みます。 [初回構築の手順](course/labs/INITIAL-WORKFLOW.md) · [共通準備 P0](course/labs/docs/ja/p0.md)

## 学習の入口

- [この単元だけで学ぶ目的と前提](course/learning-outcomes.md)
- [教材の順序と到達状態](course/roadmap.md)
- [教科書・練習P・課題Mを進める順番](course/labs/README.md#教科書と演習を進める順番)
- [後半教科書の学習順序と必要知識](course/textbook-plan.md)
- [教科書全13章の章立てと各節の説明内容](course/textbook-outline.md)
- [教科書本文と章・課題の対応表（全13章）](course/textbook/README.md)
- [WEB-00 完成像](modules/WEB-00-overview/README.md)
- [WEB-02 HTTPとNginx](modules/WEB-02-http/README.md)

旧第8章を削除し、教科書は第1〜13章の連番に整理しました。停止・再開の演習を外したため、練習のP3は欠番です。自力課題はM1〜M5です。P0の接続確認は1点、M0は4点で、M1・M2・M3・M4・M5と合わせて計64素点です。

## 現在のP/M課題教材

[詳しい練習と自力課題](course/labs/README.md)には、日本語・ロシア語・ウズベク語で41段階の操作例とM1〜M5の採点基準があります。A4 PDFとローカル閲覧用のHTMLも教材zipに収録しています。

教材改訂r1.1では、49段階すべてのコマンド/設定の意味、各Pの仕組みと理解確認、通信経路と出力の読み取り例を追加しています。Mには自分で作業と確認方法を整理する案内を付けています。

正式配布r3は2027年1月31日末（UZT）まで有効です。11/03、新5台をCloudFormationで作成し、初期登録・教材配置・Google/AWS連携・実SSMからのP1/M1設定・ブラウザ確認・成績原本保存・教師表示まで受入済みです。[教師/学生の初回ワークフローとコマンド](course/labs/INITIAL-WORKFLOW.md)を参照してください。**全41手順の学生試読・母語校閲・教師の目視確認は未実施**で、[validation](course/labs/VALIDATION.md)と実機受入の範囲を分けています。全授業のCLASS_READYはfalseのままです。

## 制作担当者

- [環境構築・配布・採点・教師側システムの開発コード](development/README.md)
- [学生5台のCloudFormation](development/templates/web-lab-student.template.json) / [教師の採点受付のCloudFormation](development/templates/web-teacher-d11.template.json)
- [制作方針](COURSE_POLICY.md)
- [AI作業の入口](AGENTS.md)
- [制作・検証の手順](BUILD.md)

教員専用の解答、学生情報、認証情報はこのリポジトリに保存しません。外部教材の本文は複製せず、出典と確認日を記録します。
