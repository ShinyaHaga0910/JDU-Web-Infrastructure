# 教師用：P/M教材の準備と制作

[学生向けの入口へ戻る](README.md)


## 教師の事前準備

1. 受入済みの個別初期配布・5台/96GiB・全台SSM・内部SSH・採点登録と有効な署名版r3 installを先に完了する。新規と既存の手順を混ぜない。学生の匿名Lab ID/本人account/有効期限を案内する。
2. 共通zipの公開ファイルは共有Windowsへ置いてよい。秘密鍵、token、env、本人進捗URL、教師adminは含めない。学生はzipを本人のCloudShellへアップロードし、ホームで展開する。
3. P0のstage_resources.pyは署名版/本人binding/元5台/SG/SSMを照合後、WebとDBの固定directoryへ公開アプリ/SQL/helperだけを配置する。package・service・DB・role・password・鍵・採点認証を作らない。異なる既存資源は上書きしない。
4. Web/DB内のoffline_assets.pyは受入済みapp hashと全fileを照合して公開教材directoryへ展開する。Webの--wheelsだけが既存署名manifestから7 wheel/lockを取得する。pip/サービス設定は学生が各Pの手順で行う。
5. 初期配布参照はdistribution/STUDENT.md、foundation/STUDENT.md。実行場所は展開した署名版jdu-web-course/以下。今回のr3と教材配置helperは対応済みで、期限は**2027-01-31末（UZT）**。旧r2は書き換えず保存した。起動計画に指定する教師の価格台帳は7日以内のものを使う。
6. RDPは確認済み50 CIDRと既存password、内部SSHは踏み台、各台管理はCloudShellからSSM。初回password/権限と各段階の失敗を教師が確認する。学生全員に同じ到達時刻を要求しない。P5の前にM2、profile切替前にP6を扱う。

## 正本と生成

教材zipのTEACHING-FILE-HASHES.jsonは同梱内容の一致確認用で、OpenPGP署名の代わりではありません。初期環境・採点機能の3点セットは元の署名版をbyte単位で保持し、学生は展開前の署名検証を省略しません。

- 日本語と対訳の原稿：[content.py](authoring/content.py)。実行commandは3言語で共通。
- 仕組み・49段階の補足・出力読解・採点外の理解確認：authoring/explanations.py。
- Mの日本語合格条件：正式署名r3内の固定registry。ロシア語/ウズベク語の同じ62check：authoring/checks.py。
- 生成：[build.py](authoring/build.py)と[pages.py](authoring/pages.py)。課題別Markdown・一覧・通読版→ローカル閲覧HTML/A4 PDF、同じ初期配布3点のbyte保持、配布zipを作る。
- 自動確認：authoring/validate.py。版/hash/課題/点数/command同期、shell構文、公開資源・展開拒否、PDF/HTML/zipを検査する。
- PDFの全ページ画像化と枠外確認：authoring/qa_pdf.py。画像はローカル作業用、結果はrendering.public.json。教師による目視承認とは分ける。

生成にはPython3.12と[requirements.txt](authoring/requirements.txt)、PDFにはWindowsのMS Gothic/Arial/Consolasを使用。フォントをzipへ再配布しない。公開検証資源は同じrepoの[development](../../development/README.md)を既定で読み、特定PCの絶対pathを必要としない。学生配布zipにはauthoringや開発fixtureを含めない。再生成と確認は[BUILD.md](../../BUILD.md)に従う。

**教材初版は制作済み。母語校閲、教師の目視確認、学生が詳細手順を最初から辿る通し試験は未実施。全授業のCLASS_READYはfalseのまま。** 初期化や完成fixtureを教材受入のために学生環境へ再適用していない。

改訂r1.3（2026-11-03）では課題別ページを追加し、通常の確認・成績閲覧をブラウザへ統一しました。サーバー設定の手順、62素点、署名版のbyteは維持しています。GitHub上の学生入口はMarkdownです。HTMLはzipを展開してローカルで開きます。
