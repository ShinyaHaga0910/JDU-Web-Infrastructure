> 2026-10-30最新本人決定：初期設定は既存CloudFormationを利用し、この初回構築Web化・旧環境整理案は今回の対象外。以下は候補制作の履歴として保持する。新資源・worker読取り許可・EC2削除を進めない。現行の完成条件はPORTAL-ACCEPTANCE.mdを参照。

# R1：別Labを用意できない場合の検証案

2026-10-30、Class193548の学生AWSを実読取り。**調査案であり、削除・置換・新規配備・guard変更は未承認/未実行。** R1/R5/R6の既存残件を進めるための方法を整理し、完了条件は増やさない。

## 実際に確認した条件

- 学生AWS965244652544の既存5台はすべてrunning、元5 root IDと一致。CloudShellからEC2/EBSのService Quotasを読む要求はAccessDeniedExceptionだった。
- 同じClassのLab README（本文更新2025-06-24）で、regionごとの同時稼働9台/32vCPU、Lab次回開始時に手動停止分も含めて全台を起動する説明を確認。予算表示はUsed $7 of $50で、READMEには予算情報の遅延も明記されている。これは残額確定や現在費用の実測ではない。
- ツールの9台guardは停止中を含む非終了台数を数える。READMEの「同時稼働」とは定義が異なる。しかし、旧5＋新5を保持するとLab再開時に10台起動を試みるため、停止だけを条件にした併設やguard緩和は採用しない。
- 現12資源helper候補のValidateTemplateは学生CloudShellで成功。SHA256 `7aee44bd72cc7a111431a3e03d60f18870d45e5b23e4739cce402ba46f9dac09`、3 parameter、capabilitiesなし。code/宛先は架空fixtureで、資源作成・role動作・artifact実取得を確認したものではない。

## 台数を空ける最小案

候補は旧repo1台のEC2だけを終了し、既存4台＋新5台＝9台にする方法。教師EC2や別Classは対象にしない。元の暗号化disk96GiBと採点原本・認証は保持する。

| 対象 | 読取りで確認した値 |
| --- | --- |
| EC2 | `i-08f8a40fdaa5bb240` / `jdu-web-class193548-test1-repo` |
| CloudFormation | `jdu-web-class193548-test1` / `RepoInstance`、現在のPhysical IDと一致 |
| root | `vol-07c3cc6ffdd36afb9` / 32GiB / encrypted |
| 現在の終了時設定 | **DeleteOnTermination=true。現状のまま終了するとdiskも消えるため実行不可** |

実施する場合は、復旧に必要なinstance/volume/AMI/SG/subnet/profile/ENI/UserData等の控えを教師管理の非公開領域へ保存し、対象rootのDeleteOnTermination=falseを適用・再読取りしてから、当該EC2だけを終了する具体計画が必要。diskの保存だけで同じinstance IDへ戻せるとは説明しない。復元時は別IDとなり、旧5台を固定したchecker/baseline/登録の再対応が別途必要になる。旧repo終了後は旧環境のpackage配布と旧5台の検査が使えなくなる。元採点原本は削除せず保持する。

この影響があるため、**まだ削除実行の承認を求める段階ではない**。先に下記の配布と本人割当を含む全体の実行計画を完成させ、実際の変更計画に対して直前確認をまとめる。

## EC2を1台減らすだけでは解決しない点

現行`PortalPreparation`は既存の学校本人/AWS bindingとMETAを上書きしない。旧EC2を終了しても、同じ学校GoogleとAWSの新規割当は既存bindingにより拒否される。拒否条件を外したり、古いbindingや原本を削除して試験を通さない。

検討する方法は、元bindingを保持し、同じGoogleを学生役にする新規構築試験の登録先を検証用の別table/サービス設定へ分けること。元Google認証設定の再利用と、試験後の既存Web/サービス設定への復帰を含め、R5の既存の授業/検証分離と合わせて計画する。新しい公開URLやGoogle credentialが必須と決め付けず、既存入口の更新で足りるかを先に確認する。これらはまだAWS変更計画ではない。

有効な新署名course/core・固定artifact公開、Web/private serviceの初回準備flagとtimeout、元5台専用status/checker以降の実通信確認も必要。独立した学生Googleは未確保なので、先生を学生役にした試験はR1候補の検証として扱い、独立学生identityのR6を合格にはしない。

## 次の順序

1. 教師CloudShellへ接続し、元artifactと署名制作手順・登録設定を確認する。
2. 有効署名配布/worker、初回準備の配備設定、元bindingを保持した試験用割当を具体化する。
3. 既存環境の控えと復旧方法・実変更計画を揃えた後、旧repo終了と試験用配備をまとめて直前確認する。承認前にEC2終了や権限追加をしない。
4. 承認された計画でR1の初回構築を実試験する。全体終了は引き続きR1〜R6の固定表で判定する。

[元のClass Lab入口](https://awsacademy.instructure.com/courses/193548/modules/items/19156612)。認証付きREADME URLや一時キーは記録しない。
