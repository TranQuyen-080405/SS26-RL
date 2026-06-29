"""Parse / serialize công thức dạng token (cục reward + phép toán)."""

import re

from RL_lib.lab_registry import REWARD_ELEMENTS
from RL_lib.reward_formula import safe_eval_formula

_PART_PREFIX = "_p_"
_OP_DISPLAY = {"+": "+", "-": "−", "*": "×", "/": "÷", "^": "^", "(": "(", ")": ")"}


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
            if s[i] in "+-*/()^":
                ch = s[i]
                tokens.append(
                    {"kind": "op", "value": ch, "display": _OP_DISPLAY.get(ch, ch)}
                )
                i += 1
                continue
            m = re.match(r"\d+(?:\.\d+)?", s[i:])
            if m:
                num = m.group()
                tokens.append({"kind": "num", "value": num, "display": num})
                i += len(num)
                continue
            i += 1
    return tokens


def compile_student_formula(expr, enabled_eids):
    if not expr or not str(expr).strip():
        return ""
    s = str(expr).strip()
    for lbl, eid in labels_sorted():
        if eid not in enabled_eids:
            continue
        s = s.replace(lbl, "%s%s" % (_PART_PREFIX, eid))
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
