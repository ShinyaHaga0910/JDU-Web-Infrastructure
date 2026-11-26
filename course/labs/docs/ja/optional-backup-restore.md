# 発展課題案　PostgreSQLのバックアップとリストア

授業で扱う場合は、M3でPostgreSQLの接続と認証を終えたあとに実施します。作業先はDBサーバーです。発展課題用のデータベース2つを用意します。

## 作業すること

1. 練習用の空のデータベースを作り、テーブルに架空の備品を2件登録する。件数と各行の内容を確認しておく。
2. `pg_dump -Fc` でテーブルの定義とデータを保存する。`-Fc` は `pg_restore` で読み込めるカスタム形式を指定するオプションです。
3. 復元用の空のデータベースを別に作り、`pg_restore` でバックアップから復元する。
4. 復元先に接続し、テーブルを開けること、2件の備品の値が元と一致することを確認する。

バックアップは、データベースの定義やデータを別のファイルに保存する作業です。リストアでは、そのファイルを読み込み、データベースを復元します。提出物には元と復元先のデータベース名、SELECTで確認した結果を記載します。

## 旧演習のプログラム

旧P3・M3では、EC2の停止・起動を挟んで同じディスクのファイルが残ることを確認していました。停止・起動を追加で扱う場合は、次のコードを参照できます。

- [停止前・停止中・再開後の証拠を扱う旧チェック](https://github.com/ShinyaHaga0910/JDU-Web-Infrastructure/blob/main/development/01_roles/cyber_security/tools/web_lab_assessment/assessment_check.py)
- [同じディスク・ファイルのハッシュ・起動IDを比較する処理](https://github.com/ShinyaHaga0910/JDU-Web-Infrastructure/blob/main/development/01_roles/cyber_security/tools/web_lab_assessment/remote_guest.py)
- [教師用の旧検証スクリプト](https://github.com/ShinyaHaga0910/JDU-Web-Infrastructure/blob/main/development/01_roles/cyber_security/tools/web_lab_assessment/accept_storage_cycle.py)

旧チェックはEC2のデータ保持を確認するものです。データベースのリストアは、復元先のテーブルとデータを確認します。この案の採点は教員による確認を想定し、通常課題の配点には含めません。
