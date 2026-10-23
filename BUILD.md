# 教材の制作と確認

1. `COURSE_POLICY.md`と対象単元のREADMEを読む。
2. その単元の到達条件と構成図を決める。
3. 説明原稿、手順付き練習、異なる対象の自力課題、確認項目、再開・復旧手順を作る。
4. 相対リンク、用語、対象service、port、設定ファイル、図の矢印を照合する。
5. 学生権限の新しいLab環境で最初から実行し、使用版・結果・未実施を`validation.md`に記録する。
6. 配布PDF・スライドを原稿から更新し、ページ数・リンク・図の読込を自動確認する。目視確認は教員が行う。

自動検査のPASSだけで学生手順が完成したとは判断しません。CloudFormation、実環境の設定、予算を確認していない手順は、学生向けの確定手順として公開しません。

## 構築・採点システムの開発

コードの正本は[development](development/README.md)です。Linux/WSLでPython3とGPGを用意し、repo rootで実行します。

```bash
python3 -B development/run_local_checks.py
```

移管元byteの確認と選択したunit/mock検査であり、AWS資源を作成しません。前提・実機受入との区別は[TESTING.md](development/TESTING.md)を参照します。

## P/M教材の生成と確認

Python3.12の専用環境に次の依存を入れ、repo rootから実行します。

```bash
python -m pip install -r course/labs/authoring/requirements.txt
python -B course/labs/authoring/build.py --no-pdf
python -B course/labs/authoring/validate.py
python -B course/labs/authoring/qa_pdf.py
```

--no-pdfは保存済みPDFを保持し、Markdown/HTML/zipを更新します。PDFも作り直す場合はWindowsのMS Gothic/Arial/Consolasを用意して--no-pdfを外します。公開署名資源はdevelopment/03_knowledge以下を既定で読みます。意図的に別の公開資源rootを使う場合だけJDU_WEB_PROJECT_ROOTで指定します。署名済みの原本を教材変更で書き換えません。

qa_pdf.pyはPopplerのpdftotext/pdftoppmをPATH上へ用意して実行します。全ページをtmp/pdfs以下へ画像化し、本文の枠外文字・ページ数・空白画像を自動確認してrendering.public.jsonへ記録します。教師による目視承認・母語校閲の結果にはしません。

## GitHubへの反映

素材・コード・生成物・検証記録の関連差分を揃え、認証情報、秘密鍵、private plan/state、大容量cacheがないことを確認してコミット・pushします。今後の通常作業にもこの手順を適用します。
