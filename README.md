# gen-ai-ladder-program

生成AIで PLC のラダー/ST（構造化テキスト）を半自動生成するための Claude Code スキル。

## 全体フロー

```
① 自然言語仕様            （入力）
② 構造化仕様の生成        ← スキル
③ デバイス/ラベル割付     ← スキル
④ ST 生成                 ← スキル（ST を正、ラダーは変換ビュー）
⑤ 静的チェック            ← スキル（scripts/static_check.py）
─────────────────────────────────
⑥ 人間レビュー            （観点をスキルが提示）
⑦ GX Works3 実装          （インポート用ファイルを出力）
⑧ シミュレーション
⑨ 実機確認
```

設計思想:
- **AI に物理アドレスを断定させない** — デバイスマスタ（CSV）を単一の真実とし、ST はラベルで書く。
- **ST を正、ラダーは従** — 後段の検証・Git 差分管理を一本化。
- **安全はゲート** — 非常停止・インターロック欠落、二重コイル、未定義デバイスを静的チェックで検出。
- **不明点は断定せず assumptions に記録** — 各工程末のゲートで人間に確認。

## 使い方

Claude Code で `ladder-gen` スキルを呼び出し、制御仕様（自然言語）を渡す。
各工程の成果物は `out/<案件名>/` に出力される。

スキル本体: [`.claude/skills/ladder-gen/SKILL.md`](.claude/skills/ladder-gen/SKILL.md)

### 静的チェッカー単体実行

```bash
python3 .claude/skills/ladder-gen/scripts/static_check.py \
  --st out/<案件名>/03_program.st \
  --devices out/<案件名>/02_device_master.csv \
  --spec out/<案件名>/01_structured_spec.yaml \
  --report out/<案件名>/04_static_check.txt
```

ERROR が 1 件でもあれば終了コード 1。`--spec` は任意だが安全/インターロック検査に必要。
（YAML 解析に `pyyaml` を使用。未導入でも簡易フォールバックで動作。）

## 構成

```
.claude/skills/ladder-gen/
  SKILL.md                          スキル本体（工程の実行手順）
  references/
    structured-spec-schema.md       工程② 構造化仕様スキーマ
    device-allocation.md            工程③ デバイス割付の原則
    st-generation-guide.md          工程④ ST コーディング規約
    static-check-rules.md           工程⑤/⑥ チェック項目とレビュー観点
  templates/
    structured-spec.template.yaml   構造化仕様テンプレート
    device-master.template.csv      デバイスマスタテンプレート
  scripts/
    static_check.py                 工程⑤ 静的チェッカー
  examples/
    motor-fwd-rev/                  モータ正逆運転制御の完成例
```

## 現状と今後

実装済み: 工程②〜⑤（構造化〜静的チェック）と人間レビュー観点の提示（⑥）。
今後の候補: GX Works3 連携の自動化（⑦）、シミュレーション結果の取り込み（⑧）、
状態遷移（CASE）からのラダー図ビュー生成。
