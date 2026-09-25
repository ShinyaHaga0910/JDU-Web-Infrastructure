# WEB-02 症状からの確認

| 症状 | 最初に分けること | 観測対象 |
| --- | --- | --- |
| Ubuntu自身でも応答しない | Nginxが待っているか | service、listen port、error log |
| HTTP 404 | requestのpathと配置したfileが一致するか | Web root、file名、Nginx設定、access log |
| HTTP 403 | file・directoryをNginxが読めるか | permission、Nginx error log |
| Ubuntu自身では成功、別clientでは失敗 | 接続経路・送信元の許可があるか | IP、route、Security Group、OS側の待受address |
| 接続はあるが意図しない内容 | 違うfileやserver blockへ到達していないか | Host header、設定、返ってきた本文、log |

確認は症状に合わせて選びます。エラーが出たからすぐ再起動するのではなく、現在の状態とlogを先に保存します。安全な演習対象以外へ通信試験を行いません。
