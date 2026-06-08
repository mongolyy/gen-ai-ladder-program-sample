# examples — ladder-gen の成果物サンプル

スキルが各工程で生成する中間成果物の完成例。

## motor-fwd-rev（モータ正逆運転制御）

自然言語仕様:
> 正転ボタンで正転、逆転ボタンで逆転。停止ボタンで停止。
> 正転と逆転は同時に ON しない。非常停止で全停止。運転中はランプ点灯。

| ファイル | 工程 | 内容 |
|----------|------|------|
| `01_structured_spec.yaml` | ② | 構造化仕様（I/O・インターロック・安全・前提） |
| `02_device_master.csv` | ③ | デバイス/ラベル割付表 |
| `03_program.st` | ④ | 生成された ST ソース |
| `04_static_check.txt` | ⑤ | 静的チェック結果（ERROR 0） |
| `06_ladder_view.txt` | ⑥ | ST から変換したラダー図ビュー（レビュー補助） |
| `gxw3_global_labels.csv` | ⑦ | GX Works3 取り込み用グローバルラベル CSV |
| `gxw3_device_comments.csv` | ⑦ | GX Works3 取り込み用デバイスコメント CSV |
| `gxw3_program.st` | ⑦ | GX Works3 取り込み用 ST |

### 静的チェックを再実行する

```bash
python3 ../scripts/static_check.py \
  --st motor-fwd-rev/03_program.st \
  --devices motor-fwd-rev/02_device_master.csv \
  --spec motor-fwd-rev/01_structured_spec.yaml \
  --report motor-fwd-rev/04_static_check.txt
```

### 設計のポイント

- 正転/逆転とも自己保持 + 相互排他（`AND NOT MOTOR_REV` / `AND NOT MOTOR_FWD`）で
  正逆同時 ON を物理的に作れないようにしている（インターロック C004 を満たす）。
- `ESTOP` は B 接点。式中で `AND ESTOP`（正常時 TRUE）を運転許可条件に入れている。
- 各出力は 1 箇所のみで代入し、二重コイル（C001）を避けている。

### ラダー図ビューを生成する

```bash
python3 ../scripts/ladder_view.py \
  --st motor-fwd-rev/03_program.st \
  --out motor-fwd-rev/06_ladder_view.txt
```

## conveyor-seq（コンベア起動シーケンス：状態遷移のデモ）

自然言語仕様:
> 起動ボタンで搬送開始。停止ボタンまたは非常停止で停止処理へ。
> 停止処理が終わったら待機へ戻る。非常停止(B接点)で全停止。

| ファイル | 工程 | 内容 |
|----------|------|------|
| `01_structured_spec.yaml` | ② | 状態（IDLE/RUNNING/STOPPING）と遷移を含む構造化仕様 |
| `02_device_master.csv` | ③ | 状態変数 STATE を含むデバイス割付表 |
| `03_state_machine.st` | ④ | 状態遷移から生成した CASE 状態機械 ST |

### 状態機械 ST を再生成する

```bash
python3 ../scripts/gen_state_machine.py \
  --spec conveyor-seq/01_structured_spec.yaml \
  --state-var STATE \
  --out conveyor-seq/03_state_machine.st
```

CASE の各ケースで `STATE` に代入しているが、静的チェッカーはケース分岐を相互排他と
認識するため二重コイル（C001）にはならない。
