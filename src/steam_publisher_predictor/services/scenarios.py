from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path

from steam_publisher_predictor.models import ManualInputs, SalesBreakdown, SteamGame
from steam_publisher_predictor.services.calculator import calculate_sales

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "data" / "scenarios"


@dataclass
class Scenario:
    name: str
    art_base: float = 5.0
    gameplay_depth: float = 5.0
    scope: float = 5.0
    narrative: float = 5.0
    ip_factor: float = 0.2
    influencer_factor: float = 0.2
    exposure_base: float = 0.2
    intent_base: float = 0.25
    purchase_base: float = 0.3
    platform_fit: float = 1.0
    region_fit: float = 1.0
    price_fit: float = 1.0
    overlap_adjustment: float = 0.75
    user_pool_override: int = 0
    discussion_manual_score: float = 5.0
    persistence_manual_score: float = 5.0
    analyst_adjustment: float = 0.0
    peak_dau: int = 0
    median_line: float = 0.0
    sexual_or_gore: bool = False
    extreme_novelty: bool = False
    real_time_juice: bool = False
    systemic_interlock: bool = False
    complex_system: bool = False
    linear_experience: bool = False


@dataclass
class ScenarioResult:
    scenario: Scenario
    result: SalesBreakdown


PRESETS = {
    "Conservative": Scenario(
        name="Conservative",
        art_base=3.0,
        gameplay_depth=4.0,
        scope=3.0,
        narrative=3.0,
        ip_factor=0.05,
        influencer_factor=0.05,
        exposure_base=0.1,
        intent_base=0.15,
        purchase_base=0.15,
        platform_fit=0.7,
        region_fit=0.7,
        price_fit=0.8,
        overlap_adjustment=0.6,
        user_pool_override=0,
        analyst_adjustment=-0.5,
        peak_dau=100,
        median_line=0.02,
    ),
    "Baseline": Scenario(
        name="Baseline",
        art_base=5.0,
        gameplay_depth=5.0,
        scope=5.0,
        narrative=5.0,
        ip_factor=0.2,
        influencer_factor=0.2,
        exposure_base=0.2,
        intent_base=0.25,
        purchase_base=0.3,
        platform_fit=1.0,
        region_fit=1.0,
        price_fit=1.0,
        overlap_adjustment=0.75,
        user_pool_override=0,
        analyst_adjustment=0.0,
        peak_dau=500,
        median_line=0.05,
    ),
    "Optimistic": Scenario(
        name="Optimistic",
        art_base=8.0,
        gameplay_depth=9.0,
        scope=8.0,
        narrative=7.0,
        ip_factor=0.5,
        influencer_factor=0.5,
        exposure_base=0.4,
        intent_base=0.4,
        purchase_base=0.45,
        platform_fit=1.1,
        region_fit=1.1,
        price_fit=1.05,
        overlap_adjustment=0.85,
        user_pool_override=0,
        analyst_adjustment=0.5,
        peak_dau=5000,
        median_line=0.15,
    ),
}


def get_preset_names() -> list[str]:
    return list(PRESETS.keys())


def load_preset(name: str) -> Scenario:
    if name in PRESETS:
        return Scenario(**asdict(PRESETS[name]))
    return Scenario(name=name)


def run_scenario(
    scenario: Scenario,
    game: SteamGame,
    scenario_cfg_name: str | None = None,
) -> ScenarioResult:
    """Run a scenario with optional scenario-specific calibration overrides.

    Args:
        scenario: Scenario definition with manual input values.
        game: Fetched Steam game data.
        scenario_cfg_name: Name of the scenario calibration config
            (e.g. 'conservative', 'baseline', 'optimistic').
            If provided, uses ``calculate_sales_with_scenario`` to apply
            scenario-specific calibrations (cl_cap, cl_k2).
    """
    manual_inputs = ManualInputs(
        art_base=scenario.art_base,
        gameplay_depth=scenario.gameplay_depth,
        scope=scenario.scope,
        narrative=scenario.narrative,
        ip_factor=scenario.ip_factor,
        influencer_factor=scenario.influencer_factor,
        exposure_base=scenario.exposure_base,
        intent_base=scenario.intent_base,
        purchase_base=scenario.purchase_base,
        platform_fit=scenario.platform_fit,
        region_fit=scenario.region_fit,
        price_fit=scenario.price_fit,
        overlap_adjustment=scenario.overlap_adjustment,
        user_pool_override=scenario.user_pool_override,
        discussion_manual_score=scenario.discussion_manual_score,
        persistence_manual_score=scenario.persistence_manual_score,
        analyst_adjustment=scenario.analyst_adjustment,
        peak_dau=scenario.peak_dau,
        median_line=scenario.median_line,
        sexual_or_gore=scenario.sexual_or_gore,
        extreme_novelty=scenario.extreme_novelty,
        real_time_juice=scenario.real_time_juice,
        systemic_interlock=scenario.systemic_interlock,
        complex_system=scenario.complex_system,
        linear_experience=scenario.linear_experience,
    )

    # Webber 2026/06/13: When a scenario calibration config name is provided,
    #   use calculate_sales_with_scenario to apply scenario-specific calibrations
    #   (cl_cap, cl_k2, quality_bias) on top of the manual inputs.
    if scenario_cfg_name:
        result = calculate_sales_with_scenario(game, manual_inputs, scenario=scenario_cfg_name)
    else:
        result = calculate_sales(game, manual_inputs)
    return ScenarioResult(scenario=scenario, result=result)


def save_scenario(scenario: Scenario, name: str | None = None) -> Path:
    SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    filepath = SCENARIOS_DIR / f"{name or scenario.name}.json"
    data = asdict(scenario)
    filepath.write_text(__import__("json").dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return filepath


def load_saved_scenario(name: str) -> Scenario | None:
    filepath = SCENARIOS_DIR / f"{name}.json"
    if not filepath.exists():
        return None
    data = __import__("json").loads(filepath.read_text(encoding="utf-8"))
    return Scenario(name=data.get("name", name), **{k: v for k, v in data.items() if k != "name"})


def list_saved_scenarios() -> list[str]:
    SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    return [f.stem for f in SCENARIOS_DIR.glob("*.json")]


def delete_scenario(name: str) -> bool:
    filepath = SCENARIOS_DIR / f"{name}.json"
    if filepath.exists():
        filepath.unlink()
        return True
    return False
