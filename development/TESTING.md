# 移管ソースの検証

## ローカルの確認

Linux/WSLのPython3とGPGで、repository rootから次を実行する。選択したunit/mock regressionだけを実行し、AWSへの配備・変更は行わない。

```bash
python3 -B development/run_local_checks.py
```

Python構文、instance選択、5台template/SSM/controller、教師受付、暗号化受渡し、62素点/観測、配布/再配布/署名、アプリ設定・bundleを確認する。結果はlocal-checks.public.jsonに保存する。初回移管では184件中181件が合格、root/systemd専用の3件はskipだった。AWS実機試験の結果ではない。

初回移管の全byteを再照合する場合は--verify-importを付ける。IMPORT-MANIFESTは移管時の履歴なので、今後意図してソースを修正した後はその照合と通常の回帰検査を区別する。現行の学生template/教師builder/固定appの照合はverify_source_integrity.pyで行う。

```bash
python3 -B development/run_local_checks.py --verify-import
python3 -B development/verify_source_integrity.py
```

履歴の全scriptが初回cloneだけで実機検証できる、という意味ではない。過去probeの実private plan/state、署名秘密鍵、大容量package cacheはGitHubへ登録しない。実PostgreSQL/Nginx/Gunicornを使うintegration fixtureは、専用の架空環境/収録資源が必要であり、このoffline runnerには含めない。

## 既存のAWS受入と残件

署名済みr2、D08/D11の実機受入と、今回のGitHubへのソース移管の検証を分ける。元の固定62素点とD08/D11の署名物を、ソース保存だけを理由に再発行したりAWSへ適用しない。

新しいD12の公開資源搬入と学生が49手順を最初から辿る試験、母語校閲、教師確認、本人の成功password手入力とapp後の全5台停止/再開は未受入のまま。[教材側の範囲](../course/labs/VALIDATION.md)を参照。全授業CLASS_READYはfalse。

新しいコード変更では、対応するunit/mock regressionに加え、必要な実機受入を明示して行う。旧migration用の同じ実環境を無断で初期化しない。
