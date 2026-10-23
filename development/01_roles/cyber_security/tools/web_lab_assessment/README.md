# Web D11：62素点の採点機能

正式学生配布の入口と新規/更新手順は[Web配布版](../web_lab_release/README.md)へ統合済み。保存済みの署名R8/registryはそのまま使い、このfolderは制作・受入の正本として保持する。

2026-10-22、本人が62素点方式で採点機能と残checkerの実装・検証を承認。

M1 HTTP8、M2 DNS13、M3保存3、M4 DB9、M5アプリ13、M6権限16。
各採点checkのPASSを1点。Pは別の練習進捗、M0/環境確認は0点。
教師が科目の25点へ換算する。本人実演・教師の実演点は設けない。

10/23、採点/checkerの実装と実AWS候補受入を完了。M1〜M6は8/13/3/9/13/16、計62/62、P0〜P6/M0も別表示で合格。正式D11学生配布とD12教材は次工程。最新の作業位置と受入の限界は[再開記録](RESUME.md)。
旧D08署名archive、登録5台、認証情報、既存v1提出は保持する。
v2は固定registry ID/hashと完全check集合を照合し、v1を成績へ自動変換しない。

通常確認は読取りのみ。アプリ機能確認は本人が起動する対話モードで、
既存passwordを踏み台のメモリー内だけで使い、専用の架空備品だけを作成・編集する。
停止再開は本人が行い、checkerはサーバーを停止しない。

## 学生用の確認入口

既存D08の5台、CloudShell private state、SSH鍵、RDP/採点認証を維持したまま、
署名検証した別folderから`assessment_check.py`を使う。既存の配備・登録コマンドを実行し直さない。

```sh
python3 -B assessment_check.py M2 --no-submit
python3 -B assessment_check.py M2
python3 -B assessment_check.py M5 --functional
python3 -B assessment_check.py M6 --functional
```

`P0`〜`P6`、`M0`〜`M6`が対象。通常は読取り、指定なしで送信する。
`--functional`は本物のSSM端末で既存アプリpasswordを非表示入力する。
同じ確認回の専用CK-P/CK-M架空備品だけを登録・編集し、password/cookieは報告へ含めない。
実AWSで通常観測/送信/再送、対話SSMの非表示入力/誤認証拒否を確認した。
成功passwordの本人手入力は未試験。機能成功は教師fixtureで正規passwordと実HTTP/CSRF/DB/公開反映を確認している。
旧D08の`jdu-web-check`はbootstrap/P1/M1用のまま。正式D11入口の配布が済むまで、この別folderと混同しない。
実環境では`--command-state ~/.jdu-web-student/<匿名Lab-ID>/command-state.json`を明示する。

Storageは`M3 --prepare-stop`で正常markerを記録し、本人が同じWebを停止、
`M3 --observe-stopped`で停止状態を記録する。同じWebを再開して`M3`で比較する。
Pは`P3`に読み替える。checkerが停止・起動やmarker作成を代行することはない。

送信待ちは表示された`--retry <request-id>`で元の報告を再送する。
`--no-submit`の結果は教師の成績へ入らない。通常確認では機能checkをUNKNOWNに保つ。

## 教師用の進捗・素点

既存教師credentialで`teacher_cli.py context`を使い、登録済みLab/Deploymentを
`verification`または`course`へ指定する。初期値`unassigned`と`verification`は成績出力から除く。
教師の管理キーを学生側へ渡さない。

```sh
python3 -B teacher_cli.py context --lab-id <匿名Lab-ID> --deployment-id <登録UUID> --context verification
python3 -B teacher_cli.py export --output <新規保存先.json>
python3 -B teacher_cli.py export --csv --output <新規保存先.csv>
```

分母は常に62。Mごとに最新の評価可能な提出1回を参照し、未知のある最新状態とは分ける。
最高点の自動選択・異なる提出のPASS寄せ集め・25点換算はしない。
DynamoDBの数値型を通常の整数へ変換してJSON/CSVへ出力する。
旧v1は原本と進捗として保持し、新しい仕様の得点へ自動変換しない。

## 候補の署名と更新

`build_candidate.py`は公開sourceだけを厳密な一覧でまとめ、アプリの固定manifest/hashを照合する。
署名は既存教師署名鍵をローカルで使用する。秘密鍵は配布物・AWSへ送らない。
`candidate_install.install`へ別途信頼済みD08の`release_validation`と固定fingerprintを渡し、
展開前の署名と展開後の全fileを検査する。既存folder/state/起動入口を上書きしない。

`upgrade_teacher.py`は既存Stackのcodeと初回のadmin認証付き2 routeだけを変更できる。
2回目以降はrouteを完全一致で保持するCode-only更新とする。鍵、IAM、EC2、DB、API ID、EIP、SGは変更しない。
prepare→review→executeの計画を別々に保存し、実行済み計画を重複実行しない。

## ローカル検証（2026-10-23）

採点/API/観測25試験（rootで全件実行）、既存設定3試験、
実PostgreSQL16・Nginx/Gunicorn5試験、実BIND9の5試験、練習profile実サービス3試験を使用。
練習と本課題のpasswordログイン・専用架空備品の登録/編集・logout・未認証拒否、
DB分離と実効権限、DNS UDP/TCP/権威応答/NXDOMAIN/AXFR拒否を確認する。
WSL fixtureはloopback/高位portだけを使い、AWS・共有Windowsの資格情報は使わない。

`prepare_local_practice.py`はWSLの既知の架空DB専用の一度限りの準備処理。
学生配布へ収録しない。既存DBやroleがあれば再作成・password変更せず停止する。
実AWSのHBA/SG/SSM、5台の全課題、停止再開、教師受付/画面は別途受入する。

教師受付/3言語画面、学生の既存5台/SSM、新M0〜M6の初期状態7件と教師DBの原本/受領/最新結果は
10/23に実AWSで照合済み。既存の検証Labは成績出力から除外したまま。
正常DNS/DB/appの全課題を実AWSで確認済み。DNS自身の制御確認はlocalhostを使い、
private IPから問い合わせるclientは元の踏み台/Webだけを許可する。

HTTPは元D08のguest/課題sourceのhashを照合して観測を再利用する。
今回nonce・送信元・200応答を元access.log又は公式アプリのpublic access logで確認するため、
アプリ導入後もM1/P1の確認を維持できる。既存D08のsource/署名物は変更しない。
M1=8/8、M2=13/13、M3=3/3と、HTTPの8→4→8、同じWebの停止/再開後の保存・HTTP・DNSを実AWSで合格。
DB9/アプリ13/権限16、練習側も合格。sudo一覧の終了値だけで権限を推定せず、全権限拒否の明示を確認する。
教師DDBで18原本/receiptを独立照合し、現在UNKNOWNでも参照成績を保持、検証Labを実成績から除外することを確認。
教師専用fixture/受入helperは学生候補へ収録しない。今回の成功環境は学生の完成環境として配布しない。
