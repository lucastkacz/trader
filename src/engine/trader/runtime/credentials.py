"""Credential-tier resolution for the trader runtime."""

from typing import Any


def resolve_credentials(settings: Any, credential_tier: str) -> tuple[str, str]:
    """Resolve API key/secret from configured credential tier."""
    if credential_tier == "live":
        return settings.exchange_live_api_key or "", settings.exchange_live_api_secret or ""
    return settings.exchange_readonly_api_key or "", settings.exchange_readonly_api_secret or ""
