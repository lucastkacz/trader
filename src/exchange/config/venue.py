"""Typed YAML config for exchange venue market profiles."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

class StrictExchangeConfigModel(BaseModel):
    """Base model that rejects unknown exchange config keys."""

    model_config = ConfigDict(extra="forbid")


class CcxtMarketContractConfig(StrictExchangeConfigModel):
    """Market contract options passed to CCXT."""

    name: str = Field(min_length=1)
    default_type: str | None
    default_sub_type: str | None
    default_settle: str | None
    fetch_market_types: list[str]

    def matches_market(self, market: Mapping[str, Any]) -> bool:
        """Return whether a CCXT market row belongs to this configured profile."""
        if self.default_type is not None and not _matches_market_type(
            market,
            self.default_type,
        ):
            return False
        if self.default_sub_type is not None and not _matches_market_sub_type(
            market,
            self.default_sub_type,
        ):
            return False
        return self.default_settle is None or market.get("settle") == self.default_settle


class CcxtExchangeConfig(StrictExchangeConfigModel):
    """CCXT exchange construction policy."""

    name: str = Field(min_length=1)
    enable_rate_limit: bool
    adjust_for_time_difference: bool
    recv_window: int = Field(gt=0)
    market_contract: CcxtMarketContractConfig

    def to_ccxt_kwargs(self, *, api_key: str, api_secret: str) -> dict[str, Any]:
        """Return constructor kwargs for an async CCXT exchange class."""
        options: dict[str, Any] = {
            "adjustForTimeDifference": self.adjust_for_time_difference,
            "recvWindow": self.recv_window,
        }
        contract = self.market_contract
        if contract.default_type is not None:
            options["defaultType"] = contract.default_type
        if contract.default_sub_type is not None:
            options["defaultSubType"] = contract.default_sub_type
        if contract.default_settle is not None:
            options["defaultSettle"] = contract.default_settle
        if contract.fetch_market_types:
            options["fetchMarkets"] = {"types": list(contract.fetch_market_types)}
        return {
            "enableRateLimit": self.enable_rate_limit,
            "apiKey": api_key,
            "secret": api_secret,
            "options": options,
        }


def load_ccxt_exchange_config(path: str | Path) -> CcxtExchangeConfig:
    """Load a typed CCXT exchange config from YAML."""
    return _load_config(path, "ccxt_exchange", CcxtExchangeConfig)


def _load_config(
    path: str | Path,
    top_level_key: str,
    model: type[StrictExchangeConfigModel],
) -> Any:
    data = _read_yaml(path)
    if top_level_key not in data:
        raise ValueError(f"Config file missing required top-level key '{top_level_key}': {path}")
    if len(data) != 1:
        keys = ", ".join(sorted(data))
        raise ValueError(f"Config file must contain only '{top_level_key}', found: {keys}")
    return model.model_validate(data[top_level_key])


def _read_yaml(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a YAML mapping: {path}")
    return data


def _matches_market_type(market: Mapping[str, Any], market_type: str) -> bool:
    typed_flag = market.get(market_type)
    if isinstance(typed_flag, bool):
        return typed_flag
    return market.get("type") == market_type


def _matches_market_sub_type(market: Mapping[str, Any], sub_type: str) -> bool:
    typed_flag = market.get(sub_type)
    if isinstance(typed_flag, bool):
        return typed_flag
    return market.get("subType") == sub_type
