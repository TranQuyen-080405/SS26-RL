"""Eval công thức reward an toàn (AST) cho Learn Lab."""

import ast
import operator
import re

_BIN = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
_CMP = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}
_BOOL = {ast.And: all, ast.Or: any}


def normalize_student_ops(expr):
    """Chuẩn hóa phép học sinh (+ − × ÷ ^) sang cú pháp Python eval."""
    s = str(expr).strip()
    s = s.replace("\u2212", "-").replace("\u2013", "-").replace("\u2014", "-")
    s = s.replace("\u00d7", "*").replace("\u00f7", "/")
    s = re.sub(r"\s*\^\s*", " ** ", s)
    return s


def safe_eval_formula(expr, variables):
    if not expr or not str(expr).strip():
        return 0.0
    normalized = normalize_student_ops(expr)
    tree = ast.parse(normalized.strip(), mode="eval")
    return float(_eval_node(tree.body, variables))


def _eval_node(node, variables):
    if isinstance(node, ast.Constant):  # For Python 3.8+
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in variables:
            raise ValueError("Biến không hợp lệ: %s" % node.id)
        return variables[node.id]
    if isinstance(node, ast.UnaryOp):
        v = _eval_node(node.operand, variables)
        if isinstance(node.op, ast.USub):
            return -v
        if isinstance(node.op, ast.Not):
            return not v
        if isinstance(node.op, ast.UAdd):
            return +v
    if isinstance(node, ast.BinOp):
        return _BIN[type(node.op)](_eval_node(node.left, variables), _eval_node(node.right, variables))
    if isinstance(node, ast.BoolOp):
        vals = [_eval_node(v, variables) for v in node.values]
        return _BOOL[type(node.op)](vals)
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, variables)
        for op, comp in zip(node.ops, node.comparators):
            right = _eval_node(comp, variables)
            if not _CMP[type(op)](left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.IfExp):
        return _eval_node(node.body, variables) if _eval_node(node.test, variables) else _eval_node(node.orelse, variables)
    raise ValueError("Cú pháp không hỗ trợ: %s" % type(node).__name__)
