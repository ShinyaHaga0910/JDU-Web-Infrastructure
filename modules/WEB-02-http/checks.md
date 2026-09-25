# WEB-02 確認項目

| ID | 確認 | 判定の根拠 | 状態 |
| --- | --- | --- | --- |
| WEB02-C1 | 配布fileが指定pathにある | file名、内容、permission | Lab未確定 |
| WEB02-C2 | Nginxがactive | systemdの状態 | 実機未確認 |
| WEB02-C3 | 想定address・portで待受 | `ss`とNginx設定 | 実機未確認 |
| WEB02-C4 | Ubuntu自身から意図した内容が返る | HTTP statusと本文 | 実機未確認 |
| WEB02-C5 | 指定clientから到達する | client側のstatusと本文 | 経路未確定 |
| WEB02-C6 | 不要な送信元から到達しない | 許可・拒否の設定と負試験 | 経路未確定 |
| WEB02-C7 | requestのlogを示せる | 時刻・path・status | 実機未確認 |

自動checkerは状態を読み取り、設定を変更しない。公開範囲・到達経路を決めるWEB-01完成後に実装します。状態のPASSだけで理由の理解を判定しません。
