# 構造化仕様スキーマ（工程②）

自然言語仕様を、機械可読かつ人間レビュー可能な中間表現へ構造化するためのスキーマ。
形式は YAML。テンプレートは `../templates/structured-spec.template.yaml`。

## トップレベル項目

| キー | 必須 | 説明 |
|------|------|------|
| `meta` | ✓ | 案件名・バージョン・対象PLC機種など |
| `io` | ✓ | 入力 (`inputs`) と出力 (`outputs`) のリスト |
| `internal` | | 内部リレー・タイマ・カウンタ・データ |
| `states` | | 状態（ステップ）の定義 |
| `transitions` | | 状態遷移（from / to / condition） |
| `interlocks` | ✓ | インターロック条件（安全上の禁止/許可条件） |
| `safety` | ✓ | 非常停止など安全要件 |
| `logic` | | 上記で表現しきれない補足ロジック・タイミング |
| `assumptions` | | AI が補完した前提（仕様に明示が無かった項目） |

## 各項目の書式

### io.inputs / io.outputs

各要素:

```yaml
- label: START_PB          # ラベル（シンボル名）。英大文字+アンダースコア推奨
  type: BOOL               # BOOL / INT / WORD / REAL など
  description: 起動押しボタン
  device: ""               # 物理アドレス。工程③で確定。②では空でよい
  active: high             # high(A接点) / low(B接点)。入力の有効論理
```

### internal

```yaml
timers:
  - label: T_DRY
    preset_ms: 5000
    description: 乾燥タイマ
counters:
  - label: C_PRODUCT
    preset: 100
    description: 製品カウンタ
relays:
  - label: M_RUNNING
    description: 運転中フラグ（自己保持）
data:
  - label: D_SPEED
    type: INT
    description: 設定速度
```

### states / transitions（状態遷移がある場合）

```yaml
states:
  - id: IDLE
    description: 待機
  - id: RUNNING
    description: 運転中
  - id: STOPPING
    description: 停止処理中

transitions:
  - from: IDLE
    to: RUNNING
    condition: START_PB AND NOT ESTOP
  - from: RUNNING
    to: STOPPING
    condition: STOP_PB OR fault
```

`condition` は読みやすい疑似ブール式で書く（AND/OR/NOT、ラベル名、比較）。
工程④で ST 式へ変換する。

### interlocks

「ある出力/動作を許可/禁止する条件」を明示する。安全の要。

```yaml
- name: モータ正逆同時禁止
  forbid: MOTOR_FWD AND MOTOR_REV   # この状態を作ってはならない
- name: ドア開時は搬送停止
  when: DOOR_OPEN
  forbid: CONVEYOR
```

### safety（必須）

```yaml
estop:
  label: ESTOP            # 非常停止入力のラベル
  active: low             # 通常はB接点（断線時に安全側）
  on_trip: 全出力OFF       # 非常停止時の挙動
reset:
  label: RESET_PB
  description: 復帰操作
```

非常停止が仕様に明示されていない場合でも、安全上ほぼ必須。
`assumptions` に「非常停止を ESTOP(B接点) として追加した」と記録し、ゲート②で確認する。

### assumptions

```yaml
- AI が補完: 非常停止 ESTOP(B接点) を追加。仕様に明示なし。
- AI が補完: 電源投入時は IDLE 状態から開始すると仮定。
```

## 構造化のチェックリスト

- [ ] すべての出力に対して「ON/OFF 条件」が定義されているか
- [ ] 非常停止とその時の出力挙動が定義されているか
- [ ] 相互排他（同時 ON 禁止）が interlocks に記述されているか
- [ ] タイマ/カウンタのプリセット値が数値で確定しているか
- [ ] 状態遷移に抜け（どの状態からも戻れない等）がないか
- [ ] 仕様に無く AI が補完した項目はすべて assumptions に記録したか
