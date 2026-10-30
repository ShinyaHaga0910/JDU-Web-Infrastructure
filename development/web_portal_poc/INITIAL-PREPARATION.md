# R1 初回環境準備の実装状況

2026-10-30。全体の終了条件は[PORTAL-ACCEPTANCE.md](PORTAL-ACCEPTANCE.md)のR1〜R6に固定する。この文書はR1の内訳であり、新しい完了項目を追加するものではない。**R1未完了・AWS未適用。**

## 学生が設定する課題を残す

ブラウザで自動準備する対象はVPC/5台/署名済み依存資源のrepo/踏み台GUI/SSM/内部SSH/採点の入口まで。学生がサーバーへ入って、ソフトウェアの導入、設定ファイル・DNS・DB権限・アプリサービスを変更し、構文検査→サービス反映→実通信を確認する課題は代行しない。Pは詳細な練習、Mは異なる条件の自力課題で、確認ボタンは解答設定を自動適用しない。

現行node_bootstrap.pyはWebのnginx、DNSのbind9、DBのpostgresql-16が未導入であることを初期状態として確認する。教材のstage_resources.pyも公開資源の配置だけで、package/service/DB/role/passwordを作らない。現在62点まで構築した検証5台と、新規学生の開始状態を区別し、前者を初期化して試験しない。

## 今回追加した内部処理

| 部分 | 動作 | 検証範囲 |
| --- | --- | --- |
| portal_preparation.py | 元成績META/完成済み5台を要求せず、教師の事前割当を作る。学校IDは既存HMACで扱い、同じAWS/Labの重複割当と既存binding上書きを拒否する | Motoの実SDK transaction。実Google/実AWSでは未試験 |
| 同上 begin/complete | 既存Google sessionに対応するnonce付きSTSで、割り当てた学生AWSを確認。期限切れは新しいform、再読込みは同じ有効な操作へ戻す | STS fetchはstub、署名の実認証は未試験 |
| 同上 confirm | 明示POSTでfoundation_onlyの要求を1件だけ保存。GET/再送はEC2作成へ進めない | Motoで重複・失効・既存データとの競合を検査 |
| browser_link_handler.py / template builder | preparation専用のAWS確認用CloudFormationを生成し、短期STS proofを固定HTTPS callbackへ送る。既存環境の登録とは別用途。鍵/パスワードのコピー不要 | SDK signer/HTTP stub/inline import。AWS未適用 |
| 既存Webのcallback | 新しいpreparation callbackだけを明示フラグで開く。既定は閉鎖。既存enrollment登録と受領を混同しない | NodeのAPI試験。学生用の準備画面はまだない |
| initial_stack.py | 既存controllerの本物の21パラメーター構築とAMI/予算判定を再利用し、割当と署名資材のhash/期限、96GiB/全5台SSMを確認してCreateStackへ渡す。意図を先に保存し、応答不明時や再送では同じStackを観測する | 元selector/template/parameter builder＋Moto journal＋模擬EC2/CFN。実作成なし |

initial_stackは内部classであり、配備済みのLambda handlerではない。GPG署名を検証済みの資材と、本人が確定した割当を実行workerから渡す必要がある。自己申告JSONをverifiedとして受け付ける公開routeは作らない。RDP hashや署名URLを進捗表・ログへ保存しない。

CloudFormationのClientRequestTokenも固定するが、それだけで二重作成防止を主張しない。元要求・Stack名/ID・タグ・templateを照合し、観測不能では保留する。[AWS CreateStackの定義](https://docs.aws.amazon.com/AWSCloudFormation/latest/APIReference/API_CreateStack.html)。

## R1内でまだ必要な接続

- 学生用準備画面と教師の正式な事前割当・署名配布への接続。
- 学生AWSでの実行Lambda/進捗保存先のpackage/template、価格/AMI等の読取り計画、非表示RDP入力からのhash生成とCreateStackへの接続。
- 作成後の初期状態検査、S3閉鎖、常設SSM/内部SSH/採点登録、公開教材資源配置、元checkへの接続。学生の解答設定は適用しない。
- 有効な新署名版を使った実作成と、未完成の演習開始状態の確認。これはR1の受入、一般学生の通し受入はR6で確認する。

2026-10-30にEdgeの学生AWS965244652544を確認。既存5台は全てstopped、保存済みroot ID一致、nonterminated=5。新5台で計10台となり旧controllerの保守的9台上限を超える。AWSのサービスquotaと断定せず、元5台削除/上限無断変更で通さない。別の初回配備用環境の確保は実作成前に必要。コード制作は継続できる。

実機記録はverification/2026-10-30-initial-preparation-core.public.json。既存成績の変更、新規AWS資源、権限追加、credential発行は行っていない。
