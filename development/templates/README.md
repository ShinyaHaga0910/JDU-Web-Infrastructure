# 現行CloudFormationの入口

- [学生5台](web-lab-student.template.json)：受入済み署名版r2内のweb-lab-ssm-all-nodes-c5.template.jsonと同一byte。踏み台/Web/DNS/DB/repo、元root計96GiB、全5台の常設SSMを含む。
- [教師62素点受付](web-teacher-d11.template.json)：現在のweb_lab_assessment/build_teacher.pyで生成。元のAPI/Table/固定入口を基礎に、62素点の保存・表示と認証付き教師操作を組み込む。

実値のVPC/subnet/AMI、既存LabRole、配布manifest、本人用認証の設定は、署名controllerと教師の専用手順で行う。ここに保存したJSONだけで任意の既存Labを置換しない。rdp password/採点token/教師adminや実行済みprivate parameter fileは含めない。
