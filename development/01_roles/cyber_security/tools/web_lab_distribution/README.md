# Web Lab：D08正式配布

2026-10-23追記：現在の学生向け入口は[D08＋D11をまとめた正式Web配布版](../web_lab_release/README.md)。下のD08 r3はその中のfoundationとして全byteを保持している。全課題の採点には新しい入口を使う。

2026-10-22、Class193548向け初期環境配布版 **d08-class193548-20261022-r3** を制作し、教師AWS170126527713の既存非公開S3へ保存・全object GET一致を確認した。教師・学生AWS965244652544のChrome CloudShellで、展開前raw署名、展開後全file・内外署名・期限を検証した。既存5台・state・採点tokenは変更していない。

## 入口

- [学生用手順](STUDENT.md)：署名確認、本人recipient、暗号化受信、新規構築と通常再開。
- [教師用手順](TEACHER.md)：教師の先行起動、学生別の初回発行、既存認証の再配布、署名更新。
- [配布範囲](RELEASE.md)：D08初期環境の配布と、未完の全課題・教材を区別。
- 配布実体：[公開ファイルのみの署名archive](../../../../03_knowledge/aws_official/web_lab_packages_2026-10-15/distribution-class193548-r3.tar.gz)、同名`.asc`、folder内の公開鍵。

署名fingerprintは **65EC6784750CCFA703BA7179519284E45155EC2A**。archive SHA256は **3848f9adb04cd7af37c4343e1c3c1dc695133cccace8f6fd8c14401c5b08d86d**、96,301 bytes。配布manifest SHA256は **4d15fd4975404b12c5f0257752db086626b8301bb7af4670f1ade72bc39d86ec**。

**期限：2026-10-27 14:24:57 UZT（09:24:57 UTC）。** 自動延長はしない。署名期限後の既存state移行を未検証のまま実施しない。教師用手順の署名更新レビューを授業前に行う。

## 制作・検証

`build_release.py`は受入済みcoreの署名・payload・別学生新規配備/停止再開/GUI・全29証跡のhashを検査し、coreの全byteを保持した外側配布版を署名する。学生別private設定をarchiveへ入れない。別ClassへはそのClassの受入済みcoreから制作する。

`distribution.py`はClass/教師を署名に固定し、学生account/Lab ID/recipientを個別照合する。newは既存Labを拒否し、reuseは教師DBと元credentialの一致を要求する。再配布でtokenや登録5台を更新しない。共通配布物の検証はローカル処理、recipient/発行/受信は各自のCloudShellで行う。

`publish_release.py`は外側archiveの署名と展開済みtreeの一致、S3公開禁止を検査してから、既存bucketの`distributions/d08-class193548-20261022-r3/`へ4objectを保存する。上書き・権限追加・公開化はしない。3公開assetと最後のpublication.jsonを再取得して照合する。

10件の試験は、異なる2組のClass/account、別学生/別recipient/期限切れ/extra admin拒否、実OpenSSL CMSでの既存token再配布/復号と再受信拒否、元credential/教師DB不変、非TTY拒否、private file、公開物の同一再試行/不一致上書き拒否、別archive/不正path拒否を含む。実署名の改変・余分file拒否、archiveと全tree一致、旧core全byte一致も確認した。

今回の一般化した初回new/sendを、新しい実学生で再度発行・配備する試験は行っていない。元の新規5台受入は同じcoreの別学生実機証跡、一般化した再配布の暗号処理はローカル実暗号試験、既存tokenの有効性は教師実DBの読取り照合として区別する。授業全体のCLASS_READYはfalse。D11全課題・配点・残判定器、完成DNS/DB/app、D12教材は引き続き残件。

r1/r2は制作途中のローカル版で、AWS配布先へ保存していない。運用するのはr3のみ。
