# CLAUDE.md — pmq (prediction-market quant system)

Operating brief for Claude Code sessions in this repo. Read RESEARCH.md before proposing
strategy changes — every design decision here traces to verified evidence in that file.

## Critical context that overrides your training data

1. **Polymarket V2 migration (2026-04-28).** The global venue moved to CTF Exchange V2 +
   pUSD collateral. `py-clob-client` (v1), `@polymarket/clob-client` (v1), `Polymarket/agents`,
   and virtually every pre-2026 tutorial are DEAD/ARCHIVED. Your training data is full of v1
   patterns — do not use them. Current official stack: `polymarket-client` (Polymarket/py-sdk)
   or `py-clob-client-v2`. This repo's global adapter is plain public REST and unaffected.
2. **The operator is US-based.** polymarket.com global is geo-blocked for US trading — it is
   a READ-ONLY data source here (public Gamma/CLOB/Data APIs, no auth, no ToS-violating
   workarounds — never suggest VPNs). Execution venues are Polymarket US (api.polymarket.us)
   and Kalshi. If Polymarket's pending CFTC request to onshore the on-chain exchange is
   granted, revisit — an execution adapter for the global CLOB becomes the top priority.
3. **Fees exist now** (since Jan–Mar 2026). Never write arb/edge math without fee terms from
   `pmq.core.fees`. The constants there were verified against official fee docs July 2026 —
   re-verify against docs.polymarket.com/trading/fees, docs.polymarket.us/fees, and the
   Kalshi fee PDF before trusting them in a new quarter.
4. **Supply-chain caution:** `dev-polymarket/clob-client-v2` on GitHub is a typosquat; this
   niche is full of star-farmed scam repos. Only add dependencies from the pinned list in
   pyproject.toml or official orgs (Polymarket/*, ccxt).

## Commands

```bash
pip install -e ".[dev]"     # or: uv pip install -e ".[dev]"
pytest                      # unit tests — pure math/logic, no network
ruff check src tests        # lint
pmq doctor                  # env + venue reachability
pmq markets                 # live global markets via Gamma (public)
pmq scan-negrisk            # one basket-scan cycle (measurement only)
pmq whales                  # one whale-flow poll (needs config/whales.yaml)
```

## Architecture

```
src/pmq/
  config.py                 pydantic-settings; .env; Mode: dry_run | paper | live
  core/models.py            venue-agnostic domain models (Market, OrderBook, Opportunity…)
  core/fees.py              all three venues' fee formulas — single source of truth
  core/arb.py               pure arb math (two-leg cross-venue, negRisk baskets)
  core/risk.py              RiskManager: hard caps, daily-loss halt, KILL file switch
  venues/polymarket_global  READ-ONLY public data (Gamma/CLOB/Data) + whale trades
  venues/kalshi.py          full client: RSA-PSS auth, demo env = paper backend
  venues/polymarket_us.py   Ed25519 auth skeleton; order endpoints TODO(verify) — see file
  strategies/               scan() -> list[Opportunity]; strategies NEVER place orders
  execution/engine.py       the ONLY order path; mode-gated; risk-checked; alert-only for
                            multi-leg (leg risk unhandled by design until telemetry exists)
  data/recorder.py          books/opportunities -> parquet (backtest foundation)
```

Invariants to preserve:
- Strategies emit `Opportunity`; only `ExecutionEngine` touches order endpoints.
- Every order passes `RiskManager.check_order` — fail-closed.
- `dry_run` is the default mode everywhere. Live mode must never be a default of anything.
- Cross-venue pairs execute only with `resolution_verified: true` in config/pairs.yaml —
  a human must diff resolution texts first (wording mismatch = #1 documented loss source).
- Secrets only in `.env` (gitignored). Never log private keys or signatures.

## Roadmap (work top-down; don't skip ahead)

- **M0 — accounts:** operator opens Kalshi (has demo env — get demo API keys immediately)
  and Polymarket US (KYC, then polymarket.us/developer for Ed25519 keys). Code work possible
  before this completes using global public data + Kalshi public endpoints.
- **M1 — data layer proven:** `pmq doctor` all green; recorder capturing books for 10–20
  candidate markets on a cron; verify parquet output loads clean.
- **M2 — PMUS client completed:** confirm signing byte-format + endpoint paths against
  docs.polymarket.us OpenAPI with real keys; implement markets/book/balance; leave
  place_order NotImplementedError until M4.
- **M3 — measurement running:** negrisk scanner + cross-venue scanner (pairs.yaml with 5–10
  hand-verified pairs) + whale tracker on 30–60s cadences, all logging Opportunities to
  parquet. Run 2+ weeks. Analyze: how often does net-of-fee edge appear? At what depth?
  Around which events? This data decides what gets built next — not vibes.
- **M4 — paper execution:** wire Kalshi demo-env order lifecycle through ExecutionEngine;
  fill telemetry (requested vs filled price, latency); leg-risk handling design for two-leg
  arb (fill-or-kill sequencing, unwind rules).
- **M5 — small live:** only what M3 measurement justified, at minimum size, risk caps tight.
- **M6 (evidence says this is the real prize) — maker module:** two-sided quoting on
  Polymarket US (maker rebate −0.0125) / reward-pool markets, with inventory skew, markout
  toxicity tracking, and a news kill-switch. Steal architecture from warproxxx/poly-maker
  (MIT): regime machine, target-vs-live order reconciliation, dead-man heartbeat. Its README
  honestly states the naive version loses money — the moat is adverse-selection defense.

## Verification checklist for any new strategy code

1. Pure math in `core/`, unit-tested with known-answer cases (see tests/test_arb.py style).
2. Fee terms included and sourced from `core/fees.py`.
3. Depth-aware sizing (top-of-book only unless depth-walk implemented).
4. Emits Opportunity; no order calls.
5. Recorded to parquet so the claim "this would have made money" is checkable later.
