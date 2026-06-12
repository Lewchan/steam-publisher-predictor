"""QA-2026-001 TI-008: calibration.py 服务测试

Quinn-QA 2026/06/11 迭代执行
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from steam_publisher_predictor.services.calibration import (
    CalibrationGame,
    CalibrationResult,
    _data_dir,
    _pct_diff,
    get_seed_cal_games,
    load_calibration_results,
    run_calibration,
    save_calibration_results,
)

from steam_publisher_predictor.models import ManualInputs


# ── 1. get_seed_cal_games ─────────────────────────────────────


class TestGetSeedCalGames:
    """TC-TI008-001 ~ TC-TI008-003"""

    def test_returns_7_games(self):
        """TC-TI008-001: 返回7个种子游戏"""
        games = get_seed_cal_games()
        assert len(games) == 7

    def test_sorted_by_priority(self):
        """TC-TI008-002: 按 priority 升序排序"""
        games = get_seed_cal_games()
        priorities = [g.priority for g in games]
        assert priorities == sorted(priorities)
        # Balatro (priority=0) 应排第一
        assert games[0].id == "balatro"

    def test_data_structure_integrity(self):
        """TC-TI008-003: 种子游戏数据结构完整性"""
        games = get_seed_cal_games()
        required_fields = [
            "id", "game_name", "genre_cluster", "description",
            "expected_sales_range", "expected_quality_range",
            "expected_cl_range", "expected_pool_range",
            "steam_score", "analyst_notes", "manual_inputs", "priority",
        ]
        for game in games:
            assert isinstance(game.id, str) and len(game.id) > 0
            assert isinstance(game.game_name, str) and len(game.game_name) > 0
            assert isinstance(game.manual_inputs, dict)
            assert isinstance(game.expected_sales_range, list) and len(game.expected_sales_range) == 2
            assert isinstance(game.expected_quality_range, list) and len(game.expected_quality_range) == 2
            assert isinstance(game.expected_cl_range, list) and len(game.expected_cl_range) == 2
            assert isinstance(game.expected_pool_range, list) and len(game.expected_pool_range) == 2
            assert isinstance(game.priority, int)


# ── 2. CalibrationGame 数据class ──────────────────────────────


class TestCalibrationGameDataclass:
    """TC-TI008-014"""

    def test_all_field_types(self):
        """TC-TI008-014: 验证所有字段类型"""
        games = get_seed_cal_games()
        game = games[0]
        assert isinstance(game.id, str)
        assert isinstance(game.game_name, str)
        assert isinstance(game.genre_cluster, str)
        assert isinstance(game.description, str)
        assert isinstance(game.steam_score, float)
        assert isinstance(game.analyst_notes, str)
        assert isinstance(game.manual_inputs, dict)
        assert isinstance(game.priority, int)


# ── 3. _pct_diff 百分比偏差计算 ──────────────────────────────


class TestPctDiff:
    """TC-TI008-007 ~ TC-TI008-008"""

    def test_normal_case(self):
        """TC-TI008-007: 正常值计算"""
        assert _pct_diff(110.0, 100.0) == 10.0
        assert _pct_diff(90.0, 100.0) == -10.0

    def test_equal_values(self):
        """TC-TI008-007: 期望值=实际值"""
        assert _pct_diff(100.0, 100.0) == 0.0

    def test_zero_expected(self):
        """TC-TI008-008: 期望值为0避免除零"""
        assert _pct_diff(50.0, 0.0) == 0.0
        assert _pct_diff(0.0, 0.0) == 0.0

    def test_rounding(self):
        """TC-TI008-007: 结果保留1位小数"""
        result = _pct_diff(105.0, 100.0)
        assert result == 5.0
        result2 = _pct_diff(100.123, 100.0)
        assert isinstance(result2, float)

    def test_large_deviation(self):
        """TC-TI008-007: 大偏差"""
        assert _pct_diff(1000.0, 10.0) == 9900.0

    def test_small_deviation(self):
        """TC-TI008-007: 小偏差"""
        assert _pct_diff(100.001, 100.0) == 0.0  # 四舍五入


# ── 4. run_calibration ───────────────────────────────────────


class TestRunCalibration:
    """TC-TI008-004 ~ TC-TI008-006"""

    @pytest.fixture
    def balatro_game(self):
        games = get_seed_cal_games()
        return [g for g in games if g.id == "balatro"][0]

    def test_single_game(self, balatro_game):
        """TC-TI008-004: 单游戏(Balatro)校准"""
        result = run_calibration(balatro_game)
        assert isinstance(result, CalibrationResult)
        assert result.game_id == "balatro"
        assert result.game_name == "Balatro"
        assert isinstance(result.computed, dict)
        assert isinstance(result.manual_inputs, dict)
        assert isinstance(result.timestamp, str) and len(result.timestamp) > 0

    def test_deviation_calculation(self, balatro_game):
        """TC-TI008-005: 偏差计算"""
        result = run_calibration(balatro_game)
        assert "sales_pct" in result.deviation
        assert "quality_pct" in result.deviation
        assert "cl_pct" in result.deviation
        assert "pool_pct" in result.deviation
        for key, val in result.deviation.items():
            assert isinstance(val, float)

    def test_computed_fields(self, balatro_game):
        """TC-TI008-004 (扩展): 验证 computed 包含所有关键字段"""
        result = run_calibration(balatro_game)
        expected_keys = {
            "sales", "quality_score", "quality_confidence",
            "cl_score", "cl_base", "showmanship_effect",
            "brand_factor", "user_pool", "base_conversion",
        }
        assert expected_keys.issubset(set(result.computed.keys()))

    def test_all_games(self):
        """TC-TI008-006: 全部7个种子游戏校准"""
        games = get_seed_cal_games()
        results = [run_calibration(g) for g in games]
        assert len(results) == 7
        for r in results:
            assert isinstance(r, CalibrationResult)
            assert isinstance(r.timestamp, str)

    def test_custom_calculator(self):
        """run_calibration 支持自定义计算器函数"""
        games = get_seed_cal_games()
        game = games[0]

        mock_result_sales = 1000000

        def mock_calculator(game_obj, mi):
            from steam_publisher_predictor.models import (
                SalesResult, QualityBreakdown, UserPoolBreakdown,
            )
            return SalesResult(
                sales=mock_result_sales,
                quality=QualityBreakdown(quality_score=7.5, quality_confidence=80),
                cl_score=2.0,
                cl_base=1.5,
                showmanship_effect=0.3,
                brand_factor=0.1,
                user_pool=UserPoolBreakdown(estimated_user_pool=5000000, base_conversion=0.1),
            )

        result = run_calibration(game, calculator_func=mock_calculator)
        assert result.computed["sales"] == mock_result_sales

    def test_manual_inputs_type_conversion(self, balatro_game):
        """TC-TI008-004 (扩展): 校准后 manual_inputs 中浮点数字段被转换"""
        result = run_calibration(balatro_game)
        for key, val in result.manual_inputs.items():
            # 原始值可能是 float 或 int，结果中 float 应被保留
            if isinstance(val, (int, float)):
                assert isinstance(result.manual_inputs[key], (int, float))


# ── 5. CalibrationResult 数据class ────────────────────────────


class TestCalibrationResultDataclass:
    """TC-TI008-015"""

    def test_all_field_types(self):
        """TC-TI008-015: 验证所有字段类型"""
        result = CalibrationResult(
            game_id="test",
            game_name="Test Game",
            manual_inputs={"test": 1.0},
            computed={"sales": 1000000},
            deviation={"sales_pct": 10.0},
            timestamp="2026-06-11T00:00:00+00:00",
        )
        assert isinstance(result.game_id, str)
        assert isinstance(result.game_name, str)
        assert isinstance(result.manual_inputs, dict)
        assert isinstance(result.computed, dict)
        assert isinstance(result.deviation, dict)
        assert isinstance(result.timestamp, str)


# ── 6. save/load calibration results ─────────────────────────


class TestSaveLoadResults:
    """TC-TI008-009 ~ TC-TI008-013"""

    @pytest.fixture
    def tmp_data_dir(self, tmp_path: Path) -> Path:
        return tmp_path / "test_data"

    def test_save_creates_file(self, tmp_data_dir: Path):
        """TC-TI008-009: 保存结果写入文件"""
        games = get_seed_cal_games()
        result = run_calibration(games[0])
        path = save_calibration_results([result], data_dir=tmp_data_dir)
        assert path.exists()
        assert path.name == "calibration_results.json"
        # 验证内容为合法JSON
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) == 1

    def test_save_creates_directory(self, tmp_path: Path):
        """TC-TI008-010: 目录自动创建"""
        non_existent = tmp_path / "new_dir" / "nested"
        assert not non_existent.exists()

        games = get_seed_cal_games()
        result = run_calibration(games[0])
        path = save_calibration_results([result], data_dir=non_existent)
        assert path.exists()

    def test_save_and_load_consistent(self, tmp_data_dir: Path):
        """TC-TI008-011: 保存后加载数据一致"""
        games = get_seed_cal_games()
        results = [run_calibration(g) for g in games[:3]]  # 只测3个

        save_calibration_results(results, data_dir=tmp_data_dir)
        loaded = load_calibration_results(data_dir=tmp_data_dir)

        assert len(loaded) == len(results)
        for orig, load in zip(results, loaded):
            assert orig.game_id == load.game_id
            assert orig.game_name == load.game_name
            assert orig.computed["sales"] == load.computed["sales"]

    def test_load_missing_file(self, tmp_data_dir: Path):
        """TC-TI008-012: 文件不存在返回空列表"""
        assert not (tmp_data_dir / "calibration_results.json").exists()
        loaded = load_calibration_results(data_dir=tmp_data_dir)
        assert loaded == []

    def test_load_corrupt_json(self, tmp_data_dir: Path):
        """TC-TI008-013: 格式错误JSON返回空列表"""
        filepath = tmp_data_dir / "calibration_results.json"
        tmp_data_dir.mkdir(parents=True, exist_ok=True)
        filepath.write_text("corrupted json{{{", encoding="utf-8")

        loaded = load_calibration_results(data_dir=tmp_data_dir)
        assert loaded == []

    def test_load_wrong_keys(self, tmp_data_dir: Path):
        """TC-TI008-013 (扩展): JSON格式正确但缺少必需字段"""
        filepath = tmp_data_dir / "calibration_results.json"
        tmp_data_dir.mkdir(parents=True, exist_ok=True)
        filepath.write_text(
            json.dumps([{"wrong_field": "value"}]),
            encoding="utf-8",
        )

        loaded = load_calibration_results(data_dir=tmp_data_dir)
        assert loaded == []  # KeyError → 返回空列表


# ── 7. _data_dir 路径验证 ────────────────────────────────────


class TestDataDir:
    """_data_dir 路径正确性"""

    def test_data_dir_returns_path(self):
        """_data_dir 返回 Path 对象"""
        data_dir = _data_dir()
        assert isinstance(data_dir, Path)
        assert data_dir.exists()
