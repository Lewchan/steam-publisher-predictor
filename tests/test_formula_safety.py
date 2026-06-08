# Steve 2026/06/07 迭代创建 - 测试 forecasting.py 完整功能覆盖

from datetime import date
from unittest import mock

import pytest

from steam_publisher_predictor.models import SteamGame
from steam_publisher_predictor.services.forecasting import (
    DEFAULT_FORMULA,
    FormulaError,
    _validate_node,
    build_features,
    evaluate_formula,
    predict_sales,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BASE_GAME = SteamGame(
    app_id=42,
    name="Test Game",
    url="https://store.steampowered.com/app/42/",
    developer_names=["Studio"],
    publisher_names=["Pub"],
    genres=["RPG"],
    steam_tags=["RPG"],
    categories=["Single-player"],
    supported_languages=["English"],
    price_usd=19.99,
    review_count=5000,
    review_score=80.0,
    metacritic_score=75,
    dlc_count=2,
    required_age=16,
    has_demo=True,
    has_achievements=True,
    is_free=False,
    coming_soon=False,
    release_date="2025-01-15",
    short_description="A test game for formula safety testing.",
    steamdb=None,
)

VALID_FEATURES = {
    "price_usd": 19.99,
    "review_count": 5000.0,
    "review_score": 80.0,
    "metacritic_score": 75.0,
    "has_demo": 1.0,
    "has_achievements": 1.0,
    "is_free": 0.0,
    "dlc_count": 2.0,
    "developer_count": 1.0,
    "publisher_count": 1.0,
    "genre_count": 1.0,
    "category_count": 1.0,
    "description_length": 51.0,
    "supported_language_count": 1.0,
    "required_age": 16.0,
    "days_since_release": 500.0,
    "coming_soon": 0.0,
}

# ---------------------------------------------------------------------------
# evaluate_formula — happy-path correctness
# ---------------------------------------------------------------------------

def test_simple_addition():
    result = evaluate_formula("a + b", {"a": 3.0, "b": 4.0})
    assert result == 7.0


def test_multiplication_and_division():
    result = evaluate_formula("(x * y) / z", {"x": 10.0, "y": 2.0, "z": 4.0})
    assert result == pytest.approx(5.0)


def test_power_operator():
    result = evaluate_formula("x ** 2", {"x": 5.0})
    assert result == 25.0


def test_negative_result_clamped_by_max():
    # max(0, -100) == 0
    result = evaluate_formula("max(0, -100)", {})
    assert result == 0.0


def test_default_formula_produces_reasonable_result():
    result = evaluate_formula(DEFAULT_FORMULA, VALID_FEATURES)
    # The formula has large constants; result should be positive and reasonable
    assert result > 0


# ---------------------------------------------------------------------------
# evaluate_formula — allowed functions only
# ---------------------------------------------------------------------------

def test_allowed_abs():
    assert evaluate_formula("abs(-5)", {}) == 5.0


def test_allowed_log():
    assert evaluate_formula("log(1)", {}) == pytest.approx(0.0)


def test_allowed_log1p():
    assert evaluate_formula("log1p(0)", {}) == pytest.approx(0.0)


def test_allowed_max_min():
    assert evaluate_formula("max(a, b)", {"a": 1, "b": 2}) == 2.0
    assert evaluate_formula("min(a, b)", {"a": 1, "b": 2}) == 1.0


def test_allowed_pow():
    assert evaluate_formula("pow(2, 3)", {}) == 8.0


def test_allowed_sqrt():
    assert evaluate_formula("sqrt(16)", {}) == 4.0


# ---------------------------------------------------------------------------
# evaluate_formula — disallowed constructs
# ---------------------------------------------------------------------------

def test_rejects_builtin_len():
    with pytest.raises(FormulaError, match="Only approved functions"):
        evaluate_formula("len(x)", {"x": 1.0})


def test_rejects_builtin_open():
    with pytest.raises(FormulaError, match="Only approved functions"):
        evaluate_formula("open('config')", {})


def test_rejects_disallowed_operator():
    with pytest.raises(FormulaError, match="not allowed"):
        evaluate_formula("x // 2", {"x": 10.0})  # floor div not in ALLOWED


def test_rejects_unknown_variable():
    with pytest.raises(FormulaError, match="Unknown variable"):
        evaluate_formula("a + secret", {"a": 1.0})


def test_rejects_unknown_function_call():
    with pytest.raises(FormulaError, match="Unknown variable or function|Only approved"):
        evaluate_formula("os.getenv('KEY')", {})


def test_rejects_dunder_access():
    """Try to access __builtins__ or __class__."""
    with pytest.raises(FormulaError):
        evaluate_formula("__builtins__", {})


def test_rejects_attribute_access():
    """ast.Attribute is not handled, should raise FormulaError."""
    with pytest.raises(FormulaError, match="Unsupported formula construct"):
        evaluate_formula("x.__class__", {"x": 1.0})


# ---------------------------------------------------------------------------
# evaluate_formula — constant validation
# ---------------------------------------------------------------------------

def test_rejects_string_constant():
    with pytest.raises(FormulaError, match="Only numeric constants"):
        evaluate_formula("'hello'", {})


def test_rejects_none_constant():
    with pytest.raises(FormulaError, match="Only numeric constants"):
        evaluate_formula("None", {})


def test_rejects_list_constant():
    with pytest.raises(FormulaError):  # Rejected as unsupported construct
        evaluate_formula("[1, 2, 3]", {})


# ---------------------------------------------------------------------------
# evaluate_formula — unary operators
# ---------------------------------------------------------------------------

def test_positive_unary():
    assert evaluate_formula("+5", {}) == 5.0


def test_negative_unary():
    assert evaluate_formula("-3", {}) == -3.0


def test_rejects_bitwise_not():
    """~ is BitWise_Not, not in ALLOWED_UNARY_OPERATORS."""
    with pytest.raises(FormulaError, match="not allowed"):
        evaluate_formula("~5", {})


# ---------------------------------------------------------------------------
# evaluate_formula — syntax errors
# ---------------------------------------------------------------------------

def test_syntax_error_raised():
    with pytest.raises(FormulaError, match="syntax error"):
        evaluate_formula("a +", {})


def test_empty_formula():
    with pytest.raises(FormulaError, match="syntax error"):
        evaluate_formula("", {})


# ---------------------------------------------------------------------------
# evaluate_formula — boundary values
# ---------------------------------------------------------------------------

def test_zero_value():
    assert evaluate_formula("a * 0", {"a": 100.0}) == 0.0


def test_very_large_value():
    result = evaluate_formula("x * y", {"x": 1e15, "y": 1e15})
    assert result == pytest.approx(1e30)


def test_negative_input():
    result = evaluate_formula("x + y", {"x": -5.0, "y": 3.0})
    assert result == -2.0


def test_decimal_precision():
    result = evaluate_formula("x + y", {"x": 0.1, "y": 0.2})
    assert result == pytest.approx(0.3, abs=1e-9)


# ---------------------------------------------------------------------------
# _validate_node — unit-level
# ---------------------------------------------------------------------------

def test_validate_constant_int():
    import ast
    tree = ast.parse("42", mode="eval")
    _validate_node(tree, set())  # should not raise


def test_validate_constant_float():
    import ast
    tree = ast.parse("3.14", mode="eval")
    _validate_node(tree, set())  # should not raise


def test_validate_constant_string_rejected():
    import ast
    tree = ast.parse("'hello'", mode="eval")
    with pytest.raises(FormulaError):
        _validate_node(tree, set())


def test_validate_known_variable_accepted():
    import ast
    tree = ast.parse("my_var", mode="eval")
    _validate_node(tree, {"my_var"})  # should not raise


def test_validate_unknown_variable_rejected():
    import ast
    tree = ast.parse("unknown", mode="eval")
    with pytest.raises(FormulaError, match="Unknown variable"):
        _validate_node(tree, {"known_var"})


def test_validate_disallowed_operator_rejected():
    import ast
    tree = ast.parse("a // b", mode="eval")
    with pytest.raises(FormulaError, match="not allowed"):
        _validate_node(tree, {"a", "b"})


# ---------------------------------------------------------------------------
# build_features
# ---------------------------------------------------------------------------

def test_build_features_returns_all_keys():
    features = build_features(BASE_GAME, today=date(2026, 6, 7))
    expected_keys = {
        "price_usd", "review_count", "review_score", "metacritic_score",
        "has_demo", "has_achievements", "is_free", "dlc_count",
        "developer_count", "publisher_count", "genre_count",
        "category_count", "description_length", "supported_language_count",
        "required_age", "days_since_release", "coming_soon",
    }
    assert set(features.keys()) == expected_keys


def test_build_features_days_since_release():
    features = build_features(BASE_GAME, today=date(2026, 1, 15))
    assert features["days_since_release"] == pytest.approx(365.0)


def test_build_features_zero_days_for_coming_soon():
    game = SteamGame(
        app_id=99, name="Coming", url="https://x.app/99/",
        developer_names=[], publisher_names=[], genres=[],
        steam_tags=[], categories=[], supported_languages=[],
        price_usd=0.0, review_count=0, review_score=0.0,
        metacritic_score=0, dlc_count=0, required_age=0,
        has_demo=False, has_achievements=False, is_free=False,
        coming_soon=True, release_date=None, short_description="",
    )
    features = build_features(game, today=date(2026, 1, 1))
    assert features["days_since_release"] == 0.0


def test_build_features_all_values_are_float():
    features = build_features(BASE_GAME, today=date(2026, 6, 7))
    for v in features.values():
        assert isinstance(v, float)


# ---------------------------------------------------------------------------
# predict_sales (integration)
# ---------------------------------------------------------------------------

def test_predict_sales_returns_result():
    result = predict_sales(BASE_GAME, "review_count * 10")
    assert result.game.app_id == 42
    assert result.formula == "review_count * 10"
    assert result.features is not None
    assert result.estimated_sales == pytest.approx(50000.0)


def test_predict_sales_default_formula():
    result = predict_sales(BASE_GAME, DEFAULT_FORMULA)
    assert result.estimated_sales > 0


def test_predict_sales_rejects_bad_formula():
    with pytest.raises(FormulaError):
        predict_sales(BASE_GAME, "__builtins__")
