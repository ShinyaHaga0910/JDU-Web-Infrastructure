# 教師用：D08の正式配布運用

## 授業前

1. 自分のAcademyのClassとAWS accountを確認し、先に教師用採点受付を稼働させる。学生5台と教師サーバーは別account。教師adminは教師CloudShellだけに置く。
2. 配布版のClass・教師account・API・固定IP・署名期限・公開価格台帳の期限を確認する。`distribution.py verify`で全fileと内外署名を確認する。
3. 教師画面、HTTPS health、非公開payloadを確認する。授業中は教師側Labも稼働させる。学生への送信案内には教師の稼働時間と未送信時の連絡方法を添える。
4. 学生ごとに重複しない匿名Lab IDを割り当てる。学生の個人AWS accountとそのLab IDの対応は教師のprivate台帳で管理する。氏名やメールアドレスを共通配布物へ入れない。

この版はD08初期環境用。P1/M1候補は科目得点ではなく、D11の全課題・配点、D12の授業教材は別工程。

## 学生ごとの初回発行

学生が自分のCloudShellで作った公開recipient requestを受け取る。学生AWS accountとcertificate SHA256を本人と独立に照合する。request自身の申告だけで承認しない。

```bash
python3 -B distribution.py plan --trusted-fingerprint "$FINGERPRINT" \
  --request "$HOME/student-001-recipient.public.json" \
  --student-account "$STUDENT_ACCOUNT" --recipient-sha256 "$RECIPIENT_SHA256" \
  --mode new --plan "$HOME/student-001-plan.private.json"
```

指定Class・教師・学生・Lab ID・教材hash・期限と、新規認証の発行を確認したら、教師自身が実行する。

```bash
python3 -B distribution.py send --trusted-fingerprint "$FINGERPRINT" \
  --plan "$HOME/student-001-plan.private.json" --student-account "$STUDENT_ACCOUNT" \
  --recipient-sha256 "$RECIPIENT_SHA256" --teacher-config "$HOME/.jdu-web-teacher/teacher.credentials.json" \
  --workspace "$HOME/student-001-issued" --confirmed-access
```

学生に渡すのはstudent-delivery.encrypted.cms、そのSHA256、有効期限のみ。元credentialと発行workspaceは教師CloudShellに保持する。教師admin・他学生のcredentialは渡さない。受け渡しは1時間以内、recipientは最大1日で失効する。

## 期限切れ・同じ学生への再配布

**newで発行し直さない。** 元のcredentialを使う。学生には新しいrecipient requestだけ作ってもらい、同じ匿名Lab ID・AWS accountを確認する。

```bash
python3 -B distribution.py plan --trusted-fingerprint "$FINGERPRINT" \
  --request "$HOME/student-001-new-recipient.public.json" \
  --student-account "$STUDENT_ACCOUNT" --recipient-sha256 "$RECIPIENT_SHA256" \
  --mode reuse --existing-credential "$HOME/student-001-issued/own-student.credentials.json" \
  --plan "$HOME/student-001-refresh-plan.private.json"
python3 -B distribution.py send --trusted-fingerprint "$FINGERPRINT" \
  --plan "$HOME/student-001-refresh-plan.private.json" --student-account "$STUDENT_ACCOUNT" \
  --recipient-sha256 "$RECIPIENT_SHA256" --teacher-config "$HOME/.jdu-web-teacher/teacher.credentials.json" \
  --existing-credential "$HOME/student-001-issued/own-student.credentials.json" \
  --workspace "$HOME/student-001-refreshed-01" --confirmed-access
```

教師の結果DBに保存されたtoken hash・有効状態・Lab IDと元credentialが一致する場合だけ、同じ認証と新しい教材URLを暗号化する。登録5台・Deployment ID・過去の提出は更新しない。旧検証環境のcredentialも元の個別fileを指定してreuseできる。

初回sendが途中停止した場合はintent・元credential・教師DBの状態を確認する。元credentialが保存されていれば消さず保持する。未確定の発行を別workspaceで繰り返さない。教師への保存が確認できた後はreuseへ進む。

## 公開配布物と秘密

LMSなどで共通配布できるのは、署名archive、分離署名、公開鍵、公開価格台帳、説明書。初期化用大容量payloadは教師の非公開S3に保持する。公開bucket化しない。学生には期限付きでそのobjectだけを取得させる。

教師CloudShellから、配布版と一致するarchiveを既存の非公開bucketへ保存できます。新しい公開権限は追加しません。同じobject名は、完全一致なら再確認だけを行い、不一致なら上書きせず停止します。

```bash
python3 -B publish_release.py --root . --archive "$HOME/jdu-web-distribution.tar.gz" \
  --trusted-fingerprint "$FINGERPRINT" --output "$HOME/d08-publication.public.json"
```

Windowsへの秘密鍵・採点tokenのdownloadや手動コピーを手順に含めない。共有Windowsのログイン情報の保存を促さない。パスワード入力は学生本人がCloudShellで非表示入力する。

## 配布版・署名の更新

外側配布版の期限は内側core・署名鍵の期限を超えられない。今の版の期限はdistribution-release.jsonを正とする。署名の期限を無視したり、jsonの日付だけ変更したりしない。

制作担当はbuild_release.pyで、元の受入証跡索引・core署名・hashを検査してから別名の配布版を作る。同じ配布版を上書きしない。大容量payload・template・controller・教師接続先を変える場合は、その差分を受入してから昇格する。

core自体の署名更新はbuild_student_tools.pyで新しいmanifestを正規に署名し、価格台帳と教師/payloadの新しい公開factsも照合する。既存stateはmanifest SHAと結び付くため、新coreへ無条件に差し替えない。既存Labへの更新は元state/元root/認証を保持した移行レビューと再確認を必須にし、未検証の移行を学生へ案内しない。期限前の定期点検で、次の授業日まで有効な版を準備する。

新Classでは教師の受付と非公開payloadをそのClassに準備し、そのClassの別学生受入を済ませたcoreから配布版を作る。Class193548の教師・学生用private設定を転用しない。
