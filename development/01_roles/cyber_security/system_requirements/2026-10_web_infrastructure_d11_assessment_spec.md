# D11：Web課題・合格条件・システム素点の仕様

更新: 2026-10-23（Asia/Tashkent）。**v0.2。本人実演なし・システム側は25点に制限せず、科目の25点への換算は教師が行う**という本人の訂正を反映。v0.1の「自動22点＋本人実演3点」と、検査を25個の採点群へ圧縮する案は撤回する。

10/22に本人が62素点方式での実装・検証を承認し、10/23に実AWSで全6課題62/62・教師画面/原本照合を合格。検証Labは実成績から除外し、正式D11学生入口/配布とD12を次工程とする。受入の範囲と限界は[採点ツールの記録](../tools/web_lab_assessment/RESUME.md)を参照する。対応する[JSON契約](2026-10_web_infrastructure_d11_assessment_contract.json)と[静的照合結果](2026-10_web_infrastructure_d11_validation.public.json)を同時に管理する。D08の正式配布物・既存5台/SSH/RDP/採点認証を保持する。

## 1. 方式を見直した根拠

現行Webのhttp_task.pyはP1/M1を同じ10個のcheck IDで検査し、progress_api.pyはPASS件数・全件数・UNKNOWN件数、提出原本と課題ごとの最新結果を保存する。重み付き科目点、課題全体の正式registry、最高点の自動採用は実装されていない。OS-Linux-Controlの現行progress_app.pyも課題ごとのpassed/totalを保存・表示している。

統合科目のassessment-policy.mdは、分野ごとの素点合計を後で25点へ換算する方針である。前案の25点固定はこの換算を早すぎる段階で行っていた。今回、**独立した採点checkのPASSを1素点**として数え、必要なcheck集合から満点を決める。100点など別の目標満点にも合わせない。

| 自力課題 | 到達状態 | 素点満点案 |
| --- | --- | ---: |
| M1 | HTTP | 8 |
| M2 | 内部DNS | 13 |
| M3 | 保存と停止再開 | 3 |
| M4 | PostgreSQL基盤 | 9 |
| M5 | アプリ連携 | 13 |
| M6 | 公開範囲と実効権限 | 16 |
| **合計** | **全て自動確認対象。教師の実演点なし** | **62** |

この62点は配分枠ではなく、下記の独立した採点checkの合計である。実機受入で観測不能・重複と分かったcheckは、仕様版を更新して分母も改める。未実装項目を分母から黙って外し、完成授業の満点として表示しない。

P0～P6は手順付き練習、M0は準備、M1～M6が自力課題。旧M7の本人実演・構成説明・口頭確認の採点は削除する。WEB-08/09の観測や構成理解は教材と各課題の再確認で扱い、別の必須実演や手動採点へ置き換えない。本人の理解やbrowser操作経路を自動検査で証明したとも書かない。

## 2. 数えるもの・数えないもの

- 各checkはPASS=1点、観測できたFAIL=0点。上位の合成判定や同じ検査の再実行で追加点を作らない。1つの確認対象に複数の期待値がある場合は、全部満たしてその1点とする。
- 提供済みVPC/EC2/volume容量/SG/SSM/repo、accountと登録IDの一致は準備確認で0点。学生が自動提供資源を独力で作ったという加点をしない。
- Pにも対応するcheckの成功件数と時刻を残す。Pは練習の達成表示で、Mの素点合計へ重ねて加えない案。P未提出を理由にMを禁止せず、必要機能を現在の環境で確認する。
- 後続課題が前のHTTP/DNS/DBを再確認しても、その前提検査には再加点しない。例：M4のSQL接続とM5のアプリ実接続は別の到達状態だが、M5でM4の点も再度加えない。
- UNKNOWN、前提未完了、送信待ち、未提出、NOT_APPLICABLEを自動で0点またはPASSにしない。期待集合と固定分母は保持する。例：5 PASS/2 FAIL/1 UNKNOWNは「暫定5/8・未判定1」で、確定5点にしない。

M1は既存10検査のうち、IDENTITYとREPO_PREREQUISITEを0点の準備確認、残る8検査を各1点とする。**元の「検査2/10」は準備だけの成功なので「素点0/8」**となる。既存10 ID・file/path/本文・v1提出原本を変えず、正式registryの採点対象一覧で区別する。

全合格は同じ確認回で必要な準備が整い、全採点checkがPASSであること。部分点は残すが、部分点取得を全機能完成と表示しない。科目全体の合格点、締切、換算と丸めは教師が成績を付ける段階で決める。

## 3. 提出回と教師の進捗確認

既存実装に合わせ、**締切時点で教師へ保存済みの最新の評価可能な1回をMごとに参照する案**とする。v0.1の最高点自動採用は必須要件から外す。再提出は何度でも可能。異なる回の成功checkを寄せ集めて満点にしない。課題ごとの選択回・日時・仕様版・Lab/Deploymentを残し、教師は履歴を確認して最終確定する。

新しい結果がUNKNOWN等を含む場合は現在状態を「確認不能/暫定」と表示し、直前の評価可能な回を勝手に0点へ置換しない。新しい評価可能なFAILはその回の部分点として扱う。旧回の得点を表示する場合は、その日時と「現在状態とは別の参照値」を明示する。Mごとの得点合計は、全サービスが同時に正常だった証明ではない。完成確認は同じ実行期間に前提も再確認する。

教師画面/出力は匿名Lab ID、課題別の素点/固定満点、PASS/FAIL/UNKNOWN、未提出、最新日時、参照提出ID、送信状態を持つ。Pと準備結果はM合計へ入れない。提出がある課題だけを分母にして満点を作らず、未提出は空欄と件数で示す。締切後の未提出の成績処理は教師が行う。教師の成績表へ素点と満点を渡し、システムで25点への圧縮をしない。

`--no-submit`は自己確認。保存受領がなければ成績参照へ入れず、同じrequest/bodyで再送する。旧D08の17件や検証用Labの結果を実学生の成績へ自動変換しない。

## 4. 初期状態・練習と自力課題の対象

初期提供は同じ5台。全台のSSMを常設し、CloudShellから各台へssm-userで管理できる。内部SSH鍵は踏み台内だけで扱い、共有Windowsへ出さない。RDPは50 CIDR制限とpassword認証、一般HTTPは80、管理はprivate8080、アプリはloopback8000のまま。

| 組 | Pの対象 | Mの対象 |
| --- | --- | --- |
| 0 | 手順付きでhost/userと踏み台/Webを確認 | M0で登録5 roleの実資源/経路を確認。0点 |
| 1 | /var/www/html/practice.txt、/practice.txt | /var/www/html/mission.txt、/mission.txt |
| 2 | guide.lab.test→10.20.1.20、practice-db.lab.test→10.20.2.20 | lab.testの既定6 A record |
| 3 | /var/lib/jdu-web/practice/storage.txt | /var/lib/jdu-web/mission/storage.txt |
| 4 | jdu_catalog_practice、catalog_practice_setup/catalog_practice_app | jdu_catalog、catalog_setup/catalog_app |
| 5/6 | practice DB/profile、practice_admin、P5用備品 | mission DB/profile、lab_admin、M5用備品 |

P1本文は`JDU WEB-02 practice: HTTP response verified.\n`、M1は`JDU WEB-02 mission: independent HTTP delivery.\n`（末尾LF）。JSONの既存期待値を維持する。P2は現在のP1、M2は現在のM1のfileを使う。M2のA recordはbastion=10.20.1.10、web/admin=10.20.1.20、dns=10.20.2.10、db=10.20.2.20、repo=10.20.2.30。Pの追加名を許すが、PだけでMを完成扱いしない。

推奨順はP0/M0→P1/M1→P2/M2→P3/M3→P4/M4→P5→P6→M5→M6。MはPを省略して進められる。P4はIPでDB接続、M4は現在のM2による通常DNS接続。P5にはM2/P4、M5にはM2/M4、P6にはP5、M6にはM5の現在機能が必要。Storageの時期は調整できる。

P5/P6を同じpractice profileで終えてから、同じservice/配置先/portをmission profileへ切り替える。練習DBは残す。checkerがprofileを自動変更しない。Mへ移行後のP5/P6は過去の練習記録として表示し、現在の不合格や自動巻戻しにしない。**practice/missionの設定・SQL/helper対応はローカル実装済み。実PostgreSQL/Nginx/Gunicornで練習と本課題の分離を確認した。AWSの同じ5台での通し受入は未完了。**

アプリの指定備品は次の部分集合。DEMOや自動確認用など他の正当なrecordを許し、idの連番やtable全体の一致を要求しない。

| 対象 | code | name | quantity | location | 公開 |
| --- | --- | --- | ---: | --- | --- |
| P5 | P5-PUBLIC-001 | Practice keyboard | 4 | Training shelf A | true |
| P5 | P5-PRIVATE-001 | Practice mouse | 2 | Training shelf B | false |
| M5 | M5-PUBLIC-001 | Mission monitor | 6 | Lab cabinet C | true |
| M5 | M5-PRIVATE-001 | Mission router | 1 | Lab cabinet D | false |

## 5. 自力課題の採点check

各表の1行が1素点。Pは同じ種類を別の対象値で観測する。新しい固定registry/checkerは別の署名候補に収録する。既存D08 commandへ新規IDを渡して動作するとは案内しない。

### M1：HTTP（8点）

repoと管理経路が使え、Nginx/指定fileは未導入から開始。学生が内部APTで導入し、起動・設定・file配信を行う。既存10検査のうち採点対象8件は次のとおり。

| check ID（各1点） | 確認対象 | PASS条件 |
| --- | --- | --- |
| WEB02_NGINX_ACTIVE | Nginx起動 | 既存checkerでnginxのactiveを確認。 |
| WEB02_CONFIG_VALID | Nginx構文 | 既存checkerでnginx -tが成功。 |
| WEB02_LISTEN_80 | 80番待受 | 既存checkerでprivate/all-interfaceの80番待受を確認。 |
| WEB02_FILE | 配信file | 既存checkerどおり指定本文・通常file・root所有・0644を確認。 |
| WEB02_LOCAL_HTTP | Web自身のHTTP | 既存checkerでloopbackの200と本文完全一致。 |
| WEB02_BASTION_HTTP | 踏み台からHTTP | 既存checkerでprivate IP経由の200と本文完全一致。 |
| WEB02_PUBLIC_HTTP | 外部からHTTP | 既存checkerでCloudShellからpublic IP経由の200と本文完全一致。 |
| WEB02_ACCESS_LOG | 要求とlog | 既存checkerで今回のnonce付き要求がaccess logに残る。 |

IDENTITY/REPO_PREREQUISITEは0点の前提。アプリ導入後も/practice.txtと/mission.txtをNginxの静的経路として保つ教員template対応が必要。

### M2：内部DNS（13点）

BIND未導入・OS resolverはAWS初期設定から開始。学生がBIND/zone/通常resolverを設定する。digで問い合わせ先を明示した成功だけでは完成にしない。

| check ID（各1点） | 確認対象 | PASS条件 |
| --- | --- | --- |
| WEB03_SERVICE | BIND起動 | BINDがactiveである。 |
| WEB03_CONFIG_VALID | DNS構文 | named設定とlab.test zoneの構文検査が成功する。 |
| WEB03_ZONE_AUTHORITY | 権威zone | lab.testのSOA/NSと権威応答が設計と一致する。 |
| WEB03_REQUIRED_RECORDS | 必要なA record | P/M別の必須record全件が期待private IPを返す。6名を6点へ水増ししない。追加の正当な練習名を許す。 |
| WEB03_UDP_RESPONSE | UDP応答 | 踏み台・Webの両方からUDP53で必要な回答が得られる。 |
| WEB03_TCP_RESPONSE | TCP応答 | 踏み台・Webの両方からTCP53で必要な回答が得られる。 |
| WEB03_NORMAL_RESOLVER | 通常resolver | 踏み台/Webの通常resolverがBINDだけを使い、対象名をhostsやbrowser DoHで代用しない。 |
| WEB03_NAMED_HTTP | 名前によるHTTP | 踏み台の通常resolverを使い、P/M別host名と既存HTTP fileで200/正しい本文を確認する。 |
| WEB03_DB_NAME | DB名の通常解決 | Webの通常resolverでP/M別DB名が10.20.2.20になる。 |
| WEB03_FORWARD_ONLY | 外部名の転送 | forward only/転送先10.20.0.2の実効設定と外部名解決を確認する。外部Web接続成功は要求しない。 |
| WEB03_NXDOMAIN | 未登録名 | その回で作る未登録lab.test名に権威NXDOMAINが返る。 |
| WEB03_CLIENT_ACL | 問い合わせ制限 | BINDのquery/recursion/cache ACLがlocalhost・踏み台・Webのみを許す実効設定になっている。SGだけの遮断でBIND ACLの実証としない。 |
| WEB03_AXFR_DENIED | zone転送拒否 | 通常問い合わせが同じ回に成功する踏み台/WebからAXFRが明示拒否される。timeoutだけではPASSにしない。 |

DNS停止やcache削除をcheckerが自動実行しない。DNS/DB/repo自身のOS resolverはAWSを維持し、学生PCのDNS変更は不要。外部名の上流を観測できない時はUNKNOWNとする。

### M3：保存と停止再開（3点）

既存Web root上に学生がmarkerを作る。UTF-8/LFで`lab_id=<匿名Lab ID>\ntask=M3\npayload=mission-storage-2026\n`。P3はtask=P3/payload=practice-storage-2026。提供済みvolumeの対応・空き20%以上かつ2GiB以上は0点の前提。

| check ID（各1点） | 確認対象 | PASS条件 |
| --- | --- | --- |
| WEB04_MARKER_CONTENT | 保存内容 | 学生が作ったP/M別markerのpath・匿名Lab ID・task・本文が一致する。 |
| WEB04_MARKER_PERMISSIONS | 保存fileの権限 | markerはroot:root/0644、親directoryは0755である。 |
| WEB04_STOP_START_RETENTION | 停止再開後の保持 | 同じ配備の停止前/停止状態/再開後の証跡で、元instance/volumeとmarker hashが同じ、boot IDが変化したことを確認。単なるrebootや旧fixture記録では代用しない。 |

checkerはmarkerを作らず、停止・再開もしない。停止前の準備証跡だけでは保持をPASSにしない。本人の明示的停止操作と、CloudShell側で停止状態を観測した証跡を残すhelperが必要。P/Mのmarkerを先に用意すれば一回の停止再開を共有できる。追加EBS/mount/backup/restoreは課さない。

### M4：PostgreSQL基盤（9点）

DB package未導入から、16/main・DB/2 role・接続認証を学生が用意する。この段階でアプリ11tableは不要。

| check ID（各1点） | 確認対象 | PASS条件 |
| --- | --- | --- |
| WEB05_CLUSTER_ACTIVE | DB起動 | PostgreSQL16/mainがactiveである。 |
| WEB05_CLUSTER_CONFIG | cluster設定 | 16/mainの設定・標準data directory・postgres/socket peer管理が妥当である。 |
| WEB05_LISTEN_5432 | DB待受 | 10.20.2.20:5432で待ち受ける。 |
| WEB05_DATABASE_OWNER | DBとschemaの所有者 | P/M別DBとpublic schemaのownerが対応するsetup roleである。 |
| WEB05_ROLE_ATTRIBUTES | DB role | 対応runtime roleはLOGIN。両roleにsuperuser/CREATEDB/CREATEROLE/REPLICATION/BYPASSRLSや昇格membershipがない。setupは構築中LOGIN/完成後NOLOGINの両段階を認める。 |
| WEB05_HBA_SCRAM | 接続認証規則 | pg_hbaはWeb /32・列挙したprofile DB/roleだけにSCRAMを許可し、それ以外の広い許可がない。 |
| WEB05_WEB_SQL | Webの認証SQL | Pはprivate IP、Mは通常DNS名からruntime roleで新規認証接続し、current_database/current_user/SELECT結果が一致する。 |
| WEB05_BAD_PASSWORD_DENIED | 誤password拒否 | 同じ回の正規接続を対照に、1回の誤password接続が明示認証拒否される。秘密値やhashは返さない。 |
| WEB05_WRONG_TARGET_DENIED | 他DB/管理role拒否 | Webからpostgres role・許可外DB・他profileへの接続をHBA等で明示拒否する。未作成practice DB自体は必須にしない。 |

通常roleの接続秘密はWeb内の/etc/jdu-web/db-practice.runtime.envまたはdb-mission.runtime.envへ本人の非表示入力で保存するhelper案。root:root0600とし、CloudShell引数・SSM Run Command本文・結果へ秘密を載せない。setup用passwordを混ぜず、M5後は対象app.envとの一致を確認する。helperは未実装。DBのdata directoryは/var/lib/postgresql/16/main、postgres0700を維持する。

### M5：アプリ連携（13点）

学生は教員コード・venv・systemd/Nginx template・設定helperを使って配置/接続する。アプリのプログラミングは不要。起動とデータの存在だけで、ログイン・書込み・ログアウトの動作をPASSにしない。

| check ID（各1点） | 確認対象 | PASS条件 |
| --- | --- | --- |
| WEB06_ARTIFACTS | アプリ資源 | 教員配布コード・依存・固定版が一致する。学生はアプリコードを書かない。 |
| WEB06_SERVICE | アプリservice | systemd serviceがactive/enabledで、設計の専用catalog userで起動する。 |
| WEB06_LOOPBACK | 内部アプリ待受 | Gunicornが127.0.0.1:8000のみで待ち受ける。 |
| WEB06_PROFILE_DATABASE | アプリDB接続 | app.envと実接続が選択profileのDB/runtime roleを通常DNSで使う。M4の単体SQL接続とは別にアプリ実接続を確認。 |
| WEB06_MIGRATIONS | tableとmigration | 教員固定migrationと11table/必要sequenceが対象DBに揃う。 |
| WEB06_REQUIRED_RECORDS | 指定備品の保存 | P/M別の指定2件が対象DBに期待値で保存される。必須部分集合として照合する。 |
| WEB06_PUBLIC_DATA | 一般画面のDB反映 | 一般80のHTTP200と公開対象の値がDBと一致する。固定HTMLのみではPASSにしない。 |
| WEB06_ADMIN_ENTRY | 管理入口 | 通常DNSのadmin.lab.test:8080/admin/に踏み台から到達し、正しいログイン画面が返る。 |
| WEB06_STATIC | 静的資源 | 一般/管理画面に必要なCSS等が正しい入口から取得でき、Content-Typeも妥当である。 |
| WEB06_PASSWORD_LOGIN | 実認証ログイン | 対話型自動確認で実passwordと正しいCSRF/session処理によって対象staffとしてHTTPログインする。force_loginやsession直書きを使わない。 |
| WEB06_CREATE_REFLECT | 新規登録と反映 | 同じ自動確認回で専用nonceの架空備品1件を管理HTTPから登録し、PostgreSQLと一般画面の値が一致する。 |
| WEB06_EDIT_REFLECT | 編集と反映 | その回にchecker自身が作った専用備品だけの数量を変更し、DBと一般画面の更新が一致する。 |
| WEB06_LOGOUT | ログアウト | 同じsessionをPOSTでログアウトし、そのcookieを再使用しても管理画面は再認証を要求する。 |

最初の9件は主に配置/接続/既存状態、最後の4件は次節の対話型自動確認を必要とする。完成コードのローカルfixture test成功を、その学生Labの実HTTP成功へ流用しない。一般画面で非公開情報を出さないことはM6、初期化roleの終了もM6でそれぞれ一度だけ加点する。

### M6：公開範囲と実効権限（16点）

安全な提供済みSGをわざと広げる課題は作らない。学生が構築したNginx/OS file/DB/appの制限を確認する。外部8080/8000不可や全5台SSM/RDP制限等の提供済み境界は0点の準備確認。M5のloopback待受にも重ねて点を付けない。

| check ID（各1点） | 確認対象 | PASS条件 |
| --- | --- | --- |
| WEB07_PUBLIC_ADMIN_DENIED | 一般入口の管理拒否 | 公開80の/adminおよび配下・表記揺れがNginx/アプリで拒否され、偽装headerでも管理画面を返さない。 |
| WEB07_SECRET_PERMISSIONS | 秘密fileの権限 | app.env/有効runtime秘密fileはroot:root0600、linkではなく、catalog等から読取り不可。内容は送信しない。 |
| WEB07_CODE_PROTECTED | コード保護 | 実行catalog userはコード/venv/親directoryを改変できず、非login・非sudoである。 |
| WEB07_SECRET_HTTP_DENIED | 秘密のHTTP非公開 | 秘密をstatic/public配下へ置かず、固定した秘密path候補を一般HTTPで取得できない。 |
| WEB07_SETUP_RETIRED | 初期化権限の終了 | 対応setup roleはNOLOGIN/password NULL/既存sessionなし。一時setup.envも終了している。 |
| WEB07_ITEM_PRIVILEGES | 備品tableの実効権限 | catalog_itemはSELECT/INSERT/UPDATEのみ。DELETE・権限委譲を許さない。所有者/PUBLIC/membership経由も含める。 |
| WEB07_AUTH_USER_PRIVILEGES | 認証tableの列権限 | auth_userはSELECTとUPDATE(last_login,password)のみ。属性変更・table全体UPDATE/INSERT/DELETEを許さない。 |
| WEB07_AUTH_LOOKUP_PRIVILEGES | 認証参照の権限 | auth_group/auth_permission/関連中間table/content_typeはSELECTのみ。 |
| WEB07_SESSION_PRIVILEGES | sessionの権限 | django_sessionはSELECT/INSERT/UPDATE/DELETEのみを許す。必要なDELETEを一律禁止しない。 |
| WEB07_AUDIT_PRIVILEGES | 管理logの権限 | django_admin_logはSELECT/INSERTのみ。UPDATE/DELETEを許さない。 |
| WEB07_MIGRATION_PRIVILEGES | schema/migrationの保護 | runtimeはdjango_migrations権限・schema CREATE・アプリobject所有権を持たず、既定外の実効許可もない。 |
| WEB07_SEQUENCE_PRIVILEGES | sequenceの実効権限 | 必要な備品/admin log ID sequenceはUSAGEだけ。他の過剰権限とsetvalを許すUPDATEがない。nextval/setvalを実行して試さない。 |
| WEB07_ADMIN_PERMISSIONS | アプリ管理者の範囲 | 対象管理者はstaffかつ非superuser、備品view/add/changeのみ。削除・user/group管理権限やrouteがない。 |
| WEB07_ANONYMOUS_DENIED | 匿名更新の拒否 | 正規routeと妥当なCSRF条件で匿名の登録/編集を試し、認証を要求して対象DBを書き換えない。同じ回の正規ログイン/登録成功を対照にする。 |
| WEB07_BAD_PASSWORD_DENIED | アプリ誤認証の拒否 | 正規認証の成功を対照に、1回の誤passwordで認証sessionが成立しない。既存passwordの変更や総当たりはしない。 |
| WEB07_PRIVATE_DATA_HIDDEN | 非公開備品の保護 | 対象DBの非公開備品が一般画面へ出ず、公開備品は同じ回に表示される。 |

権限は所有者、PUBLIC、継承membership、列権限、grant optionを含めて実効状態を照合する。拒否は正規動作との対照が必要。匿名拒否・誤認証拒否は同じ自動確認回の実ログイン/登録成功を伴わせる。CSRF不足の403だけで認可成功としない。

## 6. 本人実演を使わないアプリの動作確認

これは**学生が起動する自動検査の設計**で、教師立会い・画面共有・口頭説明・実演点を要求しない。通常の読取り確認と、データを作る機能確認モードを区別する。採点を実装する段階で、実行前に副作用を短く表示する。

1. CloudShellから踏み台の対話SSM端末を開く。学生が既存の対象アプリ管理者passwordを非表示で1回入力する。秘密をSSMコマンド本文/引数/履歴/観測JSONへ含めず、踏み台の検査processのメモリー内だけで使う。新しい共通passwordや検査用管理者を作らない。
2. 自動処理が実際のadmin.lab.test:8080へ通常DNS/HTTPで接続し、CSRF/cookieを扱ってログインする。Djangoのforce_login、DBのsession直接作成、password変更で認証を迂回しない。
3. `CK-<P又はM>-<12桁nonce>`の架空備品を1件だけ作り、DBと公開画面を照合。その同じ1件の数量だけを更新して再照合する。既存の学生備品や指定2件を書き換えず、確認用備品は残す。session、管理log、採番sequenceが変化することは想定する。
4. M6では正規成功を対照に匿名の登録/編集と誤passwordを各限定回数で試す。拒否側でDB変更を認めない。最後にログアウトし、元cookieで管理画面へ戻れないことを確認する。秘密/cookie/HTTP本文を教師結果へ送信しない。
5. 同一Lab/Deployment/profile/確認回nonceと固定check集合を照合し、真偽だけを通常の提出結果へまとめる。過去の機能確認を新しい読取り検査へ継ぎ足して満点にしない。

上の対話・実HTTP・DB照合のコードは**ローカル実装済み、AWS統合受入は未完了**。10/23に実Nginx/Gunicorn/PostgreSQLの両profileでpasswordログイン、専用架空備品の登録/編集、拒否、logoutとDB分離を確認した。固定fixture passwordやローカルの結果を学生Labの合格へ流用しない。

password入力なしの読取り確認だけなら、M5の4機能checkと、M6の正規認証を対照にする拒否checkはUNKNOWN。DBに備品があるだけで新規登録のHTTP経路や本人による入力を証明したことにしない。秘密入力が必要なのは自動検査の認証のためであり、本人実演を復活させる条件ではない。

## 7. 観測・保存・実装の境界

提出は固定課題ID/仕様ID・hash/check集合/role/実instanceと照合する。欠落・重複・余分・未知ID・他の配備を拒否し、学生が送るpointsや都合のよい少数checkを信用しない。すべての課題を固定registryへ登録し、システム側で採点対象PASSを数える。各報告は現APIの100 check上限内に収める。

通常checkerは構成変更、package導入、SG緩和、DNS停止、profile切替、OS再起動をしない。対話型機能確認だけが前節の専用record/sessionへ限定して変更する。秘密値、password hash、cookie、env本文を結果に入れない。禁止SQLの確認は実効権限照会を優先し、既存行を変える検査を行わない。sequenceのnextval/setvalはrollbackでも進むため呼ばない。

timeoutは閉鎖成功の証明にしない。正常な対照、source/destination/port、rule/route/listen、拒否結果を合わせる。送信SGで先に遮断される経路では、宛先ACL単独の拒否を実証したと扱わない。採点のための新しいEC2/port/外向き通信許可は追加しない。

D08の既存dispatchはbootstrap/P1/M1を維持する。D11の別入口assessment_check.pyはP0〜P6/M0〜M6を固定registryに従って扱い、wire v2で新しい採点受付へ送る。JSON設計契約の版とwireの版は別に検証する。教師側のregistry/素点表示/参照回の集計/成績出力は10/23に更新完了を確認。新checker/practice profile/対話型機能確認はローカル受入済みだが、学生5台からの全AWS統合受入は未完了。v1原本と旧D08署名物を保持し、OS/Linuxのrepoや既存採点環境は変更しない。

## 8. 次の制作と受入

1. 既存P1/M1を使い、固定registry・採点8/準備2の区別・課題別素点と最新/未判定/履歴を実装。初期2/10→素点0/8、HTTP機能8件全PASS→8/8を確認する。手動採点APIや最高点機能を新たな必須条件にしない。
2. DNS→Storage→DB checker、停止状態の証跡、秘密入力helperを制作。未導入・Pだけ・誤設定・完成・観測障害を区別する。
3. app/helper/SQLのprofile対応、M1静的経路保持、対話型自動機能確認を制作。同じ5台でP5/P6→M5/M6を受入する。
4. 全6 Mの固定分母/未提出/未判定/再送/締切時の参照回と素点出力、個別Labとtest Labの分離を確認する。変更を新たに署名し、既存state/認証を保つ移行を受入する。
5. 問題文・教材・checker・教師画面・fixtureを同じ仕様版へ揃え、完成DNS/DB/appの通し受入とD12を仕上げる。

本書とJSONの整合確認は設計の検査であり、62点分の実機採点成功ではない。**D11実装と全授業のCLASS_READYは未完了/false。**

## 参照と確認範囲

- [P/M設計](../lesson_plans/2026-10-13_web_infrastructure_exercises_and_autograding_design.md)、[設計台帳](2026-10_web_infrastructure_design_decision_register.md)。
- [アプリ](2026-10_web_infrastructure_catalog_app_spec.md)、[DNS](2026-10_web_infrastructure_dns_design.md)、[DB](2026-10_web_infrastructure_database_design.md)、[サービス](2026-10_web_infrastructure_service_design.md)、[通信](2026-10_web_infrastructure_network_design.md)の既存仕様を優先。
- 読取り照合：tools/web_lab_teacher/http_task.py、http_task_guest.py、check_http.py、check_dispatch.py、progress_api.py。web_lab_catalogのconfiguration.py、admin.py、SQL、tests/test_proxy.py、tests/test_runtime.py。
- ローカルIntroduction-CyberSecurity/course/2026/assessment-policy.mdとOS-Linux-Control/COURSE_POLICY.md、2026/lab/teacher/lambda/progress_app.pyを確認。25点は教師の分野別換算枠で、checker素点の固定上限ではない。既存Web repoの旧4台/backup/本人実演記述より、本人の最新5台/backup除外/実演なしを優先。
- 前版で確認した[PostgreSQL16の実効権限](https://www.postgresql.org/docs/16/functions-info.html)、[sequence](https://www.postgresql.org/docs/16/functions-sequence.html)、[Django5.2の認証](https://docs.djangoproject.com/en/5.2/topics/auth/default/)は2026-10-22確認。配点はこれら公式資料の規定ではなく、既存システムに合わせたJDU向け設計案。
