# 教師向け　ブラウザ採点の準備

ここで使うのは教師用 Learner Lab の CloudShell（`us-east-1`）です。最初に教師セットアップを済ませます。採点ポータルは別の CloudFormation スタックとして配備します。学生は初回設定済みの演習環境を使えます。

## 1. URLを発行する

```bash
setup=$(mktemp)
curl -q -fsS https://raw.githubusercontent.com/ShinyaHaga0910/JDU-Web-Infrastructure/refs/heads/main/development/setup-classroom.sh -o "$setup" &&
  bash "$setup" portal-prepare
```

画面に `PortalUrl` と `Google OAuth redirect URI` が表示されます。この時点のURLはGoogle設定用です。終わった後も同じCloudShellで `"$setup"` を使います。変数が残っていなければ、上のコマンドで再取得できます。

## 2. Google Cloudにログインの戻り先を追加する

1. 学校のGoogleアカウントで [Google CloudのClients](https://console.cloud.google.com/auth/clients) を開き、授業用のGoogle Cloudプロジェクトを選びます。Googleから2段階認証を求められた場合は、アカウントの本人が設定します。
2. Google Auth Platformの **Clients** で授業用の **Web application** クライアントを選びます。初回は **Create Client** から作成します。
3. **Authorized redirect URIs → Add URI** に、手順1で表示された `https://…/auth/callback` を入力して **Save** を押します。既存のURIは保持します。 [Googleの設定手順](https://developers.google.com/identity/protocols/oauth2/web-server#creatingcred)
4. 既存クライアントを再利用する場合は、教師AWSのSecrets Managerに保管しているOAuthのシークレット名を次の手順で指定します。新規クライアントの場合は、[鍵の登録スクリプト](store_google_oauth.py)を使います。クライアントシークレットは非表示で入力します。

## 3. Googleログインと採点を接続する

`GOOGLE-SECRET-NAME` をSecrets Managerのシークレット名に置き換えます。受講者のAWSアカウントを `--student-account` で指定します。クラスに複数ある場合は、このオプションをアカウントごとに繰り返します。

```bash
bash "$setup" portal-enable --google-secret GOOGLE-SECRET-NAME \
  --student-account STUDENT-AWS-ACCOUNT --expires-on YYYY-MM-DD
```

`--expires-on` に学期最終日を入力します。タシケント時間でその日いっぱい利用でき、翌日の午前0時からポータルは利用できなくなります。

スクリプトは、登録済みの採点テーブルに成績表示・提出サービスを接続します。ログイン用のシークレットは現在のポータル用に作り、Google側で使っているクライアントを再利用します。学生AWSへの許可は、本人確認用テンプレート1ファイルを読むためのものです。

## 4. 利用するGoogleアカウントを登録する

学生のAWSアカウントと、教師基盤に登録された学生のLab IDを指定します。続く入力欄には学生の学校Googleメールを入れます。

```bash
bash "$setup" portal-approve --student-account STUDENT-AWS-ACCOUNT --lab-id STUDENT-LAB-ID
```

教師用の成績一覧は、閲覧を許可するクラスとLabを指定します。複数の場合は `--lab-id` をLabごとに繰り返します。続く入力欄には教師の学校Googleメールを入れます。

```bash
bash "$setup" portal-teacher --class-id CLASS-ID --lab-id STUDENT-LAB-ID
```

## 5. URLを共有する

```bash
bash "$setup" portal-url
```

有効化した採点ページのURLが1行で表示されます。教師セットアップの完了画面でも確認できます。学校Googleでログインし、学生は最初だけ「本人AWSとの連携」を済ませます。P0の採点結果と保存済みの点数が表示されるところまで確認してから、同じURLをクラスのLMSで共有します。


## 学期が終わったら

期限になると、学生・教師のログインとブラウザ採点が自動で停止します。既にログインしているブラウザにも適用されます。成績原本は保持されます。

Google Cloudの **Clients → 授業用クライアント → Authorized redirect URIs** を開き、今回のポータルの `/auth/callback` だけを削除して保存します。ほかの授業のリダイレクトURIは残します。LMSの授業案内から採点URLを外します。
