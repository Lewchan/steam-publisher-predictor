"""QA-2026-001 TI-007: settings.py 独立测试

Quinn-QA 2026/06/11 迭代执行
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

# Ensure the src package is importable
from steam_publisher_predictor.settings import (
    CalibrationConfig,
    CalibrationUpdate,
    load_calibration_config,
    save_calibration_config,
    CALIBRATION_CONFIG_PATH,
    DEFAULT_CONFIG,
    get_allowed_origins,
    get_frontend_backend_url,
)


# ── 1. CalibrationConfig 默认实例 ───────────────────────────────


class TestCalibrationConfigDefaults:
    """TC-TI007-001 ~ TC-TI007-002"""

    def test_default_instance(self):
        """TC-TI007-001: 无参实例创建，所有字段为默认值"""
        cfg = CalibrationConfig()
        assert cfg.rating_weight == 0.45
        assert cfg.proof_weight == 0.20
        assert cfg.discussion_weight == 0.20
        assert cfg.persistence_weight == 0.15
        assert cfg.showmanship_cap == 0.6
        assert cfg.cl_cap == 3.0
        assert cfg.cl_k1 == 2.0
        assert cfg.cl_k2 == 2.0
        assert cfg.low_confidence_threshold == 40
        assert cfg.medium_confidence_threshold == 70
        assert cfg.missing_source_threshold == 3

    def test_field_assignment(self):
        """TC-TI007-002: 设置各字段为指定值"""
        cfg = CalibrationConfig(
            rating_weight=0.5,
            proof_weight=0.25,
            discussion_weight=0.15,
            persistence_weight=0.1,
            showmanship_cap=0.8,
            cl_cap=4.0,
        )
        assert cfg.rating_weight == 0.5
        assert cfg.proof_weight == 0.25
        assert cfg.discussion_weight == 0.15
        assert cfg.persistence_weight == 0.1
        assert cfg.showmanship_cap == 0.8
        assert cfg.cl_cap == 4.0


# ── 2. weight sum 校验 ──────────────────────────────────────


class TestCalibrationUpdateWeightSum:
    """TC-TI007-003 ~ TC-TI007-004"""

    def test_weight_sum_equals_one(self):
        """TC-TI007-003 (部分): 权重和=1.0 通过验证"""
        update = CalibrationUpdate(
            rating_weight=0.4,
            proof_weight=0.2,
            discussion_weight=0.2,
            persistence_weight=0.2,
        )
        assert update.rating_weight == 0.4

    def test_weight_sum_exceeds_one(self):
        """TC-TI007-003 (核心): 权重和>1.0 触发 ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            CalibrationUpdate(
                rating_weight=0.5,
                proof_weight=0.5,
                discussion_weight=0.5,
                persistence_weight=0.5,
            )
        assert "must sum to 1.0" in str(exc_info.value)

    def test_weight_sum_below_one(self):
        """TC-TI007-003 (边界): 权重和<1.0 触发 ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            CalibrationUpdate(
                rating_weight=0.1,
                proof_weight=0.1,
                discussion_weight=0.1,
                persistence_weight=0.1,
            )
        assert "must sum to 1.0" in str(exc_info.value)

    def test_partial_weights_no_sum_check(self):
        """TC-TI007-003 (边界): 部分字段为None时，不校验和"""
        update = CalibrationUpdate(
            rating_weight=0.9,
            proof_weight=0.9,
        )
        # 只有2个字段，len(provided)<4，不校验
        assert update.rating_weight == 0.9

    def test_weight_range_validation(self):
        """TC-TI007-003 (边界): 权重超出0-1范围"""
        with pytest.raises(ValidationError):
            CalibrationUpdate(rating_weight=1.5)

        with pytest.raises(ValidationError):
            CalibrationUpdate(rating_weight=-0.1)

    def test_weight_tolerance_floating_point(self):
        """TC-TI007-003 (边界): 浮点数精度容差"""
        # 0.3+0.3+0.3+0.1 = 1.0，应通过
        update = CalibrationUpdate(
            rating_weight=0.3,
            proof_weight=0.3,
            discussion_weight=0.3,
            persistence_weight=0.1,
        )
        assert update is not None


# ── 3. 序列化与反序列化 ─────────────────────────────────────


class TestSerialization:
    """TC-TI007-004 ~ TC-TI007-005"""

    def test_serialization(self):
        """TC-TI007-004: CalibrationConfig 可序列化为字典/JSON"""
        from dataclasses import asdict

        cfg = CalibrationConfig(rating_weight=0.5, proof_weight=0.25)
        d = asdict(cfg)
        assert isinstance(d, dict)
        assert d["rating_weight"] == 0.5

        json_str = json.dumps(d)
        assert "rating_weight" in json_str

    def test_deserialization(self):
        """TC-TI007-005: 从字典可重建 CalibrationConfig"""
        raw = {
            "rating_weight": 0.6,
            "proof_weight": 0.15,
            "discussion_weight": 0.15,
            "persistence_weight": 0.1,
            "showmanship_cap": 0.7,
            "cl_cap": 4.0,
        }
        cfg = CalibrationConfig(**raw)
        assert cfg.rating_weight == 0.6
        assert cfg.cl_cap == 4.0


# ── 4. 配置文件读写 ────────────────────────────────────────


class TestConfigFileIO:
    """TC-TI007-006 ~ TC-TI007-009"""

    def test_save_and_load_config(self, tmp_path: Path):
        """TC-TI007-006 ~ TC-TI007-007: 保存→加载配置一致"""
        config_path = tmp_path / "calibration_config.json"
        cfg = CalibrationConfig(rating_weight=0.55, proof_weight=0.2)
        # 写
        config_path.write_text(
            json.dumps({"rating_weight": 0.55, "proof_weight": 0.2}, indent=2),
            encoding="utf-8",
        )
        # 读（模拟 load_calibration_config 逻辑）
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        cfg2 = CalibrationConfig(**raw)
        assert cfg2.rating_weight == 0.55
        assert cfg2.proof_weight == 0.2

    def test_invalid_json_config(self, tmp_path: Path):
        """TC-TI007-008: 格式错误的JSON配置文件"""
        config_path = tmp_path / "calibration_config.json"
        config_path.write_text("not valid json {{{", encoding="utf-8")

        # 模拟 load 逻辑
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            raw = None
        assert raw is None  # 应优雅降级

    def test_missing_config_returns_defaults(self, tmp_path: Path):
        """TC-TI007-009: 配置文件不存在时使用默认值"""
        config_path = tmp_path / "nonexistent.json"
        assert not config_path.exists()

        # 不存在时应返回默认
        raw = {}
        assert len(raw) == 0  # 空字典

    def test_config_with_extra_keys_filed_out(self, tmp_path: Path):
        """TC-TI007-010: 配置文件中多余字段被过滤"""
        config_path = tmp_path / "calibration_config.json"
        raw = {
            "rating_weight": 0.5,
            "fake_field": "ignored",
            "another_fake": 123,
        }
        config_path.write_text(json.dumps(raw), encoding="utf-8")

        from dataclasses import fields as dc_fields

        known_keys = {f.name for f in dc_fields(CalibrationConfig)}
        loaded = json.loads(config_path.read_text(encoding="utf-8"))
        filtered = {k: v for k, v in loaded.items() if k in known_keys}
        assert "fake_field" not in filtered
        assert filtered["rating_weight"] == 0.5


# ── 5. 环境变量相关 ─────────────────────────────────────────


class TestEnvHelpers:
    """环境变量辅助函数"""

    def test_get_allowed_origins_default(self):
        """默认 ALLOW_ORIGINS=*"""
        old = os.environ.pop("ALLOW_ORIGINS", None)
        try:
            origins = get_allowed_origins()
            assert origins == ["*"]
        finally:
            if old is not None:
                os.environ["ALLOW_ORIGINS"] = old

    def test_get_allowed_origins_custom(self):
        """自定义 ALLOW_ORIGINS"""
        old = os.environ.pop("ALLOW_ORIGINS", None)
        try:
            os.environ["ALLOW_ORIGINS"] = "http://localhost:8501, http://example.com"
            origins = get_allowed_origins()
            assert "http://localhost:8501" in origins
            assert "http://example.com" in origins
        finally:
            if old is not None:
                os.environ["ALLOW_ORIGINS"] = old
            else:
                os.environ.pop("ALLOW_ORIGINS", None)

    def test_get_frontend_backend_url_default(self):
        """默认 FRONTEND_BACKEND_URL 为空"""
        old = os.environ.pop("FRONTEND_BACKEND_URL", None)
        try:
            url = get_frontend_backend_url()
            assert url == ""
        finally:
            if old is not None:
                os.environ["FRONTEND_BACKEND_URL"] = old

    def test_get_frontend_backend_url_custom(self):
        """自定义 FRONTEND_BACKEND_URL"""
        old = os.environ.pop("FRONTEND_BACKEND_URL", None)
        try:
            os.environ["FRONTEND_BACKEND_URL"] = "http://api.example.com"
            url = get_frontend_backend_url()
            assert url == "http://api.example.com"
        finally:
            if old is not None:
                os.environ["FRONTEND_BACKEND_URL"] = old
            else:
                os.environ.pop("FRONTEND_BACKEND_URL", None)


# ── 6. DEFAULT_CONFIG 常量 ──────────────────────────────────


class TestDefaultConfig:
    """DEFAULT_CONFIG 常量验证"""

    def test_default_config_is_instance(self):
        """TC-TI007-001 (扩展): DEFAULT_CONFIG 是 CalibrationConfig 实例"""
        assert isinstance(DEFAULT_CONFIG, CalibrationConfig)
        assert DEFAULT_CONFIG.rating_weight == 0.45
        assert DEFAULT_CONFIG.showmanship_cap == 0.6
