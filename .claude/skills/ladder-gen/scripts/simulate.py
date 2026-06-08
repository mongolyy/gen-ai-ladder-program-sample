#!/usr/bin/env python3
"""
工程⑤.5 スキャンサイクルシミュレーター

ST プログラムをスキャンサイクルで模擬し、タイミングチャート(PNG)を生成する。

対応 ST 構文:
  - ブール/整数 代入  X := expr ;
  - IF / ELSIF / ELSE / END_IF
  - CASE / OF / ELSE / END_CASE
  - FB呼び出し (TON 等 — 簡易模擬)

使い方:
  python3 simulate.py --st prog.st --devices dev.csv --scenario scenario.yaml \\
                      [--chart chart.png] [--log sim.txt] [--cycles 30]

シナリオ YAML 書式:
  meta:
    name: テスト名
  initial:          # 初期値
    STATE: 0
    ESTOP: true
  steps:            # サイクルごとの入力切り替え
    - at_cycle: 2
      inputs:
        START_FWD: true
  watch:            # チャートに表示する変数 (省略時 = 全 I/O デバイス)
    - MOTOR_FWD
    - MOTOR_REV
"""
import argparse
import csv
import re
import sys
from pathlib import Path

try:
    import yaml
    def _yaml_load(text):
        return yaml.safe_load(text)
except ImportError:
    def _yaml_load(text):
        raise SystemExit("pyyaml が必要です: pip install pyyaml")

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


# ============================================================
# Tokenizer
# ============================================================

_TOK_SPEC = [
    ("COMMENT",    r"\(\*.*?\*\)"),
    ("LINECOMMENT", r"//[^\n]*"),
    ("TIME_LIT",   r"\bT#[^\s;,)]+|\bTIME#[^\s;,)]+"),
    ("ASSIGN",     r":="),
    ("SEMI",       r";"),
    ("COLON",      r":(?!=)"),
    ("LPAREN",     r"\("),
    ("RPAREN",     r"\)"),
    ("COMMA",      r","),
    ("CMP",        r"<>|<=|>=|<|>|="),
    ("DOT",        r"\."),
    ("NUMBER",     r"\b\d+\b"),
    ("WORD",       r"[A-Za-z_][A-Za-z0-9_]*"),
    ("SKIP",       r"[\s]+"),
    ("OTHER",      r"."),
]
_TOK_RE = re.compile(
    "|".join(f"(?P<{n}>{p})" for n, p in _TOK_SPEC),
    re.DOTALL,
)

_KW = {
    "IF", "THEN", "ELSE", "ELSIF", "END_IF",
    "CASE", "OF", "END_CASE",
    "WHILE", "DO", "END_WHILE",
    "FOR", "TO", "BY", "END_FOR",
    "PROGRAM", "END_PROGRAM",
    "VAR", "VAR_INPUT", "VAR_OUTPUT", "VAR_GLOBAL", "END_VAR",
    "FUNCTION", "END_FUNCTION", "FUNCTION_BLOCK", "END_FUNCTION_BLOCK",
    "AND", "OR", "NOT", "XOR", "MOD",
    "TRUE", "FALSE",
    "BOOL", "INT", "DINT", "UINT", "WORD", "DWORD", "REAL",
    "LREAL", "TIME", "STRING", "BYTE",
}


def tokenize(text):
    toks = []
    for m in _TOK_RE.finditer(text):
        kind = m.lastgroup
        val = m.group()
        if kind in ("SKIP", "COMMENT", "LINECOMMENT"):
            continue
        if kind == "WORD":
            upper = val.upper()
            if upper in _KW:
                kind = upper
                val = upper
        toks.append((kind, val))
    toks.append(("EOF", ""))
    return toks


# ============================================================
# Parser  →  AST (list of statement dicts)
# ============================================================
# Node types:
#   {"type": "assign",  "lhs": str, "rhs": str}
#   {"type": "fb_call", "name": str, "args": {param: expr_str}}
#   {"type": "if",      "branches": [(cond_str, [stmts])], "else": [stmts]}
#   {"type": "case",    "var": str, "branches": {int: [stmts]}, "else": [stmts]}

class _ParseError(Exception):
    pass


class _Parser:
    def __init__(self, tokens):
        self.t = tokens
        self.i = 0

    def peek(self, offset=0):
        i = self.i + offset
        return self.t[i] if i < len(self.t) else ("EOF", "")

    def consume(self, kind=None, val=None):
        tok = self.t[self.i]
        if kind and tok[0] != kind:
            raise _ParseError(f"期待 {kind}, 実際 {tok}")
        if val and tok[1].upper() != val.upper():
            raise _ParseError(f"期待 '{val}', 実際 '{tok[1]}'")
        self.i += 1
        return tok

    def try_consume(self, kind=None, val=None):
        tok = self.peek()
        if kind and tok[0] != kind:
            return None
        if val and tok[1].upper() != val.upper():
            return None
        self.i += 1
        return tok

    # ------ Statement list ------
    def parse_stmts(self, until_kinds):
        """Parse statements until peek kind is in until_kinds."""
        stmts = []
        while self.peek()[0] not in until_kinds and self.peek()[0] != "EOF":
            s = self.parse_one_stmt()
            if s:
                stmts.append(s)
        return stmts

    def parse_one_stmt(self):
        k, v = self.peek()

        # Skip VAR blocks
        if k in ("VAR", "VAR_INPUT", "VAR_OUTPUT", "VAR_GLOBAL"):
            self._skip_until_kw("END_VAR")
            return None
        if k in ("PROGRAM", "FUNCTION", "FUNCTION_BLOCK"):
            return None  # handled at top level
        if k in ("END_PROGRAM", "END_FUNCTION", "END_FUNCTION_BLOCK"):
            self.consume()
            return None

        if k == "IF":
            return self.parse_if()
        if k == "CASE":
            return self.parse_case()
        if k == "WHILE":
            return self.parse_while()

        # Assignment or FB call:  IDENT (:= expr ; | ( params ) ;)
        if k == "WORD":
            # Look ahead for := or (
            la = self.peek(1)
            if la[0] == "ASSIGN":
                return self.parse_assign()
            if la[0] == "DOT":
                # FB output usage or struct member — skip as expression
                return self._skip_to_semi()
            if la[0] == "LPAREN":
                return self.parse_fb_call()
            # Unknown identifier token, skip
            self.consume()
            return None

        # Skip semicolons
        if k == "SEMI":
            self.consume()
            return None

        # Skip anything else we don't recognise
        self.consume()
        return None

    def parse_assign(self):
        lhs_tok = self.consume("WORD")
        self.consume("ASSIGN")
        rhs_toks = self._collect_expr_toks()
        self.try_consume("SEMI")
        return {"type": "assign", "lhs": lhs_tok[1], "rhs": _toks_to_str(rhs_toks)}

    def parse_fb_call(self):
        name_tok = self.consume("WORD")
        self.consume("LPAREN")
        args = {}
        while self.peek()[0] not in ("RPAREN", "EOF"):
            if self.peek()[0] == "WORD" and self.peek(1)[0] == "ASSIGN":
                param = self.consume("WORD")[1]
                self.consume("ASSIGN")
                expr_toks = self._collect_expr_toks(stop_at={"COMMA", "RPAREN"})
                args[param] = _toks_to_str(expr_toks)
            else:
                # positional arg or unexpected, collect and break
                self._collect_expr_toks(stop_at={"COMMA", "RPAREN"})
            self.try_consume("COMMA")
        self.try_consume("RPAREN")
        self.try_consume("SEMI")
        return {"type": "fb_call", "name": name_tok[1], "args": args}

    def parse_if(self):
        self.consume("IF")
        cond_toks = self._collect_expr_toks(stop_at={"THEN"})
        self.consume("THEN")
        branches = [(_toks_to_str(cond_toks),
                     self.parse_stmts({"ELSE", "ELSIF", "END_IF"}))]
        while self.peek()[0] == "ELSIF":
            self.consume("ELSIF")
            cond_toks = self._collect_expr_toks(stop_at={"THEN"})
            self.consume("THEN")
            branches.append((_toks_to_str(cond_toks),
                              self.parse_stmts({"ELSE", "ELSIF", "END_IF"})))
        else_stmts = []
        if self.try_consume("ELSE"):
            else_stmts = self.parse_stmts({"END_IF"})
        self.consume("END_IF")
        self.try_consume("SEMI")
        return {"type": "if", "branches": branches, "else": else_stmts}

    def parse_case(self):
        self.consume("CASE")
        var_tok = self.consume("WORD")
        self.consume("OF")
        branches = {}
        else_stmts = []
        while self.peek()[0] not in ("END_CASE", "EOF"):
            if self.peek()[0] == "ELSE":
                self.consume("ELSE")
                else_stmts = self.parse_stmts({"END_CASE"})
            elif self.peek()[0] == "NUMBER":
                num = int(self.consume("NUMBER")[1])
                self.try_consume("COLON")
                stmts = self.parse_stmts({"NUMBER", "ELSE", "END_CASE"})
                branches[num] = stmts
            else:
                self.consume()  # skip unexpected
        self.consume("END_CASE")
        self.try_consume("SEMI")
        return {"type": "case", "var": var_tok[1], "branches": branches, "else": else_stmts}

    def parse_while(self):
        self.consume("WHILE")
        self._collect_expr_toks(stop_at={"DO"})
        self.consume("DO")
        self.parse_stmts({"END_WHILE"})
        self.consume("END_WHILE")
        self.try_consume("SEMI")
        return None  # not simulated

    def _collect_expr_toks(self, stop_at=None):
        if stop_at is None:
            stop_at = {"SEMI"}
        toks = []
        depth = 0
        while True:
            k, v = self.peek()
            if k == "EOF":
                break
            if k == "LPAREN":
                depth += 1
            elif k == "RPAREN":
                if depth == 0:
                    break
                depth -= 1
            elif depth == 0 and k in stop_at:
                break
            toks.append((k, v))
            self.i += 1
        return toks

    def _skip_to_semi(self):
        while self.peek()[0] not in ("SEMI", "EOF"):
            self.consume()
        self.try_consume("SEMI")
        return None

    def _skip_until_kw(self, kw):
        while self.peek()[0] not in (kw, "EOF"):
            self.i += 1
        self.try_consume(kw)


def _toks_to_str(toks):
    return " ".join(v for _, v in toks)


def parse_st(text):
    tokens = tokenize(text)
    parser = _Parser(tokens)
    # Skip top-level PROGRAM/VAR wrappers
    stmts = parser.parse_stmts({"EOF"})
    return [s for s in stmts if s is not None]


# ============================================================
# Expression evaluator
# ============================================================

_SAFE_BUILTINS = {"bool": bool, "int": int, "True": True, "False": False}

_OP_MAP = [
    (re.compile(r"\bAND\b", re.I), " and "),
    (re.compile(r"\bOR\b",  re.I), " or "),
    (re.compile(r"\bNOT\b", re.I), " not "),
    (re.compile(r"\bTRUE\b",  re.I), " True "),
    (re.compile(r"\bFALSE\b", re.I), " False "),
    (re.compile(r"\bXOR\b", re.I), " ^ "),
    (re.compile(r"<>"),  " != "),
    (re.compile(r"(?<![<>!])=(?!=)"), " == "),
]


def _st_expr_to_py(expr):
    """Translate a ST expression string to a Python-evaluable string."""
    result = expr
    # FB.Q notation → FB_Q
    result = re.sub(r"([A-Za-z_]\w*)\.([A-Za-z_]\w*)", r"\1_\2", result)
    # TIME literals → 0 (not simulated)
    result = re.sub(r"\bT#[^\s;,)]+|\bTIME#[^\s;,)]+", "0", result)
    for pattern, repl in _OP_MAP:
        result = pattern.sub(repl, result)
    return result


def eval_expr(expr_str, env):
    """Evaluate ST expression; return bool or int. Returns False on error."""
    py_expr = _st_expr_to_py(expr_str)
    try:
        result = eval(py_expr, {"__builtins__": _SAFE_BUILTINS}, env)  # noqa: S307
        return result
    except Exception:
        return False


# ============================================================
# Executor
# ============================================================

class _TimerState:
    def __init__(self):
        self.in_val = False
        self.elapsed = 0
        self.preset = 5  # scan cycles (T# not parsed precisely)
        self.q = False
        self.et = 0


def execute_stmts(stmts, env, timers):
    """Execute a list of statement AST nodes, updating env in place."""
    for stmt in stmts:
        _exec_stmt(stmt, env, timers)


def _exec_stmt(stmt, env, timers):
    t = stmt["type"]
    if t == "assign":
        lhs = stmt["lhs"]
        val = eval_expr(stmt["rhs"], env)
        # Coerce to int if the device is INT type, else bool
        if isinstance(val, bool):
            env[lhs] = val
        else:
            try:
                env[lhs] = int(val)
            except (TypeError, ValueError):
                env[lhs] = False

    elif t == "fb_call":
        _exec_fb(stmt, env, timers)

    elif t == "if":
        for cond_str, then_stmts in stmt["branches"]:
            if eval_expr(cond_str, env):
                execute_stmts(then_stmts, env, timers)
                return
        execute_stmts(stmt["else"], env, timers)

    elif t == "case":
        var_val = env.get(stmt["var"], 0)
        try:
            var_int = int(var_val)
        except (TypeError, ValueError):
            var_int = 0
        branch = stmt["branches"].get(var_int)
        if branch is not None:
            execute_stmts(branch, env, timers)
        else:
            execute_stmts(stmt["else"], env, timers)


def _exec_fb(stmt, env, timers):
    """Minimal TON/TOF/TP simulation."""
    name = stmt["name"]
    args = stmt["args"]
    if name not in timers:
        timers[name] = _TimerState()
    tmr = timers[name]

    in_val = bool(eval_expr(args.get("IN", "FALSE"), env))
    tmr.in_val = in_val

    if in_val:
        tmr.elapsed = min(tmr.elapsed + 1, tmr.preset + 1)
    else:
        tmr.elapsed = 0

    tmr.q = tmr.elapsed >= tmr.preset
    tmr.et = tmr.elapsed

    env[f"{name}_Q"] = tmr.q
    env[f"{name}_ET"] = tmr.et


# ============================================================
# Device master loader
# ============================================================

def load_devices(path):
    devices = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            label = (row.get("label") or "").strip()
            if label:
                devices[label] = {k: (v or "").strip() for k, v in row.items()}
    return devices


# ============================================================
# Scenario loader
# ============================================================

def load_scenario(path):
    with open(path, encoding="utf-8") as f:
        return _yaml_load(f.read()) or {}


# ============================================================
# Simulator
# ============================================================

def run_simulation(ast, devices, scenario, total_cycles):
    # Build initial environment from devices
    env = {}
    for label, dev in devices.items():
        io = dev.get("io", "")
        typ = dev.get("type", "BOOL").upper()
        if typ in ("INT", "DINT", "UINT", "WORD", "DWORD"):
            env[label] = 0
        else:
            env[label] = False

    # Apply scenario initial values
    initial = scenario.get("initial") or {}
    for var, val in initial.items():
        if isinstance(val, bool):
            env[var] = val
        elif isinstance(val, int):
            env[var] = val
        elif isinstance(val, str):
            env[var] = val.lower() not in ("false", "0", "no")

    # Build steps index: {cycle: {var: val}}
    steps_by_cycle = {}
    for step in (scenario.get("steps") or []):
        cyc = int(step.get("at_cycle", 0))
        steps_by_cycle.setdefault(cyc, {}).update(step.get("inputs") or {})

    timers = {}
    snapshots = []  # list of (cycle, env_copy)
    inputs = [label for label, dev in devices.items() if dev.get("io") == "input"]

    for cycle in range(total_cycles):
        # Inject inputs for this cycle
        if cycle in steps_by_cycle:
            for var, val in steps_by_cycle[cycle].items():
                if isinstance(val, bool):
                    env[var] = val
                elif isinstance(val, int):
                    env[var] = val
                else:
                    env[var] = str(val).lower() not in ("false", "0", "no")

        # Execute one scan cycle
        execute_stmts(ast, env, timers)

        snapshots.append((cycle, dict(env)))

    return snapshots


# ============================================================
# Text log formatter
# ============================================================

def format_log(snapshots, devices):
    lines = ["=== シミュレーションログ ==="]
    prev = {}
    for cycle, env in snapshots:
        changes = {k: v for k, v in env.items() if prev.get(k) != v}
        if not changes and cycle != 0:
            continue
        lines.append(f"\n[Cycle {cycle:3d}]")
        for label, dev in devices.items():
            val = env.get(label, "—")
            marker = " ←" if label in changes else "  "
            lines.append(f"  {marker} {label:20s} = {val}")
        prev = dict(env)
    return "\n".join(lines)


# ============================================================
# Timing chart
# ============================================================

def generate_chart(snapshots, devices, watch_vars, output_path, scenario=None):
    if not HAS_MPL:
        print("[WARN] matplotlib が見つかりません。チャートをスキップします。", file=sys.stderr)
        return

    cycles = [c for c, _ in snapshots]
    envs   = [e for _, e in snapshots]

    # Determine variables to plot
    if watch_vars:
        plot_vars = [v for v in watch_vars if v in envs[0]]
    else:
        plot_vars = [label for label, dev in devices.items()
                     if dev.get("io") in ("input", "output")]
    if not plot_vars:
        plot_vars = list(envs[0].keys())

    # Separate bool and int variables
    bool_vars = [v for v in plot_vars if isinstance(envs[0].get(v, False), bool)]
    int_vars  = [v for v in plot_vars if isinstance(envs[0].get(v, 0), int)
                 and v not in bool_vars]

    n_rows = len(bool_vars) + (1 if int_vars else 0)
    if n_rows == 0:
        return

    fig_height = max(3, n_rows * 0.8 + 1.5)
    fig, axes = plt.subplots(n_rows, 1, figsize=(12, fig_height), sharex=True)
    if n_rows == 1:
        axes = [axes]

    ax_idx = 0

    # Plot boolean signals as step waveforms
    for var in bool_vars:
        vals = [1 if envs[i].get(var, False) else 0 for i in range(len(cycles))]
        ax = axes[ax_idx]
        ax.step(cycles, vals, where="post", color="#2196F3", linewidth=1.5)
        ax.fill_between(cycles, vals, step="post", alpha=0.15, color="#2196F3")
        ax.set_ylim(-0.2, 1.4)
        ax.set_yticks([0, 1])
        ax.set_yticklabels(["OFF", "ON"], fontsize=8)
        ax.set_ylabel(var, fontsize=8, rotation=0, labelpad=70, ha="right", va="center")
        ax.grid(axis="x", linestyle="--", alpha=0.3)
        ax.tick_params(axis="x", labelsize=7)
        ax_idx += 1

    # Plot integer variables (e.g. STATE) as a line
    if int_vars:
        ax = axes[ax_idx]
        colors = ["#E91E63", "#4CAF50", "#FF9800", "#9C27B0"]
        for j, var in enumerate(int_vars):
            vals = [int(envs[i].get(var, 0)) for i in range(len(cycles))]
            ax.step(cycles, vals, where="post",
                    color=colors[j % len(colors)], linewidth=1.5, label=var)
        ax.set_ylabel("State", fontsize=8, rotation=0, labelpad=70, ha="right", va="center")
        ax.legend(fontsize=7, loc="upper right")
        ax.grid(axis="x", linestyle="--", alpha=0.3)
        ax_idx += 1

    axes[-1].set_xlabel("Scan Cycle", fontsize=9)
    scenario_name = (scenario or {}).get("meta", {}).get("name", "") if isinstance(scenario, dict) else ""
    title = f"Timing Chart  {scenario_name}" if scenario_name else "Timing Chart"
    fig.suptitle(title, fontsize=11, y=0.98)
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"チャート保存: {output_path}")


# ============================================================
# Main
# ============================================================

def main():
    ap = argparse.ArgumentParser(description="工程⑤.5 ST スキャンサイクルシミュレーター")
    ap.add_argument("--st",       required=True, help="ST ソース (.st)")
    ap.add_argument("--devices",  required=True, help="デバイスマスタ (.csv)")
    ap.add_argument("--scenario", required=True, help="テストシナリオ (.yaml)")
    ap.add_argument("--chart",    help="タイミングチャート出力先 (.png)")
    ap.add_argument("--log",      help="ログ出力先 (.txt)")
    ap.add_argument("--cycles",   type=int, default=30, help="シミュレーションサイクル数 (デフォルト 30)")
    args = ap.parse_args()

    with open(args.st, encoding="utf-8") as f:
        st_text = f.read()

    devices  = load_devices(args.devices)
    scenario = load_scenario(args.scenario)
    total    = scenario.get("cycles") or args.cycles

    ast = parse_st(st_text)
    if not ast:
        print("[WARN] 実行可能な文が見つかりませんでした。", file=sys.stderr)

    snapshots = run_simulation(ast, devices, scenario, total)

    watch_vars = scenario.get("watch")
    log_text = format_log(snapshots, devices)
    print(log_text)
    if args.log:
        Path(args.log).parent.mkdir(parents=True, exist_ok=True)
        Path(args.log).write_text(log_text + "\n", encoding="utf-8")

    if args.chart or not args.log:
        chart_path = args.chart or "simulation.png"
        Path(chart_path).parent.mkdir(parents=True, exist_ok=True)
        generate_chart(snapshots, devices, watch_vars, chart_path, scenario=scenario)


if __name__ == "__main__":
    main()
