import json
from datetime import datetime, timezone

import pytest

from src.engine.trader.runtime import artifacts as pairs


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


def _write_artifact(path, artifact):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact), encoding="utf-8")


def test_write_candidate_pair_artifact_does_not_replace_promoted_artifact(tmp_path):
    base_dir = tmp_path / "universes"
    promoted_path = pairs.promoted_pair_artifact_path("1m", base_dir)
    _write_artifact(promoted_path, _artifact([_valid_pair(sharpe_ratio=2.0)]))

    candidate_path = pairs.write_candidate_pair_artifact(
        pair_rows=[_valid_pair(sharpe_ratio=1.25)],
        timeframe="1m",
        exchange="bybit",
        base_dir=base_dir,
    )

    promoted = json.loads(promoted_path.read_text(encoding="utf-8"))
    assert candidate_path == pairs.candidate_pair_artifact_path("1m", base_dir)
    assert promoted_path.exists()
    assert promoted["pairs"][0]["Performance"]["sharpe_ratio"] == 2.0


def test_load_tier1_pairs_ignores_unpromoted_candidate_artifact(monkeypatch, tmp_path):
    base_dir = tmp_path / "universes"
    candidate_path = pairs.candidate_pair_artifact_path("1m", base_dir)
    _write_artifact(candidate_path, _artifact([_valid_pair()]))

    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileNotFoundError, match="surviving_pairs.json"):
        pairs.load_tier1_pairs("1m", 1.0, "bybit", base_dir)


def test_promote_candidate_pair_artifact_atomically_replaces_promoted(tmp_path):
    base_dir = tmp_path / "universes"
    promoted_path = pairs.promoted_pair_artifact_path("1m", base_dir)
    candidate_path = pairs.candidate_pair_artifact_path("1m", base_dir)
    _write_artifact(promoted_path, _artifact([_valid_pair(sharpe_ratio=0.5)]))
    _write_artifact(candidate_path, _artifact([_valid_pair(sharpe_ratio=1.25)]))

    result_path = pairs.promote_candidate_pair_artifact(
        timeframe="1m",
        exchange="bybit",
        base_dir=base_dir,
        now=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc),
    )

    assert result_path == promoted_path
    assert not candidate_path.exists()
    promoted = json.loads(promoted_path.read_text(encoding="utf-8"))
    assert promoted["pairs"][0]["Performance"]["sharpe_ratio"] == 1.25


def test_promote_candidate_pair_artifact_rejects_malformed_candidate_and_preserves_promoted(
    tmp_path,
):
    base_dir = tmp_path / "universes"
    promoted_path = pairs.promoted_pair_artifact_path("1m", base_dir)
    candidate_path = pairs.candidate_pair_artifact_path("1m", base_dir)
    _write_artifact(promoted_path, _artifact([_valid_pair(sharpe_ratio=0.5)]))
    _write_artifact(candidate_path, ["BTC|ETH"])

    with pytest.raises(ValueError, match="Legacy list-only"):
        pairs.promote_candidate_pair_artifact(
            timeframe="1m",
            exchange="bybit",
            base_dir=base_dir,
            now=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc),
        )

    promoted = json.loads(promoted_path.read_text(encoding="utf-8"))
    assert candidate_path.exists()
    assert promoted["pairs"][0]["Performance"]["sharpe_ratio"] == 0.5


def test_promote_candidate_pair_artifact_rejects_stale_candidate_and_preserves_promoted(
    tmp_path,
):
    base_dir = tmp_path / "universes"
    promoted_path = pairs.promoted_pair_artifact_path("1m", base_dir)
    candidate_path = pairs.candidate_pair_artifact_path("1m", base_dir)
    _write_artifact(promoted_path, _artifact([_valid_pair(sharpe_ratio=0.5)]))
    _write_artifact(candidate_path, _artifact([_valid_pair(sharpe_ratio=1.25)]))

    with pytest.raises(ValueError, match="stale"):
        pairs.promote_candidate_pair_artifact(
            timeframe="1m",
            exchange="bybit",
            base_dir=base_dir,
            max_age_seconds=60,
            now=datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc),
        )

    promoted = json.loads(promoted_path.read_text(encoding="utf-8"))
    assert candidate_path.exists()
    assert promoted["pairs"][0]["Performance"]["sharpe_ratio"] == 0.5


def test_promote_candidate_pair_artifact_rejects_exchange_mismatch(tmp_path):
    base_dir = tmp_path / "universes"
    candidate_path = pairs.candidate_pair_artifact_path("1m", base_dir)
    _write_artifact(candidate_path, _artifact([_valid_pair()], exchange="kucoin"))

    with pytest.raises(ValueError, match="exchange mismatch"):
        pairs.promote_candidate_pair_artifact(
            timeframe="1m",
            exchange="bybit",
            base_dir=base_dir,
            now=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc),
        )


def test_promote_candidate_pair_artifact_rejects_timeframe_mismatch(tmp_path):
    base_dir = tmp_path / "universes"
    candidate_path = pairs.candidate_pair_artifact_path("1m", base_dir)
    _write_artifact(candidate_path, _artifact([_valid_pair()], timeframe="4h"))

    with pytest.raises(ValueError, match="timeframe mismatch"):
        pairs.promote_candidate_pair_artifact(
            timeframe="1m",
            exchange="bybit",
            base_dir=base_dir,
            now=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc),
        )
