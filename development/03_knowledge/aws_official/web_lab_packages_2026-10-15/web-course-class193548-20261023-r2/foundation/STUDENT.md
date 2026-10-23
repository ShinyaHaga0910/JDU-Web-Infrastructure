# 学生用：Web演習の初期環境

## 1. 自分のAcademyと配布版を確認する

自分のAWS Academyアカウントで指定Classを開き、Labを開始してCloudShellを開きます。教師から案内されたClass、教師AWSアカウント、匿名Lab ID、有効期限を確認します。Windowsの共有アカウントへ秘密鍵・採点認証を保存する操作はありません。

教師から受け取るものは、公開の配布archive、分離署名、公開鍵、独立して確認する完全なfingerprintです。**展開前にGPGでarchiveの分離署名とfingerprintを照合**します。失効・期限切れ・不一致ならそこで止めて教師に連絡します。配布物に書かれたfingerprintだけで信用しないでください。

展開前確認の例です。3つの公開fileをCloudShellの同じ専用folderに置きます。`FINGERPRINT`は教師が独立して示した40桁の値です。署名の成功表示に加えて、VALIDSIG行の完全なfingerprint一致を確認します。一致する前に展開しません。

```bash
mkdir -m 700 "$HOME/web-release-verify"
gpg --no-options --homedir "$HOME/web-release-verify" --batch --import package-signing-public.asc
gpg --no-options --homedir "$HOME/web-release-verify" --batch --status-fd 1 \
  --verify jdu-web-distribution.tar.gz.asc jdu-web-distribution.tar.gz
# VALIDSIGの完全なfingerprintが教師案内と一致した場合だけ実行
tar -xzf jdu-web-distribution.tar.gz
cd jdu-web-distribution
```

確認済みarchiveを展開したfolderで、次を実行します。

```bash
export PYTHONDONTWRITEBYTECODE=1
python3 -B distribution.py verify --trusted-fingerprint "$FINGERPRINT"
```

GPGの最小版で公開鍵検証ができない場合は、教師の環境準備手順に従います。証明書検証や署名検証は無効にしません。

## 2. 自分専用の受け取り先を作る

```bash
python3 -B distribution.py recipient --trusted-fingerprint "$FINGERPRINT" \
  --lab-id "$LAB_ID" --workspace "$HOME/web-delivery-01"
```

教師へ渡すのは`recipient-request.public.json`だけです。ファイル中のcertificate_sha256を別の確認手段でも伝えます。recipient.keyは自分のCloudShellに保管し、送信しません。

教師から暗号化した`student-delivery.encrypted.cms`、そのSHA256、有効期限を受け取ります。教師指定のSHA256と受け取り先certificate_sha256を使い、自分で実行します。

```bash
python3 -B distribution.py receive --trusted-fingerprint "$FINGERPRINT" \
  --workspace "$HOME/web-delivery-01" --ciphertext "$HOME/student-delivery.encrypted.cms" \
  --recipient-sha256 "$RECIPIENT_SHA256" --ciphertext-sha256 "$CIPHERTEXT_SHA256" --confirmed-access
```

認証と教材URLは`web-delivery-01/received/`内にだけ保存されます。画面共有・提出・会話への貼り付けはしません。期限が切れたら新しい受け取り先を作り、教師に「同じLabの再配布」を依頼します。同じLabの採点認証はそのまま使います。

## 3. 新規の5台を準備する

すでに自分のstateやStackがある場合はここを繰り返さず、手順4へ進みます。教師から最新の公開価格台帳を受け取り、配布版のcore内台帳が古い場合はそれを指定します。

```bash
bash core/jdu-web-lab plan --lab-id "$LAB_ID" \
  --output "$HOME/web-plan.private.json" --price-catalog "$HOME/teacher-price-catalog.json"
```

5台・暗号化ディスク96GiB・限定CIDRからのRDP・公開Web80番・全台SSMを確認し、自分で実行します。12～128文字のRDPパスワードを非表示で2回入力します。キー配列にも注意してください。

```bash
bash core/jdu-web-lab create --plan "$HOME/web-plan.private.json" \
  --state "$HOME/web-state.private.json" --confirmed-access \
  --bootstrap-url-file "$HOME/web-delivery-01/received/bootstrap-url.private.txt"
```

途中で失敗したり通信が切れたりしても、作成を繰り返しません。同じstateでstatusを確認し、教師に相談します。パスワード・秘密鍵・認証fileを相談文に含めません。

## 4. 起動確認・閉鎖・SSH・採点登録

以降は常に同じstateを使います。`status`で全5台と初期化完了を確認後、教師の案内に従い順に実行します。初期化中のWAITINGを完了とは扱いません。

```bash
STATE="$HOME/web-state.private.json"
OWN="$HOME/web-delivery-01/received/own-student.credentials.json"
bash core/jdu-web-lab status --state "$STATE"
bash core/jdu-web-lab lock-prepare --state "$STATE"
bash core/jdu-web-lab lock-review --state "$STATE"
bash core/jdu-web-lab lock-apply --state "$STATE"
bash core/jdu-web-lab status --state "$STATE"
bash core/jdu-web-lab ssh-plan --state "$STATE"
bash core/jdu-web-lab ssh-apply --state "$STATE"
# 短期公開鍵の失効を62秒以上待ってから確認
bash core/jdu-web-lab ssh-verify --state "$STATE"
bash core/jdu-web-lab register-plan --state "$STATE" --student-config "$OWN"
bash core/jdu-web-lab register-apply --state "$STATE" --student-config "$OWN"
bash core/jdu-web-lab register-verify --state "$STATE" --student-config "$OWN"
bash core/jdu-web-lab install-commands --state "$STATE" --student-config "$OWN" \
  --bin-directory "$HOME/.local/share/jdu-web/student-bin"
export PATH="$HOME/.local/share/jdu-web/student-bin:$PATH"
```

内部SSHの秘密鍵は踏み台の中にだけ作られます。登録済みならapplyを繰り返さずverifyを使います。CloudShellからの管理は`bash core/jdu-web-lab ssm --state "$STATE" --role web`などで行い、ssm-userで入り`exit`で戻ります。roleはbastion/web/dns/db/repoです。

statusに表示された踏み台IPへ、RDPでlabuserと自分のパスワードを使って接続します。デスクトップとFirefoxを確認してから実行します。

```bash
bash core/jdu-web-lab preflight --state "$STATE" --gui-confirmed
jdu-web-check bootstrap
jdu-web-progress id
jdu-web-my-progress
```

## 5. 次回の再開

AcademyのLabを再開し、同じstateでstatusを確認します。公開IPは変わるため、その時の値でRDP接続します。自分の作業・鍵・採点認証は保持されます。create、recipient、SSH生成、採点登録applyを毎回行う必要はありません。教師の受付が止まっている場合は送信完了になるまで結果を保持します。

署名期限後は古い配布物で操作を続けず、教師に更新版を確認します。stateや既存サーバーを削除して解決しようとしないでください。
