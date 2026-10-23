# Web単元の設計決定一覧と完了条件

10/22 D11訂正：[仕様v0.2](2026-10_web_infrastructure_d11_assessment_spec.md)に本人の実演不要・科目25点への換算は教師という決定を反映。v0.1の22自動＋3教師は撤回し、独立check各1点でM1～M6の62素点案へ変更。既存HTTP10検査を保持し準備2件を加点対象外とする。旧M7/教師点API/最高点必須機能は削除。詳細check・最新の評価可能な提出参照は提案。registry/素点表示/新checker/profile/対話型自動機能確認と実機受入は未実装。D08署名物/AWS/実成績は変更なし。

10/22最新：**D08の実装・別学生新規配備受入・初期環境の正式配布版r3まで完了。** 教師170/学生965でv7新規5台・停止再開・全17提出を受入後、core全byteを保持した外側r3を署名し、教師private S3へ保存/GET一致・両CloudShell署名/全file検証を完了した。D09/D10の実通信/資源/初期化/常設全台SSM/停止再開もその受入範囲に含む。正式な全課題/配点/残checkerはD11、完成DNS/DB/appの通し確認と教材は後続。distribution_ready=true、CLASS_READY=false。期限10/27 14:24:57 UZT。正本は[検証状況](../../../03_knowledge/aws_official/web_lab_ami_2026-10-15/verification_status.md)最上部、運用は[正式配布README](../tools/web_lab_distribution/README.md)。以下の表の実機未確認/未配布は旧時点の履歴として読む。

10/20最終受入：同じ新5台/元rootで署名c5-v6のテスト２候補受入が合格。常設全5台SSM・S3閉鎖・内部SSH/個別採点登録、基盤47/47・AWS29/29・全role/network、実課題13件/教師保存、空cache役割別導入・7wheel/WSGI起動、登録後停止再開/本人GUI/作業保持を確認。学生導入packageは初期状態へ復元済み。v4で新規作成後のv5/v6移行を検証した範囲で、v6 cold CreateStack/別学生accountは未検証。本人指定の別学生Lab [193548]を次に確認する。正式学生配布/D08全体/CLASS_READYは保留。詳細は[最新検証状況](../../../03_knowledge/aws_official/web_lab_ami_2026-10-15/verification_status.md)冒頭。以下の以前の未実装/待ち状態よりこの最終記録を優先。

10/20決定：本人指定でSSM管理対象を踏み台だけから学生5台すべてへ変更し、経路を常設する。CloudShell/ssm-user、既存2 private endpoint共用、全5台LabInstanceProfile、共有Windowsに秘密鍵を保存しない運用とする。踏み台から内部4台へのSSH演習は維持。c5-v5署名候補に同じ5台/元rootを移行し、S3閉鎖後もSSMを維持するAWS29項目・全role/network合格まで実確認。停止再開、実session、SSH鍵/個別採点登録、GUI等の未完了をD08の残件として管理し、CLASS_READYと混同しない。

更新: 2026-10-15（Asia/Tashkent）  
用途: 何をどこまで決めるかを先に定義し、この一覧を基準にチャットの次の議題を選ぶ。  
状態: 決定済み内容の照合と、未決項目・設計の完了条件を整理した進行案。未採用の案を決定済みとして扱わない。

## 1. 設計する範囲

対象は、各学生のAWS Academy Learner Labで動く5台の小さなWebシステムと、それを構築するP/M演習・自動判定である。学生はアプリコードを書かず、教員提供アプリを配置・接続する。Webシステムを構築して正常動作できることを到達点とする。backup/restoreは今回の課題・採点対象外。

システム設計では「何が動けば完成か」「誰が何を用意するか」「各サービスを何でどう接続するか」「初期環境から再現できるか」を、実装担当が判断に迷わない粒度まで決める。演習・採点設計はその完成状態と構築範囲から逆算する。

この一覧は、全設定fileを会話で一行ずつ決める要求ではない。名前・path・補助script等の実装上の選択はCodexが具体案を整合させて進める。アプリの機能、学生が構築する範囲、必須課題、採点対象など授業の目的・負担を変える事項はユーザーの決定と提案を区別する。

## 2. 項目と決める深さ

| ID | 決定項目 | 決める深さ・完了条件 | 現在の状態 |
| --- | --- | --- | --- |
| D01 | 目的・対象範囲 | 学生が何を作ればよいか、何を必須課題に含めるかが明記されている | Web構築と正常動作、アプリ開発なし、backup/restoreなしは確定。完成動作はD03。証明書・HTTPS追加はユーザー撤回済み |
| D02 | サーバー配置とIP | 5台の役割、subnet、IP、管理・閲覧・配布経路が一意に対応する | 単一VPC/AZ、公開2台・private3台、IP表は確定。実際のregion/AZはD10 |
| D03 | 完成アプリの機能 | 表示内容、利用者の操作、DBの読み書き、完成動作の確認方法が決まる | ユーザーの委任に基づきDjango備品カタログを選定。一般一覧、管理者ログイン・登録・編集、DB保存と公開画面反映、学生設定の5点を具体化。仕様はcatalog_app_specを参照。実装は未実施 |
| D04 | 教員の初期提供と学生の構築 | 各段階の開始時に存在するもの、学生が導入・変更するもの、配布資源が区別されている | ユーザーが分担案を了承。教員は開始できるAWS資源・踏み台・package配布・完成コード、学生は起動確認とDNS/DB/Webの導入・設定・連携。構築順・終了条件は下表。配備実装はD08/D10 |
| D05 | サービスと接続設定 | OS/architecture、runtime、Nginx→アプリ、起動user・service・port・file、SSH/RDP認証、秘密の渡し方が仕様化されている | service_designで具体化。Ubuntu24.04/amd64、Xfce/xrdp/Firefox、Python3.12/Django5.2/Gunicorn/psycopg3、専用catalog user・service・配置・設定fileを選定。依存/初期配備/AMI/実機はD08/D10の残件 |
| D06 | 内部DNS | zone/record、問い合わせclient、resolver設定、外部名の扱い、DNS構築前の導入経路が仕様化されている | dns_designで5条件を具体化。既存lab.testの6 A record、踏み台/Web→BIND、外部名はAWS DNSへforward only、初期APT/SSHはIP指定。通常resolver設定・拒否/再起動受入を定義。実機は未実施 |
| D07 | DBと必要な保存 | DB/table/架空データ、app roleの許可SQL、接続認証、データ保存先と必要容量が決まる | database_designで5条件を具体化。catalog_setupで初期作成後NOLOGIN、catalog_appはtable/列単位DML、Web/32だけSCRAM、標準保存先、DBルートgp3 16 GiBを設計値に選定。migration/grant/AMI容量と実機受入は未検証 |
| D08 | パッケージ配布 | OS/AMIと整合する本体・依存・browser・app資源、repo版/署名/保存先、初期配備方式が決まる | 1128 DEB/7wheel/app/checkerを収録・署名し、公式AMIからの実5台作成・閉鎖・全5台SSM・個別SSH/採点登録・offline役割導入・WSGI起動・停止再開保持をテスト２で受入。bytecode修正版c5-v6、基盤47/47/AWS29/29/実課題13件/3言語教師本人画面が合格。v6 cold createと別学生Lab [193548]の取得/配備/登録/送信は未検証、正式配布は保留 |
| D09 | 通信と管理 | inbound/egress、route、SG、公開範囲、採点/初期配備の追加通信が一組で再現できる | 10/15ユーザーが全台送信/route・初期化S3とteaching閉鎖・教員共通固定IP受付の構成を採用。network_designにNET-01〜10あり。受付/bucket等の実値・Lab権限/quota・実装/受入が残るため、採用と配布可能を区別 |
| D10 | AWS資源と運用 | region/AZ/AMI/type/EBS、権限、費用、初期構築・起動・停止・再開・終了処理を固定できる | us-east-1/単一AZ・公式AMI、medium1/small3/micro1・root計96 GiBを具体化。ユーザー指示でT3固定を廃し、同一AZで3サイズが揃うx86_64 T系の5台合計最安を起動前scriptで選定。読取りselectorと9件のlocal試験は作成/合格、CloudFormation組込み・AWS実値/権限/性能/費用実測は残件 |
| D11 | P/Mと自動判定 | 同じ技能・異なる対象の練習/課題、初期状態、合格条件、前提、教師進捗とシステム素点が対応し、科目25点への換算は教師が別に行う | 10/22本人訂正をv0.2/JSONへ反映。P0～P6/M0～M6、採点check各1点でMは計62素点案、準備/練習は成績合計外、M7実演なし。現P1/M1互換を保持。registry/素点表示/残checker/profile/対話型自動機能確認・実機受入は残件。詳細と提出回参照方針は提案 |
| D12 | 教材と配布 | 説明・手元手順・課題・図・言語・形式・学生入口・使用版を一致させる | 10/23本人指定でまずP/Mのみ。日本語原稿＋RU/UZ、P0-P6の49段階/M0-M6の固定62check、HTML/PDF6冊/zipを教材repo course/labsへ制作。正式署名r2と同期。母語校閲・教師確認・新しい教材の学生通し受入は未実施、CLASS_READY=false。独立教科書/投影資料は今回対象外 |

既存の構成図や一部原稿があることと、サービス設定・課題・実機動作が完成していることは別々に管理する。

## 3. 設計完了の判断

システム設計（D01〜D10）の完了は、次の情報が一組として揃い、実装の入力にできること。

1. 完成時の利用操作と期待結果（D03）。
2. 5台の役割・IP・通信・DNS・サービス・DB設定。
3. 教員の初期提供と学生の操作範囲、および完成までの順序。
4. 事前保存のpackageとapp資源で、DNS・Web・DBが未構築の状態から導入できる仕様。
5. AWS資源の選択と、新規構築・停止/再開の手順。
6. 正常経路の成功と不要経路の拒否を含む受入確認表。

AMI ID、packageの完全依存と厳密なversion、実費・起動性能、Lab権限などは、実機調査で確定する。候補値を書いただけでは確認済みとしない。授業版を固定するまでに、該当する値と検証結果を残す。

設計完了、コード実装完了、学生権限の実機受入、教材配布可能、は別の到達点とする。設計の未決事項がなくても実機確認前は「動作保証済み」と扱わない。

## 4. 次に決めることと順序

最新: D03〜D07は仕様具体化、D08は公式AMI＋CloudFormation＋install.sh、D09は初期化用S3/授業前閉鎖/固定採点受付を含む構成をユーザーが採用した。[D10の資源と運用](2026-10_web_infrastructure_aws_operations_design.md)でregion/type/容量・参考費用・権限確認・停止再開/終了手順を具体化した。D08〜D10はAMI実ID/受付/S3等の入力実値・Lab実権限・制作/実機受入が残る。次はpilot用入力を確定し、D08のtemplate/script・全依存収録を制作、通し受入へ進む。D11の詳細課題と採点は完成構成に合わせて作る。

### D08の配布入口と初期化処理の実装仕様

2026-10-15、T系/AZの自動選定後に次に決める内容を依頼された。D09/D10で通信・資源選定の方針が揃ったためD08へ戻る。既存の役割分担・配布URL・署名・初期化順を再決定せず、学生が起動する入口と制作物の対応を確定する。

| 今回詰める範囲 | 完了時に残すもの |
| --- | --- |
| 教員の事前準備 | 基準AMI照合→依存収録→署名→S3配置→受付設定の制作順、配布manifestと実値の確認担当 |
| 学生の起動入口 | セットアップcommand、学生入力と教員配布入力の区別、selector→CloudFormation→teaching更新の一続きの操作 |
| 初期化scriptの仕様 | 既存common/repo/bastion/student-base分担を実file・引数・入出力・実行順へ対応。課題サービスを完成させない |
| 起動失敗と再試行 | 容量不足/権限/quota/認証/初期化失敗の分類、候補除外、上限、成功済み資源と学生設定の保持 |
| 開始可能の表示 | 既存PKG/NET受入を実検査commandへ対応し、成功/未完/失敗と次の操作を表示 |

今回の設計完了条件は、実装担当が上記のfile・引数・順序・判定を迷わず制作できる仕様が揃うこと。AMI実ID・S3/採点受付等はAWS環境を確認して埋める。script制作、全依存収録、学生権限での新規起動/停止再開はその後の制作・受入であり、仕様化だけでD08全体を完了にしない。続く授業設計はD11のP/M・合格条件・配点、D12の授業構成/教材とする。

ユーザーが慎重な検討と進行を依頼したため、[D08初期化の実装仕様](2026-10_web_infrastructure_bootstrap_contract.md)を作成した。上記5点をcommand/file/引数/状態/失敗分岐へ具体化し、初期化成功と授業開始可能を分けた。hashの相互参照を避けるmanifest分割、lockでDeploymentPhase以外を変更しない条件、個別SSH/host確認と採点登録、作成済み資源を自動削除しない再試行を定義した。

その時点の到達点はD08の詳細設計。続く進行依頼に基づき、[manifest schemaと署名検証/読取りplan](../tools/web_lab_bootstrap/README.md)を制作し、local24試験に合格した。既存selectorの9試験も合格。署名/期限/hash/実行tool一致を確認し、planではAMI/公開鍵/既存Stack/S3 prefix list/template/AZ/type/価格を読取り照会する。学生の小さなtool archiveにはbundleを要求せず、配布EC2取得後の検証へ保留する。試験は使い捨て鍵と模擬AWSで、実照会/実配備は未実施。次はAMI/必要toolの実確認・依存収録・最小repo template/install処理へ進む。create/lock・採点の最小登録/認証疎通も未実装で、D08とD11の受入依存を残す。

### D09の決定範囲と検討結果

2026-10-15、残件の整理と次議題の選定を依頼されたため、CloudFormation＋install.shの成立に必要な通信条件を次の議題とする。5台/IP・アプリ機能・学生の構築範囲は既存仕様を使い、以下の5点まで決める。

| 決める項目 | 決める深さ |
| --- | --- |
| 5台の許可通信 | 接続元・宛先・protocol/port・目的・SG参照を、受信/送信と初期化中/授業中で対応させる |
| routeと初回搬入 | public/privateのroute、初期化用S3 endpointとpolicy、DNS未完成時の取得経路を定義する |
| 初期化から授業への切替 | 配布ready→他4台準備→全台確認→初期化用許可の閉鎖→授業開始の順、実行担当、失敗時の扱いを固定する |
| 教員採点受付への限定送信 | 固定受付の構築方式、実IP/domainを配布設定へ渡す方法、DNS未完成/送信失敗時の扱いを既存HTTPS＋Labトークン方針へ対応させる。未取得のIP/domainは作らない |
| 許可/拒否の受入 | 必要なAPT/管理/アプリ/採点通信は成立し、不要な外部通信・管理入口・DB接続等は拒否される確認表を作る |

D09の設計完了は、上記がCloudFormationの設定入力と切替手順に変換でき、未確定の実IP/domain・権限・quotaと担当先が明示されること。実値が未確定の箇所を含む状態では、AWS適用可能・授業開始可能とは扱わない。実権限・性能・費用の確認はD10、template/script制作と依存収録はD08/D10、課題別採点はD11へ対応させる。

残件の順序はD09→D10（権限の可否確認は先行）→D08の制作/受入→D11→D12を基本とする。初期環境・完成アプリ・checkerは未制作、AWS実機受入も未実施なので、設計済み項目を含め実装と検証は別に残る。

D09の今回の結果: 通信表、public/private route、初期化用S3の限定policy、DeploymentPhaseでの閉鎖、WaitConditionの1＋4件の完了待ち、教員共通EC2/EIPの受付案、10項目のNET受入を具体化した。受付実IP/domain・bucket・region別資源ID・Lab権限/quotaは未確定で、D09を完了扱いにはしない。通信案を入力にD10の実値と成立条件の確認へ進む。

その後、ユーザーが上記構成を了承しD10検討を指示した。D09は採用済みとして保持し、実値と受入はD10/D08へ対応させる。

### D10の決定範囲と検討結果

今回はregion/AZ/公式AMI、5台のtype/EBS、学生/教員の権限と入力、費用、起動/停止/再開/失敗/削除までを決める。資源案は[D10仕様](2026-10_web_infrastructure_aws_operations_design.md)を正本とする。

us-east-1を第一候補に単一AZ、Ubuntu24.04/amd64/Canonical公式AMIの実IDを版固定する。ユーザーがAZ/type不一致の過去エラーを指摘したため、T3固定を廃しmedium1・small3・micro1の区分を保つ。起動前scriptで提供AZ/architecture/性能と実価格を確認し、同一AZで3サイズが揃うx86_64 T系familyの5台合計最安を選ぶ。root gp3計96 GiB、credit standard、停止再開の既存AZ/type保持を維持する。先の12.68/20.19 USDはT3の参考試算であり、選定したtype/実単価で再計算する。

読取りselectorは[tools/web_lab_instance_selector](../tools/web_lab_instance_selector/README.md)へ作成し、9項目のlocal試験を確認した。価格不明・古い台帳では最安を推測せず停止し、容量不足時の候補除外/再選定と既存planの再利用を提供する。CloudFormationへ渡すparameterを出力するが、実配備・起動エラー分類/自動再試行・Lab実機はD08の残件。

AMI実ID、LabごとのAZ、S3/受付の実値、実権限と予算は未確定。AWS操作や権限検証は行っておらず、候補資源を配布可能な確定値とは扱わない。次はpilot入力・実権限を確認し、D08制作/受入へ戻る。

### D03で使用した決定範囲（記録）

この議題では、次の5点まで決めた。

- 題材と画面に表示する架空データ。
- 閲覧だけか、入力してDBへ保存する機能も持つか。
- WebがDBから取得／保存する内容。
- 完成を確認する操作と期待結果。
- 学生が設定する項目と、教員が配布するコード・データ。

当初の閲覧だけの案は置換済み。最新は管理者／一般入口を分離し、管理者が架空備品をDBへ登録して一般一覧へ反映するアプリ。ユーザーから機能・題材・設定範囲の選定を委任され、登録・編集・公開切替を備えた最小構成を選定した。削除等は機能に含めない。

その後はD04の初期状態と学生の構築範囲、D05〜D08のservice/DNS/DB/package、D09〜D10の残る通信・AWS条件へ進む。機能と環境仕様が揃った段階でD11のP/Mと自動判定を作り、D12へ展開する。AWSの権限・費用・GUI等の可用性確認は、設計を妨げる条件がないか早めに並行して調べる。

### D04の採用分担（2026-10-13ユーザー了承）

この議題では、共通AWS基盤と5台それぞれの授業開始状態、学生が導入・設定する範囲、構築順、段階終了時の確認までを決める。AMIの実値・全設定file・配布の具体的方式・配点はそれぞれD05/D08/D10/D11へ残す。

| 対象 | 教員が用意する開始状態 | 学生が行う作業 |
| --- | --- | --- |
| 共通AWS基盤 | VPC/subnet/route/SGと5台を指定構成で開始できる配布手順・資源。授業の開始状態では通信が成立 | 各自のLabで環境を起動し、台数・配置・IP・許可元を確認。今回の必須作業は配布手順での開始・確認までとし、白紙からの手作業再構築は要求しない |
| 踏み台 | GUI・RDP・browser・SSH clientを設定済み | RDPで接続し、各サーバーをSSH管理。DNS構築後に名前で接続 |
| パッケージ | 保存済み資源と署名付きAPT配布を稼働済み。他4台へAPT接続設定・署名検証用公開鍵を初期提供 | IP指定の配布先から取得し、導入結果を確認。配布サーバー自体の構築は必須課題にしない |
| DNS | UbuntuとSSH・基本確認toolのみ。BIND未導入 | BIND導入、zone/record設定、client側の名前解決設定・確認 |
| DB | UbuntuとSSH・基本確認toolのみ。PostgreSQL未導入 | PostgreSQL導入、DB/role/接続制限設定。table定義は教員提供migrationをWeb側から適用 |
| Web | UbuntuとSSH・基本確認toolのみ。Nginx・アプリは未稼働。完成コードと設定templateを配布 | Nginx/runtime導入、アプリ配置、DB接続・service・一般／管理入口・管理者ID設定、登録と表示の確認 |

採用する構築順と段階終了条件:

| 段階 | 終了時に確認できる結果 |
| --- | --- |
| 初期接続・package取得 | 5台の配置/IPを確認。RDP・内部SSHが成立し、授業BIND未完成でもIP指定のAPT取得が成功 |
| Nginx静的ページ | 学生PCからWeb公開IPv4のHTTP80で指定ページを表示 |
| DNS | BINDの設定検証と問い合わせが成功し、踏み台からweb/admin、Webからdbの内部名を解決 |
| DB | 指定DB/roleを作成し、Webから必要な認証で接続。許可対象外のDB接続を拒否 |
| アプリ連携と管理者登録 | 配布migrationを適用し、専用serviceでアプリ起動。管理者が登録し一般一覧・SQLへ同じ内容が反映 |
| 全体確認 | 一般／管理の許可・拒否、非公開備品、service起動、停止・再開後の正常動作を一続きで確認 |

P/Mの具体的な値と得点はD11で確定する。DB終了条件の一時的な接続確認と、アプリ連携後の最終DB権限はD07で対応させる。

ユーザーは「あなたの推奨案で問題ないです。次に進んでください」と了承した。分担と構築順を採用し、上記終了条件はその具体化として記録する。実際の配布資源の形式と初期配備方式・AWS権限はD08/D10で検証する。

### D07で使用した決定範囲と決める深さ

D07の決定範囲は、既存のPostgreSQL16系列・jdu_catalog/catalog_item・架空備品・catalog_appを維持し、以下を埋めること。[DB設計](2026-10_web_infrastructure_database_design.md)で具体化済み。以下は決定時に使用した完了条件の記録。

| D07の完了条件 | 次に決める詳細 |
| --- | --- |
| DB/table/架空データ | 既存アプリ仕様とmigrationを照合し、認証/session等の補助tableも対象にする |
| app roleの許可SQL | 通常実行に必要な権限をtableごとに定義し、DB全体の管理権限と区別 |
| 初期作成・更新 | migration用の権限、実行担当、通常運用への切替手順 |
| 接続認証 | Webのみの接続許可に対応するDB待受・認証・接続元/DB/roleの条件 |
| 保存先と必要容量 | DBの配置・必要EBS容量の基準、停止・再開での維持を定義。実測とEBS実値はD10 |

D07の受入は、正しいWeb接続で必要な読み書きが成功し、不要な権限・接続を拒否し、migrationから通常実行への切替後もアプリが動くことを確認する。SQL設定の記載だけで実機合格とは扱わない。採点受付の固定IP/domain等はD09/D11の残件として保持し、D07の完了条件へ混ぜない。

## 5. このチャットでの進行ルール

D08の完了を、収録範囲の名前を列挙しただけで判定しない。完全な版/hashのmanifestと新規Labでの導入結果が必要。D08はD10のAMI/権限に依存するため、設計議題の順番と実収録・実機受入の完了順は同一にしない。

- 各議題の開始時に、この一覧のID、決める範囲、依存する項目を示す。
- 議題終了時に、ユーザー決定、Codexの具体化、提案、未確認を記録する。
- 決定済みの項目は、必要な変更理由が生じた場合に更新する。
- 残件が依存する項目を基準に次の議題を選ぶ。直前に話題になった技術だけを理由に設計範囲を広げない。
- 技術の変更案は、D01のWeb構築という目的と学生負担への影響を確認する。backup/restoreを必須へ戻さない。

## 6. 正本への入口

- [システムの棚卸しと決定内容](../lesson_plans/2026-10-13_web_infrastructure_final_system_inventory.md)
- [現行ネットワーク設計](2026-10_web_infrastructure_network_design.md)
- [サービスと接続設定](2026-10_web_infrastructure_service_design.md)
- [内部DNS設計と完了条件](2026-10_web_infrastructure_dns_design.md)
- [DBの接続認証・権限・保存先](2026-10_web_infrastructure_database_design.md)
- [保存済みパッケージと初期配備](2026-10_web_infrastructure_package_distribution_design.md)
- [起動入口・role script・失敗時処理と準備判定](2026-10_web_infrastructure_bootstrap_contract.md)
- [採用した採点集約と限定送信の設計](2026-10_web_infrastructure_grading_transport_design.md)
- [AWS資源・費用・停止再開と終了](2026-10_web_infrastructure_aws_operations_design.md)
- [P/M採点設計案](../lesson_plans/2026-10-13_web_infrastructure_exercises_and_autograding_design.md)
- [教材の現在地](../lesson_plans/2026-10-13_web_infrastructure_status_and_next_steps.md)

本一覧の作成前は既存記録に基づいて構成・IP・許可範囲を順に整理していたが、全決定項目と決める深さの一覧を先に固定していたわけではない。今回その不足を補い、以後の判断基準とする。
