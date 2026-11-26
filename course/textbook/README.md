# Webインフラストラクチャー教科書

後半授業の教科書。日本語全13章（第1〜13章）の本文・図・HTML・PDFを作成済み。[章・節の設計](../textbook-outline.md)と既存P/Mの構成に対応させている。文章は教員が編集しやすい章別Markdownを正本とする。OS・Linux教材の説明形式をそのまま踏襲することを優先せず、全体像・各部の役割・実作業とのつながりを分かりやすく示す。

2026-11-17：削除済みのストレージの旧第8章を詰め、第1〜13章の連番へ整理した。旧第9〜14章は第8〜13章に対応する。練習P0〜P5と課題M0〜M5はテーマごとに同じ番号を使う。現行の配点は[演習の案内](../labs/README.md)を参照。

## 全章をまとめた資料

- [第1〜13章の統合版PDF](output/pdf/web_textbook_ja.pdf)
- [統合版の生成記録と使用した原稿・図の版](textbook.validation.public.json)
- [統合版の確認記録](TEXTBOOK_VALIDATION.md)

統合版は、現在保存されている全13章の原稿と図生成元から各章を再生成して作る。表紙、移動できる目次、章・節のしおり、通しページ番号を備える。個々の章の原稿が正本であり、更新後は次のコマンドで統合版も更新する。

```powershell
python course/textbook/build/build_textbook.py --date 2026-11-19
```

`--date`には、その版の更新日を指定する。生成記録に全章の原稿・図・PDFのハッシュを保存し、生成中に原稿が変わっていないこと、章の本文が統合後も保持されていることを確認する。

## 章と練習と課題の対応

[教科書と演習を進める順番](../labs/README.md#教科書と演習を進める順番)から、読む章とその直後のP・Mを順に開けます。学習表では章をC（Chapter）で表します。C1は第1章です。

Pは手順付きの練習、Mは別の対象を自分で設定する課題である。P1〜P5とM1〜M5がテーマごとに対応し、P0/M0は共通準備。教科書の章数は演習数とは別である。

| 読む章 | 説明すること | 練習 | 自力課題 |
| --- | --- | --- | --- |
| C1〜C3 | 全体像、AWSのネットワーク、接続と作業場所 | P0 | M0・以後の共通準備 |
| C4〜C5 | HTTPの仕組み、Nginxによる静的配信 | P1 | M1 |
| C6〜C7 | DNSの仕組み、BINDと通常の名前解決 | P2 | M2 |
| C8〜C9 | DBとSQL、PostgreSQLの接続・認証 | P3 | M3 |
| C10〜C11 | Web・アプリ・DBの連携、配置と設定 | P4 | M4 |
| C12 | 公開範囲、最小権限、構築用権限の終了 | P5 | M5 |
| C13 | 運用・保守、ITILに沿った障害対応 | 全Pで参照 | 全Mで参照 |

実際の演習順はP0 → M0 → P1 → M1 → P2 → M2 → P3 → M3 → P4 → P5 → M4 → M5。P4のpractice環境をP5で整理してから、M4のmission環境へ切り替える。各単元の課題が満点になったことを学生が課題画面で確認して次へ進む。別の進行用検査は設けない。

P5を先に行うのは、P4で使った構築用の一時設定を片付けてから、同じアプリをM4の課題用データベースに切り替えるためです。

## 作成済みの本文

- [第1章 Webシステムを構成するもの](docs/ja/01-web-system.md)
- [第1章 閲覧用HTML](output/html/web_textbook_ch01_ja.html)
- [第1章 A4縦PDF](output/pdf/web_textbook_ch01_ja.pdf)
- [第2章 AWS上のネットワークと通信経路](docs/ja/02-network-paths.md)
- [第2章 閲覧用HTML](output/html/web_textbook_ch02_ja.html)
- [第2章 A4縦PDF](output/pdf/web_textbook_ch02_ja.pdf)
- [第3章 サーバーへの接続と作業場所](docs/ja/03-connecting-and-working.md)
- [第3章 閲覧用HTML](output/html/web_textbook_ch03_ja.html)
- [第3章 A4縦PDF](output/pdf/web_textbook_ch03_ja.pdf)
- [第3章：手元のPC・RDP・SSH端末の入れ子の図](assets/figures/ch03-fig01-nested-screen.png)
- [第3章：RDP実画面例の出典とライセンス](assets/third-party/rdp-desktop-example.md)
- [第4章 HTTPでページをリクエストする仕組み](docs/ja/04-http-requests-and-responses.md)
- [第4章 閲覧用HTML](output/html/web_textbook_ch04_ja.html)
- [第4章 A4縦PDF](output/pdf/web_textbook_ch04_ja.pdf)
- [第5章 Nginxによる静的ファイルの配信](docs/ja/05-nginx-static-files.md)
- [第5章 閲覧用HTML](output/html/web_textbook_ch05_ja.html)
- [第5章 A4縦PDF](output/pdf/web_textbook_ch05_ja.pdf)
- [第6章 DNSによる名前解決の仕組み](docs/ja/06-dns-name-resolution.md)
- [第6章 閲覧用HTML](output/html/web_textbook_ch06_ja.html)
- [第6章 A4縦PDF](output/pdf/web_textbook_ch06_ja.pdf)
- [第7章 内部DNSの設定と動作確認](docs/ja/07-internal-dns-configuration.md)
- [第7章 閲覧用HTML](output/html/web_textbook_ch07_ja.html)
- [第7章 A4縦PDF](output/pdf/web_textbook_ch07_ja.pdf)
- [第8章 リレーショナルDBとSQLの基本](docs/ja/08-databases-and-sql.md)
- [第8章 閲覧用HTML](output/html/web_textbook_ch08_ja.html)
- [第8章 A4縦PDF](output/pdf/web_textbook_ch08_ja.pdf)
- [第9章 PostgreSQLの接続と認証](docs/ja/09-postgresql-connections.md)
- [第9章 閲覧用HTML](output/html/web_textbook_ch09_ja.html)
- [第9章 A4縦PDF](output/pdf/web_textbook_ch09_ja.pdf)
- [第10章 WebサーバーとアプリとDBの連携](docs/ja/10-web-app-and-database.md)
- [第10章 閲覧用HTML](output/html/web_textbook_ch10_ja.html)
- [第10章 A4縦PDF](output/pdf/web_textbook_ch10_ja.pdf)
- [第11章 提供アプリの配置と初期設定](docs/ja/11-application-deployment.md)
- [第11章 閲覧用HTML](output/html/web_textbook_ch11_ja.html)
- [第11章 A4縦PDF](output/pdf/web_textbook_ch11_ja.pdf)
- [第12章 公開範囲と最小権限](docs/ja/12-access-and-least-privilege.md)
- [第12章 閲覧用HTML](output/html/web_textbook_ch12_ja.html)
- [第12章 A4縦PDF](output/pdf/web_textbook_ch12_ja.pdf)
- [第13章 運用・保守と障害への対応](docs/ja/13-observation-and-recovery.md)
- [第13章 閲覧用HTML](output/html/web_textbook_ch13_ja.html)
- [第13章 A4縦PDF](output/pdf/web_textbook_ch13_ja.pdf)
- [全体構成図 PNG](assets/figures/fig01-system-overview.png) / [SVG](assets/figures/fig01-system-overview.svg)
- [SSHとRDPの比較図](assets/figures/fig04-ssh-rdp.png)
- [VPC・公開範囲・SGの関係図](assets/figures/fig05-network-boundaries.png)
- [第1章の制作・確認の記録](VALIDATION.md)
- [第2章の制作・確認の記録](CHAPTER02_VALIDATION.md)
- [第3章の制作・確認の記録](CHAPTER03_VALIDATION.md)
- [第4章の制作・確認の記録](CHAPTER04_VALIDATION.md)
- [第5章の制作・確認の記録](CHAPTER05_VALIDATION.md)
- [第6章の制作・確認の記録](CHAPTER06_VALIDATION.md)
- [第7章の制作・確認の記録](CHAPTER07_VALIDATION.md)
- [第8章の制作・確認の記録](CHAPTER08_VALIDATION.md)
- [第9章の制作・確認の記録](CHAPTER09_VALIDATION.md)
- [第10章の制作・確認の記録](CHAPTER10_VALIDATION.md)
- [第11章の制作・確認の記録](CHAPTER11_VALIDATION.md)
- [第12章の制作・確認の記録](CHAPTER12_VALIDATION.md)
- [第13章の制作・確認の記録](CHAPTER13_VALIDATION.md)

第1章はP0/M0のための共通導入であり、第1章だけを読んでM1へ直行する構成ではない。M1に必要なHTTPとNginxの説明は第4〜5章で扱う。

第7〜13章の集計は[制作と自動確認](CHAPTER07_13_VALIDATION.md)を参照する。

## 更新方法

本文は`docs/ja/`の章別Markdown、図とHTML/PDFの生成元は`build/build_chapter01.py`〜`build/build_chapter13.py`。第7〜13章の図は`build/chapter_figures_07_13.py`で管理する。表示用の共通処理は第1章の生成元に置き、各章は自分の原稿・図・出力を指定して生成する。コマンド例は実行場所を本文で示し、改行を保った独立した枠へ出力する。Python 3とPillow・ReportLab・pypdf、および日本語フォントを使う。フォントは同梱しない。

```powershell
python course/textbook/build/build_chapter01.py
python course/textbook/build/build_chapter02.py
python course/textbook/build/build_chapter03.py
python course/textbook/build/build_chapter04.py
python course/textbook/build/build_chapter05.py
python course/textbook/build/build_chapter06.py
python course/textbook/build/build_chapter07.py
python course/textbook/build/build_chapter08.py
python course/textbook/build/build_chapter09.py
python course/textbook/build/build_chapter10.py
python course/textbook/build/build_chapter11.py
python course/textbook/build/build_chapter12.py
python course/textbook/build/build_chapter13.py
```

`JDU_FONT_SANS`と`JDU_FONT_SERIF`で日本語TrueTypeフォントを指定できる。既定はWindowsのNoto Sans JP / Noto Serif JP。出力は同じ最新版ファイルを更新する。
