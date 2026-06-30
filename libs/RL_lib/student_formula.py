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


def label_for(eid):
    return REWARD_ELEMENTS[eid]["label"]


def labels_sorted():
    items = [(meta["label"], eid) for eid, meta in REWARD_ELEMENTS.items()]
    return sorted(items, key=lambda x: -len(x[0]))


def default_total_formula(enabled_modules):
    tokens = []
    for eid, meta in REWARD_ELEMENTS.items():
        if meta["module"] in enabled_modules:
            if tokens:
                tokens.append({"kind": "op", "value": "+", "display": "+"})
            tokens.append({"kind": "reward", "value": meta["label"], "display": meta["label"]})
    if not tokens:
        tokens = [{"kind": "reward", "value": "Mỗi bước đi", "display": "Mỗi bước đi"}]
    return tokens


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
            parts.append(val)
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
    s = str(expr).strip()
    while i < len(s):
        if s[i].isspace():
            i += 1
            continue
        for lbl in labels:
            if s[i:].startswith(lbl):
                tokens.append({"kind": "reward", "value": lbl, "display": lbl})
                i += len(lbl)
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
    return tokens


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
    s = normalize_student_ops(expr)
    for lbl, eid in labels_sorted():
        if eid not in enabled_eids:
            # Replace with 0.0 if the module for this label is disabled
            s = re.sub(r'\b' + re.escape(lbl) + r'\b', '0.0', s)
        else:
            s = re.sub(r'\b' + re.escape(lbl) + r'\b', f"{_PART_PREFIX}{eid}", s)

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
