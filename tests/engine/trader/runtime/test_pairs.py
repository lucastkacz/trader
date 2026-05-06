import json

import pytest

from src.engine.trader.runtime import pairs


def _valid_pair(sharpe_ratio=1.25):
    return {
        "Asset_X": "BTC/USDT",
        "Asset_Y": "ETH/USDT",
        "Hedge_Ratio": 1.7,
        "Best_Params": {
            "lookback_bars": 540,
            "entry_z": 2.0,
        },
        "Performance": {
            "sharpe_ratio": sharpe_ratio,
            "final_pnl_pct": 12.5,
        },
    }


def _artifact(pair_rows, timeframe="1m", exchange="bybit"):
    return pairs.build_pair_artifact(
        pair_rows=pair_rows,
        timeframe=timeframe,
        exchange=exchange,
        generated_at="2026-01-01T00:00:00+00:00",
    )


def test_load_tier1_pairs_validates_and_filters(monkeypatch, tmp_path):
    universe_dir = tmp_path / "data" / "universes" / "1m"
    universe_dir.mkdir(parents=True)
    path = universe_dir / "surviving_pairs.json"
    path.write_text(
        json.dumps(_artifact([_valid_pair(sharpe_ratio=1.25), _valid_pair(sharpe_ratio=0.5)])),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)

    tier1 = pairs.load_tier1_pairs("1m", min_sharpe=1.0, exchange="bybit")

    assert len(tier1) == 1
    assert tier1[0]["Asset_X"] == "BTC/USDT"
    assert tier1[0]["Performance"]["sharpe_ratio"] == 1.25


def test_load_tier1_pairs_rejects_mismatched_artifact_metadata(monkeypatch, tmp_path):
    universe_dir = tmp_path / "data" / "universes" / "1m"
    universe_dir.mkdir(parents=True)
    path = universe_dir / "surviving_pairs.json"
    path.write_text(
        json.dumps(_artifact([_valid_pair()], timeframe="4h")),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="timeframe"):
        pairs.load_tier1_pairs("1m", min_sharpe=1.0, exchange="bybit")


def test_load_tier1_pairs_rejects_mismatched_artifact_exchange(monkeypatch, tmp_path):
    universe_dir = tmp_path / "data" / "universes" / "1m"
    universe_dir.mkdir(parents=True)
    path = universe_dir / "surviving_pairs.json"
    path.write_text(
        json.dumps(_artifact([_valid_pair()], exchange="kucoin")),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="exchange"):
        pairs.load_tier1_pairs("1m", min_sharpe=1.0, exchange="bybit")


def test_load_tier1_pairs_rejects_legacy_list_only_artifact(monkeypatch, tmp_path):
    universe_dir = tmp_path / "data" / "universes" / "1m"
    universe_dir.mkdir(parents=True)
    (universe_dir / "surviving_pairs.json").write_text(
        json.dumps(["BTC|ETH", "SOL|ADA"]),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="Legacy list-only"):
        pairs.load_tier1_pairs("1m", min_sharpe=1.0, exchange="bybit")


def test_load_tier1_pairs_rejects_malformed_artifact_envelope(monkeypatch, tmp_path):
    universe_dir = tmp_path / "data" / "universes" / "1m"
    universe_dir.mkdir(parents=True)
    artifact = _artifact([_valid_pair()])
    del artifact["metadata"]["generated_at"]
    (universe_dir / "surviving_pairs.json").write_text(
        json.dumps(artifact),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="generated_at"):
        pairs.load_tier1_pairs("1m", min_sharpe=1.0, exchange="bybit")


def test_load_tier1_pairs_rejects_pair_count_mismatch(monkeypatch, tmp_path):
    universe_dir = tmp_path / "data" / "universes" / "1m"
    universe_dir.mkdir(parents=True)
    artifact = _artifact([_valid_pair()])
    artifact["metadata"]["pair_count"] = 2
    (universe_dir / "surviving_pairs.json").write_text(
        json.dumps(artifact),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="pair_count mismatch"):
        pairs.load_tier1_pairs("1m", min_sharpe=1.0, exchange="bybit")


def test_load_tier1_pairs_rejects_missing_performance_sharpe(monkeypatch, tmp_path):
    universe_dir = tmp_path / "data" / "universes" / "1m"
    universe_dir.mkdir(parents=True)
    bad_pair = _valid_pair()
    del bad_pair["Performance"]["sharpe_ratio"]
    (universe_dir / "surviving_pairs.json").write_text(
        json.dumps(_artifact([bad_pair])),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="Performance.*sharpe_ratio"):
        pairs.load_tier1_pairs("1m", min_sharpe=1.0, exchange="bybit")


def test_load_tier1_pairs_rejects_missing_best_params(monkeypatch, tmp_path):
    universe_dir = tmp_path / "data" / "universes" / "1m"
    universe_dir.mkdir(parents=True)
    bad_pair = _valid_pair()
    del bad_pair["Best_Params"]["lookback_bars"]
    (universe_dir / "surviving_pairs.json").write_text(
        json.dumps(_artifact([bad_pair])),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="Best_Params.*lookback_bars"):
        pairs.load_tier1_pairs("1m", min_sharpe=1.0, exchange="bybit")


def test_validate_surviving_pair_rows_rejects_non_list_rows():
    with pytest.raises(ValueError, match="must contain a list"):
        pairs.validate_surviving_pair_rows({"Asset_X": "BTC/USDT"}, "artifact.json")


def test_extract_pair_artifact_rejects_legacy_list_artifact():
    with pytest.raises(ValueError, match="Legacy list-only"):
        pairs.extract_pair_artifact_pairs(["BTC|ETH"], "artifact.json")


def test_load_tier1_pairs_missing_artifact_tells_operator_to_run_research(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileNotFoundError, match="Run research first"):
        pairs.load_tier1_pairs("1m", min_sharpe=1.0, exchange="bybit")
