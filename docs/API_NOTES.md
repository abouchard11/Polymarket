# API Notes (verified against official docs + live calls, 2026-07-23)

Condensed integration reference so Claude Code sessions don't re-research. Re-verify anything
marked (verify) before first live use. Primary sources: docs.polymarket.com, docs.polymarket.us,
docs.kalshi.com, kalshi.com/docs/kalshi-fee-schedule.pdf.

## Polymarket global (data layer — public, no auth)

| Surface | Base | Notes |
|---|---|---|
| Gamma (metadata) | https://gamma-api.polymarket.com | /events, /markets, /tags; `events?active=true&closed=false`; limit/offset |
| CLOB (books/prices) | https://clob.polymarket.com | /book?token_id=…, /books, /price, /midpoint, /prices-history |
| Data API | https://data-api.polymarket.com | /trades?user=0x…, /positions?user=0x…, /closed-positions |
| WSS market | wss://ws-subscriptions-clob.polymarket.com/ws/market | no auth; book, price_change, last_trade_price, best_bid_ask events; client pings every 10s |
| RTDS | wss://ws-live-data.polymarket.com | activity/trades topics |
| Sports WSS | wss://sports-api.polymarket.com/ws | server pings 5s, pong within 10s |

Rate limits (docs.polymarket.com/api-reference/rate-limits): Gamma general 4,000/10s
(/markets 300/10s, /events 500/10s); CLOB /book /price /midpoint 1,500/10s each, batched
variants 500/10s; Data API 1,000/10s general, /trades 200/10s, /positions 150/10s.
Throttled/queued rather than hard-rejected; sliding windows.

Useful Gamma market fields: `conditionId`, `clobTokenIds` (JSON string!), `outcomes` (JSON
string), `negRisk`, `orderMinSize`, `orderPriceMinTickSize`, `umaBond`, `umaResolutionStatus`,
`rewardsMinSize`, `rewardsMaxSpread`, `events[].openInterest`.

V2 facts: CTF Exchange V2 `0xE111180000d2663C0091e4f400237545B87B996B`; NegRisk exchange
`0xe2222d279d744050d28e00520010520000310F59`; collateral = pUSD
`0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB` (1:1 wrapper over USDC.e); order books were wiped
at 2026-04-28 cutover; order struct dropped nonce/feeRateBps/expiration, added timestamp/
metadata/builder; fees computed protocol-side at match time (`getClobMarketInfo()` for
authoritative per-market fee params — the raw Gamma makerBaseFee/takerBaseFee=1000 is NOT bps).

If global trading ever opens to US: official SDKs are Polymarket/py-sdk (`pip install
polymarket-client`, recommended) and py-clob-client-v2 (PyPI, what poly-maker wraps). Auth:
L1 EIP-712 ("ClobAuthDomain" v1, chainId 137) -> POST /auth/api-key -> L2 HMAC headers.
Order types GTC/GTD/FOK/FAK, post-only supported. Trading limits: POST /order 5,000/10s burst.

## Polymarket US (execution — KYC + API keys required)

- REST: https://api.polymarket.us/v1 ; also WebSocket, gRPC
  (grpc-api.prod.polymarketexchange.com), FIX 150 msg/s via AWS PrivateLink (institutional).
- Auth: Ed25519 signature over timestamp+method+path (verify exact byte format/separators
  against the OpenAPI when keys exist); headers `X-PM-Access-Key`, `X-PM-Timestamp` (ms,
  ±30s), `X-PM-Signature`. Keys: polymarket.us/developer after in-app KYC (Socure; SSN/DOB).
- Rate limits: 20 req/s per key (authenticated) and per IP (public); higher by request.
- Fees (effective 2026-07-01): fee = Θ·C·p·(1−p); taker Θ=0.06; **maker Θ=−0.0125 (rebate)**;
  taker-volume tiers 10%/25%/50% rebate at $250k/$1M/$10M prior-month; banker's rounding to
  $0.01; no fee on cancels. Can be tier-placed by proving 30-day volume from another venue.
- Incentives: liquidity program scoring = DiscountFactor^(ticks from best) × size, DF
  0.30–0.90 per market, per-second snapshots, per-side normalization, Target Size to qualify;
  pools published at polymarket.us/rewards. Order features: modify/cancel-replace,
  close-position, preview, RFQ/combos.
- Sports-first venue; live in 49 states (Nevada out per court order).

## Kalshi (execution — has DEMO env for paper trading)

- REST prod: https://external-api.kalshi.com/trade-api/v2
- REST demo: https://external-api.demo.kalshi.co/trade-api/v2
- WSS prod: wss://external-api-ws.kalshi.com/trade-api/ws/v2
- Auth: RSA-PSS SHA256 over `{timestamp_ms}{METHOD}{path}` (path keeps /trade-api/v2 prefix,
  strips query); headers KALSHI-ACCESS-KEY / KALSHI-ACCESS-SIGNATURE / KALSHI-ACCESS-TIMESTAMP.
- Rate limits: token buckets, most calls cost 10 tokens. Basic (auto): 200 read/100 write
  tokens/s; Advanced 300/300 (application); up to Prime 4,000/4,000. 429 on exceed.
- Fees (2026-02-05 schedule): taker = ceil_to_cent(0.07·C·P·(1−P)); INX/NASDAQ100 series
  0.035; maker 0.0175 on designated series only; no settlement fees; no API fees.
- Orderbook format: yes/no sides as [price_cents, count] resting bids; BUY-YES liquidity at
  (100 − best_no_bid). Order POST /portfolio/orders: ticker, action buy/sell, side yes/no,
  type limit, count, yes_price|no_price (cents), client_order_id.
- Withdrawal timing 3–30 days historically (arb capital-lockup factor). International users
  now accepted (member agreement lists countries).

## Resolution (global venue)

UMA Managed Optimistic Oracle V2 since UMIP-189 (Aug 2025): proposals whitelisted to 37
addresses; bond ~$500–750 (per-market `umaBond`); 2h challenge window; disputes -> UMA DVM
token vote (~48h). Serial crypto (5m/15m/hourly) resolves via Chainlink instead. Disputed-
resolution tail risk is real: $7M Ukraine-minerals (Mar 2025), $237M Zelenskyy suit (Jul 2025),
$60M+ Strategy-BTC (Jun 2026) — no refunds issued.

## Gotchas collected from the research pass

- Gamma returns `clobTokenIds` and `outcomes` as JSON-encoded STRINGS, not arrays.
- CLOB book side ordering isn't guaranteed best-first — normalize (adapter does).
- Kalshi fee rounds UP per order — at 1-contract granularity fees are relatively brutal;
  batch sizing matters.
- Data-API fills are visible only AFTER they happen — whale signals are inherently lagged;
  merge exits (YES+NO -> collateral) fire NO sale event.
- Polymarket US pUSD/global pUSD are unrelated balances; Polymarket US is fiat, not on-chain.
- Cross-venue "same" events differ in resolution source, cutoff time, and edge-case wording —
  the pair registry exists because of documented losses to this.
