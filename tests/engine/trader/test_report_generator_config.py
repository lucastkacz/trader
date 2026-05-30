from argparse import Namespace

from src.engine.trader.cli.report_generator import _pair_validity_config
from src.engine.trader.config import load_pipeline_config


def test_pipeline_report_uses_typed_pair_validity_policy_by_default():
    pipeline_cfg = load_pipeline_config("configs/pipelines/dev.yml")
    args = Namespace(
        pipeline="configs/pipelines/dev.yml",
        market_data_base_dir=None,
        pair_validity_window_bars=None,
        pair_validity_min_bars=None,
        max_latest_data_age_bars=None,
        open_position_review_half_life_multiple=None,
    )

    config = _pair_validity_config(args, pipeline_cfg)

    assert config is not None
    assert config.recent_window_bars == 240
    assert config.min_recent_bars == 60
    assert config.max_latest_data_age_bars == 5
    assert config.open_position_review_half_life_multiple == 3.0


def test_pipeline_report_allows_explicit_pair_validity_overrides():
    pipeline_cfg = load_pipeline_config("configs/pipelines/dev.yml")
    args = Namespace(
        pipeline="configs/pipelines/dev.yml",
        market_data_base_dir=None,
        pair_validity_window_bars=120,
        pair_validity_min_bars=45,
        max_latest_data_age_bars=3,
        open_position_review_half_life_multiple=2.0,
    )

    config = _pair_validity_config(args, pipeline_cfg)

    assert config is not None
    assert config.recent_window_bars == 120
    assert config.min_recent_bars == 45
    assert config.max_latest_data_age_bars == 3
    assert config.open_position_review_half_life_multiple == 2.0
