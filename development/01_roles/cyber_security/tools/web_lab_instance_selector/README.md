# Web LabのT系インスタンスとAZの選定

EC2起動前に、AWS CLIの読取り照会と価格比較を行うPython3 script。AWS資源の作成・削除・起動・停止は行わない。CloudFormation本体への組込みとLearner Lab実機受入は残件。

mediumの踏み台1台、smallのWeb/DB/repo3台、microのDNS1台を、同じT系family・同じAZで起動できる組合せから選ぶ。amd64互換、HVM/EBS、memory/CPUの条件をmetadataで確認し、Linux/Shared/On-Demandの5台合計額が最安のものを出力する。世代番号やfamily名から価格を推測しない。

## 使用

学生PCまたはAWS CloudShell等の、AWS CLIとPython3・Lab認証がある場所で実行する。EC2内のinstall.shは、選定後の初期化を担当する。

```bash
python3 select_instances.py --region us-east-1 --output new-plan.json
```

読取りAPIはDescribeInstanceTypes、DescribeAvailabilityZones、DescribeInstanceTypeOfferings、Pricing GetProducts。Pricing APIのendpointはus-east-1、価格商品のregionCodeは対象regionを指定する。AWS CLIの自動paginationを使用する。

LabでPricing APIが許可されない場合は、教員がAWS Price Listから取得した価格台帳を渡す。台帳のregion/USD/取得日時を検査し、7日超・未来日・候補の価格欠品は停止する。価格取得失敗を理由に固定T3や世代順へ切り替えない。

`collect_price_catalog.py --output NEW-CATALOG.json --evidence NEW-ROWS.json` はus-east-1のAWS公式CSVから新しい台帳と根拠行を作る。全取得bytes/SHA、公開日、Linux/Shared/OnDemand/Hrs/USD/適用日/同typeの矛盾価格を検査し、既存fileは上書きしない。T系全価格の収集と、実AWS提供・architecture・micro/small/mediumが揃うfamily/AZの選定は別の段階。台帳を新しくしても署名済みarchive内の古い台帳を書き換えず、外部の新fileを--price-catalogで明示する。

```bash
python3 select_instances.py --price-catalog teacher-prices.json --output new-plan.json
```

台帳形式（価格部分は教員が実際に取得した値を記入。例示価格を本番へ転用しない）:

```json
{
  "region": "us-east-1",
  "currency": "USD",
  "source": "AWS Price List",
  "collected_at": "<timezone付き取得日時>",
  "prices": {"<instance type>": "<USD/h>"}
}
```

結果のcloudformation_parametersにLabAvailabilityZoneと5役割のInstanceTypeを出力する。ranked_candidatesは安い順のfamily/AZ候補一覧。memory/CPU/価格は選定結果を保存し、個々のLabでfamilyが違っても教材の役割・size・設定項目を揃える。

## 既存環境と起動失敗

既存Stackの更新・通常再開では、実際のAZ/typeと保存済みplanの一致を配備script側で確認し、次の形式で再利用する。今回のselector単体はStack照合・配備を行わない。

```bash
python3 select_instances.py --existing-plan deployed-plan.json --output reused-plan.json
```

既存planの再利用は価格/APIを再照会しない。出力先に既存fileがあれば上書きしない。

提供されていても、その瞬間の容量・Labの起動権限は保証されない。容量不足を確認した新規配備では、失敗したfamily/AZを除外して次候補を得られる。Unauthorized/AccessDeniedだけでfamilyの拒否と断定せず、教員が確認したtype制限だけをfamily除外へ反映する。session切れ・quota・AMI・network/初期化失敗ではtypeを自動変更しない。

```bash
python3 select_instances.py --exclude-pair t3a@us-east-1a --output retry-plan.json
```

このcommandは失敗Stackを操作しない。配備側の再試行は初回の空の環境だけを対象に上限3候補とし、成功済み資源がある場合のlog保存と再配置・削除は別手順で扱う。既存の学生設定やDBがある環境を安いAZへ自動移動しない。

## 検証

```bash
python3 -m unittest discover -s . -p 'test_*.py' -v
```

offlineの価格/AZ/architecture/既存plan検証を行う。--snapshotは同じ入力形のテストJSON専用で、AWS起動可能の根拠にはしない。AWS実照会、CloudFormationのparameter連携、起動失敗からの再試行は未検証。

設計の正本: [D10の資源と運用](../../system_requirements/2026-10_web_infrastructure_aws_operations_design.md)。AWS APIの一次資料は同設計の選定節を参照。
