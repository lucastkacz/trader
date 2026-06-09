from src.data.sync.config import load_ohlcv_backfill_config


def test_default_backfill_config_returns_fetch_policy():
    print(
        "\nTEST: Loads configs/data/ohlcv_backfill/default.yml and confirms it becomes "
        "the runtime OHLCV fetch/retry policy."
    )
    config = load_ohlcv_backfill_config("configs/data/ohlcv_backfill/default.yml")

    policy = config.to_fetch_policy()

    assert policy.fetch_limit == 1000
    assert policy.max_retries == 3
    assert policy.retry_backoff_seconds == 5.0
    assert policy.request_pause_seconds == 0.5
