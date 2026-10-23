# Web演習のRDP接続元（2026-10-15更新）

RIPE Databaseの組織逆引きでUztelecom/IST Telecomの10 ASNを再確認し、RIPEstat RISの2026-10-15 00:00 UTC観測からoriginating IPv4だけを取得した。個人の連絡先情報は収録しない。

- Uztelecom: 142 prefix → 34 CIDR、77,824 IPv4。
- IST Telecom: 26 prefix → 16 CIDR、42,240 IPv4。
- 合計50 CIDR、120,064 IPv4。全アドレス集合の一致を検査し、近似による範囲拡張はない。
- 2026-10-13の許可範囲と同じ集合。組織・ASN・観測元URLはJSONに保存した。
- この一覧はRDP 3389の接続元限定用。SSH、採点受付、AWS全般の許可には転用しない。

取得処理: `01_roles/cyber_security/tools/web_lab_bootstrap/refresh_rdp_allowlist.py`。AWS認証なしの公開HTTPS照会をChromeのCloudShellから実行した。
