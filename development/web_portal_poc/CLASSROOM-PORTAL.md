# 教師向け　ブラウザ採点の準備

ここで使うのは教師用 Learner Lab の CloudShell（`us-east-1`）です。教師の初回セットアップで、採点ポータル用の CloudFormation スタックも配備します。学生は初回設定済みの演習環境を使えます。

## 1. 教師セットアップでURLと利用期限を設定する

```bash
setup=$(mktemp)
curl -q -fsS https://raw.githubusercontent.com/ShinyaHaga0910/JDU-Web-Infrastructure/refs/heads/main/development/setup-classroom.sh -o "$setup" &&
  bash "$setup" teacher
```

言語を選び、タシケント時間での学期最終日と、教師用ポータルで使う学校のGoogleメールアドレス（`@jdu.uz`）を入力します。既存の教師環境にポータルと教師の閲覧許可を追加する場合も、同じ教師用セットアップを実行します。

画面に `PortalUrl` と `Google OAuth redirect URI` が表示されます。この時点のURLはGoogle設定用です。終わった後も同じCloudShellで `"$setup"` を使います。変数が残っていなければ、最初の2行でスクリプトを再取得できます。

## 2. Google Cloudにログインの戻り先を追加する

1. 学校のGoogleアカウントで [Google CloudのClients](https://console.cloud.google.com/auth/clients) を開き、授業用のGoogle Cloudプロジェクトを選びます。Googleから2段階認証を求められた場合は、アカウントの本人が設定します。
2. Google Auth Platformの **Clients** で授業用の **Web application** クライアントを選びます。初回は **Create Client** から作成します。
3. **Authorized redirect URIs → Add URI** に、手順1で表示された `https://…/auth/callback` を入力して **Save** を押します。既存のURIは保持します。 [Googleの設定手順](https://developers.google.com/identity/protocols/oauth2/web-server#creatingcred)
4. 既存クライアントを再利用する場合は、教師AWSのSecrets Managerに保管しているOAuthのシークレット名を次の手順で指定します。新規クライアントの場合は、次のコマンドで鍵を教師AWSに登録します。続く入力欄にクライアントシークレットを入れます。入力した文字は表示されません。

```bash
bash "$setup" portal-secret --google-client-id GOOGLE-CLIENT-ID
```

## 3. Googleログインと採点を接続する

既存の鍵を再利用する場合は、`GOOGLE-SECRET-NAME` をSecrets Managerのシークレット名に置き換えます。直前に `portal-secret` で鍵を登録した場合は、`--google-secret GOOGLE-SECRET-NAME` を省略します。

```bash
bash "$setup" portal-enable --google-secret GOOGLE-SECRET-NAME
```

手順1で指定した最終日が使われます。タシケント時間でその日いっぱい利用でき、翌日の午前0時からポータルは利用できなくなります。有効化するときに日付を変更する場合は `--expires-on YYYY-MM-DD` を追加します。

スクリプトは、登録済みの採点テーブルに成績表示・提出サービスを接続します。ログイン用のシークレットは現在のポータル用に作り、Google側で使っているクライアントを再利用します。

稼働中の採点ポータルへ最新版を反映する場合は、教師用CloudShellで最新のセットアップスクリプトを取得し、`bash "$setup" portal-refresh` を実行します。現在のログイン設定とポータルURLを使って更新します。

## 4. 学生が自分の演習環境を登録する

`@jdu.uz` のアカウントで学生向けページにログインできます。学生のメールアドレスやAWSアカウントを教師が個別に登録する作業はありません。

初回だけ **自分のAWS環境を登録** を開き、表示されたコマンドを自分の学生用CloudShellで実行します。複数の演習環境が表示されたら、今回使うLabを選びます。CloudShellが表示する連携コードを採点ページに貼り付け、**連携する** を押します。連携コードは、発行元のページで10分間使えます。

### 教師用の成績一覧を設定する

初回セットアップで入力した学校Googleアカウントでログインすると、教師用の成績一覧を開けます。今回の共通登録コードで登録した学生が一覧に自動で追加されます。クラスIDと学生のLab IDの入力は不要です。

更新前に作成した演習環境をこの一覧に追加する場合は、教師用セットアップを更新したあと、学生が同じ共通登録コードで学生用セットアップを再実行します。既存の演習環境を使って再登録します。

## 5. URLを確認して共有する

教師用CloudShell（`us-east-1`）で、次を実行します。別のセッションを開いた場合は、[トップページのコマンド](../../README.md#採点ページのurlを確認する)を使うとスクリプトの取得からやり直せます。

```bash
bash "$setup" portal-url --lang ja
```

有効化した採点ページのURLが1行で表示されます。教師用AWSの **CloudFormation → Stacks → `jdu-web-infrastructure-portal` → Outputs → `PortalUrl`** でもURLを確認できます。

教師用の成績一覧を直接開くには、取得したURLの末尾に `/teacher?lang=ja` を付けます。学生の課題確認画面は同じポータルの `/checks?lang=ja` にあります。

学校Googleでログインし、P0の採点結果と保存済みの点数が表示されるところまで確認してから、同じURLをクラスのLMSで共有します。学生はLMSのURLを使い、最初だけ「本人AWSとの連携」を済ませます。


## 学期が終わったら

期限になると、学生・教師のログインとブラウザ採点が自動で停止します。既にログインしているブラウザにも適用されます。成績原本は保持されます。

Google Cloudの **Clients → 授業用クライアント → Authorized redirect URIs** を開き、今回のポータルの `/auth/callback` だけを削除して保存します。ほかの授業のリダイレクトURIは残します。LMSの授業案内から採点URLを外します。
