# RDP接続時のキー配列と確認手順

更新: 2026-10-16。テスト２の実機確認で、キー配列の違いによるLogin failedを本人が確認し、配列を合わせた後にデスクトップとFirefoxの起動まで成功した。日本語配列から英語配列へ変わった等の具体的な方向・キーは未記録。特定の変換が全PCで起こるとは決めつけない。

10/16の停止・再開検証後、テスト２の踏み台の現在IPv4は **34.229.52.188**。旧54.204.57.192から変更。passwordとCIDR制限は維持。次回も現在IPを確認する。

## Windowsからの接続

1. Windowsキー＋Rから`mstsc`を開く。接続先はそのLabの踏み台の**現在の公開IPv4**を使う。停止・起動で変わる場合がある。
2. ユーザー名は`labuser`。Windowsアカウント名、ubuntu、ドメイン付きの名前と混同しない。
3. Lab専用のRDP passwordを入力する。Session選択がある場合はXorgを使う。
4. デスクトップが開いたらFirefoxを起動する。接続成功だけでbrowserも受入済みとは扱わない。

Windowsの資格情報画面を明示する場合は`mstsc /v:<現在の公開IPv4> /prompt`を使う。`/prompt`だけで全PCのキー配列問題が必ず解決するとは保証しない。

## Login failedになった場合

- 入力中のキーボード配列とCaps Lockを確認する。特に記号は、キーに印刷された文字と送信される文字が違う場合がある。
- 配列確認は秘密でない文字列で行う。passwordを見える欄、会話、スクリーンショット、共有メモへ入力しない。
- 青いxrdp画面まで到達し、`sesman connect ok`の後に`login failed for user labuser`が出る場合は、接続経路は通っている。入力値・アカウント・認証ログを切り分ける。
- 繰り返し失敗しただけでpasswordを変更したり、RDPのCIDR制限を広げたりしない。必要に応じて教員が認証記録を確認する。

## 本検証で確認した範囲

2026-10-16、本人操作でキー配列差が原因と判明し、デスクトップ・Firefoxの実表示に成功。サーバー側の診断でも設定済みpassword hashは配備値と一致し、labuserのロック・期限切れはなかった。passwordの変更や認証制御の緩和はしていない。

RDPのpasswordと、内部SSH用秘密鍵、アプリ管理者、DB、採点登録の認証情報は用途が異なる。RDP/Firefox成功は内部4台へのSSH・採点登録の成功を意味しない。

Windows標準の接続clientの一次資料：[Microsoft mstsc](https://learn.microsoft.com/windows-server/administration/windows-commands/mstsc)。
