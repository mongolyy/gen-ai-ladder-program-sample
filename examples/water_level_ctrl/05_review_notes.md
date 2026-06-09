# 人間レビュー用メモ — water_level_ctrl（水位制御）

工程⑤（静的チェック）通過後の、人間レビュー観点メモ。
自動チェックでは検出しにくい設計妥当性を中心に確認する。

- 静的チェック: **ERROR 0 / WARN 0**（`04_static_check.txt`）
- 実装方式: 状態機械（CASE文）。状態遷移 IDLE↔FILLING↔ALARM。出力は各1代入で二重コイルなし。

## 生成ロジック（要点）

```st
CASE STATE OF
    0: (* IDLE *)
        IF (LOW_SENS OR RUN_PB) AND ESTOP AND NOT PUMP_FAULT THEN STATE := 1; END_IF;
    1: (* FILLING *)
        IF PUMP_FAULT THEN
            STATE := 2;        (* 異常が最優先 *)
        ELSIF HIGH_SENS OR STOP_PB OR NOT ESTOP THEN
            STATE := 0;
        END_IF;
    2: (* ALARM *)
        IF FAULT_RESET AND NOT PUMP_FAULT AND ESTOP THEN STATE := 0; END_IF;
    ELSE STATE := 0;
END_CASE;

PUMP_MOTOR := (STATE = 1) AND ESTOP AND NOT PUMP_FAULT;
RUN_LAMP   := (STATE = 1);
ALARM_LAMP := (STATE = 2);
```

## レビュー観点チェックリスト

### 安全
- [ ] **非常停止のフェイルセーフ**: `ESTOP` は B接点（通常ON、押す/断線でFALSE）。
      FILLING→IDLE 遷移条件に `NOT ESTOP` が含まれ、トリップ時に同スキャンで IDLE に遷移。
      出力式にも `AND ESTOP` を追加（二重安全ゲート）。実機配線が B接点か要確認。
- [ ] **非常停止後の自動再起動の禁止**: ESTOP トリップ後は STATE=IDLE(0)。
      解除後に `LOW_SENS` が OFF かつ `RUN_PB` が OFF であれば自動起動しない。
      ただし **LOW_SENS が ON のままの場合は次スキャンで IDLE→FILLING に自動遷移する**。
      水位制御の性質上これは正常動作だが、人が立ち入る設備では意図通りか要確認。
      安全上問題があれば `IDLE→FILLING` 条件を `RUN_PB` のエッジ検出に変更すること。
- [ ] **異常ラッチの妥当性**: PUMP_FAULT=OFF になっても ALARM 状態を保持する。
      `FAULT_RESET AND NOT PUMP_FAULT AND ESTOP` の 3 条件がそろうまで IDLE に戻らない。
      FAULT_RESET だけ押しても PUMP_FAULT が残っている間は解除されないことを確認。

### 制御ロジック / 状態遷移
- [ ] **FILLING→ALARM が最優先**: `IF PUMP_FAULT THEN ... ELSIF ... END_IF` の構造で、
      PUMP_FAULT と HIGH_SENS が同時に TRUE でも ALARM 遷移が優先される。意図通りか確認。
- [x] **停止優先（Stop Priority）**: IDLE→FILLING 条件に `NOT HIGH_SENS AND NOT STOP_PB` を追加。
      満水中（HIGH_SENS=ON）や停止ボタン押下中（STOP_PB=ON）は RUN_PB を押しても起動しない。
      これにより FILLING に入って即次スキャンで IDLE へ戻る「1スキャンのみの出力」を防止。
- [ ] **FILLING→IDLE の非常停止条件**: `NOT ESTOP` をトリガとして IDLE に遷移する。
      ESTOP がトリップした次スキャンで STATE=0 になり、出力式 `AND ESTOP` も FALSEになる。
      同スキャン内で安全側へ落ちることを確認（スキャン内でCASE遷移→出力の順に実行）。
- [ ] **ALARM→IDLE 後の自動起動**: FAULT_RESET を押したスキャンで STATE=0(IDLE) になる。
      同スキャン内では CASE の 2: ブランチが実行されるため 0: ブランチは動かない。
      **次スキャン**で STATE=0 になり、LOW_SENS が ON なら IDLE→FILLING に遷移する
      （cycle 57→58 の挙動。シミュレーションで確認済み）。意図通りか確認。
- [ ] **ELSE ブランチ**: 不正な STATE 値（停電復帰時の D0 値化け等）の場合に STATE=0 へ戻す保護。
      D0 の初期値・保持設定を確認すること。

### 割付
- [ ] X/Y アドレス（X0〜X6, Y10〜Y12）が実機端子と一致するか（採番案のため要確認）。
- [ ] `STATE`(D0,INT) の停電保持の要否。必要なら D0 をラッチ領域へ変更し、
      電源再投入後に ALARM 状態から再開するかを検討すること。
- [ ] `LOW_SENS`/`HIGH_SENS` の物理的な取付位置・センサ種別（フロートスイッチ/電極式/超音波等）を確認。
      センサが HIGH_SENS=ON でも LOW_SENS=ON のまま（シングルポイント感知の場合）の
      挙動が仕様と一致するかを確認。

### スキャン依存
- [ ] CASE の遷移判定と出力代入は同一スキャン内で実行される（ST は逐次実行）。
      FILLING→IDLE 遷移が発生したスキャンで PUMP_MOTOR=(STATE=1) も即 FALSE になる。
      ラダーの「コイル保持遅延 1 スキャン」問題は ST には存在しない点を確認。

## AI が置いた前提（assumptions）の確認

| # | 前提 | 確認 |
|---|------|------|
| 1 | ESTOP を B接点(active=low)として追加。断線時に安全側 | [ ] |
| 2 | LOW_SENS/HIGH_SENS は水位到達でONになる A接点フロートスイッチと解釈 | [ ] |
| 3 | 非常停止解除後に LOW_SENS=ON なら次スキャンで自動復帰（水位制御として正常動作） | [ ] |
| 4 | PUMP_FAULT は A接点（異常時ON）。B接点配線なら論理反転が必要 | [ ] |
| 5 | FAULT_RESET は NOT PUMP_FAULT かつ ESTOP 健全の状態でのみ有効 | [ ] |
| 6 | 電源投入時 STATE=0(IDLE) から開始（D0 初期値 0） | [ ] |
| 7 | IDLE→FILLING 条件に NOT HIGH_SENS・NOT STOP_PB を追加（停止優先・チャタリング防止） | [x] |

## 次工程

- 工程⑦: `export_gxworks3.py` で GX Works3 取り込み用ファイルを生成済み。
- ラダー図ビュー: `06_ladder_view.txt` — 状態機械の整数比較式（`STATE = 1` 等）は
  ASCII ラダー変換非対応のため `[非対応]` と表示される（ST ソースを直接参照すること）。
- シミュレーション: `scenario.yaml` / `07_timing_chart.png` / `07_sim_log.txt` 参照。
