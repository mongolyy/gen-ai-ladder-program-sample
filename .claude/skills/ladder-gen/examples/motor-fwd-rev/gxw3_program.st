(* ============================================================
   案件名: motor-fwd-rev  モータ正逆運転制御
   自動生成（要レビュー）。ラベルはデバイスマスタに一致。
   ============================================================ *)

(* --- 1. 運転許可 (非常停止/停止条件) ---
   ESTOP は B接点: 正常時 TRUE、押下/断線時 FALSE。
   STOP_PB 押下 または ESTOP 断 で運転不許可。 *)

(* --- 2. 正転 出力ロジック (自己保持 + 正逆インターロック) --- *)
MOTOR_FWD := (START_FWD OR MOTOR_FWD)
             AND NOT STOP_PB
             AND ESTOP
             AND NOT MOTOR_REV;

(* --- 3. 逆転 出力ロジック (自己保持 + 正逆インターロック) --- *)
MOTOR_REV := (START_REV OR MOTOR_REV)
             AND NOT STOP_PB
             AND ESTOP
             AND NOT MOTOR_FWD;

(* --- 4. 運転ランプ --- *)
RUN_LAMP := MOTOR_FWD OR MOTOR_REV;
