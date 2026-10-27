# Webポータル：読取り処理の小規模試作

2026-10-27。Issue [#1](https://github.com/ShinyaHaga0910/JDU-Web-Infrastructure/issues/1) の初期試作。**まだWeb Functionsに配備していない**。学生の画面・学生AWSとの認証済み接続・End Lab後の実機受入は未実施で、授業で使える製品ではない。

## 今回のコード

- `grade_reader.py` は既存の学生用lab tokenで認証し、既存 `project_lab` の62素点と現在／参照結果を返す。教師用APIの内部で使うための関数であり、HTTP入口やブラウザ認証を公開しない。生のtoken、メール、チェック明細は結果に含めない。
- `status.py` は学生アカウント内の信頼済み既存bindingを受け、STSアカウント、CloudFormationのLab/Deploymentと5台のID、EC2タグを確認する。EC2とSSMを読取り、停止・取得不能を区別する。起動、停止、コマンド送信、採点データの更新は行わない。
- `identity_proof.py` は、固定のAWS STSだけに短時間の署名付きGetCallerIdentityを送り、セッションに紐付く一回限りのnonceを検証する候補を試作する。模擬試験のみで実AWSの署名・nonceヘッダー検証は未確認。永続・原子的なchallenge store、学生ログイン、学生Labと接続先への結び付けは未実装であり、公開しない。
- bindingはサーバー側で確立しなければならず、ブラウザからの任意入力をそのまま渡してはいけない。学生本人とAWSアカウント、Stack、ポータル認証の安全な結び付けは未実装。

## ローカル試験

このdirectoryで `python -B -m unittest -v test_status test_grade_reader test_identity_proof` を実行。架空のAWS応答で、5台停止、取得不能、別account/Stack/タグの拒否、62点と現在UNKNOWNの併存、他Lab/誤tokenの拒否、認証用nonceの期限・再利用・不正な接続先の拒否を検証する。実AWS試験ではない。

既存7群の回帰試験では、6群が合格（計3件skip）、配布群は固定署名版の期限切れにより2件のsetupで停止した。期限を回避したり署名を変更したりしていない。

## 教師AWSでの読取り確認

2026-10-27、Class 193548の教師AWSから既存DynamoDBを直接読み、既存Pythonの `project_lab` で検証用Labの保存済み成績が62/62、現在の未解決が0、検証用コンテキストであることを確認した。教師EC2を経由しない読取りだが、そのEC2は当時runningであり、**EC2停止中・End Lab後の実証ではない**。この確認はCloudShellで行い、新しいWeb Functionsや `grade_reader.py` のAWS配備を意味しない。

同日、別の学生AWSのCloudShellからSTSのアカウント、保存済みstateとbaseline、CloudFormationのLab/Deploymentと5台のinstance ID、各EC2タグを照合した。5台ともrunning・SSM Onlineを確認。個別の読取り操作であり、`status.py` やブラウザ経由での実証ではない。学生ポータルとAWSアカウントの認証済み連携は引き続き未実装。

## 残る受入

1. 教師・学生の実アカウントと既存5台を確認し、既存の保存済み成績と読取り結果を照合する。
2. EC2非依存の経路をWeb Functionsへ接続し、EC2停止中とEnd Lab後の依存API/DBを別々に確認する。
3. 学生のAWS identityを検証して信頼済みbindingを確立し、他人のLabを拒否する。共有PCに秘密鍵や長期認証情報を残さない。
4. 実5台のEC2/SSMとIP、署名期限をブラウザで確認する。試作はまだ署名期限を表示しない。署名版r2の期限は2026-10-27 14:24:57 UZTで、新規構築には更新が必要。

同じ5台と既存のdisk、採点結果、認証情報、署名版を保持する。観測不能を0点に変換せず、ページを開くだけでEC2を起動しない。元のEC2からの提出は従来の教師中継EC2に依存したままである。
