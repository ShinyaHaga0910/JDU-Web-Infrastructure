# Web演習：正式学生配布入口

2026-10-23、**web-course-class193548-20261023-r2**を正式配布版として制作し、教師の非公開S3へ保存、教師/別学生のChrome CloudShellで受入した。D08正式r3とD11署名R8の全byteを保持し、全14課題を扱う本人用jdu-web-checkと新規/既存学生の手順をまとめた。

- [学生用手順](STUDENT.md)
- [教師用手順](TEACHER.md)
- [配布範囲と試験の限界](RELEASE.md)
- 配布3点：[jdu-web-course.tar.gz](../../../../03_knowledge/aws_official/web_lab_packages_2026-10-15/web-course-class193548-20261023-r2-download/jdu-web-course.tar.gz)、[分離署名](../../../../03_knowledge/aws_official/web_lab_packages_2026-10-15/web-course-class193548-20261023-r2-download/jdu-web-course.tar.gz.asc)、[公開鍵](../../../../03_knowledge/aws_official/web_lab_packages_2026-10-15/web-course-class193548-20261023-r2-download/package-signing-public.asc)。この3点をそのまま共通配布できる。
- [正式配布受入結果](../../../../03_knowledge/aws_official/web_lab_packages_2026-10-15/web-course-class193548-20261023-r2.acceptance.public.json)。
- [教師の実受入](../../../../05_records/network/2026-10-23_web_course_teacher_distribution.public.json)、[学生の実受入](../../../../05_records/network/2026-10-23_web_course_student_distribution.public.json)。短期URL/credentialは含めない。

archive **345264 bytes / SHA256 8d83ec96f05798b5b1fd0ef4ded318e286f88ab256c344cbd1722408bfd397e3**、署名fingerprint **65EC6784750CCFA703BA7179519284E45155EC2A**。全68fileの外側署名にClass193548/教師170126527713/固定62素点registryを対応付ける。

**有効期限：2026-10-27 14:24:57 UZT**。元foundation/署名鍵の期限を延ばしていない。次版は別の配布IDで正規に署名し、既存stateと認証を保持して受入する。

## 導入と更新

展開前のraw署名を独立fingerprintで確認し、展開後のstudent.py verifyで全fileと初期環境/採点機能の内側署名を再確認する。student.py installは本人のSTS/account、元core manifest、登録deployment、config/元root/5台とSSM・networkを照合してから本人CloudShellへ導入する。CloudShellで既定のhome権限777を実検出したため、本人所有のhomeを700へ保護してから保存する。

導入先は ~/.local/share/jdu-web/courses/<配布ID>/<Lab ID>/。kit/とbin/、private binding、activate.shを分け、元コマンド・元config/state/baseline/内部SSH enrollmentを上書きしない。既存認証は再発行せず、同一導入の再試行は全内容を照合して確認だけで終える。異なる既存fileやリンク、別account/別manifest/差し替えconfigは拒否する。新binをPATHの先頭に加える方式で旧入口へ復帰できる。

## 実受入

- 署名・改変/余分file/別signer拒否、安全なarchive、個人binding/リンク/上書き拒否、CloudShell home保護、旧file保持/復帰、private S3排他putの13試験が合格。
- 教師/学生両CloudShellで展開前署名・全68file・内側署名を合格。学生の実installと同一再試行で元4設定fileの保持を内部照合。元5台/SSH/RDP/採点認証は保持。
- 新入口の全14課題help、M0自己確認、M1=8/8、M4=9/9、M6元16/16の再送を実確認。本人用の元進捗コマンドも同じ認証でsessionを作り、本人画面のHTTPS200/62点を確認。
- 教師private S3の distributions/web-course-class193548-20261023-r2/ へ4objectを保存し全GET一致、public block/AES256を維持。公開ソフトウェア3fileの1時間リンクを実GETし全hash一致。教師用のJSON/CSV exportは検証Labを除外し0データ行/30列header。

r1はCloudShell homeの既定権限への対処を追加する前の制作途中版。S3へ正式配布していない。実行用はr2。搬入時にできたPython cacheは各CloudShellのgenerated-cache-retainedへ移して保管し、元署名fileは変更していない。実行入口は全てpython3 -Bを使う。

## 制作

build_release.pyは受入済みfoundationと独立署名されたassessment archive、18原本/receiptと62点の実受入記録を検査し、学生のテストidentityを除いた参照証拠を同梱する。教師専用の完成fixtureは配布しない。新ClassではそのClassの受入済みfoundation/教師を使う。

teacher.py publishは同じ教師の既存private bucketにだけ保存し、上書きや権限追加をしない。teacher.py context/exportは既存の教師認証と署名されたAPI宛先を使う。今のverification Labをcourseへ変更していない。

**distribution_ready=true / class_ready=false**。D12教材と母語校閲、成功passwordを本人が入力する試験、app導入後の全5台停止/再開は別工程。固定のブラウザ入口は[WEB-PORTAL-001](../../../../02_planning/tasks/issues/WEB-PORTAL-001.md)へ登録済み。Web FunctionsのLearner Labでの利用は本人確認済みで、今回そのportalを実装していない。
