import pandas as pd
from src.data.storage.local_funding import LocalFundingStore

def test_local_funding_store_path_generation(tmp_path):
    """Path generation should follow standard directory layout."""
    store = LocalFundingStore(str(tmp_path))
    path = store.path_for_funding("BTC/USDT:USDT", "Bybit")
    
    assert path.name == "BTC_USDT_USDT.parquet"
    assert path.parent.name == "funding"
    assert path.parent.parent.name == "bybit"

def test_local_funding_store_save_and_load_success(tmp_path):
    """Saving and loading valid funding data should preserve values and enforce contracts."""
    store = LocalFundingStore(str(tmp_path))
    data = pd.DataFrame([
        {"timestamp": 1600000060000, "funding_rate": -0.0002},
        {"timestamp": 1600000000000, "funding_rate": 0.0001},
        {"timestamp": 1600000000000, "funding_rate": 0.0001}, # duplicate to drop
    ])

    store.save_funding("BTC/USDT:USDT", "Bybit", data)
    loaded = store.load_funding("BTC/USDT:USDT", "Bybit")

    # Order should be sorted by timestamp, duplicate dropped
    assert len(loaded) == 2
    assert loaded["timestamp"].tolist() == [1600000000000, 1600000060000]
    assert loaded["funding_rate"].tolist() == [0.0001, -0.0002]
    
    # Types must be strict
    assert loaded["timestamp"].dtype == "int64"
    assert loaded["funding_rate"].dtype == "float64"

def test_local_funding_store_empty_frame(tmp_path):
    """Saving empty frame should write standard typed columns."""
    store = LocalFundingStore(str(tmp_path))
    empty_df = pd.DataFrame(columns=["timestamp", "funding_rate"])

    store.save_funding("BTC/USDT:USDT", "Bybit", empty_df)
    loaded = store.load_funding("BTC/USDT:USDT", "Bybit")

    assert loaded.empty
    assert list(loaded.columns) == ["timestamp", "funding_rate"]
    assert loaded["timestamp"].dtype == "int64"
    assert loaded["funding_rate"].dtype == "float64"

def test_local_funding_store_missing_file_returns_empty(tmp_path):
    """Loading a missing file should return a typed empty DataFrame."""
    store = LocalFundingStore(str(tmp_path))
    loaded = store.load_funding("ETH/USDT:USDT", "Bybit")

    assert loaded.empty
    assert list(loaded.columns) == ["timestamp", "funding_rate"]
    assert loaded["timestamp"].dtype == "int64"
    assert loaded["funding_rate"].dtype == "float64"

def test_local_funding_store_read_metadata(tmp_path):
    """Metadata must be readable back from Parquet schema."""
    store = LocalFundingStore(str(tmp_path))
    data = pd.DataFrame([{"timestamp": 1600000000000, "funding_rate": 0.0001}])

    store.save_funding("BTC/USDT:USDT", "Bybit", data)
    meta = store.read_metadata("BTC/USDT:USDT", "Bybit")

    assert meta["symbol"] == "BTC/USDT:USDT"
    assert meta["exchange"] == "Bybit"
    assert meta["schema_version"] == "1"
    assert "updated_at" in meta
