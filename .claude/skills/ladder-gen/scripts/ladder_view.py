#!/usr/bin/env python3
"""
ラダー図ビュー — ST のブール代入文を ASCII ラダー図へ変換する。

ST を「正」、ラダーを「従(ビュー)」とする方針に基づき、レビュー時に回路を
直感的に確認するための補助表示を生成する。

対応: OUT := <ブール式>;  (AND / OR / NOT / 括弧 / 識別子 / TRUE / FALSE)
非対応 (比較・演算・FB 呼び出し等) の文は、式をそのまま注記して表示する。

  AND = 直列接点、 OR = 並列分岐、 NOT = b接点 ]/[ 、 通常 = a接点 ] [ 、 出力 = ( )

使い方:
  python3 ladder_view.py --st prog.st [--out ladder.txt]
"""
import argparse
import re

# ---------------- ST から代入文を取り出す ----------------
def strip_comments(text):
    text = re.sub(r"\(\*.*?\*\)", " ", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", " ", text)
    return text


def extract_assignments(text):
    """[(lhs, rhs)] を返す。文末 ; で区切り、:= を含む文のみ。"""
    text = strip_comments(text)
    stmts = [s.strip() for s in text.split(";") if ":=" in s]
    result = []
    for s in stmts:
        lhs, rhs = s.split(":=", 1)
        lhs = lhs.strip()
        # 単純な代入先 (FB 入力 IN:= などのネストは対象外) のみ
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", lhs):
            result.append((lhs, rhs.strip()))
    return result


# ---------------- ブール式パーサ ----------------
# AST: ("var", name, negated) / ("and", [..]) / ("or", [..])
BOOL_TOKEN = re.compile(r"\(|\)|[A-Za-z_][A-Za-z0-9_.]*")


class ParseError(Exception):
    pass


def tokenize_bool(expr):
    toks = BOOL_TOKEN.findall(expr)
    # 想定外文字が残る式は非対応扱いにする
    leftover = BOOL_TOKEN.sub("", expr).strip()
    if leftover:
        raise ParseError(f"非対応トークン: {leftover!r}")
    return toks


class Parser:
    def __init__(self, toks):
        self.toks = toks
        self.i = 0

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def next(self):
        t = self.peek()
        self.i += 1
        return t

    def parse(self):
        node = self.parse_or()
        if self.i != len(self.toks):
            raise ParseError("余分なトークン")
        return node

    def parse_or(self):
        nodes = [self.parse_and()]
        while (self.peek() or "").upper() == "OR":
            self.next()
            nodes.append(self.parse_and())
        return nodes[0] if len(nodes) == 1 else ("or", nodes)

    def parse_and(self):
        nodes = [self.parse_unary()]
        while (self.peek() or "").upper() == "AND":
            self.next()
            nodes.append(self.parse_unary())
        return nodes[0] if len(nodes) == 1 else ("and", nodes)

    def parse_unary(self, negated=False):
        t = self.peek()
        if t is None:
            raise ParseError("式が空")
        if t.upper() == "NOT":
            self.next()
            return self.parse_unary(not negated)
        if t == "(":
            self.next()
            node = self.parse_or()
            if self.next() != ")":
                raise ParseError("括弧が閉じていない")
            return self._negate(node) if negated else node
        if t in (")",) or t.upper() in ("AND", "OR"):
            raise ParseError(f"予期しないトークン {t!r}")
        self.next()
        return ("var", t, negated)

    def _negate(self, node):
        # 括弧に NOT が付いた場合はド・モルガンで分配
        if node[0] == "var":
            return ("var", node[1], not node[2])
        if node[0] == "and":
            return ("or", [self._negate(c) for c in node[1]])
        if node[0] == "or":
            return ("and", [self._negate(c) for c in node[1]])
        return node


# ---------------- ASCII ラダー描画 ----------------
# Block = (lines: list[str], rail: int)  全行同じ幅。rail は接続行のインデックス。
def leaf_block(name, negated):
    sym = "]/[" if negated else "] ["
    contact = "--" + sym + "--"
    width = max(len(name) + 1, len(contact))
    label = name.center(width)
    cont = contact.center(width, "-")
    return ([label, cont], 1)


def coil_block(name):
    sym = "( )"
    coil = "--" + sym + "--"
    width = max(len(name) + 1, len(coil))
    return ([name.center(width), coil.center(width, "-")], 1)


def _width(block):
    return len(block[0][0])


def series(blocks):
    lines_list = [b[0] for b in blocks]
    rails = [b[1] for b in blocks]
    above = max(rails)
    below = max(len(l) - 1 - r for l, r in zip(lines_list, rails))
    height = above + below + 1
    padded = []
    for lines, rail in zip(lines_list, rails):
        w = len(lines[0])
        top = above - rail
        bottom = height - len(lines) - top
        block = [" " * w] * top + lines + [" " * w] * bottom
        padded.append(block)
    merged = ["".join(block[r] for block in padded) for r in range(height)]
    return (merged, above)


def parallel(blocks):
    width = max(_width(b) for b in blocks)
    # 各ブランチを同幅へ揃える (rail 行は - で延長、他は空白)
    norm = []
    rails_abs = []
    cur = 0
    for lines, rail in blocks:
        block = []
        for idx, ln in enumerate(lines):
            block.append(ln.ljust(width, "-" if idx == rail else " "))
        rails_abs.append(cur + rail)
        cur += len(block)
        norm.append(block)
    stacked = [ln for block in norm for ln in block]
    first, last = rails_abs[0], rails_abs[-1]
    out = []
    for i, ln in enumerate(stacked):
        if i in rails_abs:
            left = "+"
            right = "+"
        elif first < i < last:
            left = "|"
            right = "|"
        else:
            left = " "
            right = " "
        out.append(left + ln + right)
    return (out, first)


def render_expr(node):
    if node[0] == "var":
        return leaf_block(node[1], node[2])
    if node[0] == "and":
        return series([render_expr(c) for c in node[1]])
    if node[0] == "or":
        return parallel([render_expr(c) for c in node[1]])
    raise ParseError("未知ノード")


def render_rung(lhs, node):
    body = series([render_expr(node), coil_block(lhs)])
    lines, _ = body
    # 左右の電源母線
    return ["|" + ln + "|" for ln in lines]


# ---------------- メイン ----------------
def main():
    ap = argparse.ArgumentParser(description="ST ブール式 → ASCII ラダー図ビュー")
    ap.add_argument("--st", required=True, help="ST ソース")
    ap.add_argument("--out", help="出力先 (省略時は標準出力)")
    args = ap.parse_args()

    try:
        with open(args.st, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        raise SystemExit(f"ERROR: ST ファイルが見つかりません: {args.st}")
    except OSError as e:
        raise SystemExit(f"ERROR: ST ファイルの読み込みに失敗しました: {e}")

    out_lines = ["=== ラダー図ビュー (ST からの参考変換) ===",
                 "凡例: ] [ a接点  ]/[ b接点  ( ) 出力コイル  | 母線", ""]
    for lhs, rhs in extract_assignments(text):
        out_lines.append(f"-- {lhs} := {rhs}")
        try:
            node = Parser(tokenize_bool(rhs)).parse()
            out_lines.extend(render_rung(lhs, node))
        except ParseError as e:
            out_lines.append(f"   [非対応: {e}] 式をそのまま参照してください")
        out_lines.append("")

    report = "\n".join(out_lines)
    print(report)
    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(report + "\n")
        except OSError as e:
            raise SystemExit(f"ERROR: 出力ファイルの書き込みに失敗しました: {e}")


if __name__ == "__main__":
    main()
