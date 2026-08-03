"""Settings loaded from environment / .env. Secrets never live in code or YAML."""

from __future__ import annotations

from enum import Enum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Mode(str, Enum):
    DRY_RUN = "dry_run"   # log intents, never send orders (default)
    PAPER = "paper"       # Kalshi demo env for real order lifecycle; PMUS simulated
    LIVE = "live"         # real money — requires explicit opt-in


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    pmq_mode: Mode = Mode.DRY_RUN

    # Kalshi
    kalshi_api_key_id: str = ""
    kalshi_private_key_path: str = "./kalshi_private_key.pem"
    kalshi_use_demo: bool = True

    # Polymarket US
    pmus_access_key: str = ""
    pmus_private_key_b64: str = ""

    # Risk
    pmq_max_notional_per_market: float = 500.0
    pmq_max_total_notional: float = 2_000.0
    pmq_max_daily_loss: float = 200.0
    pmq_min_edge_bps: float = 150.0

    # Endpoints (override for testing)
    gamma_base: str = "https://gamma-api.polymarket.com"
    clob_base: str = "https://clob.polymarket.com"
    data_api_base: str = "https://data-api.polymarket.com"
    pmus_base: str = "https://api.polymarket.us/v1"
    kalshi_base_prod: str = "https://external-api.kalshi.com/trade-api/v2"
    kalshi_base_demo: str = "https://external-api.demo.kalshi.co/trade-api/v2"

    @property
    def kalshi_base(self) -> str:
        return self.kalshi_base_demo if self.kalshi_use_demo else self.kalshi_base_prod


@lru_cache
def settings() -> Settings:
    return Settings()
