# Web単元のAWS資源と起動停止運用

10/20最終受入：同じ新5台/元rootで署名c5-v6のテスト２候補受入が合格。常設全5台SSM・S3閉鎖・内部SSH/個別採点登録、基盤47/47・AWS29/29・全role/network、実課題13件/教師保存、空cache役割別導入・7wheel/WSGI起動、登録後停止再開/本人GUI/作業保持を確認。学生導入packageは初期状態へ復元済み。v4で新規作成後のv5/v6移行を検証した範囲で、v6 cold CreateStack/別学生accountは未検証。本人指定の別学生Lab [193548]を次に確認する。正式学生配布/D08全体/CLASS_READYは保留。詳細は[最新検証状況](../../../03_knowledge/aws_official/web_lab_ami_2026-10-15/verification_status.md)冒頭。以下の以前の未実装/待ち状態よりこの最終記録を優先。

10/20更新：本人の指定で、CloudShell→5台すべてのSSM接続を常設する。既存LabInstanceProfile（SSM以外のLabRole権限も含む）を全台に付け、既存2個のprivate endpointを共用する。追加EC2・EBS・endpointを作らず、同じ5台/元rootを継続。停止再開後もSSM経路を維持し、共有Windowsへ秘密鍵を保存しない。署名tools c5-v5への同一5台移行とS3閉鎖後のAWS29項目・全role/networkは実合格。以後の停止再開・実session・内部SSH/採点・GUI受入はverification_status.md冒頭へ記録する。

更新: 2026-10-15（Asia/Tashkent）  
対象: D10。D09の構成は同日のユーザー了承により採用。以下はAWS資源・運用の具体案。

学生1人につき既存の5 EC2を維持し、公式Ubuntu24.04とCloudFormation＋初期化scriptで開始状態を揃える。教員は共通のS3搬入元と固定IPの採点受付を用意する。授業後は学生の5台を停止してEBSを保持し、次回は同じStackを再開する。backup/restoreは学生課題に加えない。

## 今回決める範囲と状態

| 完了条件 | 具体化する内容 | 残る確認 |
| --- | --- | --- |
| region/AZ/AMI | us-east-1を第一候補、単一AZ、公式Ubuntu24.04/amd64を版固定 | 学生Labの提供/権限、AZ/typeの組合せ、AMI実ID・owner・root最小容量 |
| 性能と保存 | micro/small/mediumの役割を維持し、提供AZと実価格からT系familyを自動選択。root gp3容量とcredit設定 | GUI/初期化/appの性能、Lab許可/空き容量、収録資源と一時展開の実サイズ |
| 権限と配布入力 | 学生Stack・教員共通資源・事前準備・渡す値を分離 | endpoint/SG/CloudFormation/署名付き取得の実権限 |
| 費用 | 公開単価による学生と教員の概算、停止中の残費用 | 実Labの残予算/計上、S3/転送/既存backend/domain等の費用 |
| 運用 | 新規構築、制限切替、停止/再開、障害診断、終了処理 | 学生権限の通し受入と実測時間 |

資源の候補と運用手順を仕様化する。実AMI・IP/domain/bucket・Lab権限が未確定なので、D10完了・授業配布可能とはまだ判定しない。

## リージョンとAZ

第一候補はus-east-1（N. Virginia）。既存Linux教材の手順と教員テストでの利用記録に合わせ、学生5台、教員のS3搬入元、採点の固定入口をこのregionに揃える。既存採点APIの実regionは別途照合する。

既存Linux教材にはus-east-1での構築とus-east-1aのテスト記録があるが、Webの5台構成や今回のLab権限を証明するものではない。[ローカルLinux Labの記録](C:/Users/user/Documents/JDU-public/OS-Linux-Control/2026/lab/README.md)

学生側は単一AZ。ユーザーがAZ/typeの固定による過去の起動エラーを指摘したため、T3固定案を変更する。起動前scriptが利用可能AZとx86_64 T系のmicro/small/mediumを照会し、1つのAZですべて提供されるfamily/AZ候補を料金順に選ぶ。初回選択をLabの配備記録に固定し、更新時に自動再選択しない。AZ名が同じでも別accountで同じ物理AZとは限らないため、全学生へus-east-1aを無条件に強制しない。[AZ名とaccountの対応](https://docs.aws.amazon.com/global-infrastructure/latest/regions/aws-availability-zones.html)

us-east-1が対象Labで使えない場合は配布前にregionを見直し、AMI・S3・通知bucket・prefix list・料金・採点入口を一組で再確認する。学生ごとに異なるregionへ自動fallbackしない。

## 公式AMIの選定と固定

| 項目 | 選定条件 |
| --- | --- |
| OS | Ubuntu Server24.04 LTS（Noble）、通常のserver image |
| CPU/起動 | amd64（EC2ではx86_64）、HVM、EBS root、選定したT系familyに対応 |
| 発行元 | Canonical、通常AWS partitionのowner 099720109477 |
| image名 | ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-* |
| 除外 | Arm、Minimal、Pro、EKS、Marketplaceの別製品を同一版の代わりに使わない |
| 固定する値 | region・AMI ID・image名・CreationDate・owner・root device名/最小容量・初期package一覧 |

教員がEC2 DescribeImagesまたは公式SSM公開parameterを使って候補を取得し、ownerとmetadataを照合する。選定後は実AMI IDを配布manifestとtemplate入力へ固定する。学生の起動ごとにcurrent/latestを解決させない。[CanonicalのAMI選定仕様](https://ubuntu.com/aws/docs/aws-how-to/instances/find-ubuntu-images/)

AMI実IDは未確定。学生LabでDescribeImagesの照合と起動を行い、依存資源を収録する基準版を確定する。公開locatorの表示だけでLabの起動可能性を判定せず、別OSへ自動変更しない。

## 各サーバーの性能とディスク

| 役割/IP | type案 | vCPU / memory | root gp3 | 理由 |
| --- | --- | --- | --- | --- |
| 踏み台10.20.1.10 | 選定family.medium | 2以上 / 4 GiB以上 | 24 GiB | Xfce/xrdp/Firefoxと採点集約を同時に利用 |
| Web10.20.1.20 | 選定family.small | 1以上 / 2 GiB以上 | 16 GiB | Nginx、Gunicorn1 worker、Djangoと設定作業 |
| DNS10.20.2.10 | 選定family.micro | 1以上 / 1 GiB以上 | 8 GiB | BINDとSSH・検査toolの小規模利用 |
| DB10.20.2.20 | 選定family.small | 1以上 / 2 GiB以上 | 16 GiB | PostgreSQL16と小さな授業DB。D07の容量案を維持 |
| 配布10.20.2.30 | 選定family.small | 1以上 / 2 GiB以上 | 32 GiB | 全資源の保存、初回archiveと展開中の一時領域 |
| 合計 | 5 EC2 | 実typeの合計 / 11 GiB以上 | 96 GiB | vCPU数はfamilyに依存。T3系の場合10 vCPU |

sizeとmemoryは役割別に保ち、familyとAZは自動選択する。T2/T3/T3a等の名称を価格順と決めつけず、AWS metadataのCPU/architecture/memoryと実価格で判定する。Arm系は既存amd64資源と一致しないため除外する。上表は設計上の候補条件で、実測済みの最低要件ではない。

### 起動前scriptの自動選定

[選定scriptと使用手順](../tools/web_lab_instance_selector/README.md)を作成した。EC2内のinstall.shより前に学生PC/CloudShell側で実行し、選定結果をCloudFormationへ渡す。AWS資源を変更しない読取り専用selectorで、実配備wrapperとの組込み・AWS実機受入は未実施。

1. DescribeAvailabilityZones、DescribeInstanceTypesで利用可能な通常AZとT系micro/small/mediumを収集し、x86_64/HVM/EBSと上表の性能条件を確認する。
2. DescribeInstanceTypeOfferingsをAZ単位で照会し、同じfamilyの3サイズが同じAZに揃う候補を作る。regionだけの提供状況で判断しない。[提供状況API](https://docs.aws.amazon.com/cli/latest/reference/ec2/describe-instance-type-offerings.html)
3. AWS Price Listのregion別Linux/Shared/On-Demand毎時単価を取得し、medium×1＋small×3＋micro×1の5台合計で比較する。最安family/AZを選び、同額ならfamily/AZ ID等で決定的に選ぶ。価格のない候補を無視して「最安」とせず停止する。[価格検索API](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/using-price-list-query-api.html)
4. Pricing APIをLabで使えない場合は、教員が取得した同一region/USD・7日以内の価格台帳を使う。AZ提供状況はそのLabで新しく照会する。台帳の期限切れや価格欠品では世代順・T3固定へfallbackしない。
5. LabAvailabilityZoneとBastion/Web/Dns/Db/PackageInstanceType、価格根拠、次候補一覧を保存する。更新/停止再開は既存の実AZ/typeとの一致を確認して再利用し、価格が変わっても再選定しない。

Offeringは、その瞬間の空き容量やLabの起動許可を保証しない。初回配備wrapperは明確なInsufficientInstanceCapacityで失敗したfamily/AZを記録し、次候補のplanを得る設計とする。一部資源が作成済みなら自動削除/別AZへの追加をせず診断へ進み、整理後の初回再試行を通算最大3候補とする。Unauthorized/AccessDeniedだけではfamily拒否と断定せず、明示的に確認されたtype制限だけを除外条件にする。認証切れ・quota・AMI/設定・script失敗ではtypeを変更しない。詳細は[D08の失敗時の分岐](2026-10_web_infrastructure_bootstrap_contract.md)に従う。selectorは除外と候補出力まで実装済みで、起動エラー分類・配備再試行は制作の残件。

すでに一部EC2が作られた場合は、logと残資源を確認してから初回専用の再配置手順を適用する。単一AZを保つため、残ったEC2をそのままに別AZへ追加しない。既存の学生設定やDBを持つ環境を自動削除/移動する方式にはしない。

- rootはgp3、3000 IOPS・125 MiB/sを基本とし、追加性能を購入しない。各容量はAMIのroot最小容量以上であること。[gp3の仕様](https://docs.aws.amazon.com/ebs/latest/userguide/general-purpose.html)
- EBSは暗号化あり、AWS管理のaws/ebsを基本とする。独自KMS keyの共有を前提にしない。Labの暗号化/起動権限は実機確認し、失敗時に自動で暗号化を外さない。
- 選定したT系のCPU creditはstandardを明記する。Unlimitedの追加CPU credit料金を基本見積へ持ち込まず、familyごとのcredit枯渇時の性能と初期化時間を測る。性能不足ならtype/時間配分を再検討する。
- EC2の詳細monitoringは無効、IMDSv2必須、instance metadataのhop limitは1、hibernation・Spot・Auto Scalingは使わない。必要なsystemd serviceは再起動で戻る構成にする。
- 手動mount・追加data volume・swap構築を学生の必須課題にしない。受入時は空き容量20%以上かつ2 GiB以上。配布はbundle＋展開物＋APT cacheが一時的に共存してもこの条件を満たす。
- rootのDeleteOnTermination=true。通常停止では保持するが、最終削除ではrootも削除する。教材版更新のために学生EC2を自動置換しない。

## 学生と教員のAWS資源

| 所有/用途 | 資源と準備 |
| --- | --- |
| 各学生のStack | VPC1、subnet2、route table2、IGW1、役割別SG5＋Bootstrap SG1、S3 gateway endpoint1、EC2/EBS各5、WaitConditionの配布1件＋他4件とHandle。学生EIP/NAT/追加endpointなし |
| 教員の搬入元 | us-east-1のprivate S3 bucket、版固定prefix、全bundleとmanifest。Block Public Access有効、SSE-S3、署名付きGET URL。bucket作成は学生課題に含めない |
| 教員の採点入口 | D09採用構成の共通EC2＋EIP1＋Nginx HTTPS443。small/2 GiB以上・x86_64 T系の提供/価格を同様に比較し、root gp3 16 GiB、standard。学生用selectorの5台合計とは別に評価 |
| 教員の既存採点backend | 既存API Gateway/Lambda/DynamoDBを調査して接続。Web用API・token/ID対応はD11で実装 |

S3は現行releaseを授業期間中保持し、利用中prefixへ上書きしない。署名付きURLの期限と署名元credentialの有効期間を配備前に確認する。授業中のAPT先は10.20.2.30のまま。教員のS3/採点入口を、学生のEnd Labで停止される場所へ置かない。

教員の採点入口は、実domain・有効なCA証明書・固定上流を設定する。証明書はDNS認証を基本として学生向け80を追加せず、所有domainとDNS providerを確認して発行/更新手順を固定する。期限・更新担当・疎通確認を教員の配備記録へ残す。管理経路は教員の管理元だけへ制限し、学生向け443の採点APIと分離する。EIPを維持したままEC2を停止しても、EIPとEBSの費用は残る。

## 権限と配布前確認

学生Stackで新しいIAM user/roleを作らない。CloudFormationの実行は学生のLab認証を使用し、新しいservice role作成を必須にしない。EC2のinstance profileも原則不要とする。対象Labで既存profileが必要な場合だけ、指定済みLabInstanceProfile等の利用とiam:PassRoleを確認する。既存Linuxがprofileを使っていることをWebの必須条件へ自動転用しない。

SSHはLabごとに学生が作成/登録したEC2 key pair名を入力する。private keyをtemplate・UserData・配布bundleへ保存しない。RDP password hashは個別入力、DB password・Django SECRET_KEY・Lab採点tokenは共有bundleに含めない。採点token等は初回接続後に教員提供手順で個別設定し、D11の登録方式へ対応させる。

| 確認対象 | 必要な確認 | 合格の根拠 |
| --- | --- | --- |
| 読取り照会 | AZ、type offerings、AMI metadata、S3 prefix list、quota | 出力を匿名のLab検証記録へ保存 |
| CloudFormation | template検証、作成/変更セット/更新/削除、Events読取り | 実際の学生権限でpilot Stackを作成・更新できる |
| EC2/network | 5台/選定typeの合計vCPU、指定IP、key pair、EBS暗号化、SG/route/IGW/endpoint | 5台同時の作成と必要な操作が成功 |
| S3 | 教員bucketの署名付きGET、WaitCondition Put、endpoint policy | bootstrapでは成功、teachingでは拒否 |
| quota | RDP50 rule、ENIごとのSG2個、EC2/volume/endpoint数 | 現行Labの実quotaと5台起動が成立 |
| 運用 | Stop/Start、public IP確認、保護の有効化/解除、最終削除 | データ保持・通信閉鎖の維持・終了後の残資源確認 |

ValidateTemplateやDescribeの成功だけでは、実作成権限・容量を保証しない。新規pilotは初期化からteaching更新まで一続きで確認する。今回の調査では学生Labに対するこれらの実行結果は取得していない。

### 配布manifestへ固定する入力

region、AMI ID/owner/image名/初期一覧、LabごとのAZ、5台のtype/root容量、release/hash/template版、S3 prefix list ID、教員bucket/release prefix、採点受付IPv4/FQDN/URL、初期化timeout、RDP許可CIDRの確認日を記録する。Lab IDは匿名IDとし、学生の氏名やemailをAWS resource名へ直接使わない。

Stack名はjdu-web-<匿名LabID>を基本とし、タグCourse=cyber-security、Unit=web、LabId、Release、Roleを付ける。tagだけで本人確認・token認証を代用しない。

## 費用の参考概算

以下は自動選定へ変更する前のT3構成の参考試算として保持する。2026-10-15確認の公開単価を使い、Linux/Unix・us-east-1・On-Demand、t3.medium1＋t3.small3＋t3.micro1、gp3標準性能・96 GiB、public IPv4は起動中の2個を前提とする。自動選定後は保存した実単価とtypeで再計算する。無料枠・教育credit・割引は差し引かず、Lab残予算や実計上額ではない。

| 単価 | 参考値（USD） | 根拠 |
| --- | --- | --- |
| t3.micro / small / medium | 0.0104 / 0.0209 / 0.0418 毎時 | [T3のus-east-1価格表](https://aws.amazon.com/ec2/instance-types/t3/) |
| gp3容量 | 0.08 / GiB-month | [AWSのus-east-1比較表](https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-storage-compare-volume-types.html)、[EBS料金](https://aws.amazon.com/ebs/pricing/) |
| public IPv4 | 1個あたり0.005毎時 | [VPC料金](https://aws.amazon.com/vpc/pricing/) |
| S3 gateway endpoint | endpoint自体の追加料金なし | [AWS仕様](https://docs.aws.amazon.com/vpc/latest/privatelink/gateway-endpoints.html)。S3保存/要求等の費用は別 |

学生の5台分computeは0.1149/h、公開IPv4を加えると0.1249/h。96 GiBを1か月保持する容量費用は約7.68。停止しても容量費用は残る。

| 利用例（設計上の仮定） | compute＋IPv4 | EBSを1か月保持 | 小計 |
| --- | --- | --- | --- |
| 月40時間だけ5台を起動 | 約5.00 | 約7.68 | 約12.68 / 学生・月 |
| 月730時間の常時起動 | 約91.18 | 約7.68 | 約98.86 / 学生・月 |
| 教員の共通入口だけを730時間起動 | 約18.91（t3.small＋EIP1） | 約1.28（16 GiB） | 約20.19 / 教員共通・月 |

S3保存/GET、データ転送、既存API/Lambda/DynamoDB、DNS/domain、税等は上表に含めない。実授業の稼働時間、学生人数、残credit、資源の保持期間を入れた見積を配布前に確認する。教員共通入口の小計は既存採点backendを含む全体料金ではない。

毎回、Start Lab前後の残予算表示を確認し、予定残作業の概算＋余裕20%を下回る場合は教員が継続方法を判断する。自動で有料の個人accountへ移さない。授業終了時は全5台の停止を確認する。

## 新規構築から授業開始

1. 教員が先にbucket/release、固定採点受付、入力manifestとpilotを用意する。未確定IP/domainや署名付きURLで学生へ配らない。
2. 学生はStart Lab後、指定region・既存Stackの有無・残予算・key pairを確認する。既存Stackがある場合は新規作成を選ばない。
3. 初回だけDeploymentPhase=bootstrapでStackを作成する。RepoReadyのtimeoutは1800秒、他4台のAllNodesReadyは2700秒を上限案とし、実測後に確定する。最大待機時間と通常完了時間を混同しない。
4. 配布1件＋他4件の成功とrole別検査を確認する。5台の初期化は30分以内を検証目標とし、GUI/credit/展開時間を実測してD12の初回授業配分へ反映する。
5. 同じtemplate/資源IDを保持してteachingへ更新し、S3許可を閉鎖する。変更セットでEC2/EBSの置換がないことを確認する。
6. RDP/内部SSH/APT、採点登録と送信、S3/不要外部通信の拒否を確認し、授業開始可能とする。BIND/DB/アプリはこの時点で完成を要求しない。

配布成功後はStack termination protectionを有効にする案とし、学生が削除と停止を混同しない手順を付ける。Labで保護変更が許可されるか確認する。日常の更新でAMI/AZ/primary IPを変えず、既存の学生成果物を置換しない。

## 停止と再開

| 操作 | 手順と確認 |
| --- | --- |
| 授業終了 | 採点の送信済み/未送信を確認してアプリの書込みを終える。学生PCのAWS ConsoleでWebを通常停止し、DB/DNS/配布、最後に踏み台を停止。全5台がstoppedになったことを確認してEnd Labを行う |
| 次回開始 | Start Labで認証を更新し、同じStack/EC2を確認。配布・DNS・DBを起動し、続いてWeb・踏み台を起動する。必要serviceがreadyになるまで確認を待つ |
| 接続先 | 踏み台/Webの現在のpublic IPv4をEC2 Consoleで取得する。CloudFormationの以前のOutputsだけを正本にしない。private IPと内部DNS recordは変更しない |
| 再開検査 | teaching状態、S3閉鎖、RDP/SSH、配布、構築済みservice、登録済み備品を確認。未構築サービスは未完として扱う |
| 初期化script | stop/startで再導入や初期データ投入を行わない。破損時は診断を先にし、学生DBや設定を無断で初期化しない |

EBSの保持と自動public IPv4の変更は[AWSのstop/start仕様](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/how-ec2-instance-stop-start-works.html)に従う。End Labによる自動停止範囲・自動再起動・session期限は対象Labで確認し、全5台の手動確認を省略する根拠にしない。

## 失敗時と最終終了

初期構築失敗時はCloudFormationの成功資源保持を使う案とし、Events・cloud-init・role別logを確認してから再試行/更新/削除を判断する。保持した資源にも料金が発生するため、診断を終えた失敗環境を放置しない。[CloudFormationの失敗時保持](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stack-failure-options.html)

teaching更新失敗時は実際のegress/endpoint policyを確認し、rollbackでbootstrapに戻っていれば授業開始可能としない。WaitConditionの再作成・古い通知の再使用・EC2置換を通常再試行へ混ぜない。復旧不能を理由に既存Stackを自動削除しない。

単元終了時だけ、教員の終了指示と未送信結果の確認後、学生がtermination protectionを解除して対象Stackを削除する。rootもDeleteOnTerminationで削除し、残EC2/EBS/ENI/SG/endpoint等がないことを確認する。backup/snapshot取得や削除後の復元は課題にしない。教員共通bucket/受付/既存backendは学生Stackに含めず、学生の終了操作では削除しない。

## 実機で確認する受入

| ID | 確認 | 成功条件 |
| --- | --- | --- |
| AWS-01 | region/AZ/AMI/提供type/価格 | Canonical ownerとAMI metadataを確認し、x86_64 T系3サイズを単一AZで提供。価格が揃い5台合計最安を選定。欠品時に誤った最安を出さず、容量不足時の次候補と既存維持を確認 |
| AWS-02 | 学生権限とquota | 5台・暗号化root・SG/endpoint・通知を作成し、teaching更新まで成功 |
| AWS-03 | 初期化と性能 | GUI/browser/SSHが利用でき、OOMなし、credit枯渇を含む時間を記録。通常初期化30分目標とtimeoutを評価 |
| AWS-04 | 容量 | 全台の空き20%以上かつ2 GiB以上、配布の展開ピークも収容 |
| AWS-05 | stop/start | 同じprivate IP・設定・備品を保持し、public IP更新で再接続。初期化を繰り返さずS3閉鎖を維持 |
| AWS-06 | 初期化/更新失敗 | 診断logが残り、未完成/通信開放を成功扱いにせず、既存成果物を自動削除しない |
| AWS-07 | 料金とLab予算 | 実際の起動/停止状態と保持資源を照合し、見積・残予算・実計上の差を記録 |
| AWS-08 | 最終削除 | 対象学生Stackとroot等を削除し、教員共通資源は保持。不要な課金資源を残さない |

次はこの資源案でpilotの入力実値・Lab権限を確認し、D08のtemplate/script・依存収録を制作する。D08/D09/D10の通し受入後に配布版を固定し、D11の課題別判定へ展開する。AWS資源の作成、権限照会、起動・費用実測は今回行っていない。

## 関連設計

- [設計決定一覧と完了条件](2026-10_web_infrastructure_design_decision_register.md)
- [採用した通信と切替](2026-10_web_infrastructure_network_design.md)
- [パッケージ配布と初期化](2026-10_web_infrastructure_package_distribution_design.md)
- [サービスと接続設定](2026-10_web_infrastructure_service_design.md)
- [DBの保存と権限](2026-10_web_infrastructure_database_design.md)

仕様・公開単価の確認日: 2026-10-15。運用案の受入は対象Learner Labで別途行う。
