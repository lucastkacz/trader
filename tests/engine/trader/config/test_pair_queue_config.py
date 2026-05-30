from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from src.engine.trader.config import load_pipeline_config


def write_yaml(tmp_path, data):
    path = tmp_path / "config.yml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_all_shipped_pipeline_configs_declare_future_entry_pair_queue():
    pipeline_paths = sorted(Path("configs/pipelines").glob("*.yml"))
    parsed = [load_pipeline_config(path) for path in pipeline_paths]

    assert {cfg.execution.pair_queue.enabled for cfg in parsed} == {True}
    assert {cfg.execution.pair_queue.mode for cfg in parsed} == {"future_entries"}
    assert {cfg.execution.pair_queue.allocation.max_open_positions for cfg in parsed} == {None}
    assert {cfg.execution.pair_queue.allocation.max_positions_per_pair for cfg in parsed} == {1}
    assert {
        cfg.execution.pair_queue.allocation.max_positions_per_asset
        for cfg in parsed
    } == {None}


def test_all_shipped_pipeline_configs_declare_pair_validity_policy():
    pipeline_paths = sorted(Path("configs/pipelines").glob("*.yml"))
    parsed = [load_pipeline_config(path) for path in pipeline_paths]

    assert {cfg.execution.pair_validity.recent_window_bars for cfg in parsed} == {240}
    assert {cfg.execution.pair_validity.min_recent_bars for cfg in parsed} == {60}
    assert {
        cfg.execution.pair_validity.max_latest_data_age_bars
        for cfg in parsed
    } == {2, 5}
    assert {
        cfg.execution.pair_validity.open_position_review_half_life_multiple
        for cfg in parsed
    } == {3.0}


@pytest.mark.parametrize(
    ("field_path", "match"),
    [
        (("execution", "pair_queue"), "pair_queue"),
        (("execution", "pair_validity"), "pair_validity"),
        (("execution", "pair_validity", "recent_window_bars"), "recent_window_bars"),
        (("execution", "pair_validity", "min_recent_bars"), "min_recent_bars"),
        (
            ("execution", "pair_validity", "max_latest_data_age_bars"),
            "max_latest_data_age_bars",
        ),
        (
            ("execution", "pair_validity", "open_position_review_half_life_multiple"),
            "open_position_review_half_life_multiple",
        ),
        (("execution", "pair_queue", "enabled"), "enabled"),
        (("execution", "pair_queue", "mode"), "mode"),
        (("execution", "pair_queue", "scoring"), "scoring"),
        (("execution", "pair_queue", "validity_thresholds"), "validity_thresholds"),
        (("execution", "pair_queue", "allocation"), "allocation"),
    ],
)
def test_missing_pair_queue_fields_fail_loudly(tmp_path, field_path, match):
    cfg = yaml.safe_load(open("configs/pipelines/dev.yml"))
    target = cfg["pipeline"]
    for key in field_path[:-1]:
        target = target[key]
    del target[field_path[-1]]

    with pytest.raises(ValidationError, match=match):
        load_pipeline_config(write_yaml(tmp_path, cfg))


def test_pair_queue_rejects_unknown_mode(tmp_path):
    cfg = yaml.safe_load(open("configs/pipelines/dev.yml"))
    cfg["pipeline"]["execution"]["pair_queue"]["mode"] = "allocate_entries"

    with pytest.raises(ValidationError, match="mode"):
        load_pipeline_config(write_yaml(tmp_path, cfg))


def test_pair_queue_uses_null_for_unlimited_limits(tmp_path):
    cfg = yaml.safe_load(open("configs/pipelines/dev.yml"))
    parsed = load_pipeline_config(write_yaml(tmp_path, cfg))

    assert parsed.execution.pair_queue.allocation.max_open_positions is None
    assert parsed.execution.pair_queue.allocation.max_positions_per_asset is None
    assert parsed.execution.pair_queue.validity_thresholds.max_bars_since_promotion is None


def test_pair_queue_rejects_zero_allocation_limits(tmp_path):
    cfg = yaml.safe_load(open("configs/pipelines/dev.yml"))
    cfg["pipeline"]["execution"]["pair_queue"]["allocation"]["max_open_positions"] = 0

    with pytest.raises(ValidationError, match="max_open_positions"):
        load_pipeline_config(write_yaml(tmp_path, cfg))


def test_pair_queue_rejects_all_zero_scoring_weights(tmp_path):
    cfg = yaml.safe_load(open("configs/pipelines/dev.yml"))
    scoring = cfg["pipeline"]["execution"]["pair_queue"]["scoring"]
    scoring["research_weight"] = 0.0
    scoring["validity_weight"] = 0.0
    scoring["opportunity_weight"] = 0.0

    with pytest.raises(ValidationError, match="at least one"):
        load_pipeline_config(write_yaml(tmp_path, cfg))


def test_pair_queue_runtime_policy_kwargs_preserve_null_unlimited_values():
    cfg = load_pipeline_config("configs/pipelines/dev.yml")

    kwargs = cfg.execution.pair_queue.to_runtime_policy_kwargs()

    assert kwargs["max_open_positions"] is None
    assert kwargs["max_positions_per_pair"] == 1
    assert kwargs["max_positions_per_asset"] is None
    assert kwargs["max_bars_since_promotion"] is None
