# A.T.O.M/tools/calculator.py
"""
Safe math expression evaluator for the A.T.O.M agent.
Uses Python's ast module to evaluate expressions without calling eval()
directly, preventing code injection.
"""
import ast
import math
import operator
import re

# Allowed operators
_OPS = {
    ast.Add:      operator.add,
    ast.Sub:      operator.sub,
    ast.Mult:     operator.mul,
    ast.Div:      operator.truediv,
    ast.Pow:      operator.pow,
    ast.Mod:      operator.mod,
    ast.FloorDiv: operator.floordiv,
    ast.USub:     operator.neg,
    ast.UAdd:     operator.pos,
}

# Allowed math functions
_FUNCS = {
    "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
    "tan": math.tan,   "log": math.log, "log10": math.log10,
    "log2": math.log2, "exp": math.exp, "abs": abs,
    "ceil": math.ceil, "floor": math.floor, "round": round,
    "pi": math.pi,     "e": math.e,
}


def _safe_eval(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant: {node.value}")

    if isinstance(node, ast.BinOp):
        op = _OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op(_safe_eval(node.left), _safe_eval(node.right))

    if isinstance(node, ast.UnaryOp):
        op = _OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported unary operator")
        return op(_safe_eval(node.operand))

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only named functions are allowed")
        fname = node.func.id
        if fname not in _FUNCS:
            raise ValueError(f"Function '{fname}' not allowed")
        fn = _FUNCS[fname]
        args = [_safe_eval(a) for a in node.args]
        return fn(*args)

    if isinstance(node, ast.Name):
        if node.id in _FUNCS:
            return _FUNCS[node.id]
        raise ValueError(f"Unknown name: {node.id}")

    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)

    raise ValueError(f"Unsupported AST node: {type(node).__name__}")


# ── Unit-conversion shortcuts ────────────────────────────────────── #
_UNIT_PATTERNS = [
    (re.compile(r"([\d.]+)\s*km\s+(?:to|in)\s+miles?", re.I),
     lambda m: f"{float(m.group(1))} km = {float(m.group(1)) * 0.621371:.4f} miles"),
    (re.compile(r"([\d.]+)\s*miles?\s+(?:to|in)\s+km", re.I),
     lambda m: f"{float(m.group(1))} miles = {float(m.group(1)) * 1.60934:.4f} km"),
    (re.compile(r"([\d.]+)\s*(?:°?C|celsius)\s+(?:to|in)\s+(?:°?F|fahrenheit)", re.I),
     lambda m: f"{float(m.group(1))}°C = {float(m.group(1)) * 9/5 + 32:.2f}°F"),
    (re.compile(r"([\d.]+)\s*(?:°?F|fahrenheit)\s+(?:to|in)\s+(?:°?C|celsius)", re.I),
     lambda m: f"{float(m.group(1))}°F = {(float(m.group(1)) - 32) * 5/9:.2f}°C"),
    (re.compile(r"([\d.]+)\s*kg\s+(?:to|in)\s+(?:lbs?|pounds?)", re.I),
     lambda m: f"{float(m.group(1))} kg = {float(m.group(1)) * 2.20462:.4f} lbs"),
    (re.compile(r"([\d.]+)\s*(?:lbs?|pounds?)\s+(?:to|in)\s+kg", re.I),
     lambda m: f"{float(m.group(1))} lbs = {float(m.group(1)) * 0.453592:.4f} kg"),
    (re.compile(r"([\d.]+)\s*%\s+of\s+([\d.]+)", re.I),
     lambda m: f"{m.group(1)}% of {m.group(2)} = {float(m.group(1)) / 100 * float(m.group(2)):.4f}"),
]


def calculate(expression: str) -> str:
    """
    Safely evaluate a math expression or unit conversion.
    Input: any natural-language math string, e.g. '(42 * 3.14) / 2'
    """
    expr = expression.strip()

    # Unit conversion shortcuts
    for pattern, formatter in _UNIT_PATTERNS:
        m = pattern.search(expr)
        if m:
            return formatter(m)

    # Strip natural language wrappers
    for strip in ("calculate ", "compute ", "what is ", "evaluate ",
                  "how much is ", "what's "):
        if expr.lower().startswith(strip):
            expr = expr[len(strip):]

    # Replace ^ with ** for Python
    expr = expr.replace("^", "**")

    try:
        tree = ast.parse(expr, mode="eval")
        result = _safe_eval(tree.body)

        # Format nicely
        if isinstance(result, float) and result == int(result):
            result = int(result)
        return f"{expression.strip()} = {result}"

    except ZeroDivisionError:
        return "❌ Division by zero."
    except Exception as e:
        return f"❌ Could not evaluate '{expression}': {e}"
