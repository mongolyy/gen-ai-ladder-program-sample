# 生成サンプル: コンベア起動制御（conveyor_start）

`ladder-gen` スキルで、自然言語の制御仕様から ST（構造化テキスト）を生成した一連の
中間成果物のサンプル。各工程のゲートを通過した結果をそのまま収録している。

> 通常、これらの成果物は `out/<案件名>/` に出力され `.gitignore` で除外される。
> ここではスキルの入出力を示す**サンプルとして** `examples/` に永続化している。

## 題材

1本のベルトコンベアを押しボタンで起動/停止する制御。自己保持方式、状態遷移なし。

- 起動/停止ボタンで運転（自己保持）
- 非常停止（B接点・フェイルセーフ）が最優先
- 出口ワーク検出センサで**一時停止**（除去で自動再開。運転フラグは保持）

## 生成された ST（本体）

```st
M_RUNNING      := (START_PB OR M_RUNNING) AND NOT STOP_PB AND ESTOP;
CONVEYOR_MOTOR := M_RUNNING AND ESTOP AND NOT WORK_SENS;
RUN_LAMP       := M_RUNNING;
```

## ファイル一覧

| ファイル | 工程 | 内容 |
|---|---|---|
| `01_structured_spec.yaml` | ② 構造化仕様 | I/O・内部リレー・インターロック・安全要件・前提 |
| `02_device_master.csv` | ③ デバイス割付 | ラベル ↔ 物理アドレス（採番案） |
| `03_program.st` | ④ ST 生成 | ST 本体（正） |
| `04_static_check.txt` | ⑤ 静的チェック | ERROR 0 / WARN 0 |
| `05_review_notes.md` | ⑥ レビュー観点 | 人間レビュー用チェックリストと前提確認 |
| `06_ladder_view.txt` | 補助 | ST からの ASCII ラダー図ビュー |
| `gxw3_global_labels.csv` | ⑦ GX Works3 連携 | グローバルラベル一括取り込み用（BOM付UTF-8） |
| `gxw3_device_comments.csv` | ⑦ GX Works3 連携 | デバイスコメント取り込み用 |
| `gxw3_program.st` | ⑦ GX Works3 連携 | ST POU 貼り付け用 |
| `scenario.yaml` | シミュレーション | 4シーンの入力シナリオ（起動/停止/一時停止/非常停止） |
| `07_timing_chart.png` | シミュレーション | タイミングチャート（PNG） |
| `07_timing_chart_ascii.txt` | シミュレーション | タイミングチャート（ASCII テキスト） |
| `07_sim_log.txt` | シミュレーション | スキャンサイクルシミュレーションログ |

## タイミングチャート概要

`scenario.yaml` に定義した 4 シーンのシミュレーション結果。

| Cycle | イベント |
|-------|---------|
| 3     | START_PB → コンベア起動（自己保持） |
| 20    | STOP_PB → 通常停止 |
| 25    | START_PB → 再起動 |
| 32    | WORK_SENS=ON → CONVEYOR_MOTOR 停止 / **M_RUNNING・RUN_LAMP は保持** |
| 38    | WORK_SENS=OFF → CONVEYOR_MOTOR 自動再開 |
| 45    | ESTOP=FALSE → 非常停止（全出力 OFF） |
| 46    | ESTOP=TRUE（解除）← M_RUNNING=OFF のまま・自動復帰なし |
| 50    | START_PB → 手動再起動 |

## 再現方法

```bash
# 工程⑤ 静的チェック
python3 .claude/skills/ladder-gen/scripts/static_check.py \
  --st 03_program.st --devices 02_device_master.csv \
  --spec 01_structured_spec.yaml --report 04_static_check.txt

# 補助 ラダー図ビュー
python3 .claude/skills/ladder-gen/scripts/ladder_view.py \
  --st 03_program.st --out 06_ladder_view.txt

# 工程⑦ GX Works3 取り込みファイル
python3 .claude/skills/ladder-gen/scripts/export_gxworks3.py \
  --devices 02_device_master.csv --st 03_program.st \
  --labels gxw3_global_labels.csv --comments gxw3_device_comments.csv \
  --out-st gxw3_program.st

# シミュレーション（要 pyyaml, matplotlib）
python3 .claude/skills/ladder-gen/scripts/simulate.py \
  --st 03_program.st --devices 02_device_master.csv \
  --scenario scenario.yaml \
  --chart 07_timing_chart.png --log 07_sim_log.txt
```
