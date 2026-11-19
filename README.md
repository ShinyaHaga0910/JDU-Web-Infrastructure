# JDU Web Infrastructure

**日本語** · [Русский](README.ru.md) · [O‘zbekcha](README.uz.md)

JDUのWebインフラストラクチャー構築教材です。今セミスターは`Introduction-CyberSecurity`という統合科目の後半で使用します。将来は、この教材を独立した科目の入口として使用できる構成にします。

学生はAWSのVPC内でEC2上のDNS・Web・DBを構築し、教員提供アプリをWebとDBへ接続します。通信経路、公開範囲、service、port、log、保存と復旧を確認します。学生がアプリケーションをプログラミングする授業ではありません。

## AWS演習環境の構築

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
- [後半教科書の学習順序と必要知識](course/textbook-plan.md)
- [教科書全13章の章立てと各節の説明内容](course/textbook-outline.md)
- [教科書本文と章・課題の対応表（全13章）](course/textbook/README.md)
- [WEB-00 完成像](modules/WEB-00-overview/README.md)
- [WEB-02 HTTPとNginx](modules/WEB-02-http/README.md)

旧第8章を削除し、教科書は第1〜13章の連番に整理しました。演習のP3/M3は欠番で、採点対象は5課題・合計59素点です。

## 現在のP/M課題教材

2026-11-13、P3/M3を除く[詳しい練習と自力課題](course/labs/README.md)を課題別ページへ整理しました。日本語・ロシア語・ウズベク語で、44段階の操作例と現行59素点の採点条件を読めます。初期設定後の[課題確認・成績閲覧はWeb Portal](course/labs/docs/ja/portal.md)を使います。A4 PDFとローカル閲覧HTMLは教材zipにも同梱しています。

教材改訂r1.1では、49段階すべてのコマンド/設定の意味、各Pの仕組みと理解確認、通信経路と出力の読み取り例を追加しています。Mには自分で作業と確認方法を整理する案内を付けています。

正式配布r3は2027年1月31日末（UZT）まで有効です。11/03、新5台をCloudFormationで作成し、初期登録・教材配置・Google/AWS連携・実SSMからのP1/M1設定・ブラウザ確認・成績原本保存・教師表示まで受入済みです。[教師/学生の初回ワークフローとコマンド](course/labs/INITIAL-WORKFLOW.md)を参照してください。**全44手順の学生試読・母語校閲・教師の目視確認は未実施**で、[validation](course/labs/VALIDATION.md)と実機受入の範囲を分けています。全授業のCLASS_READYはfalseのままです。

## 制作担当者

- [環境構築・配布・採点・教師側システムの開発コード](development/README.md)
- [学生5台のCloudFormation](development/templates/web-lab-student.template.json) / [教師の採点受付のCloudFormation](development/templates/web-teacher-d11.template.json)
- [制作方針](COURSE_POLICY.md)
- [AI作業の入口](AGENTS.md)
- [制作・検証の手順](BUILD.md)

教員専用の解答、学生情報、認証情報はこのリポジトリに保存しません。外部教材の本文は複製せず、出典と確認日を記録します。
