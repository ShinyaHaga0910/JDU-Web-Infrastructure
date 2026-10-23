# Web単元：踏み台への採点集約と限定送信の設計

更新: 2026-10-16（Asia/Tashkent）  
対象: D09/D11。2026-10-13にユーザーが推奨構成を採用。  
状態: 踏み台集約の構成方針は採用済み。2026-10-15、別StackのWeb専用教師受付とclientを制作し、テスト２の実APIを10ケース確認した。学生5台のchecker・集約・通信閉鎖・D11配点は未受入。各学生の5 EC2を維持し、既存Linuxの採点コード・教師Stackは変更していない。

独自domainがないというユーザー回答に合わせ、AWS発行のHTTPS名と、EIP付きNginx streamのSNI限定中継を採用した。固定IPv4への接続でもAWS名のCA/hostname検証を維持する。教師が学生より先に別Stackを立て、匿名Lab ID別のtokenを発行する。実値・操作・検証範囲は [教師用受付README](../tools/web_lab_teacher/README.md) を参照。現時点はAPI fixtureの結果で、学生5台の構築受入ではない。

10/16最新追補：本人が既存OS/Linuxのcommand/systemと同じように教師が進捗を追える構成を明示。現行OS-Linux-Controlの2026/labを参照し、Web専用で課題別LATEST保存・途中/UNKNOWNの反映・古い再送による巻戻し防止・教師/本人ページ・日/Uz/露・30秒更新を実装し、実API8群合格。実5台の登録/verifyと踏み台47項目送信/教師保存も受入済み。個人CloudShellのjdu-web-check bootstrapはSSM→踏み台で集約・自動送信し、送信失敗でlocal結果を変えない。JDUメールは本人入力/確認の後だけ本人METAに紐付け、教師/本人以外へ返さない。実学生メールは未収集。D11の課題ID/配点/課題checkerは未定義、学生向け署名配布への統合は残件。以下の「未受入/実値未確定」は当時の設計経過で、現在地はverification_status.mdを優先する。

## 1. 採用した構成

各サーバーで状態を検査し、踏み台で一回の採点実行に対応する結果を集約し、踏み台だけが教員の採点受付へHTTPS送信する。踏み台のInternet送信は原則禁止を維持し、教員の固定受付IP:443だけを例外許可する方針を採用する。認証はHTTPSのserver証明書検証とLab専用トークンを使用する。以前のWeb送信役案は置換済み。

| 場所 | 役割 | 基本の実行方式 |
| --- | --- | --- |
| Web/DNS/DB/パッケージ | 自サーバーのservice・設定・応答を検査 | 教員提供checkerを採点時に実行。新規の採点待受portを作らない |
| 踏み台 | 自身の検査、内部の実通信試験、4台の結果収集・集約・送信 | 学生が採点commandを実行。既存のSSH22でremote checkerを起動 |
| 教員の共通基盤 | 送信元を認証し、結果を保存・進捗表示 | HTTPSの採点受付。各学生の5台とは別の共通基盤 |

学生は踏み台で採点commandを一回実行する。踏み台は既存のSSH公開鍵認証で各サーバーのcheckerを実行し、結果を受け取る。通常のBIND/Nginx/PostgreSQL等は常駐するが、採点checker自体の常駐は必須ではない。

常時監視や操作なしの自動更新が必要になった場合は、まず踏み台側の定期実行を検討する。各台に独自の通信daemonを追加する方式は、待受・認証・起動・版更新の管理が増えるため、初期の推奨にはしない。今回は常時監視の要件はまだ採用されていない。

## 2. 配布と結果の扱い

- checker・期待値・集約commandは教員が初期配布し、未稼働のDNS/DB/Webへ依存せず実行可能にする。学生は採点コードを書かない。
- 結果にはLab識別子、対象サーバー、課題ID、P/M、採点実行ID、使用版、実行時刻、各確認の結果を持たせる。今回の実行結果に過去の結果を混ぜて全体PASSにしない。
- SSH失敗・対象停止・timeout・checker起動失敗は「確認不能」等として表示し、設定を検査できた不合格と区別する。
- 外部送信が失敗してもローカル結果は残し、「採点結果」と「送信済み／送信待ち」を区別する。再送の重複処理はD11で定義する。
- 検査は通常読み取りを中心とする。アプリ書込み確認や拒否試験は対象・作成・片付けを明示してD11で定義する。採点器が誤設定を黙って修正する方式にはしない。
- SSH実行はLabのOS管理経路を使い、checkerが必要な権限と実行方法をD11で固定する。独自の採点用HTTP受付を4台へ増設しない。

基盤確認はjdu-web-check bootstrap、教師はjdu-web-dashboard、本人はjdu-web-my-progress、識別はjdu-web-progress idへ揃える。Pn/Mnの課題ID・観測点・配点・実checkerはD11で固定し、API試験fixtureから授業課題を作らない。

## 3. 送信先の制限と認証は別に行う

| 制御 | 目的 | 採用方針／追加候補 |
| --- | --- | --- |
| SGの送信許可 | 接続できる宛先を制限 | 踏み台から教員の固定IPv4/32、TCP443だけを追加許可 |
| HTTPSのサーバー証明書検証 | 通信の暗号化と接続先の認証 | 通常のCA検証とhostname検証。検証無効化を使用しない |
| Lab専用トークン | 結果の送信元を採点受付で認証 | 現行Linuxの方式を参考に再利用 |
| client証明書／mTLS | 証明書を提示したclientだけを採点受付で認証 | 追加要件として必要なら検討。初期案では必須にしない |

SGはIP・protocol・port等を条件にし、TLSの証明書やアプリのURL pathを判定しない。client証明書があっても、SGが許可していない通信を通せるわけではない。接続する権限をSGで許可した後、採点サーバー側でトークンまたはclient証明書を検証する。

SGの例外は「採点ツールのprocessだけ」を識別するものではなく、「教員の受付IP:443への接続」を許可するもの。受付側も採点用の必要なAPIだけを提供し、任意URLへ転送する汎用proxyにしない。認証情報はLabごとに分け、教材・Git・結果JSON・通常logへ出さない。

## 4. 現行Linuxコードの確認と追加作業

ローカルの現行`2026/lab/scripts/jdu-progress`はHTTPSを必須とし、submitでAuthorization: BearerのLab専用トークンを送信する。CA/hostname検証を無効化する指定や、client証明書を提示する指定は確認した送信処理にはない。現行backendは受信トークンを保存hashと比較して認証する。

確認した教員用CloudFormationはAPI Gateway V2/Lambda/DynamoDB構成で、API Gatewayのexecute-api URLを出力する。固定IPv4の受付やEIPはこのtemplateには存在しない。稼働中AWSの構成は今回確認していない。

したがって、IP一つのSG許可で接続先を安定させるには、教員の共通基盤に固定IPのHTTPS受付／固定上流の中継を設ける追加整備が必要。D09では教員共通環境のEC2＋EIP＋NginxのHTTPS受付を具体案とし、既存採点APIへ必要な要求だけを転送する。学生の5 EC2とは別の共通資源で、実IP・TLS用domain・構築・費用はD10の残件とする。

API GatewayのhostnameをSGへ直接指定できるとは扱わず、一時点のDNS応答IPを恒久的かつそのAPI専用の許可IPとして固定しない。全AWS範囲や全宛先TCP443を許可して「採点先だけ」と表現しない。

採点用FQDNと固定IPを配布manifestで固定し、DNS未完成時も採点送信に限ってcurlの--resolve相当で接続IPを明示する具体案とする。HTTPS URLのhostnameを維持して証明書を検証し、学生の通常DNS動作を確認する採点とは分ける。固定IP・実装・実機動作は未確定。

API GatewayでmTLSを採用する場合は、custom domain、server証明書、truststore、client証明書の発行・配布・更新等を追加する必要がある。default execute-api endpointの扱いも変更する。既存のHTTPS＋トークン方式より教員側の管理・実装は増える。

## 5. 必須の受入条件と残件

1. 踏み台から4台への既存SSH経路で検査でき、独自の採点待受portがない。
2. 対象不足・異常・過去結果を混ぜた状態が全体PASSにならない。
3. 教員の受付へ送信でき、別の外部接続先への新規通信は拒否される。
4. 正しいトークンだけで保存が成立し、誤った／他Labのトークンと識別子の組合せを拒否する。
5. TLSの証明書／hostnameの検証失敗時は送信を成功扱いしない。
6. DNS/採点受付停止・再開・再送を含め、採点と送信状態が区別される。

ユーザーは「その構成にしましょう」と了承した。踏み台のSSH検査・集約、固定受付IP:443のみの外部送信例外、HTTPS＋Lab専用トークン、各台のchecker常駐は必須にしない方針を採用した。

固定受付方式・送信経路・DNS未完成時の補助は[D09の通信案](2026-10_web_infrastructure_network_design.md)で具体化した。実IP/domain、共通基盤の実権限・費用・構築、Web専用API/ID対応、秘密の配布、採点commandと結果形式はD10/D11の残件。実装・実機受入後に送信可能と判定する。次はD10の成立条件を確認し、D08の制作/受入へ戻る。

## 参照

- [ネットワーク設計](2026-10_web_infrastructure_network_design.md)
- [P/Mと自動採点の設計案](../lesson_plans/2026-10-13_web_infrastructure_exercises_and_autograding_design.md)
- [ローカルLinux送信処理](C:/Users/user/Documents/JDU-public/OS-Linux-Control/2026/lab/scripts/jdu-progress)
- [ローカル教員採点template](C:/Users/user/Documents/JDU-public/OS-Linux-Control/2026/lab/teacher/cloudformation/progress-server.json)
- [AWS SGの指定条件](https://docs.aws.amazon.com/vpc/latest/userguide/security-group-rules.html)
- [API Gateway HTTP APIのmTLS](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-mutual-tls.html)
- [EIPの固定IPv4と費用](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/elastic-ip-addresses-eip.html)

確認日: 2026-10-13。ローカルコードと公式資料の確認であり、実サービスを変更・試験していない。
