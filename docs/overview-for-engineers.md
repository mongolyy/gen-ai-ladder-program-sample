# gen-ai-ladder-program — ソフトウェアエンジニア向け概要

## このリポジトリが解決する問題

製造業の生産設備はPLC（Programmable Logic Controller）で制御されており、その制御プログラムはラダー図またはST（Structured Text）という言語で書かれる。

従来の開発フローは「制御仕様書（Word/Excel）→ 人手でコーディング」であり、仕様書の記述ゆれや人手によるコーディングミスが安全上のリスクになる。

このリポジトリは **Claude Code スキル**として、「自然言語の仕様 → PLC プログラム（ST）」の変換を半自動化し、静的チェックで安全上の不備を機械的に検出するパイプラインを提供する。

---

## 前提知識：PLC / ラダー / ST とは

| 用語 | ソフトウェアエンジニア向けの対応概念 |
|------|--------------------------------------|
| PLC | 産業用組み込みコンピュータ（リアルタイムOS相当） |
| ラダー図 | 視覚的な制御記述言語（回路図の記法） |
| ST（Structured Text） | IEC 61131-3 準拠の手続き型言語（Pascal 風の構文） |
| デバイスアドレス | メモリアドレス（例: `M100`=内部フラグ, `Y10`=出力リレー） |
| GX Works3 | 三菱電機製PLCの統合開発環境（IDE） |
| コイル二重化 | 同一変数への複数書き込み（ラダー固有のバグパターン） |

ST はソフトウェアエンジニアが読める言語だが、ラダー図はPLCエンジニア向けの視覚表現であり相互変換が可能。本プロジェクトは **ST を正として管理し、ラダーはビュー**として扱う設計になっている。

---

## アーキテクチャ概要

```
自然言語仕様
     │
     ▼
① 構造化仕様 (YAML)        ← LLM が生成（Claude）
     │
     ▼
② デバイスマスタ (CSV)     ← LLM が生成 / 人間が確認
     │
     ▼
③ STコード (.st)           ← LLM が生成（CSVのラベルのみ使用）
     │
     ├──▶ 静的チェック      ← scripts/static_check.py
     │         │
     │    ERROR があれば中断
     │
     ▼
④ 人間レビュー
     │
     ▼
⑤ GX Works3 インポート用ファイル出力
     │
     ▼
⑥ シミュレーション / 実機確認
```

出力物はすべて `out/<案件名>/` に番号付きで書き出される（01_〜07_）。

---

## コンポーネント一覧

### スキル本体
| ファイル | 役割 |
|----------|------|
| `.claude/skills/ladder-gen/SKILL.md` | Claude Code スキルのエントリポイント。7工程の実行手順を記述したマークダウン。LLMへのプロンプト集としても機能する。 |

### スクリプト群（`.claude/skills/ladder-gen/scripts/`）

| スクリプト | 入力 | 出力 | 概要 |
|------------|------|------|------|
| `static_check.py` | `.st` + `.csv` + `.yaml` | `.txt`（チェックレポート） | 7種の静的チェック（C001〜C007）を実行。ERRORがあれば終了コード1を返す。 |
| `gen_state_machine.py` | 構造化仕様の状態遷移定義 | STのCASE文スケルトン | 状態機械をCASE文として自動生成するコード生成ツール。 |
| `ladder_view.py` | `.st` ファイル | ASCII ラダー図 | STをラダー図で可視化。PLCエンジニアへのレビュー用。 |
| `export_gxworks3.py` | `.st` + `.csv` | GX Works3インポート形式 | IDEへの取り込み用ファイルを生成。 |
| `simulate.py` | `.st` + シナリオ定義 | シミュレーション結果 | PLC動作をPythonで模倣し、テストシナリオを実行する。 |

### 参照資料（`references/`）
スキルがコード生成時に参照するルール集。LLMへの制約プロンプトとして機能する。

| ファイル | 内容 |
|----------|------|
| `structured-spec-schema.md` | 構造化仕様YAMLのスキーマ定義 |
| `device-allocation.md` | デバイスアドレスの割付ルール |
| `st-generation-guide.md` | STコーディング規約 |
| `static-check-rules.md` | 静的チェックの判定基準とレビュー観点 |

---

## 静的チェック（C001〜C007）の内容

| コード | レベル | チェック内容 |
|--------|--------|-------------|
| C001 | ERROR | 二重コイル：同一ラベルに複数の `:=` 代入 |
| C002 | ERROR | 未定義デバイス：STで使われているがCSVに存在しないラベル |
| C003 | ERROR | 非常停止（ESTOP）の欠落：安全出力をすべて OFF にする記述がない |
| C004 | ERROR | インターロック欠落：禁止組み合わせ（例：正転・逆転同時）が防止されていない |
| C005 | WARN | 未使用デバイス：CSVに定義されているがSTで参照されていない |
| C006 | WARN | 状態未到達：定義されている状態に遷移経路がない |
| C007 | WARN | タイマ未呼び出し：タイマデバイスが更新されていない |

---

## 主要な設計判断

### AIに物理アドレスを断定させない
LLMがデバイスアドレス（`M100` など）を自由に生成すると、既存設備との衝突や誤りが起きる。
→ アドレスはCSV（デバイスマスタ）で一元管理し、STはラベル名のみで記述する。

### ST を正、ラダーは変換ビュー
ラダー図はテキスト差分管理が困難。
→ STをソースオブトゥルースとし、`ladder_view.py` が可視化のためにASCIIラダーを生成する。

### 安全はゲート（安全要件を後回しにしない）
非常停止・インターロックの欠落は静的チェックのERRORとして扱い、人間レビューの前段でパイプラインを止める。

### 不明点は断定せず記録する
LLMが仕様から読み取れない設計判断（例：タイムアウト値）を勝手に決定せず、`assumptions` セクションに記録して人間に確認を求める。

---

## 開発環境のセットアップ

```bash
git clone https://github.com/mongolyy/gen-ai-ladder-program-sample.git
cd gen-ai-ladder-program-sample

# 依存ライブラリのインストール
pip install pytest pyyaml

# テストの実行
pytest
```

### スクリプトの単体実行例

```bash
# 静的チェッカー
python3 .claude/skills/ladder-gen/scripts/static_check.py \
  --st out/<案件名>/03_program.st \
  --devices out/<案件名>/02_device_master.csv \
  --spec out/<案件名>/01_structured_spec.yaml \
  --report out/<案件名>/04_static_check.txt

# ASCIIラダー図の生成
python3 .claude/skills/ladder-gen/scripts/ladder_view.py \
  out/<案件名>/03_program.st

# GX Works3用エクスポート
python3 .claude/skills/ladder-gen/scripts/export_gxworks3.py \
  --st out/<案件名>/03_program.st \
  --devices out/<案件名>/02_device_master.csv \
  --out out/<案件名>/
```

---

## ディレクトリ構成

```
.
├── .claude/skills/ladder-gen/   # Claude Code スキル本体
│   ├── SKILL.md                 # エントリポイント（工程定義）
│   ├── references/              # LLMへの制約ルール集
│   ├── templates/               # YAML/CSVのひな型
│   ├── scripts/                 # 静的チェック・コード生成ツール群
│   └── tests/                  # pytest テスト
├── examples/                   # 完成例（入力〜出力のフルセット）
│   ├── water_level_ctrl/
│   ├── conveyor_start/
│   └── fan_timer/
└── out/                        # スキル実行時の出力先（gitignore推奨）
```

---

## このプロジェクトを拡張したい場合

| やりたいこと | 変更箇所 |
|-------------|----------|
| 新しい静的チェックを追加 | `scripts/static_check.py` に関数を追加し、`references/static-check-rules.md` にルールを記述 |
| ST生成のルールを変更 | `references/st-generation-guide.md` を編集 |
| 新しい例を追加 | `examples/` に新ディレクトリを作成し、既存例を参考に構成 |
| 別のPLCメーカーに対応 | `export_gxworks3.py` に相当するエクスポータを新規作成 |
