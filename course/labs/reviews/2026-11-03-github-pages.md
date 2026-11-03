# P/M教材のGitHubページ点検（2026-11-03）

判定：課題の構成・採点との対応は揃っているが、学生にGitHubのページを直接案内する前に、下の3点の修正が必要。

対象は公開済みmainの`d8d11267f1d96bbb577134058028ec58d57f5314`。既存の認証済みGit接続で取得し、Chromeでもログイン済みの所有者アカウントから非公開リポジトリ・Markdown本文・HTMLファイルを開いて確認した。GitHubコネクタの404と、Chromeからの閲覧可否を区別する。新しい権限の付与は行っていない。

## 修正が必要な点

### 1. GitHubで読む案内がHTMLのソース表示へ進む

- 対象：[教材入口5〜10行](https://github.com/ShinyaHaga0910/JDU-Web-Infrastructure/blob/d8d11267f1d96bbb577134058028ec58d57f5314/course/labs/README.md#L5)。
- 「まず日本語の確認手順」「Русский」「O‘zbekcha」が`output/html/*/portal.html`へ、「閲覧入口：3言語HTML」が`output/html/index.html`へ進む。
- GitHubの通常のファイル画面ではHTMLはソース表示となり、読書用ページとして表示されない。実際に日本語portal.htmlで`Code`とHTML本文を確認した。[画面記録](2026-11-03-github-html-code.png)。ファイル自体の欠落ではない。
- GitHub上の読者は`docs/ja/portal.md`・`docs/ru/portal.md`・`docs/uz/portal.md`へ案内し、HTMLは教材ZIPを展開した後の閲覧用として区別する。

### 2. r3本文の冒頭と末尾で有効期限が矛盾する

- 対象：JA/RU/UZのpractice.md・missions.md、計6ファイル。
- 冒頭は2027年1月31日末 UZT、末尾は2026-10-27 14:24:57 UZTとなっている。日本語の該当箇所は[練習1319行](https://github.com/ShinyaHaga0910/JDU-Web-Infrastructure/blob/d8d11267f1d96bbb577134058028ec58d57f5314/course/labs/docs/ja/practice.md#L1319)と[課題345行](https://github.com/ShinyaHaga0910/JDU-Web-Infrastructure/blob/d8d11267f1d96bbb577134058028ec58d57f5314/course/labs/docs/ja/missions.md#L345)。
- 正規署名r3そのものは2027年1月31日末まで有効。今回見つかったのは教材の旧表記の残存であり、AWS側の期限切れではない。
- 制作元`authoring/build.py`の`emit_end()`105〜107行にも旧日付が残る。生成済みMarkdownだけを直しても再発するため、制作元と3言語の生成物を揃える必要がある。署名済みソフトウェアを書き換える修正ではない。

### 3. P/M本文だけでは現在のブラウザ採点手順へ辿れない

- 対象：JA/RU/UZのpractice.md・missions.md、計6ファイル。
- 各課題の「確認・提出」には`jdu-web-check`、`--no-submit`、`--functional`、本人用URLの案内があり、現在のブラウザ用`portal.md`やWeb Portalへの直接リンクがない。
- 教材入口にはブラウザ追補で置き換える旨があるが、P/M本文の直接リンクで読む学生には伝わらない。CLIが利用不能という判定ではなく、「初期設定後はブラウザから課題確認」という現在の案内が本文だけでは完結しない点である。
- 本文冒頭から同じ言語のブラウザ手順へ直接案内し、各課題の確認方法と、P3/M3の停止前後・P5/M5/P6/M6の秘密入力の扱いを揃える必要がある。

## 揃っている点

P0〜P6とM0〜M6は各7つ。GitHubのMarkdown本文は言語ごとにpractice.md・missions.mdへ7節ずつまとまっており、課題ごとに14個の独立ページがある構成ではない。

| 番号 | 主題 | Mの素点 |
| --- | --- | --- |
| 0 | 自分の環境と実行場所 | 0（準備確認） |
| 1 | HTTPと静的ファイル | 8 |
| 2 | 内部DNSと通常resolver | 13 |
| 3 | 元EBSの保存内容と停止・再開 | 3 |
| 4 | PostgreSQLへの認証接続 | 9 |
| 5 | 教員アプリとWeb/DBの接続 | 13 |
| 6 | 最小権限と公開範囲 | 16 |

- 日本語原稿・ロシア語・ウズベク語に各7課題、Pの49段階を確認。
- M1〜M6の合計62点・62採点IDが固定registryと一致。PとM0は成績外。
- 3言語のコマンド・設定例・出力例の枠は一致し、Bash48枠の構文を検査した。
- 教材入口・P/M本文・ブラウザ追補の計10 Markdownから、相対ファイルリンク48件をGitHub取得treeと照合。リンク先ファイルの欠落は0件。
- P1〜P6の実行場所、目的、設定・構築操作、反映、確認とMの別対象要件を読み、学生がサーバー内で設定する課題であることを確認。

今回の点検ではAWS上で14課題を再実行していない。新5台のM0/P1/M1の実受入は[別記録](../../../development/web_portal_poc/verification/2026-11-03-fresh-initial-workflow.accepted.public.json)。母語校閲と、学生アカウントによるこの非公開GitHubの閲覧権限は未確認。教材本文の修正・再生成・新たなAWS操作は行っていない。

[取得元commit・照合結果・各本文hash](2026-11-03-github-pages.public.json)。
