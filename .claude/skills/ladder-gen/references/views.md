# 状態機械生成 と ラダー図ビュー

ST を「正」とする方針のもとで、(A) 状態遷移から CASE 状態機械の ST を生成する補助と、
(B) ST を人間が見やすいラダー図へ変換するビューを提供する。

## A. 状態遷移 → CASE 状態機械（工程④の補助）

`scripts/gen_state_machine.py` は構造化仕様の `states` / `transitions` から、
状態変数を使った `CASE` 文の ST スケルトンを生成する。シーケンス制御の骨格に使う。

```bash
python3 .claude/skills/ladder-gen/scripts/gen_state_machine.py \
  --spec out/<案件名>/01_structured_spec.yaml \
  --state-var STATE \
  --out out/<案件名>/03_state_machine.st
```

- 状態 id を出現順に 0,1,2… へ採番し、`CASE STATE OF` の各分岐に対応させる。
- 各状態の遷移は `IF <condition> THEN STATE := <次状態>; END_IF;` として展開する。
- `ELSE` 分岐で不正状態を初期状態へ戻す（フェイルセーフ）。
- 各状態の**出力動作（Moore 動作）は TODO コメント**として残すので、AI/人間が埋める。

使用上の注意:
- **状態変数（既定 `STATE`, INT）をデバイスマスタへ追加すること。** 追加しないと
  静的チェック C002（未定義デバイス）になる。
- 生成後は通常の ST と同様に工程⑤ 静的チェックへ通す。CASE の各ケースで `STATE` に
  代入しても、静的チェッカーはケース分岐を相互排他と認識するため二重コイルにならない。

## B. ラダー図ビュー（工程⑥レビューの補助）

`scripts/ladder_view.py` は ST のブール代入文を ASCII ラダー図へ変換する。
ST が正であり、ラダーは**レビュー時に回路を直感的に確認するためのビュー**。

```bash
python3 .claude/skills/ladder-gen/scripts/ladder_view.py \
  --st out/<案件名>/03_program.st \
  --out out/<案件名>/06_ladder_view.txt
```

記号:

| 記号 | 意味 |
|------|------|
| `] [` | a接点（通常開） |
| `]/[` | b接点（通常閉, NOT） |
| `( )` | 出力コイル |
| `\|` | 電源母線 |
| 直列 | AND |
| 並列 | OR |

例: `MOTOR_FWD := (START_FWD OR MOTOR_FWD) AND NOT STOP_PB AND ESTOP AND NOT MOTOR_REV;`

```
| START_FWD  STOP_PB  ESTOP  MOTOR_REV  MOTOR_FWD |
|+---] [----]/[-----] [-----]/[--------( )--------|
||MOTOR_FWD                                        |
|+---] [---+                                       |
```

対応範囲:
- 対応: `AND` / `OR` / `NOT` / 括弧 / 識別子 / `TRUE` / `FALSE`。`NOT(...)` は
  ド・モルガンで接点へ分配する。
- 非対応: 比較（`>=` 等）・算術・FB 呼び出しを含む式。これらは式をそのまま注記して
  表示する（無理にラダー化しない）。状態機械（CASE）も対象外。

ラダー図ビューはあくまで参考表示であり、GX Works3 へ取り込むのは ST（工程⑦）である。
