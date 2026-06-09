(* ============================================================
   案件名: fan_timer （換気ファン タイマー自動停止制御）
   自動生成（要レビュー）。ラベル名はデバイスマスタ(02_device_master.csv)に一致。
   実装方式: 自己保持 + TON タイマー自動停止。状態遷移なし。
   ------------------------------------------------------------
   I/O:
     RUN_PB(X0,A接点) 起動  / STOP_PB(X1,A接点) 停止
     ESTOP(X2,B接点 通常ON) 非常停止
     FAN_MOTOR(Y10) 換気ファン / RUN_LAMP(Y11) 運転ランプ
     M_RUNNING(M0) 運転中フラグ(自己保持)
     M_RUN_PB_PREV(M1) RUN_PB前回値(立ち上がりエッジ検出用)
     T_AUTO_STOP(TON) 自動停止タイマー(PT=T#30m)
   ============================================================ *)

(* --- 1. 安全条件の整理（最上位） ---
   ESTOP は B接点のため、健全時 = ESTOP が TRUE（通常ON）。
   非常停止が押される＝ESTOP が FALSE → 運転解除・全出力OFF。 *)

(* --- 2. 運転フラグ（自己保持） ---
   セット : RUN_PB の立ち上がりエッジ（押した瞬間のみ）で運転ON。
            RUN_PB を押し続けていてもタイマー満了後に自動停止し、そのまま再起動しない。
   リセット: STOP_PB を押す / 非常停止（ESTOP=FALSE）/ タイマー満了（T_AUTO_STOP.Q=TRUE）で運転解除。
   非常停止解除後は M_RUNNING=FALSE のままなので、再度 RUN_PB を押すまで再開しない。 *)
M_RUNNING := ((RUN_PB AND NOT M_RUN_PB_PREV) OR M_RUNNING) AND NOT STOP_PB AND ESTOP AND NOT T_AUTO_STOP.Q;

(* --- 3. 自動停止タイマー（TON） ---
   M_RUNNING が ON の間のみ計時。M_RUNNING が OFF になれば IN=FALSE で自動リセット（ET=0）。
   PT=T#30m に達すると Q=TRUE → 上記で M_RUNNING をリセット → 次スキャンで IN=FALSE → Q=FALSE。 *)
T_AUTO_STOP(IN := M_RUNNING, PT := T#30m);

(* --- 4. 出力ロジック（各出力は1箇所のみ代入：二重コイル禁止） --- *)

(* 換気ファン:
   運転中 かつ 非常停止健全 のときのみ駆動。
   インターロック「非常停止中はファン駆動禁止」を式に内包。 *)
FAN_MOTOR := M_RUNNING AND ESTOP;

(* 運転ランプ: 運転中（タイマー計時中も含む）は点灯。 *)
RUN_LAMP := M_RUNNING;

(* --- 5. エッジ検出用前回値更新（最終行で更新し、次スキャンで参照） --- *)
M_RUN_PB_PREV := RUN_PB;
