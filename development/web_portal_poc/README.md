# Webポータル：読取り処理の小規模試作

2026-10-27。Issue [#1](https://github.com/ShinyaHaga0910/JDU-Web-Infrastructure/issues/1) の初期試作。**まだWeb Functionsに配備していない**。学生の画面・学生AWSとの認証済み接続・End Lab後の実機受入は未実施で、授業で使える製品ではない。

## 今回のコード

- `grade_reader.py` は既存の学生用lab tokenで認証し、既存 `project_lab` の62素点と現在／参照結果を返す。教師用APIの内部で使うための関数であり、HTTP入口やブラウザ認証を公開しない。生のtoken、メール、チェック明細は結果に含めない。
- `status.py` は学生アカウント内の信頼済み既存bindingを受け、STSアカウント、CloudFormationのLab/Deploymentと5台のID、EC2タグを確認する。EC2とSSMを読取り、停止・取得不能を区別する。起動、停止、コマンド送信、採点データの更新は行わない。
- bindingはサーバー側で確立しなければならず、ブラウザからの任意入力をそのまま渡してはいけない。学生本人とAWSアカウント、Stack、ポータル認証の安全な結び付けは未実装。

## ローカル試験

このdirectoryで `python -B -m unittest -v test_status test_grade_reader` を実行。架空のAWS応答で、5台停止、取得不能、別account/Stack/タグの拒否、62点と現在UNKNOWNの併存、他Lab/誤tokenの拒否を検証する。実AWS試験ではない。

## 残る受入

1. 教師・学生の実アカウントと既存5台を確認し、既存の保存済み成績と読取り結果を照合する。
2. EC2非依存の経路をWeb Functionsへ接続し、EC2停止中とEnd Lab後の依存API/DBを別々に確認する。
3. 学生のAWS identityを検証して信頼済みbindingを確立し、他人のLabを拒否する。共有PCに秘密鍵や長期認証情報を残さない。
4. 実5台のEC2/SSMとIP、署名期限をブラウザで確認する。試作はまだ署名期限を表示しない。署名版r2の期限は2026-10-27 14:24:57 UZTで、新規構築には更新が必要。

同じ5台と既存のdisk、採点結果、認証情報、署名版を保持する。観測不能を0点に変換せず、ページを開くだけでEC2を起動しない。元のEC2からの提出は従来の教師中継EC2に依存したままである。
