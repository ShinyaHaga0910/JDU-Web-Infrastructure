# Web演習：練習P・課題M

サーバーを自分で設定し、ブラウザで結果を確認する演習です。
**Pは詳しい手順つきの練習、Mは別の対象を自分で構築する課題**です。

## 言語を選ぶ

| 言語 | はじめに・接続方法 | 練習P0〜P6 | 自力課題M0〜M6 | ブラウザで確認 |
| --- | --- | --- | --- | --- |
| 日本語 | [準備と操作](docs/ja/start.md) | [練習の一覧](docs/ja/practice.md) | [課題の一覧](docs/ja/missions.md) | [確認手順](docs/ja/portal.md) |
| Русский | [Подготовка](docs/ru/start.md) | [Практика P](docs/ru/practice.md) | [Задания M](docs/ru/missions.md) | [Проверка](docs/ru/portal.md) |
| O‘zbekcha | [Tayyorgarlik](docs/uz/start.md) | [P mashqlar](docs/uz/practice.md) | [M topshiriqlar](docs/uz/missions.md) | [Tekshirish](docs/uz/portal.md) |

## 学習の進め方

1. 教師から受け取った[初回構築の手順](INITIAL-WORKFLOW.md)で、自分の5台と本人登録を準備します。
2. 上の「準備と操作」を読み、Pの操作例で仕組みと設定方法を学びます。
3. Mの完成要件に合わせて、自分でサーバーの設定を変更します。
4. [Web Portal](https://d9r6gn83y8wkl4xl.gpb.lambda-web.us-east-1.on.aws)で課題を選び、結果と保存済み成績を確認します。

P0 → M0 → P1 → M1 → P2 → M2 → P3 → M3 → P4 → M4 → P5 → P6 → M5 → M6

P5の前にM2、練習用から本課題用へ切り替える前にP6を終えます。
Pは成績外、M0は0点です。M1〜M6は合計**62素点**で、科目の25点への換算は教師が行います。

## 課題を開く（日本語）

| テーマ | 詳しい練習 | 自力課題 | Mの素点 |
| --- | --- | --- | --- |
| 環境と操作場所の確認 | [P0](docs/ja/p0.md) | [M0](docs/ja/m0.md) | 0 |
| HTTPでファイルを配信する | [P1](docs/ja/p1.md) | [M1](docs/ja/m1.md) | 8 |
| DNSで名前を解決する | [P2](docs/ja/p2.md) | [M2](docs/ja/m2.md) | 13 |
| EC2停止・再開後のファイル保持 | [P3](docs/ja/p3.md) | [M3](docs/ja/m3.md) | 3 |
| PostgreSQLの接続と認証 | [P4](docs/ja/p4.md) | [M4](docs/ja/m4.md) | 9 |
| 教師提供アプリをDBへ接続する | [P5](docs/ja/p5.md) | [M5](docs/ja/m5.md) | 13 |
| 最小権限と公開範囲を仕上げる | [P6](docs/ja/p6.md) | [M6](docs/ja/m6.md) | 16 |

各Pでは、実行場所・目的・操作・設定の意味・期待結果・困ったときの確認先を順に読みます。
Mには完成要件と採点条件を載せています。

コマンドの直前には、`# 1. …` のように操作の目的と番号を付けています。
番号はP1.2などの各手順内で振り直します。psql内では`-- 1. …`を使い、設定ファイルに書く本文とは区別しています。
各P/Mの図は「開始時点 → 今回の操作 → 確認する結果」と、設定・通信の対象を示します。図は拡大して読めます。

**SGはCloudFormationで初期設定済みです。現行P/Mの採点対象はサーバー内の設定で、SGを学生が変更する採点課題は含みません。**

## 一冊で読む・ダウンロードする

| 言語 | 練習の通読版 | 課題の通読版 |
| --- | --- | --- |
| 日本語 | [Markdown](docs/ja/practice-full.md) / [PDF](output/pdf/web_lab_practice_ja.pdf) | [Markdown](docs/ja/missions-full.md) / [PDF](output/pdf/web_lab_missions_ja.pdf) |
| Русский | [Markdown](docs/ru/practice-full.md) / [PDF](output/pdf/web_lab_practice_ru.pdf) | [Markdown](docs/ru/missions-full.md) / [PDF](output/pdf/web_lab_missions_ru.pdf) |
| O‘zbekcha | [Markdown](docs/uz/practice-full.md) / [PDF](output/pdf/web_lab_practice_uz.pdf) | [Markdown](docs/uz/missions-full.md) / [PDF](output/pdf/web_lab_missions_uz.pdf) |

[教材zipをダウンロード](output/web-lab-pm-r1.zip)して展開すると、`output/html/index.html`からHTML版をローカルで読めます。
GitHub上では上のMarkdownリンクを使ってください。HTMLファイルのGitHubページはソースコード表示になります。

## 使用版・教師用情報

2026-11-03更新、教材改訂 **r1.4**。署名配布版 `web-course-class193548-20261103-r3` は**2027年1月31日末（UZT）まで有効**です。
Web Portalは教師Lab開始中に使います。学生Labの停止中は、新しい実機確認を実行できません。

- [教師の事前準備・原稿と生成方法](TEACHER-NOTES.md)
- [確認済みの範囲と残件](VALIDATION.md)

初回構築からブラウザP1/M1・成績原本保存までの指定環境での受入は完了しています。
全49手順の学生試読、ロシア語・ウズベク語の母語校閲、教師の教材承認は未実施です。
