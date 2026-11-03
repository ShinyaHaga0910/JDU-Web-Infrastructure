# Web演習 D12：P/M課題教材

2026-11-03更新：正式配布r3 `web-course-class193548-20261103-r3` は**2027年1月31日末（UZT）まで有効**です。同梱の署名版・P0の教材配置設定・3言語のP/M教材を揃え、教師/学生の実CloudShellで全署名を検証しました。元state保持の更新導入に加え、本人承認の新5台で、初回配布・SSM/内部SSH/採点登録・教材配置・Google/AWS連携・ブラウザM0/P1/M1・原本保存/教師表示まで実受入済みです。P1だけではM1は3/8、指定ファイル作成後は8/8、新成績8/62。旧成績84行/62点と元暗号化96GiBを保持。[初回ワークフローとコマンド](https://github.com/ShinyaHaga0910/JDU-Web-Infrastructure/blob/main/course/labs/INITIAL-WORKFLOW.md)を参照します。**全49手順の学生試読・母語校閲等は別に残り、全授業CLASS_READYはfalseです。**

2026-10-30追加：初期設定は既存CloudFormation、その後の課題確認・成績閲覧はブラウザを使います。まず[日本語の確認手順](output/html/ja/portal.html)・[Русский](output/html/ru/portal.html)・[O‘zbekcha](output/html/uz/portal.html)を読みます。本文/PDFのサーバー設定コマンドは維持し、課題確認用CLIとURLコピーをこの追補へ置き換えます。期限切れの署名版は使わず、教師が有効な版を個別発行します。

2026-10-23更新、教材改訂r1.1。本人の「まずPとMだけ」「PはOS・Linux教材と同じ詳しい手順」の依頼に基づく教材。日本語原稿、ロシア語・ウズベク語の学生版を同じ構造とcommandから生成する。スライド・独立教科書・最終実演は今回作らない。

- [閲覧入口：3言語HTML](output/html/index.html)
- [配布zip：教材・公開準備資源・既存署名版3点](output/web-lab-pm-r1.zip)
- [確認範囲と残件](VALIDATION.md)

| 言語 | 詳しい練習 P0-P6 | 自力課題 M0-M6 |
| --- | --- | --- |
| 日本語 | [本文](docs/ja/practice.md) / [PDF](output/pdf/web_lab_practice_ja.pdf) | [本文](docs/ja/missions.md) / [PDF](output/pdf/web_lab_missions_ja.pdf) |
| Русский | [Текст](docs/ru/practice.md) / [PDF](output/pdf/web_lab_practice_ru.pdf) | [Текст](docs/ru/missions.md) / [PDF](output/pdf/web_lab_missions_ru.pdf) |
| O‘zbekcha | [Matn](docs/uz/practice.md) / [PDF](output/pdf/web_lab_practice_uz.pdf) | [Matn](docs/uz/missions.md) / [PDF](output/pdf/web_lab_missions_uz.pdf) |

Pは課題文を先に置き、49段階に実行場所・目的と操作・期待結果・エラー時の確認先を付けた。接続/exit、nanoの保存、psqlとshellの区別、既存passwordの非表示入力、profileの切替を省略しない。Mは完成要件と62素点の固定check表を示し、完成command列を載せない。Pは成績外、M0は0点、本人実演なし。科目25点への換算は教師が別に行う。

r1.1では全49段階へコマンド・設定値の説明を加え、各Pに開始状態・完成状態・仕組み・採点外の理解確認を用意した。HTTP/DNS/SQLの出力例、7経路の通信表、Mを始める前の作業計画も3言語で揃えた。操作コマンドと固定62check、署名ソフトウェアの版は維持する。ファイル名/展開先のweb-lab-pm-r1は同じ最新版を更新するための名前で、本文の教材改訂番号とは区別する。

## 教師の事前準備

1. 受入済みの個別初期配布・5台/96GiB・全台SSM・内部SSH・採点登録と有効な署名版r3 installを先に完了する。新規と既存の手順を混ぜない。学生の匿名Lab ID/本人account/有効期限を案内する。
2. 共通zipの公開ファイルは共有Windowsへ置いてよい。秘密鍵、token、env、本人進捗URL、教師adminは含めない。学生はzipを本人のCloudShellへアップロードし、ホームで展開する。
3. P0のstage_resources.pyは署名版/本人binding/元5台/SG/SSMを照合後、WebとDBの固定directoryへ公開アプリ/SQL/helperだけを配置する。package・service・DB・role・password・鍵・採点認証を作らない。異なる既存資源は上書きしない。
4. Web/DB内のoffline_assets.pyは受入済みapp hashと全fileを照合して公開教材directoryへ展開する。Webの--wheelsだけが既存署名manifestから7 wheel/lockを取得する。pip/サービス設定は学生が各Pの手順で行う。
5. 初期配布参照はdistribution/STUDENT.md、foundation/STUDENT.md。実行場所は展開した署名版jdu-web-course/以下。今回のr3と教材配置helperは対応済みで、期限は**2027-01-31末（UZT）**。旧r2は書き換えず保存した。起動計画に指定する教師の価格台帳は7日以内のものを使う。
6. RDPは確認済み50 CIDRと既存password、内部SSHは踏み台、各台管理はCloudShellからSSM。初回password/権限と各段階の失敗を教師が確認する。学生全員に同じ到達時刻を要求しない。P5の前にM2、profile切替前にP6を扱う。

## 正本と生成

教材zipのTEACHING-FILE-HASHES.jsonは同梱内容の一致確認用で、OpenPGP署名の代わりではありません。初期環境・採点機能の3点セットは元の署名版をbyte単位で保持し、学生は展開前の署名検証を省略しません。

- 日本語と対訳の原稿：authoring/content.py。実行commandは3言語で共通。
- 仕組み・49段階の補足・出力読解・採点外の理解確認：authoring/explanations.py。
- Mの日本語合格条件：正式署名r2内の固定registry。ロシア語/ウズベク語の同じ62check：authoring/checks.py。
- 生成：authoring/build.py。Markdown→閲覧HTML/A4 PDF、同じ初期配布3点のbyte保持、配布zipを作る。
- 自動確認：authoring/validate.py。版/hash/課題/点数/command同期、shell構文、公開資源・展開拒否、PDF/HTML/zipを検査する。
- PDFの全ページ画像化と枠外確認：authoring/qa_pdf.py。画像はローカル作業用、結果はrendering.public.json。教師による目視承認とは分ける。

生成にはPython3.12と[requirements.txt](authoring/requirements.txt)、PDFにはWindowsのMS Gothic/Arial/Consolasを使用。フォントをzipへ再配布しない。公開検証資源は同じrepoの[development](../../development/README.md)を既定で読み、特定PCの絶対pathを必要としない。学生配布zipにはauthoringや開発fixtureを含めない。再生成と確認は[BUILD.md](../../BUILD.md)に従う。

**教材初版は制作済み。母語校閲、教師の目視確認、学生が詳細手順を最初から辿る通し試験は未実施。全授業のCLASS_READYはfalseのまま。** 初期化や完成fixtureを教材受入のために学生環境へ再適用していない。
