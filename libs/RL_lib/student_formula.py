"""Parse / serialize công thức dạng token (cục reward + phép toán)."""

import re
import ast

from RL_lib.lab_registry import REWARD_ELEMENTS
from RL_lib.reward_formula import normalize_student_ops, safe_eval_formula

_PART_PREFIX = "_p_"
_OP_DISPLAY = {"+": "+", "-": "−", "*": "×", "/": "÷", "^": "^", "(": "(", ")": ")"}
_BINARY_OPS = {"+", "-", "*", "/", "^"}
_PAREN_VALS = {"(", ")"}
_VALUE_KINDS = {"reward", "num"}
_INSTANCE_SUFFIX_RE = re.compile(r" #(\d+)$")
_OP_PARSE = {
    "+": "+",
    "-": "-",
    "\u2212": "-",
    "*": "*",
    "\u00d7": "*",
    "/": "/",
    "\u00f7": "/",
    "^": "^",
    "(": "(",
    ")": ")",
}

_LABEL_ALIASES = {
    "Vào lại ô cũ": "Quay lại ô",
    "Lặp ô (tổng)": "Lặp ô gần",
    "Lặp ô tổng": "Lặp ô gần",
    "Lại gần đích": "Lại gần goal",
    "Thay đổi khoảng cách tới Goal": "Lại gần goal",
    "Thay đổi khoảng cách tới Checkpoint": "Lại gần checkpoint",
    "Giữ nguyên hướng đi": "Giữ hướng n lần thì cộng",
}


def migrate_reward_labels(expr):
    s = str(expr or "")
    for old, new in _LABEL_ALIASES.items():
        s = s.replace(old, new)
    return s


def label_for(eid):
    return REWARD_ELEMENTS[eid]["label"]


def labels_sorted():
    items = [(meta["label"], eid) for eid, meta in REWARD_ELEMENTS.items()]
    return sorted(items, key=lambda x: -len(x[0]))


def default_total_formula(enabled_modules):
    """Công thức mặc định trống — học sinh tự kéo block reward vào."""
    return []


def reward_display_label(label, idx):
    return "%s #%d" % (label, idx)


def apply_reward_instance_displays(tokens):
    """Gán display #1, #2, ... cho từng block reward trùng loại trong công thức."""
    label_to_eid = {meta["label"]: eid for eid, meta in REWARD_ELEMENTS.items()}
    counts = {}
    for tok in tokens or []:
        if tok.get("kind") != "reward":
            continue
        label = tok.get("value") or ""
        base = _INSTANCE_SUFFIX_RE.sub("", label).strip()
        if base in label_to_eid:
            label = base
            tok["value"] = base
        eid = label_to_eid.get(label)
        if not eid:
            continue
        counts[eid] = counts.get(eid, 0) + 1
        tok["display"] = reward_display_label(REWARD_ELEMENTS[eid]["label"], counts[eid])
    return tokens


def strip_instance_suffixes_from_expr(expr):
    """Chuẩn hóa 'Label #2' → 'Label' để biên dịch công thức."""
    s = migrate_reward_labels(normalize_student_ops(str(expr or "")))
    labels = sorted({meta["label"] for meta in REWARD_ELEMENTS.values()}, key=len, reverse=True)
    for lbl in labels:
        s = re.sub(re.escape(lbl) + r" #\d+", lbl, s)
    return s


def tokens_to_expr(tokens):
    if not tokens:
        return ""
    parts = []
    for t in tokens:
        kind = t["kind"]
        val = t["value"]
        if kind == "reward":
            if parts and parts[-1] not in "(+-*/^":
                parts.append(" ")
            parts.append(t.get("display") or val)
        elif kind == "num":
            if parts and parts[-1] not in "(+-*/^":
                parts.append(" ")
            parts.append(val)
        elif kind == "paren":
            parts.extend([" ", val, " "])
        else:
            parts.extend([" ", val, " "])
    return "".join(parts).strip()


def parse_expr_to_tokens(expr, known_labels):
    """Chuỗi công thức → list token (reward / op / num)."""
    if not expr or not str(expr).strip():
        return []
    labels = sorted(set(known_labels), key=len, reverse=True)
    tokens = []
    i = 0
    s = migrate_reward_labels(str(expr).strip())
    while i < len(s):
        if s[i].isspace():
            i += 1
            continue
        for lbl in labels:
            if s[i:].startswith(lbl):
                end = i + len(lbl)
                suffix = re.match(r" #(\d+)", s[end:])
                if suffix:
                    end += suffix.end()
                tokens.append({"kind": "reward", "value": lbl, "display": lbl})
                i = end
                break
        else:
            ch = s[i]
            if ch in _OP_PARSE:
                sym = _OP_PARSE[ch]
                if sym in _PAREN_VALS:
                    tokens.append(
                        {"kind": "paren", "value": sym, "display": sym}
                    )
                else:
                    tokens.append(
                        {"kind": "op", "value": sym, "display": _OP_DISPLAY.get(sym, sym)}
                    )
                i += 1
                continue
            m = re.match(r"\d+(?:\.\d+)?", s[i:])
            if m:
                num = m.group()
                tokens.append({"kind": "num", "value": str(float(num)), "display": num})
                i += len(num)
                continue
            i += 1
    return apply_reward_instance_displays(tokens)


def _token_parts(token):
    kind = token.get("kind")
    val = token.get("value")
    if kind == "op" and val in _PAREN_VALS:
        return "paren", val
    return kind, val


def validate_formula_tokens(tokens):
    """Kiểm tra cú pháp công thức học sinh (token list).

    Quy tắc:
    - Giữa hai block (reward / số) phải có đúng một phép (+ - * / ^).
    - Không được hai phép toán liền nhau.
    - Ngoặc ( ) là nhóm riêng — có thể đứng cạnh phép toán.
    - Mở ( phải có đóng ) tương ứng.
    """
    if not tokens:
        return True, ""

    paren_depth = 0
    expect = "value"
    unary_ok = False

    for t in tokens:
        kind, val = _token_parts(t)

        if kind in _VALUE_KINDS:
            if expect != "value":
                return False, "Thiếu phép toán giữa hai thành phần"
            expect = "binop"
            unary_ok = False
            continue

        if kind == "paren":
            if val == "(":
                if expect == "binop":
                    return False, "Thiếu phép toán trước ("
                paren_depth += 1
                expect = "value"
                unary_ok = True
            else:
                if expect == "value":
                    return False, "Thiếu thành phần trước )"
                if paren_depth == 0:
                    return False, "Ngoặc đóng không khớp"
                paren_depth -= 1
                expect = "binop"
                unary_ok = False
            continue

        if kind == "op":
            if val not in _BINARY_OPS:
                return False, "Phép toán không hợp lệ"
            if expect == "value":
                if unary_ok and val in ("+", "-"):
                    unary_ok = False
                    continue
                return False, "Thiếu thành phần trước phép toán"
            if expect != "binop":
                return False, "Công thức không hợp lệ"
            expect = "value"
            unary_ok = False
            continue

        return False, "Công thức không hợp lệ"

    if expect == "value":
        return False, "Công thức chưa hoàn chỉnh"
    if paren_depth != 0:
        return False, "Chưa đóng ngoặc"
    return True, ""


def compile_student_formula(expr, enabled_eids):
    if not expr or not str(expr).strip():
        return ""
    s = strip_instance_suffixes_from_expr(expr)
    for lbl, eid in labels_sorted():
        if lbl not in s:
            continue
        replacement = "0.0" if eid not in enabled_eids else "%s%s" % (_PART_PREFIX, eid)
        s = s.replace(lbl, replacement)

    # Validate expression to prevent arbitrary code execution
    tree = ast.parse(s, mode='eval')
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Call, ast.Name, ast.Constant, ast.Load, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd)):
            raise ValueError(f"Unsupported operation in formula: {type(node).__name__}")
    return s


def eval_student_formula(expr, part_values, enabled_eids):
    compiled = compile_student_formula(expr, enabled_eids)
    if not compiled:
        return 0.0
    variables = {}
    for eid in enabled_eids:
        variables["%s%s" % (_PART_PREFIX, eid)] = float(part_values.get(eid, 0.0))
    try:
        return safe_eval_formula(compiled, variables)
    except (ValueError, SyntaxError, TypeError, ZeroDivisionError):
        return 0.0
