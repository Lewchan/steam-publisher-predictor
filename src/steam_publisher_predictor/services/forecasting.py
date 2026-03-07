from __future__ import annotations

import ast
import math
from datetime import date

from steam_publisher_predictor.models import PredictionResult, SteamGame

ALLOWED_FUNCTIONS = {
    "abs": abs,
    "log": math.log,
    "log1p": math.log1p,
    "max": max,
    "min": min,
    "pow": pow,
    "sqrt": math.sqrt,
}

ALLOWED_BINARY_OPERATORS = (
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
)
ALLOWED_UNARY_OPERATORS = (ast.UAdd, ast.USub)

DEFAULT_FORMULA = """
max(
    0,
    2500
    + review_count * 18
    + review_score * 120
    + price_usd * 350
    + log1p(days_since_release) * 900
    + has_achievements * 2500
    + metacritic_score * 90
)
""".strip()


class FormulaError(ValueError):
    """Raised when a formula cannot be evaluated safely."""


def build_features(game: SteamGame, today: date | None = None) -> dict[str, float]:
    today = today or date.today()
    release_date = date.fromisoformat(game.release_date) if game.release_date else today
    days_since_release = max((today - release_date).days, 0)

    return {
        "price_usd": float(game.price_usd),
        "review_count": float(game.review_count),
        "review_score": float(game.review_score),
        "metacritic_score": float(game.metacritic_score),
        "has_demo": float(game.has_demo),
        "has_achievements": float(game.has_achievements),
        "is_free": float(game.is_free),
        "dlc_count": float(game.dlc_count),
        "developer_count": float(len(game.developer_names)),
        "publisher_count": float(len(game.publisher_names)),
        "genre_count": float(len(game.genres)),
        "category_count": float(len(game.categories)),
        "description_length": float(len(game.short_description)),
        "supported_language_count": float(len(game.supported_languages)),
        "required_age": float(game.required_age),
        "days_since_release": float(days_since_release),
        "coming_soon": float(game.coming_soon),
    }


def predict_sales(game: SteamGame, formula: str) -> PredictionResult:
    features = build_features(game)
    estimated_sales = evaluate_formula(formula, features)
    return PredictionResult(
        game=game,
        formula=formula,
        features=features,
        estimated_sales=estimated_sales,
    )


def evaluate_formula(formula: str, variables: dict[str, float]) -> float:
    try:
        tree = ast.parse(formula, mode="eval")
    except SyntaxError as exc:
        raise FormulaError(f"Formula syntax error: {exc.msg}") from exc

    _validate_node(tree, set(variables))
    value = eval(compile(tree, "<formula>", "eval"), {"__builtins__": {}}, {**ALLOWED_FUNCTIONS, **variables})
    return float(value)


def _validate_node(node: ast.AST, variables: set[str]) -> None:
    if isinstance(node, ast.Expression):
        _validate_node(node.body, variables)
        return

    if isinstance(node, ast.Constant):
        if not isinstance(node.value, (int, float)):
            raise FormulaError("Only numeric constants are allowed in formulas.")
        return

    if isinstance(node, ast.Name):
        if node.id not in variables and node.id not in ALLOWED_FUNCTIONS:
            raise FormulaError(f"Unknown variable or function: {node.id}")
        return

    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, ALLOWED_BINARY_OPERATORS):
            raise FormulaError("This operator is not allowed in formulas.")
        _validate_node(node.left, variables)
        _validate_node(node.right, variables)
        return

    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, ALLOWED_UNARY_OPERATORS):
            raise FormulaError("This unary operator is not allowed in formulas.")
        _validate_node(node.operand, variables)
        return

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_FUNCTIONS:
            raise FormulaError("Only approved functions are allowed in formulas.")
        for argument in node.args:
            _validate_node(argument, variables)
        return

    raise FormulaError(f"Unsupported formula construct: {type(node).__name__}")
