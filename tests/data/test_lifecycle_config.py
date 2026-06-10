import pytest
import yaml
from pydantic import ValidationError

from src.data.lifecycle import load_data_lifecycle_config


def test_data_lifecycle_config_loads_retention_freshness_and_cleanup():
    config = load_data_lifecycle_config("configs/data/lifecycle/default.yml")

    assert config.enabled is True
    assert config.retention.keep_days == 5
    assert config.retention.prune_after_backfill is True
    assert config.freshness.max_lag_minutes == 5
    assert config.freshness.on_stale == "refresh"
    assert config.cleanup.mode == "dry_run"
    assert config.cleanup.delete_empty_symbol_dirs is True

    retention_policy = config.retention_policy_after_backfill()
    assert retention_policy is not None
    assert retention_policy.max_age_days == 5
    assert retention_policy.max_bars is None


def test_data_lifecycle_config_rejects_unknown_keys(tmp_path):
    raw = yaml.safe_load(open("configs/data/lifecycle/default.yml"))
    raw["data_lifecycle"]["retention"]["surprise"] = True
    path = tmp_path / "lifecycle.yml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")

    with pytest.raises(ValidationError, match="surprise"):
        load_data_lifecycle_config(path)
