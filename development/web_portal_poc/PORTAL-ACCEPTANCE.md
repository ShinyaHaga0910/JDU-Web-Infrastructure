# WEB-PORTAL-001 全体の受入と次の実装

2026-10-29。目標は、学生がブラウザだけで本人のLearner Lab準備・状態・課題確認・保存成績を扱い、教師が担当学生の進捗を追えること。今回の本人連携/閲覧の成功だけでは全goalを完了にしない。

| 要件 | 現在の証拠 | 判定/残件 |
| --- | --- | --- |
| 学校Googleの本人確認、本人AWS/Labだけへの登録 | 実Google、学生965の実STS、DDB両方向binding/pair消費 | 検証Labで合格。先生を学生役に使用。一般学生の導入は未受入 |
| 本人の保存62点をEC2停止中に閲覧 | 実本人画面、元5台stopped、教師EC2 stopped | 小規模実証合格。62点/UNKNOWN/元registryは保持 |
| 学生End Lab後の本人用成績閲覧 | 人間のEnd、LMS Terminated/00:00、本人62点、状態unavailable後も62点 | 教師Lab開始中の条件で合格 |
| 5台の状態確認 | 本人画面で元5台stopped、End後は取得不能を表示 | 停止/取得不能合格。runningの本人ブラウザ表示は未受入（非公開probeのrunning実測とは区別） |
| 初回の5台準備をブラウザから実行 | 既存CLI/署名controllerのD08受入のみ | 未実装。署名/期限/価格/閉鎖/SSM/内部SSH/認証/元stateを引き継ぐ必要あり |
| 課題確認をブラウザで受付/進捗/再送 | 既存62checkとCLI/outboxの受入のみ | 未実装。固定taskだけ、永続jobと元request ID、正規checker結果の採点API送信を接続 |
| M3の停止証拠、M5/M6の機能確認 | CLI/getpass/interactiveの既存実装のみ | ブラウザ経路未実装。勝手な起動/完成設定/秘密のSSM command本文保存は禁止 |
| 教師が担当学生の進捗を一覧表示 | 既存教師CLI/JSON/CSVのみ | 新ポータル未実装。Googleメールの自称teacherや自由なLab指定では権限を与えない |
| ログアウト/未登録/不正要求の拒否 | 実未ログイン/未連携/ログアウト拒否、Node44/Motoほか41件 | 検証済み範囲を保持。実別identity/domain/誤AWS/コピーcookieの通し負例は未受入 |
| 一般の学生への配布 | POCの特定学生account限定JSON、期限切れr2保持 | 一般化と署名版の正規更新は未完。期限を無視・古い署名物を改変しない |
| 教師End Lab中の成績閲覧 | HTTPのみ応答し依存先失敗した実測あり | 本人決定で後続。今回は教師Labを開始する運用 |

実機記録は[認証済み学生ポータルの受入](verification/2026-10-29-authenticated-student-portal.public.json)。教師170126527713/学生965244652544、既存Lab class193548-test1。元5台/96GiB/認証/採点原本を保持。学校の先生Googleは本人が学生役に指定した検証用identityで、教師UIの権限は付与していない。

## 次の着手

まず、既存assessment_check/transport/registry/remote_guestと採点APIの契約を読む。固定taskの受付・永続job/SSM command ID・元report/outbox/request IDの再送を接続し、サーバー停止中は実行を受け付けず保存成績を保つ。任意shell/自己申告点数/完成fixtureをHTTP入力で受け付けない。教師中継EC2停止中も提出する経路は既存tokenを再発行せず設計・検証する。現在のCLIが使う中継を、画面だけで解消したとは扱わない。

続いて新規5台の初期準備/署名の正規更新、教師の担当範囲つき一覧を実装し、ブラウザからの通し受入を揃える。AWSへの新しいアプリ権限・公開入口・credentials作成が必要なら、先にコード/差分/計画を具体化し、該当するブラウザ規則による適用直前確認を行う。既に受領した同じ配布/本人連携の承認を再度求めない。
