# GX Works3 連携（工程⑦）

静的チェック（⑤）と人間レビュー（⑥）を通過した成果物を、GX Works3 へ取り込める
ファイルへ変換する。`scripts/export_gxworks3.py` が変換を行う。

## 前提と方針

- GX Works3 はコードの完全自動流し込み API を持たないため、本工程は
  **「取り込みやすい形のファイルを生成し、最後の取り込みは人間が GX Works3 上で行う」**
  半自動連携とする。
- ST は人間が ST エディタへ貼り付け／インポートする。ラベルとデバイスコメントは
  CSV 一括取り込みを使う（これが自動化メリットの大きい部分）。

## 生成物

```bash
python3 .claude/skills/ladder-gen/scripts/export_gxworks3.py \
  --devices out/<案件名>/02_device_master.csv \
  --st      out/<案件名>/03_program.st \
  --labels  out/<案件名>/gxw3_global_labels.csv \
  --comments out/<案件名>/gxw3_device_comments.csv \
  --out-st  out/<案件名>/gxw3_program.st
```

| 出力 | 取り込み先 |
|------|-----------|
| `gxw3_global_labels.csv` | グローバルラベル設定（ラベルエディタ） |
| `gxw3_device_comments.csv` | デバイスコメント |
| `gxw3_program.st` | プログラム本体（ST POU へ貼り付け） |

- ラベル CSV は BOM 付き UTF-8 で出力する（GX Works3 / Excel の文字化け対策）。
- `device` 列が空（割付未確定）のラベルがあると WARN を出す。工程③を先に確定すること。

## データ型のマッピング

デバイスマスタの `type` を GX Works3 の表記へ変換する（`scripts/export_gxworks3.py` の
`TYPE_MAP`）:

| マスタ | GX Works3 |
|--------|-----------|
| BOOL | ビット |
| INT | ワード[符号付き] |
| WORD | ワード[符号なし]/16ビット列 |
| DINT | ダブルワード[符号付き] |
| REAL | 単精度実数 |

未知の型はそのまま出力する。実機の表記に合わせて `TYPE_MAP` を調整する。

## GX Works3 での取り込み手順（目安）

1. **ラベル**: ナビゲーション → ラベル → グローバルラベル を開き、
   「一括取り込み（CSV）」で `gxw3_global_labels.csv` を読み込む。
2. **デバイスコメント**: デバイスコメント編集画面で CSV を取り込む。
3. **プログラム**: 対象 POU の ST エディタに `gxw3_program.st` を貼り付ける。
4. ビルド（変換）してエラーがないか確認 → 工程⑧ シミュレーションへ。

## バージョン差異への注意

GX Works3 のラベル CSV は**バージョン・言語設定で列名や並びが異なる**。
取り込みでエラーが出る場合:

1. GX Works3 側で空のグローバルラベルを 1 行作り、CSV へ**エクスポート**する。
2. そのテンプレート CSV の**ヘッダ行・列順**に合わせて、`export_gxworks3.py` の
   `LABEL_HEADER` と書き出し順を修正する。

これにより実機の流儀に確実に合わせられる。
