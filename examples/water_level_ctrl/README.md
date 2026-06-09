# 生成サンプル: 水位制御（water_level_ctrl）

`ladder-gen` スキルで、自然言語の制御仕様から ST（構造化テキスト）を生成した一連の
中間成果物のサンプル。各工程のゲートを通過した結果をそのまま収録している。

> 通常、これらの成果物は `out/<案件名>/` に出力され `.gitignore` で除外される。
> ここではスキルの入出力を示す**サンプルとして** `examples/` に永続化している。

## 題材

タンクの水位を 2 つのセンサで監視し、給水ポンプを自動制御する。
手動起動/停止、ポンプ異常検出とラッチ、非常停止を備える。

- 2 センサ（LOW_SENS / HIGH_SENS）による水位監視 + ヒステリシス制御
- 手動起動/停止ボタン
- ポンプ異常（PUMP_FAULT）を検出 → 異常ラッチ → FAULT_RESET で解除
- 非常停止（B接点フェイルセーフ）

## 既存サンプルとの違い（複雑さの追加ポイント）

| 観点 | conveyor_start | fan_timer | **water_level_ctrl** |
|------|---------------|-----------|----------------------|
| 実装方式 | 自己保持（1式） | 自己保持 + TON タイマー | **状態機械（CASE 文）** |
| 状態数 | なし（フラグのみ） | なし（フラグのみ） | **3状態（IDLE/FILLING/ALARM）** |
| 起動条件 | 1種（START_PB） | 1種（RUN_PB エッジ） | **2種（LOW_SENS 自動 + RUN_PB 手動）** |
| 停止条件 | 2種 | 3種 | **3種（HIGH_SENS/STOP_PB/ESTOP）** |
| 異常処理 | なし | なし | **異常ラッチ + リセット（ALARM 状態）** |
| 出力数 | 2 | 2 | **3（PUMP/RUN_LAMP/ALARM_LAMP）** |

## 生成された ST（本体）

```st
CASE STATE OF
    0: (* IDLE *)
        IF (LOW_SENS OR RUN_PB) AND ESTOP AND NOT PUMP_FAULT THEN STATE := 1; END_IF;
    1: (* FILLING *)
        IF PUMP_FAULT THEN STATE := 2;
        ELSIF HIGH_SENS OR STOP_PB OR NOT ESTOP THEN STATE := 0;
        END_IF;
    2: (* ALARM *)
        IF FAULT_RESET AND NOT PUMP_FAULT AND ESTOP THEN STATE := 0; END_IF;
    ELSE STATE := 0;
END_CASE;

PUMP_MOTOR := (STATE = 1) AND ESTOP AND NOT PUMP_FAULT;
RUN_LAMP   := (STATE = 1);
ALARM_LAMP := (STATE = 2);
```

## ファイル一覧

| ファイル | 工程 | 内容 |
|---|---|---|
| `01_structured_spec.yaml` | ② 構造化仕様 | I/O・内部データ・状態遷移・インターロック・安全要件・前提 |
| `02_device_master.csv` | ③ デバイス割付 | ラベル ↔ 物理アドレス（採番案） |
| `03_program.st` | ④ ST 生成 | ST 本体（正）— CASE 状態機械 |
| `04_static_check.txt` | ⑤ 静的チェック | ERROR 0 / WARN 0 |
| `05_review_notes.md` | ⑥ レビュー観点 | 人間レビュー用チェックリストと前提確認 |
| `06_ladder_view.txt` | 補助 | ST からの ASCII ラダー図ビュー（整数比較は非対応） |
| `gxw3_global_labels.csv` | ⑦ GX Works3 連携 | グローバルラベル一括取り込み用（BOM付UTF-8） |
| `gxw3_device_comments.csv` | ⑦ GX Works3 連携 | デバイスコメント取り込み用 |
| `gxw3_program.st` | ⑦ GX Works3 連携 | ST POU 貼り付け用 |
| `scenario.yaml` | シミュレーション | 4シーンの入力シナリオ |
| `07_timing_chart.png` | シミュレーション | タイミングチャート（PNG） |
| `07_timing_chart_ascii.txt` | シミュレーション | タイミングチャート（ASCII テキスト） |
| `07_sim_log.txt` | シミュレーション | スキャンサイクルシミュレーションログ |

## タイミングチャート概要

`scenario.yaml` に定義した 4 シーンのシミュレーション結果（全 85 サイクル）。

| Cycle | イベント |
|-------|---------|
|  5    | LOW_SENS=ON → 自動起動（STATE: IDLE→FILLING） |
| 12    | LOW_SENS=OFF — STATE=FILLING のまま継続（状態機械のメモリ） |
| 18    | HIGH_SENS=ON → 満水自動停止（STATE: FILLING→IDLE） |
| 25    | RUN_PB パルス → 手動起動（STATE: IDLE→FILLING） |
| 34    | STOP_PB=ON → 手動停止（STATE: FILLING→IDLE） |
| 40    | LOW_SENS=ON → 自動起動（STATE: IDLE→FILLING） |
| 48    | PUMP_FAULT=ON → 異常停止（STATE: FILLING→ALARM）・ALARM_LAMP ON |
| 53    | PUMP_FAULT=OFF — ALARM ラッチ保持（FAULT_RESET 待ち） |
| 57    | FAULT_RESET=ON → アラーム解除（STATE: ALARM→IDLE）・ALARM_LAMP OFF |
| 58    | LOW_SENS=ON のため自動復帰（STATE: IDLE→FILLING）・ポンプ再起動 |
| 65    | HIGH_SENS=ON → 満水自動停止（STATE: FILLING→IDLE） |
| 70    | RUN_PB パルス → 手動起動（STATE: IDLE→FILLING） |
| 76    | ESTOP=OFF → 非常停止（STATE: FILLING→IDLE） |
| 77    | ESTOP=ON — IDLE のまま（LOW_SENS=OFF → 自動復帰なし） |
| 81    | RUN_PB パルス → 手動再起動（STATE: IDLE→FILLING） |

## 再現方法

```bash
# 工程⑤ 静的チェック
python3 .claude/skills/ladder-gen/scripts/static_check.py \
  --st examples/water_level_ctrl/03_program.st \
  --devices examples/water_level_ctrl/02_device_master.csv \
  --spec examples/water_level_ctrl/01_structured_spec.yaml \
  --report examples/water_level_ctrl/04_static_check.txt

# 補助 ラダー図ビュー（状態機械の整数比較は [非対応] と表示）
python3 .claude/skills/ladder-gen/scripts/ladder_view.py \
  --st examples/water_level_ctrl/03_program.st \
  --out examples/water_level_ctrl/06_ladder_view.txt

# 工程⑦ GX Works3 取り込みファイル
python3 .claude/skills/ladder-gen/scripts/export_gxworks3.py \
  --devices examples/water_level_ctrl/02_device_master.csv \
  --st examples/water_level_ctrl/03_program.st \
  --labels examples/water_level_ctrl/gxw3_global_labels.csv \
  --comments examples/water_level_ctrl/gxw3_device_comments.csv \
  --out-st examples/water_level_ctrl/gxw3_program.st

# シミュレーション（要 pyyaml, matplotlib）
python3 .claude/skills/ladder-gen/scripts/simulate.py \
  --st examples/water_level_ctrl/03_program.st \
  --devices examples/water_level_ctrl/02_device_master.csv \
  --scenario examples/water_level_ctrl/scenario.yaml \
  --chart examples/water_level_ctrl/07_timing_chart.png \
  --log examples/water_level_ctrl/07_sim_log.txt
```
