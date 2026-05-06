import pytest
import yaml
from pydantic import ValidationError

from src.engine.trader.config import load_pipeline_config


def write_yaml(tmp_path, data):
    path = tmp_path / "config.yml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_wrong_top_level_key_fails_before_validation(tmp_path):
    path = write_yaml(tmp_path, {"strategy": {"name": "wrong"}})

    with pytest.raises(ValueError, match="top-level key 'pipeline'"):
        load_pipeline_config(path)


def test_extra_config_keys_are_rejected(tmp_path):
    cfg = yaml.safe_load(open("configs/pipelines/dev.yml"))
    cfg["pipeline"]["execution"]["implicit_default"] = 123
    path = write_yaml(tmp_path, cfg)

    with pytest.raises(ValidationError, match="implicit_default"):
        load_pipeline_config(path)
