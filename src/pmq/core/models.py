"""Core domain models. Keep venue-agnostic — venue adapters normalize into these."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class Venue(str, Enum):
    POLYMARKET_GLOBAL = "polymarket_global"  # read-only data for US operators
    POLYMARKET_US = "polymarket_us"
    KALSHI = "kalshi"


class FeeCategory(str, Enum):
    """Polymarket global taker-fee categories (docs.polymarket.com/trading/fees, July 2026)."""

    CRYPTO = "crypto"            # feeRate 0.07
    SPORTS = "sports"            # 0.05
    ECONOMICS = "economics"      # 0.05
    CULTURE = "culture"          # 0.05
    WEATHER = "weather"          # 0.05
    OTHER = "other"              # 0.05
    FINANCE = "finance"          # 0.04
    POLITICS = "politics"        # 0.04
    MENTIONS = "mentions"        # 0.04
    TECH = "tech"                # 0.04
    GEOPOLITICS = "geopolitics"  # 0.00 (fee-free)


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class Outcome(str, Enum):
    YES = "yes"
    NO = "no"


class Quote(BaseModel):
    price: float  # 0..1
    size: float   # contracts/shares


class OrderBook(BaseModel):
    venue: Venue
    market_id: str
    token_id: str | None = None  # Polymarket CLOB token id where applicable
    bids: list[Quote] = Field(default_factory=list)  # sorted best-first
    asks: list[Quote] = Field(default_factory=list)  # sorted best-first
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def best_bid(self) -> Quote | None:
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> Quote | None:
        return self.asks[0] if self.asks else None

    @property
    def mid(self) -> float | None:
        if self.best_bid and self.best_ask:
            return (self.best_bid.price + self.best_ask.price) / 2
        return None


class Market(BaseModel):
    venue: Venue
    market_id: str
    question: str
    outcomes: list[str] = Field(default_factory=lambda: ["Yes", "No"])
    token_ids: list[str] = Field(default_factory=list)  # global CLOB token ids, aligned to outcomes
    category: FeeCategory | None = None
    neg_risk: bool = False
    end_date: datetime | None = None
    resolution_source: str | None = None
    min_order_size: float | None = None
    tick_size: float | None = None
    raw: dict = Field(default_factory=dict)


class EventPair(BaseModel):
    """A manually verified pair of same-event markets across two venues.

    THE critical safety gate for cross-venue arb. TU Munich (arXiv:2601.01706) finding:
    'semantically equivalent' markets often are NOT — different oracles, cutoffs, exception
    rules. A pair enters the registry only after a human diffs both resolution texts.
    """

    name: str
    venue_a: Venue
    market_a: str
    venue_b: Venue
    market_b: str
    resolution_verified: bool = False  # scanner refuses execution while False
    resolution_date: datetime | None = None
    notes: str = ""


class Opportunity(BaseModel):
    strategy: str
    description: str
    edge_per_contract: float          # $ of guaranteed edge per $1 contract, net of fees
    edge_bps: float                   # edge / capital, basis points
    max_size: float                   # executable contracts at quoted depth
    capital_required: float           # $ locked until resolution
    annualized_return: float | None = None
    legs: list[dict] = Field(default_factory=list)
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WhaleSignal(BaseModel):
    wallet: str
    alias: str | None = None
    market_id: str
    question: str | None = None
    outcome: str
    side: Side
    price: float
    size_usd: float
    ts: datetime
    raw: dict = Field(default_factory=dict)


class Order(BaseModel):
    venue: Venue
    market_id: str
    outcome: Outcome
    side: Side
    price: float
    size: float
    order_id: str | None = None
    status: str = "pending"
    created: datetime = Field(default_factory=lambda: datetime.now(UTC))
