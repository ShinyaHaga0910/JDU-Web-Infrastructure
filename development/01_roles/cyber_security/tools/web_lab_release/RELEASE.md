# 配布範囲

この版は、受入済みD08初期環境と、同じ既存5台で62/62を確認したD11の採点/checkerをまとめる正式学生配布入口です。

- 共通archiveは公開ソフトウェアだけ。学生別state・SSH秘密鍵・RDP hash・DB/app password・採点token・教師admin・認証URLを含みません。
- 初期環境は既存の正式D08版を全byte保持してfoundationへ同梱します。新規構築/個別暗号化受渡しはその検証済み方式を使います。
- D11は独立署名された受入済みR8を全byte保持し、外側の署名にClass/教師/有効期限/固定registryと対応付けます。教師専用の完成fixtureは含みません。
- 学生の新しい採点コマンドは本人CloudShellだけに導入。元command-state/5台/ディスク/作業/SSH/RDP/採点認証を保持します。
- 採点満点はM1〜M6=8/13/3/9/13/16、計62。本人実演なし。25点への換算は教師が行います。
- 既存検証Labを授業成績へ変更しません。新規授業Labも教師が明示するまでは成績exportから除外します。

内側のD11-MANIFEST.jsonにあるcandidate表記と古いREADMEは受入時の保存物です。外側course-release.jsonが、この正式配布版の対象と有効期限を定めます。内側の固定観測コードやregistryを書き換えて正式版に見せかけてはいません。

受入記録は62/62の実HTTP/正規password/CSRF/DB/公開反映、教師DBの原本・receipt照合、UNKNOWNと参照値の分離、対話SSMの非表示入力/誤認証拒否を含みます。成功passwordの本人手入力、新規一般配布版での再度の5台作成、app導入後の全5台停止/再開は今回の配布版の受入範囲と分けます。

**distribution_ready=true、class_ready=false**。D12の授業本文・母語校閲を終えた全授業の公開を意味しません。固定ブラウザ入口は後工程のIssueです。
