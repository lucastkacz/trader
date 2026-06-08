import pytest

from src.exchange.config.venue import (
    load_ccxt_exchange_config,
    load_exchange_venue_config,
)


@pytest.mark.parametrize(
    ("path", "name", "default_type", "default_sub_type", "default_settle"),
    [
        (
            "configs/exchange/market_profiles/linear_usdt_swap.yml",
            "linear_usdt_swap",
            "swap",
            "linear",
            "USDT",
        ),
        (
            "configs/exchange/market_profiles/linear_usdc_swap.yml",
            "linear_usdc_swap",
            "swap",
            "linear",
            "USDC",
        ),
        (
            "configs/exchange/market_profiles/inverse_coin_swap.yml",
            "inverse_coin_swap",
            "swap",
            "inverse",
            None,
        ),
        (
            "configs/exchange/market_profiles/spot.yml",
            "spot",
            "spot",
            None,
            None,
        ),
    ],
)
def test_shipped_ccxt_market_profiles_parse(
    path,
    name,
    default_type,
    default_sub_type,
    default_settle,
):
    print(
        "\nTEST: Loads one shipped exchange market profile and confirms its CCXT "
        f"contract fields are correct. Profile: {path}"
    )
    config = load_ccxt_exchange_config(path)

    assert config.name == name
    assert config.market_contract.default_type == default_type
    assert config.market_contract.default_sub_type == default_sub_type
    assert config.market_contract.default_settle == default_settle


@pytest.mark.parametrize(
    ("path", "credential_tier"),
    [
        ("configs/exchange/venues/dev.yml", "readonly"),
        ("configs/exchange/venues/uat.yml", "readonly"),
        ("configs/exchange/venues/prod.yml", "live"),
    ],
)
def test_shipped_exchange_venues_parse(path, credential_tier):
    config = load_exchange_venue_config(path)

    assert config.exchange_id == "bybit"
    assert config.credential_tier == credential_tier
