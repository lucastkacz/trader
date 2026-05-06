from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from src.engine.trader.config import load_pipeline_config


def write_yaml(tmp_path, data):
    path = tmp_path / "config.yml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_all_shipped_pipeline_configs_use_manual_on_boot_pair_refresh():
    pipeline_paths = sorted(Path("configs/pipelines").glob("*.yml"))
    parsed = [load_pipeline_config(path) for path in pipeline_paths]

    assert {cfg.execution.pair_refresh.mode for cfg in parsed} == {"manual"}
    assert {cfg.execution.pair_refresh.reload_policy for cfg in parsed} == {"on_boot"}
    assert {
        cfg.execution.pair_refresh.stale_open_position_policy
        for cfg in parsed
    } == {"natural_exit"}


@pytest.mark.parametrize(
    ("field_path", "match"),
    [
        (("execution", "pair_refresh"), "pair_refresh"),
        (("execution", "pair_refresh", "mode"), "mode"),
        (("execution", "pair_refresh", "reload_policy"), "reload_policy"),
        (
            ("execution", "pair_refresh", "stale_open_position_policy"),
            "stale_open_position_policy",
        ),
    ],
)
def test_missing_pair_refresh_fields_fail_loudly(tmp_path, field_path, match):
    cfg = yaml.safe_load(open("configs/pipelines/dev.yml"))
    target = cfg["pipeline"]
    for key in field_path[:-1]:
        target = target[key]
    del target[field_path[-1]]

    with pytest.raises(ValidationError, match=match):
        load_pipeline_config(write_yaml(tmp_path, cfg))


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "match"),
    [
        ("mode", "scheduled", "mode"),
        ("reload_policy", "hot_reload", "reload_policy"),
        ("stale_open_position_policy", "force_close", "stale_open_position_policy"),
    ],
)
def test_invalid_pair_refresh_values_fail_loudly(tmp_path, field_name, invalid_value, match):
    cfg = yaml.safe_load(open("configs/pipelines/dev.yml"))
    cfg["pipeline"]["execution"]["pair_refresh"][field_name] = invalid_value

    with pytest.raises(ValidationError, match=match):
        load_pipeline_config(write_yaml(tmp_path, cfg))


def test_pair_refresh_rejects_extra_keys(tmp_path):
    cfg = yaml.safe_load(open("configs/pipelines/dev.yml"))
    cfg["pipeline"]["execution"]["pair_refresh"]["implicit_default"] = "surprise"

    with pytest.raises(ValidationError, match="implicit_default"):
        load_pipeline_config(write_yaml(tmp_path, cfg))
