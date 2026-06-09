(* ============================================================
   案件名: water_level_ctrl （水位制御）
   自動生成（要レビュー）。ラベル名はデバイスマスタ(02_device_master.csv)に一致。
   実装方式: 状態機械（CASE文）。状態: IDLE(0) / FILLING(1) / ALARM(2)
   ------------------------------------------------------------
   I/O:
     LOW_SENS(X0,A接点) 低水位センサ / HIGH_SENS(X1,A接点) 高水位センサ
     RUN_PB(X2,A接点) 手動起動 / STOP_PB(X3,A接点) 手動停止
     ESTOP(X4,B接点 通常ON) 非常停止
     PUMP_FAULT(X5,A接点) ポンプ異常 / FAULT_RESET(X6,A接点) 異常リセット
     PUMP_MOTOR(Y10) 給水ポンプ / RUN_LAMP(Y11) 運転ランプ / ALARM_LAMP(Y12) アラームランプ
     STATE(D0,INT) 状態変数 (0:IDLE 1:FILLING 2:ALARM)
   ============================================================ *)

(* --- 1. 安全条件の整理（最上位）---
   ESTOP は B接点。健全時=ESTOP が TRUE（通常ON）。
   非常停止が押される/断線 = ESTOP が FALSE → FILLING→IDLE 遷移でポンプ停止。
   PUMP_FAULT は A接点。異常時=PUMP_FAULT が TRUE → FILLING→ALARM 遷移でポンプ停止。 *)

(* --- 2. 状態遷移（CASE 状態機械）---
   状態エンコード: 0=IDLE(待機)  1=FILLING(給水中)  2=ALARM(異常)
   FILLING 内の IF/ELSIF は PUMP_FAULT を最優先（ELSIF より先に評価）。 *)
CASE STATE OF
    0: (* IDLE: 待機 — ポンプ停止・異常なし *)
        (* 停止優先: NOT HIGH_SENS AND NOT STOP_PB を必須条件に追加。
           満水中または停止ボタン押下中は RUN_PB を押しても起動しない。
           1スキャンのみ FILLING に入りポンプが瞬時 ON になるチャタリングを防止。 *)
        IF (LOW_SENS OR RUN_PB) AND NOT HIGH_SENS AND NOT STOP_PB AND ESTOP AND NOT PUMP_FAULT THEN
            STATE := 1; (* -> FILLING *)
        END_IF;

    1: (* FILLING: 給水中 — ポンプ運転 *)
        IF PUMP_FAULT THEN
            STATE := 2; (* -> ALARM: 異常が最優先 *)
        ELSIF HIGH_SENS OR STOP_PB OR NOT ESTOP THEN
            STATE := 0; (* -> IDLE: 満水/手動停止/非常停止 *)
        END_IF;

    2: (* ALARM: 異常 — ポンプ停止・アラーム点灯 *)
        (* 異常信号消滅 かつ リセット操作 かつ 非常停止健全 でのみ IDLE へ復帰 *)
        IF FAULT_RESET AND NOT PUMP_FAULT AND ESTOP THEN
            STATE := 0; (* -> IDLE *)
        END_IF;

    ELSE
        STATE := 0; (* 不正状態は IDLE へ *)
END_CASE;

(* --- 3. 出力ロジック（各出力は1箇所のみ代入：二重コイル禁止） --- *)

(* 給水ポンプ: FILLING(1) かつ 非常停止健全 かつ 異常なし のときのみ駆動。
   CASE での遷移後もこのスキャンでは STATE が反映されるため即時安全側へ落ちる。
   インターロック「非常停止中はポンプ禁止」「異常中はポンプ禁止」を式に内包。 *)
PUMP_MOTOR := (STATE = 1) AND ESTOP AND NOT PUMP_FAULT;

(* 運転ランプ: FILLING 中のみ点灯 *)
RUN_LAMP := (STATE = 1);

(* アラームランプ: ALARM 中のみ点灯。FAULT_RESET で IDLE へ遷移し消灯。 *)
ALARM_LAMP := (STATE = 2);
