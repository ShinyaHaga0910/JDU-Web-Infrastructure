> 2026-10-30追補：初期CloudFormation後のブラウザ確認をJA/RU/UZのportal.md / portal.htmlへ追加。元のP/M本文・PDFと初期署名物は参照版として保持し、採点CLI/URLコピーを追補の手順へ置き換えます。指定環境のM3/M5/M6・原本保存・本人/教師表示は[実受入](../../development/web_portal_poc/verification/2026-10-30-browser-special-checks-accepted.public.json)を参照。教材全手順の新規学生通し試験・母語校閲・教員目視確認を完了済みとはしません。

# D12 P/M教材の確認範囲

## 2026-11-03：期限更新と教材配置の実受入

正式配布r3は2027-01-31末（UZT）まで有効。同じ受入済みcore実行物/template/payloadとassessmentの全byteを保ち、期限と配布wrapperを正規署名で更新した。署名済みRENEWAL.jsonが元manifestと新manifestを対応付けるため、新courseの導入・教材配置に元stateをそのまま使える。旧state/command-state/SSH情報の4file不変を実確認。古いcoreの期限検証そのものを無効にするものではない。

実教師/学生CloudShellで署名・全fileを検証し、教師の既存private S3へ新しい配布IDで保存/全GET一致。学生の新しいcourse保存先へ導入後、実stage_resources.pyでWeb/DBへ5つの公開資源を配置し、同一再実行も成功した。元の5台・サービス・認証・成績を初期化していない。既存course/署名物は保持。

期限・再利用の16試験、更新教材510検査/48 Bash block、3言語PDF125頁の生成/全頁画像化/枠外0を確認。新規CloudFormationからの通し受入、母語校閲、教師目視確認は未実施。以下の旧r2の記述は初版時点の履歴で、この最新結果を優先する。

2026-10-23、教材改訂r1.1。P0-P6の49手順とM0-M6を日本語/ロシア語/ウズベク語で制作。49段階全ての説明、7つの仕組み/理解確認、HTTP/DNS/SQLの出力読解、7経路の通信表とMの作業計画を追加。初期配布と62素点checkerのAWS受入済み版へ照合する。

## 自動確認と制作物

authoring/validate.pyの結果をvalidation.public.jsonへ保存する。3言語の課題/command一致、固定registry hashとM各8/13/3/9/13/16点、62check、公開資源の固定app照合/不正archive拒否/既存差分保持、shell構文、PDFのA4/抽出文字/ページ数、HTML metadata/links、zip hashを検査する。PDFは原稿から生成し、ページ画像は制作時確認用に別保存する。目視による教材確認・承認は教師が行う。

改訂では49説明が各手順内に現れ、開始/完成/仕組み/理解確認とMの作業計画が3言語へ欠落なく出力されることも確認する。実行commandと採点条件の変更を伴わない。PDF全ページを画像化し、枠外文字などの自動検査を実施するが、母語校閲・教師目視確認・実AWSでの学生通し試験の代替とはしない。

## 実機に関する境界

- 参照したD08/D11/正式配布r2は教師/別学生のAWSで受入済み。元5台・state・SSH/RDP・採点認証を保持した更新と、採点62/62・教師原本照合の証拠がある。
- 今回は教材制作。既存の完成学生Labをresetしたり、構築済みサービス・role・passwordを再作成したりしていない。
- stage_resources.py/offline_assets.pyはローカル照合と拒否検査の対象。**この新しい教材資源の搬入と、この49手順を新規学生が通しで実行するAWS試験は未実施。** 元fixtureのAWS成功をその試験へ読み替えない。
- 正しいpasswordを学生本人が対話SSMで入力して機能成功する試験と、app導入後の全5台停止/再開は引き続き未試験。
- ロシア語/ウズベク語は翻訳初稿。母語話者校閲、学生試読、教師目視確認は未実施。
- 署名版r2の期限は2026-10-27 14:24:57 UZT。授業実施日・締切・全員の配布準備は未確定。自動検査合格だけでCLASS_READYをtrueにしない。

## 次の受入

1. 教師が各言語のP/M PDFとHTMLを確認し、母語校閲を行う。
2. 明示的に試験対象とした新規/未完成の学生LabでP0資源搬入→P/M推奨順を通し、期待/実結果と所要時間を残す。既存の完成Labを無断で初期化しない。
3. 最後に既存データ・5台・鍵・認証を保持した再開を確認し、CLASS_READYの残件を更新する。
4. 固定ブラウザ入口はWEB-PORTAL-001で別管理。Learner LabでWeb Functionsが利用できることは本人確認済み。
