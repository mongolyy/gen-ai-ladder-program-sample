(* ============================================================
   状態機械: conveyor-seq
   状態変数: STATE (INT)。デバイスマスタへ追加すること。
   状態エンコード:
     0 = IDLE  待機
     1 = RUNNING  搬送中
     2 = STOPPING  停止処理
   自動生成（要レビュー）。各状態の出力動作は TODO を埋める。
   ============================================================ *)

CASE STATE OF
    0: (* IDLE  待機 *)
        (* TODO: IDLE での出力動作をここに記述 *)
        IF START_PB AND ESTOP THEN
            STATE := 1; (* -> RUNNING *)
        END_IF;
    1: (* RUNNING  搬送中 *)
        (* TODO: RUNNING での出力動作をここに記述 *)
        IF STOP_PB OR NOT ESTOP THEN
            STATE := 2; (* -> STOPPING *)
        END_IF;
    2: (* STOPPING  停止処理 *)
        (* TODO: STOPPING での出力動作をここに記述 *)
        IF NOT CONVEYOR THEN
            STATE := 0; (* -> IDLE *)
        END_IF;
    ELSE
        STATE := 0; (* 不正状態は初期状態 IDLE へ *)
END_CASE;

