# PlcGateway_v3

三菱PLC（Ethernet/IP, MCプロトコル）とMQTTブローカーを橋渡しするPythonゲートウェイです。
PLCから読み取ったモーターのテレメトリ（回転方向・電流・回転数）をMQTTへ配信し、MQTT経由で受信したコマンド（RUN/STOP/周波数変更/方向変更）をPLCへ書き込みます。

（READMEはAI生成したものを加筆修正した．設計とコーディングは自作．ただし，コードレビューとデバッグ作業の一部はAIを使いました）

---

## 1. 導入方法（uv）

このプロジェクトは [uv](https://docs.astral.sh/uv/) でパッケージ・依存関係を管理しています。

```bash
# リポジトリを取得
git clone <https://github.com/toshi0515/PlcGateway-v3.git>
cd PlcGateway-v3

# 依存関係をインストール（仮想環境も自動で作成されます）
uv sync
```

### 設定ファイルの用意

プロジェクトルートに `config.yaml` を作成してください（`main.py` から見て2階層上のディレクトリです）。

```yaml
mq_host: "127.0.0.1"
mq_port: 1883
plc_host: "192.168.3.250"
plc_port: 10000
read_interval_ms: 500
```

| キー | 説明 |
|---|---|
| `mq_host` / `mq_port` | MQTTブローカーの接続先 |
| `plc_host` / `plc_port` | PLC（Ethernet/IP）の接続先 |
| `read_interval_ms` | PLCポーリング周期（ミリ秒） |

設定ファイルが存在しない、または値が不正な場合は、起動時にエラーログを出してプログラムが終了します。

### 実行

```bash
uv run plcgateway
```

終了する場合は `Ctrl+C` を押してください。PLC・MQTTの接続を後片付けしてから終了します。

---

## 2. 機能と使い方

### 2.1 PLC → MQTT（テレメトリ配信）

`read_interval_ms` の周期でPLCのD1000〜D1006を読み取り、以下の内容をMQTTトピック `ARMotorSystem/data` へJSON形式で配信します。

```json
{
  "timestamp": "2026-09-19T12:34:56.789000+00:00",
  "rotate_dir": 1,
  "rotation": 3000,
  "current": 150
}
```

PLCとの通信が一時的に失敗した場合は、その回の配信をスキップして次の周期に進みます（プログラムは継続します）。

### 2.2 MQTT → PLC（コマンド制御）

MQTTトピック `ARMotorSystem/cmd` を購読しており、以下のJSONコマンドを受け付けます。

| コマンド | JSON例 | パラメータ | 省略時 |
|---|---|---|---|
| RUN | `{"command":"RUN","frequency":30,"direction":1}` | frequency (0-120), direction (0/1) | frequency=30, direction=0 |
| STOP | `{"command":"STOP"}` | なし | - |
| SET_FREQUENCY | `{"command":"SET_FREQUENCY","frequency":45}` | frequency (0-120, 必須) | 省略時は処理をスキップ |
| SET_DIRECTION | `{"command":"SET_DIRECTION","direction":0}` | direction (0/1, 必須) | 省略時は処理をスキップ |

不正なJSON・未知のコマンド・範囲外の値・必須パラメータの欠落は、ログに記録した上で処理をスキップします（プログラムは継続します）。

一方、**PLCへの書き込み自体が失敗した場合はプログラムを終了します**（モーターの実際の状態と操作意図がズレたまま気づかれないことを防ぐための設計です）。ログを確認し、PLCとの接続状況を確認したうえで再起動してください。

### 2.3 動作確認（mosquittoクライアントの例）

```bash
# テレメトリを購読
mosquitto_sub -h 127.0.0.1 -t "ARMotorSystem/data" -v

# RUNコマンドを送信
mosquitto_pub -h 127.0.0.1 -t "ARMotorSystem/cmd" \
  -m '{"command":"RUN","frequency":30,"direction":1}'

# STOPコマンドを送信
mosquitto_pub -h 127.0.0.1 -t "ARMotorSystem/cmd" -m '{"command":"STOP"}'
```

---

## 3. 拡張方法

### 3.1 PLCデバイス番地を変更・追加する場合

PLCデバイス番地は設定ファイル(`config.yaml`)ではなく、**`plc.py` にハードコードされています**。

- **読み取り側**：`PlcController.read_telemetry()` 内の `batchread_wordunits(headdevice="D1000", readsize=7)` が読み取り範囲です。続くタプルのアンパック `_, _, rotate_dir, _, _, current, rotate_speed = data` が、読み取った7個の値と意味の対応関係を表しています（何番目の値が何を意味するかは、その直前のコメントに番地一覧があります）。デバイス番地を変える場合はこの2箇所を、読み取り項目を増やす場合はこれに加えて `TelemetryDTO` にフィールドを追加してください。
- **書き込み側**：`write_motor_run` / `write_motor_stop` / `write_motor_dir` / `write_freq` の各メソッド内で、`batchwrite_wordunits(headdevice="D100x", values=[...])` として番地を直接指定しています。番地を変える場合はこの引数を書き換えてください。

### 3.2 コマンドを追加する場合

コマンド名とその処理（ハンドラー）の対応は、`commands.py` の `CommandDispatcher.__init__` 内の `cmd_dict` で定義されています。

```python
self.cmd_dict = {
    "RUN": self.run_cmd,
    "STOP": self.stop_cmd,
    "SET_FREQUENCY": self.set_freq_cmd,
    "SET_DIRECTION": self.ser_dir_cmd,
}
```

新しいコマンドを追加する手順：

1. `CommandDispatcher` に新しいメソッド（例：`reset_cmd`）を追加し、必要なパラメータの検証と `PlcController` の対応メソッド呼び出しを実装する
2. `PlcController`（`plc.py`）に、対応するPLC書き込みメソッドを追加する（3.1の書き込み側と同じ要領）
3. 新しいパラメータを受け取る場合は `CommandDTO` にフィールドを追加する
4. `cmd_dict` に `"新コマンド名": self.reset_cmd` を追加する

これだけで、`mqtt.py` や `main.py` を変更する必要はありません。

### 3.3 設定項目を増やす場合

`config.py` の `Config` クラス（pydanticモデル）にフィールドを追加し、`config.yaml` にも対応するキーを追加してください。型が不正な場合は自動的に検証エラーとなり、起動時に分かりやすいログを出して終了します。

---

## 4. プロジェクト構成

```
plcgateway_v3/
├── main.py       # エントリポイント・全体の配線・ポーリングループ
├── config.py     # 設定ファイル(config.yaml)の読み込み・検証
├── plc.py        # PLC通信（pymcprotocol）・テレメトリDTO
├── mqtt.py       # MQTT通信（paho-mqtt）・トピック定義
├── commands.py   # コマンドディスパッチ・コマンドDTO
tests/
└── test_commands.py  # commands.py のユニットテスト
config.yaml       # 接続先・ポーリング周期の設定（各自作成）
```

## 5. テスト

```bash
uv run pytest
```

`commands.py` のコマンド処理ロジックについて、モック化した `PlcController` を使ったユニットテストを用意しています。