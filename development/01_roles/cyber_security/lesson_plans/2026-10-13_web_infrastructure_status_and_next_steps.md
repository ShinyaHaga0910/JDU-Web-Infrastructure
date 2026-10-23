# Webインフラストラクチャー単元：現在地と次の作業

2026-10-22 D11訂正：[仕様v0.2](../system_requirements/2026-10_web_infrastructure_d11_assessment_spec.md)に本人の「実演なし・25点換算は教師」を反映。独立した採点check各1点、HTTP8/DNS13/Storage3/DB9/app13/権限16＝62素点の案。M7の手動採点は削除。Pは練習進捗、提供済み環境と前提再確認は加点しない。最新の評価可能な提出・現在状態・未判定/未送信を区別する案。既存10検査のP1/M1は保持。registry/素点表示/残checker/profile/実HTTP自動機能確認は未実装。以下の旧時点の配点案よりこの訂正を優先する。

2026-10-22正式配布追記：D08初期環境版r3を教師private S3へ保存し、全GET・教師/学生実CloudShellのraw署名/全file検証が合格。共通の学生別受渡しと教師/学生手順は[正式配布README](../tools/web_lab_distribution/README.md)。受入済みv7本体と既存5台/state/tokenは不変。**次はD11 v0.2の素点registry・残checkerの制作と受入。科目25点への換算は教師が別に行う。** 完成DNS/DB/appの通し受入、D12教材も残る。配布期限10/27 14:24:57 UZT、distribution_ready=true、CLASS_READY=false。以下の昇格未完表記は追記前の履歴。

2026-10-22更新：**D08の別学生accountでの候補受入が合格**。Class193548の教師170126527713／学生965244652544で署名v7の実取得・新規5台/96GiB・初期化/閉鎖・全台SSM/内部SSH・個別採点登録・基盤47/47・実WEB-02の13提出・同じ5台の停止再開保持/本人RDP/Firefoxまで確認。教師側で全17提出の本文/receipt/最新進捗が一致し、教師/本人の三言語画面と短いcommandも受入した。学生が構築するNginx/BIND/DB/venv等は初期未導入の開始状態を保つ。正式候補の昇格、D11全課題ID/配点/残checker、科目全体のCLASS_READYは引き続き残る。詳細・証跡・次の一手は[検証状況](../../../03_knowledge/aws_official/web_lab_ami_2026-10-15/verification_status.md)最上部。以下の10/15以前の「未実装」「実機未確認」は当時の記録。

2026-10-15実機更新: テスト２の固定Ubuntu AMIで教員probeを実行し、基礎8チェック/651 package採取に合格した。Python3.12.3/GPG2.4.4/OpenSSL3.0.13を実測。AWS CLI/cfn-signalはUbuntuのPATHにない。学生用5台とCloudShell verify/planの通し受入は未完。次は全依存収録・最小repo制作。最新結果と残存検証資源は [検証状況](../../../03_knowledge/aws_official/web_lab_ami_2026-10-15/verification_status.md) を参照。

確認日: 2026-10-13（Asia/Tashkent）  
追記: 2026-10-15、D08の設計再開と配布前の残件を反映。  
用途: このチャットで第3単元の構成・決定・教材制作を進めるための入口  
状態: 既存決定の整理と次工程の提案。提案部分は未採用。

## 1. 現在地

10/13の追加指示により、採点・課題実装より先に最終システムを詳細化して確定する。事前保存方式の専用Ubuntuパッケージサーバーを初期から用意し、踏み台・Web・DNS・DBと合わせた5 EC2を採用した。公開2台・private3台の配置もユーザー了承済み。VPC 10.20.0.0/16、公開10.20.1.0/24、private10.20.2.0/24と各サーバーの固定private IPを設定した。今回の課題はWebシステム構築と正常動作を到達点とし、backup/restoreは実施・採点対象外。[最終システムの棚卸しとIP設計](2026-10-13_web_infrastructure_final_system_inventory.md)を最新入口とする。実AWSへの適用、従来4 EC2の共通図・教材repoの同期は未実施。

目的、対象技術、完成構成、教材の学習順序、科目内の配点は決まっている。WEB-02は日本語Markdownの初稿まで作成済み。完成形アプリ、AWS構築資源、自動判定、Web単元専用の投影・配布資料は未実装／未制作。学生権限のAWS実機受入は未実施。

最新の設計進行: D03〜D07は仕様具体化済み。D08は[保存済みパッケージと初期配備](../system_requirements/2026-10_web_infrastructure_package_distribution_design.md)を公式AMI＋CloudFormation＋install.shへ変更し制作/受入待ち。D09の[通信構成](../system_requirements/2026-10_web_infrastructure_network_design.md)はユーザー採用済み。[D10の資源と運用](../system_requirements/2026-10_web_infrastructure_aws_operations_design.md)はus-east-1/単一AZ、medium1/small3/micro1・root計96 GiB。ユーザー指示でT3固定を廃し、同一AZに揃うx86_64 T系の5台合計最安を選ぶ[selector](../tools/web_lab_instance_selector/README.md)を作成しlocal9試験を確認した。実配備wrapper連携・入力実値・Lab権限/実機は未確認でD08〜D10配布判定は保留。次はpilot入力と実権限を確認しD08制作/受入へ戻る。学生のDNS/DB/Web導入設定と採点集約・限定送信を維持する。

ローカルのJDU-Web-Infrastructure（HEAD: 020483f、最終commit日2026-09-29）の全ファイルと、JUD projectの決定・日次記録を照合した。リモート最新版、実AWS環境、別の保存先にある未記録成果物は今回確認していない。

10/15のD08詳細化: [起動入口と初期化の実装仕様](../system_requirements/2026-10_web_infrastructure_bootstrap_contract.md)で、制作順、学生入力/引数、role処理、失敗/再試行、BASE/INFRA/CLASS_READYとmanifest分割を定義した。続いて[schemaと署名検証/読取りplan](../tools/web_lab_bootstrap/README.md)を制作しlocal24試験に合格、selector9試験も合格。CloudShellでは小さなtool/設定を検証し、bundle本体は配布EC2取得後の検証へ保留する。AWSは模擬応答で、実照会/実配備は未実施。次はAMI/初期tool・必要権限の実確認、依存収録、最小repo template/install処理。create/lock/host側commandと実配布物は未制作。

## 2. 決定済みの前提

| 項目 | 現行の決定 |
| --- | --- |
| 位置付け | 2026年度の統合科目Introduction-CyberSecurityの第3単元。OS・Linux→Network→Webインフラストラクチャーの順。2027年度以降は独立科目として使える構成 |
| 目的 | 小さなWebシステムを自分で構築し、役割・通信・設定理由・変更の影響・障害原因を説明できる |
| 対象 | ほぼ初心者。第3単元の入口ではLinux操作とNetwork基礎を前提とし、不足部分は既存教材へ案内 |
| 技術 | Ubuntu、AWS VPC/EC2/Security Group、Nginx、BIND 9、Storage/EBS、PostgreSQL、教員提供アプリ |
| 学生の担当 | サーバー、ネットワーク、設定、基本SQL、接続制限、正常動作の確認。Webシステムを構築できればよい。backup/restoreは対象外、アプリのプログラミングは課さない |
| 演習環境 | AWS Academy Learner Labを学生別の実習環境として使用 |
| 学習運用 | 説明→手順付き練習→異なる対象での課題→確認・再挑戦。教材単位と授業回を一対一にしない |
| 時間 | 全45コマ、75分×週3回×15週。Web単元は参考27コマ。配分は教員が調整し、必要な説明・図を枚数や時間で削らない |
| 評価 | Web課題を科目成績25点へ換算。OS・Linux25点、Network25点、科目全体の期末試験25点と合わせて100点 |
| AI・再提出 | Webの学習・課題はAI利用可、何度でも再提出可。科目全体の期末試験はAI不可・提出一回 |
| 教材管理 | JDU-Web-Infrastructureに本文・演習・構築資源を置く。共通入口はIntroduction-CyberSecurity。過去のWeb教材は制作元として流用しない |

参考27コマの内訳はVPC5、HTTP/Web4、DNS7、Storage/PostgreSQL6、統合・Security・障害対応5。これは9/10採用プランの参考配分であり、WEB-00〜09ごとの確定授業数ではない。

## 3. 完成構成（9/29の基本構成＋10/13の5台採用）

- 踏み台・Web・DNS・DB・専用パッケージの5 EC2を採用。一つのVPC・単一AZ、公開subnet一つに踏み台とWeb、private subnet一つにDNS・DB・パッケージの配置をユーザーが了承。IP表は最新入口で設定。instance type・性能・予算・構築手順は実機確認前。
- 各EC2へ個別にSG-Bastion、SG-Web、SG-DNS、SG-DB、SG-Packageを関連付ける案。
- 通常閲覧: 学生PCのブラウザ→公開Web→Web側の教員提供アプリ→private DB。アプリがDBを利用し、Nginx自体がSQLを実行するという説明にはしない。
- 名前解決: Webは内部DNSでdb.lab.testを解決する。DNSはHTTPやDB通信の中継サーバーではない。
- 管理: 学生PC→RDP3389→Ubuntu＋軽量desktop＋xrdp＋browserの踏み台→SSH22→Web・DNS・DB。RDPの入口は許可接続元へ限定し、内部SSHはSG-Bastionからだけ許可する方針。
- DNS演習: 踏み台→DNS53でweb.lab.testをWebのprivate IPへ解決。踏み台のブラウザでIP指定から名前指定へ切り替え、同じWebを表示する。
- 学生PCのHTTP/RDPはIGW経由。通常のWeb閲覧経路に踏み台やCloudShellを挟まない。
- DNS・DBは不要に外部公開しない。DBサービスへの接続元はSG-Webとする方針。別管理経路・IAMまで含む制御の実現性は未検証。

完成図の編集元は共通repoの`orientation/slides/assets/aws-system.svg`。初回説明資料の05〜06ページにWebの紹介と完成構成がある。これはWeb単元全体の授業スライドが完成したことを意味しない。

## 4. 現行の教材順序と制作状況

現行の順序はWeb repoの`course/roadmap.md`を優先する。

ただし10/13の今回の指示により、backup/restoreは課題から除外し、Web構築と正常動作を合格条件の中心とする。下記は旧順序の棚卸しであり、Storage・観測・復旧・引き継ぎを独立必須課題として残すかは、今回の構築範囲に合わせて再整理する。

| ID | 内容 | 現在の制作状況 | 学生が示す到達の骨格 |
| --- | --- | --- | --- |
| WEB-00 | 完成像と通信要件 | READMEあり。全体図は共通repoにあり | 各役割と利用・管理・DNSの経路を説明 |
| WEB-01 | VPCと接続経路 | roadmapのみ | VPC・subnet・route・SGを構築し、許可と拒否を確認 |
| WEB-02 | HTTPとNginx | 日本語の説明・練習・課題仕様・確認・障害・再開原稿あり | 静的ページのHTTP応答とservice・port・file・logを対応付ける |
| WEB-03 | 内部DNS | roadmapのみ | 内部名で到達し、recordの誤りを切り分ける |
| WEB-04 | Storage | roadmapのみ | 保存先・容量・権限・再起動時の保持を確認 |
| WEB-05 | PostgreSQL | roadmapのみ。10/13にbackup/restoreを今回の課題から除外 | 基本SQL・role・接続制限・Web側アプリからのデータ利用 |
| WEB-06 | 教員提供アプリとDB接続 | 制作要件のREADMEのみ | ブラウザ→Web側アプリ→DB→応答を実演 |
| WEB-07 | 公開範囲と権限 | roadmapのみ | 必要な経路の成功と不要な経路の拒否 |
| WEB-08 | 観測と復旧 | roadmapのみ | 症状→観測→原因→修正→再確認 |
| WEB-09 | 最終実演と引き継ぎ | roadmapのみ | 構成図・停止／再開手順・個人実演 |

WEB-02も配布完成版ではない。配布file、具体的な配置path、初期状態、接続先、自力課題の判定とcheckerは未確定／未実装。`validation.md`はNginx実機、学生権限、学生試読、配布スライド/PDFを未実施／未作成としている。

## 5. 次に詰める事項

10/13の後続希望により、演習はLinuxと同様の「手順付きP」と「パラメータを変えた同技能の自力課題M」に分け、両方へ自動判定を付ける方向で整理する。採点・次段階の前提確認・実装難易度の具体案は[二種類の演習と自動採点の設計案](2026-10-13_web_infrastructure_exercises_and_autograding_design.md)を参照する。得点配分や実装方式は未確定。

1. **各教材単位の完了条件と評価。** 最新はD11 v0.2。本人実演なし、システム素点を各採点checkの達成件数で記録し、教師が後で科目25点へ換算する。課題別の詳細check・提出回参照方針は案として具体化済み、実装/実機受入は残る。
2. **教員提供アプリの具体像。** 画面で何をするか、架空データ、学生が設定する項目、起動方式、Nginxとアプリの関係、認証情報の保管・配布。コード開発を学生へ課さない前提は維持する。
3. **学生が作る範囲と教員の初期配布。** VPC/EC2/各serviceをどこから学生が作るか、練習と課題で何を変えるか、復旧checkpointの範囲。
4. **Learner Labでの実現性。** 必要権限、5 EC2の費用・GUI性能、Mac/共有WindowsからのRDP、private側の事前保存package取得、resolver設定、別管理経路、停止・再開・保存・削除。
5. **学生向けの制作形式と言語。** Webの本文は現状日本語初稿。三言語併記の投影資料と各言語の配布資料をどこまで作るか、Google Slides/PPTXか既存のMarkdown→HTML/PDF形式かをWeb制作開始時に整理する。OS授業の形式をWebの新決定として自動適用しない。
6. **実際の授業配分。** 開始時期と利用できる残り授業数に合わせて、参考27コマを調整する。開始日・締切は未確認のまま扱う。

## 6. 推奨する制作順序（提案・未採用）

| 順 | 作業 | 成果物・終了条件 |
| --- | --- | --- |
| 1 | WEB-00〜09の授業構成表を具体化 | 各単位に到達目標、作るもの、練習、課題、確認証拠、前提を付ける。未決事項を明示 |
| 2 | 完成形の小さなデモと環境検証 | 教員提供アプリの仕様を決め、RDP・DNS・HTTP・DB・private側導入・再開を学生権限で通し確認 |
| 3 | WEB-01の手順とWEB-02初稿を完成 | 実機結果でpath・初期状態・fixture・確認条件を固定。説明→練習→課題→判定→復旧が一続きで実行できる |
| 4 | WEB-00〜02の投影・配布資料を制作 | 全体像、通信経路、操作主体を図解。配布手順は実機確認済みの内容と一致。目視は教員が行う |
| 5 | DNS、Storage、DB、統合、権限、復旧へ展開 | 同じ環境を段階的に育て、各単位の単体確認と統合確認を残す |

このチャットの最初の制作対象には、手順1の「各単位で何を作り、何を示せば終わりか」の構成表を推奨する。構成表の初案作成は、未確認のAWS機能を仮定せず進められる。Web全単元の投影資料は、完成形と最初の演習単位の検証結果を反映しながら展開する。

## 7. 古い記述との照合

- 9/10採用プランおよび9/25制作方針の旧本文にある「Webはprivate」「静的Webとpsqlを別々に使う完成形」は、9/29の公開Web＋教員提供アプリ＋private DBの決定で置換済み。
- 古いWEB-00〜08表は、WEB-06へアプリ統合を追加した現行WEB-00〜09に置換済み。共通repoの教材索引には旧範囲が残る。
- 公開subnetを踏み台用とWeb用に分ける途中案も置換済み。現在は二台で一つの公開subnetを共有する。
- 7〜8月の11回案・MariaDB・旧Webスライドは今回の制作元にしない。
- 本調査では旧記録の本文や教材repoを改変せず、優先すべき現行記録を本メモで明確にした。

## 8. 参照先

- [Web教材の方針](C:/Users/user/Documents/JDU-private/JDU-Web-Infrastructure/COURSE_POLICY.md)
- [現行の教材順序](C:/Users/user/Documents/JDU-private/JDU-Web-Infrastructure/course/roadmap.md)
- [Web到達目標](C:/Users/user/Documents/JDU-private/JDU-Web-Infrastructure/course/learning-outcomes.md)
- [WEB-00](C:/Users/user/Documents/JDU-private/JDU-Web-Infrastructure/modules/WEB-00-overview/README.md)
- [WEB-02検証記録](C:/Users/user/Documents/JDU-private/JDU-Web-Infrastructure/modules/WEB-02-http/validation.md)
- [WEB-06制作要件](C:/Users/user/Documents/JDU-private/JDU-Web-Infrastructure/modules/WEB-06-app-integration/README.md)
- [科目の採点方式](C:/Users/user/Documents/JDU-private/Introduction-CyberSecurity/course/2026/assessment-policy.md)
- [初回投影資料](C:/Users/user/Documents/JDU-private/Introduction-CyberSecurity/orientation/slides/README.md)
- [9/29の変更記録](../../../02_planning/daily_sources/2026-09-29_sources.md)
- [45コマ採用プラン](2026-09_infrastructure_foundations_45sessions_adopted_plan.md)
- [9/25制作方針・9/29最新決定](2026-09-25_semester_orientation_web_authoring_policy.md)

