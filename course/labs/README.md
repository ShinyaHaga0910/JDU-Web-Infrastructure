# Web演習：練習P・課題M

サーバーを自分で設定し、ブラウザで結果を確認する演習です。
**C（Chapter）は教科書の章、P（Practice）は手順付きの練習、M（Mission）は自分で取り組む課題**です。

## 言語を選ぶ

| 言語 | 練習P0〜P6 | 自力課題M0〜M6 |
| --- | --- | --- |
| 日本語 | [練習の一覧](docs/ja/practice.md) | [課題の一覧](docs/ja/missions.md) |
| Русский | [Практика P](docs/ru/practice.md) | [Задания M](docs/ru/missions.md) |
| O‘zbekcha | [P mashqlar](docs/uz/practice.md) | [M topshiriqlar](docs/uz/missions.md) |

P3/M3は欠番です。DNSからDBへ進みます。

## 教科書と演習を進める順番

環境構築の案内に従って、自分の演習環境を用意します。共通登録コードを使う場合は[学生用スクリプト](../../README.md#学生側のコマンド)、署名付き配布を使う場合は[初回構築の手順](INITIAL-WORKFLOW.md)を参照してください。

PとMは、同じ演習環境の5台を使います。練習で導入したソフトウェアや設定は後の課題でも使い、配信ファイルやDNSの名前、データベースなど、課題で指定された対象を設定します。P5では備品管理アプリを練習用DBにつなぎ、P6で練習用の構築権限を片付けてから、M5で同じアプリを課題用DBにつなぎます。M6で課題用の権限と公開範囲を仕上げます。

MではPで練習した操作を、課題で指定されたファイル名・DNS名・DB・ロールなどに適用します。M4のDB名での接続はP4.7で、M5のアプリ停止と接続設定の切り替えはP6.3で先に練習します。

表を上から順に進めます。各行で教科書を先に読み、その行のP・Mに取り組みます。点数のあるMは、授業の課題画面で表の点数に達したことを確認してから次に進みます。

| 学ぶテーマ | 先に読む教科書 | 次に取り組む演習 | 課題画面で確認する点数 |
| --- | --- | --- | --- |
| システムの全体像と接続 | [C1 Webシステムの構成](../textbook/docs/ja/01-web-system.md)<br>[C2 AWSのネットワークと通信経路](../textbook/docs/ja/02-network-paths.md)<br>[C3 サーバーへの接続と作業場所](../textbook/docs/ja/03-connecting-and-working.md) | [P0 環境と実行場所](#p0-共通登録コード方式で接続を練習する) → [M0 環境と実行場所](docs/ja/m0.md) | 授業で案内 |
| HTTPでファイルを配信する | [C4 HTTPの仕組み](../textbook/docs/ja/04-http-requests-and-responses.md)<br>[C5 Nginxで静的ファイルを配信](../textbook/docs/ja/05-nginx-static-files.md) | [P1](docs/ja/p1.md) → [M1](docs/ja/m1.md) | 8/8 |
| DNSで名前を解決する | [C6 DNSによる名前解決](../textbook/docs/ja/06-dns-name-resolution.md)<br>[C7 内部DNSの設定と動作確認](../textbook/docs/ja/07-internal-dns-configuration.md) | [P2](docs/ja/p2.md) → [M2](docs/ja/m2.md) | 13/13 |
| PostgreSQLの接続と認証 | [C8 リレーショナルDBとSQL](../textbook/docs/ja/08-databases-and-sql.md)<br>[C9 PostgreSQLの接続と認証](../textbook/docs/ja/09-postgresql-connections.md) | [P4](docs/ja/p4.md) → [M4](docs/ja/m4.md) | 9/9 |
| 提供アプリを練習用DBへ接続する | [C10 Web・アプリ・DBの連携](../textbook/docs/ja/10-web-app-and-database.md)<br>[C11 提供アプリの配置と初期設定](../textbook/docs/ja/11-application-deployment.md) | [P5](docs/ja/p5.md) | — |
| 練習環境の公開範囲と権限を整える | [C12 公開範囲と最小権限](../textbook/docs/ja/12-access-and-least-privilege.md) | [P6](docs/ja/p6.md) | — |
| 提供アプリを自力課題用DBへ接続する | 必要な箇所をC10・C11で読み返す | [M5](docs/ja/m5.md) | 13/13 |
| 自力課題の公開範囲と権限を仕上げる | 必要な箇所をC12で読み返す | [M6](docs/ja/m6.md) | 16/16 |
| 運用・保守と障害への対応 | [C13 運用・保守と障害への対応](../textbook/docs/ja/13-observation-and-recovery.md) | M6の後に読みます。演習中にエラーが出たときも参照できます。 | — |

M1・M2・M4・M5・M6の自動採点は計**59素点**です。授業の配点は教師の案内に従ってください。

### C1 → C2 → C3 → P0 → M0の進め方

C1では備品管理システムの全体像と5台の役割をつかみます。C1の「練習・課題1」は、後でP1・M1で構築するWeb配信の予告です。C2では、Windowsから踏み台の公開IPへRDPでつなぐ経路と、踏み台からWebの内部IPへSSHでつなぐ経路に注目します。C3では、RDP・内部SSH・SSMで、それぞれどの端末とユーザーを使うのかを確認します。

#### P0 共通登録コード方式で接続を練習する

学生用スクリプトが完了したら、以下の接続練習を始めます。スクリプトがLab IDを自動で発行し、教材の配置と採点先への登録を済ませます。

1. [P0.1](docs/ja/p0.md#p01-5台のinstance-idを記録する)で、自分の5台と各インスタンスIDを照合します。
2. [P0.5](docs/ja/p0.md#p05-rdpで踏み台のデスクトップを開く)で、Windowsから踏み台のデスクトップにRDPで入り、ユーザー名 `labuser` と操作場所を確認します。
3. 踏み台のデスクトップ内で端末を開き、`lab-ssh web` を実行します。接続後の `id -un` は `ubuntu`、`hostname -I` にはWebの内部IP `10.20.1.20` が表示されます。
4. [P0.2](docs/ja/p0.md#p02-ssmで入り戻る)に沿って、学生用CloudShellからWebへSSM接続します。ユーザー `ssm-user` とサーバーの役割 `web` を確認します。P1の設定作業でもこの経路を使います。

[M0](docs/ja/m0.md)では、P0で練習したWebサーバーへの接続を応用します。EC2の一覧から自分のDBサーバーを選び、SSMで接続して、役割が db、操作ユーザーが ssm-user であることを確認します。教師が課題画面を案内したら、P0.4とM0を画面でも確認します。共通登録コード方式のウォークスルーで課題画面の接続設定がこれからの場合は、P0の接続確認を済ませてC4・C5へ進み、P1の設定作業に入れます。

[署名付き配布方式のP0](docs/ja/p0.md)を使う場合は、P0.3で後の演習に使う教材ファイルをWebサーバーとDBサーバーに配置します。共通登録コード方式では、環境構築時にその2台へ配置されます。

各Pでは、実行場所・目的・操作・設定の意味・期待結果・困ったときの確認先を順に読みます。
Mには完成要件と採点条件を載せています。

コマンドの直前には、`# 1. …` のように操作の目的と番号を付けています。
番号はP1.2などの各手順内で振り直します。psql内では`-- 1. …`を使い、設定ファイルに書く本文とは区別しています。
各P/Mの図は、設定対象と通信経路を示します。

**SGはCloudFormationで初期設定済みです。現行P/Mの採点対象はサーバー内の設定で、SGを学生が変更する採点課題は含みません。**

## 一冊で読む・ダウンロードする

| 言語 | 練習の通読版 | 課題の通読版 |
| --- | --- | --- |
| 日本語 | [Markdown](docs/ja/practice-full.md) / [PDF](output/pdf/web_lab_practice_ja.pdf) | [Markdown](docs/ja/missions-full.md) / [PDF](output/pdf/web_lab_missions_ja.pdf) |
| Русский | [Markdown](docs/ru/practice-full.md) / [PDF](output/pdf/web_lab_practice_ru.pdf) | [Markdown](docs/ru/missions-full.md) / [PDF](output/pdf/web_lab_missions_ru.pdf) |
| O‘zbekcha | [Markdown](docs/uz/practice-full.md) / [PDF](output/pdf/web_lab_practice_uz.pdf) | [Markdown](docs/uz/missions-full.md) / [PDF](output/pdf/web_lab_missions_uz.pdf) |

[教材zipをダウンロード](output/web-lab-pm-r1.zip)して展開すると、`output/html/index.html`からHTML版をローカルで読めます。
GitHub上では上のMarkdownリンクを使ってください。HTMLファイルのGitHubページはソースコード表示になります。

## 教師用情報

課題の確認には、教師がそのクラスに案内した課題画面を使います。学生Labの停止中は、新しい実機確認を実行できません。

- [教師の事前準備・原稿と生成方法](TEACHER-NOTES.md)
- [確認済みの範囲と残件](VALIDATION.md)

初回構築からブラウザP1/M1・成績原本保存までの指定環境での受入は完了しています。
全43手順の学生試読、ロシア語・ウズベク語の母語校閲、教師の教材承認は未実施です。
