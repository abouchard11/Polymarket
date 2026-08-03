# pmq — prediction-market quant system

Scaffold for automated prediction-market trading on **US-legal rails**: Polymarket global as
a read-only data/signal source, **Polymarket US** and **Kalshi** as execution venues.

Built 2026-07-23 from a verified-evidence research pass — see **RESEARCH.md** (what actually
makes money and what's dead, with sources) and **CLAUDE.md** (operating brief for Claude Code,
including the V2-migration trap that invalidates most online tutorials).

## Design in one paragraph

Strategies are pure scanners that emit `Opportunity` objects; a single `ExecutionEngine`
applies hard risk limits (per-market cap, total cap, daily-loss halt, `KILL` file switch) and
mode gating. Default mode is `dry_run` — nothing is ever sent. `paper` mode uses Kalshi's demo
environment for a real order lifecycle. Fee math for all three venues lives in one module and
is unit-tested against the official schedules, because the zero-fee era ended in early 2026
and every naive arb calculation online is now wrong.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                        # all green, no network needed
cp .env.example .env          # fill in keys as accounts come online
pmq doctor                    # reachability check
pmq markets                   # live Polymarket global data (public, no account)
pmq scan-negrisk              # one arb-scan cycle (measurement only)
```

## What's implemented vs stubbed

| Component | Status |
|---|---|
| Polymarket global data (Gamma/CLOB/Data APIs) | working, public, no auth |
| Whale-flow tracker + evidence-based filters | working (needs config/whales.yaml wallets) |
| NegRisk sum-to-one scanner | working (measurement only — US can't trade global venue) |
| Fee math: global / Polymarket US / Kalshi | working, unit-tested vs official schedules |
| Risk manager + kill switch | working, unit-tested |
| Kalshi client (RSA-PSS auth, demo env) | implemented, needs API keys to exercise |
| Cross-venue arb scanner + pair registry | implemented, alert-only (leg risk by design) |
| Polymarket US client | auth skeleton; endpoints marked TODO(verify) — needs KYC + keys |
| Execution engine | dry_run/paper/live gating; multi-leg deliberately alert-only |
| Book/opportunity recorder -> parquet | library working; `pmq record` CLI wiring = roadmap M1 |
| Backtester, maker module | not built — see CLAUDE.md roadmap M4/M6 |

## First real-world steps (accounts, not code)

1. **Kalshi**: open account, generate API keys, and grab **demo-env** keys — that's the paper
   backend. 2. **Polymarket US**: KYC in app, then create Ed25519 API keys at
   polymarket.us/developer. 3. Fill `.env`, run `pmq doctor`.

Polymarket's global on-chain venue geo-blocks US trading; this repo uses it as data only.
(A CFTC request to onshore it is pending — if granted, add an execution adapter.)

## Not advice

Prediction-market trading loses money for ~69% of participants (see RESEARCH.md §1); this is
tooling, not a recommendation, and nothing here is legal or financial advice.
