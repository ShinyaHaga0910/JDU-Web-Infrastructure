# Webインフラストラクチャー教科書

後半授業の教科書。現在は日本語第1章の本文骨子を作成し、他章は[章・節の設計](../textbook-outline.md)に説明内容を定めている。文章は教員が編集しやすい章別Markdownを正本とする。OS・Linux教材の説明形式をそのまま踏襲することを優先せず、全体像・各部の役割・実作業とのつながりを分かりやすく示す。

## 章と練習と課題の対応

Pは手順付きの練習、Mは別の対象を自分で設定する課題である。P1〜P6とM1〜M6はそれぞれ6つあり、P0/M0は共通準備。教科書の章数は演習数とは別である。

| 読む章 | 説明すること | 練習 | 自力課題 |
| --- | --- | --- | --- |
| 第1〜3章 | 全体像、AWSのネットワーク、接続と作業場所 | P0 | M0・以後の共通準備 |
| 第4〜5章 | HTTPの仕組み、Nginxによる静的配信 | P1 | M1 |
| 第6〜7章 | DNSの仕組み、BINDと通常の名前解決 | P2 | M2 |
| 第8章 | 保存領域、停止と再開後の保持 | P3 | M3 |
| 第9〜10章 | DBとSQL、PostgreSQLの接続・認証 | P4 | M4 |
| 第11〜12章 | Web・アプリ・DBの連携、配置と設定 | P5 | M5 |
| 第13章 | 公開範囲、最小権限、構築用権限の終了 | P6 | M6 |
| 第14章 | 観測、障害の切り分けと復旧 | 全Pで参照 | 全Mで参照 |

実際の演習順はP0 → M0 → P1 → M1 → P2 → M2 → P3 → M3 → P4 → M4 → P5 → P6 → M5 → M6。P5のpractice環境をP6で整理してから、M5のmission環境へ切り替える。各単元の課題が満点になったことを学生が課題画面で確認して次へ進む。別の進行用検査は設けない。

通常のP→Mの交互順に対し、現行のP5/P6は例外となる。同じアプリを共用しており、practice側の一時setup設定がある状態ではmissionへ切り替えられないため、P6の終了処理を先に行う。P5→M5→P6→M6へ変更する場合は終了処理とprofile切替の手順・実装を合わせて修正する必要があり、対応表の順序だけを入れ替えない。

## 作成済みの本文

- [第1章 Webシステムを構成するもの](docs/ja/01-web-system.md)
- [第1章 閲覧用HTML](output/html/web_textbook_ch01_ja.html)
- [第1章 A4縦PDF](output/pdf/web_textbook_ch01_ja.pdf)
- [全体構成図 PNG](assets/figures/fig01-system-overview.png) / [SVG](assets/figures/fig01-system-overview.svg)
- [制作・確認の記録](VALIDATION.md)

第1章はP0/M0のための共通導入であり、第1章だけを読んでM1へ直行する構成ではない。M1に必要なHTTPとNginxの説明は第4〜5章で扱う。

## 更新方法

本文は`docs/ja/01-web-system.md`、図とHTML/PDFの生成元は`build/build_chapter01.py`。Python 3とPillow・ReportLab・pypdf、および日本語フォントを使う。フォントは同梱しない。

```powershell
python course/textbook/build/build_chapter01.py
```

`JDU_FONT_SANS`と`JDU_FONT_SERIF`で日本語TrueTypeフォントを指定できる。既定はWindowsのNoto Sans JP / Noto Serif JP。出力は同じ最新版ファイルを更新する。
