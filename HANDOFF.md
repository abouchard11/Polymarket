# HANDOFF.md — Session-1 Directive for Claude Code Desktop

Written 2026-07-23 by the Cowork session that built this scaffold. You (Claude Code) have no
memory of that session — everything you need is in this repo. This file is your directive
for the first working session in this workspace.

## 0. What this is and how it got here

`pmq` is a prediction-market quant scaffold built from a same-day, three-track verified
research pass (GitHub API sweep, strategy-evidence review with academic sources, platform-
mechanics review against official docs). The evidence dossier is `RESEARCH.md`; condensed
API integration facts are `docs/API_NOTES.md`; architecture/conventions are `CLAUDE.md`.
Owner: Alex — US-based, $10k–$100k intended bankroll, no venue accounts opened yet.

**THE MOST IMPORTANT FACT: no strategy is pinned down.** Alex's initial scaffold picks
(cross-venue arbitrage + whale copy-trading) were priorities for what to scaffold, not
commitments. The research says those two are the *weakest* standalone edges in 2026, while
maker-side flow (rebates + reward pools + passive fills) has the strongest verified evidence
but is the hardest fight. This tension is unresolved BY DESIGN. Do not resolve it yourself —
resolve it by interviewing Alex (section 3) and then by measurement (M3), not by vibes.

## 1. Current state (all claims tested 2026-07-23)

Working and verified:
- 32 unit tests pass (`pytest`), ruff clean. Fee math tested against official schedules.
- Live-smoke-tested from the build environment: Gamma, CLOB, Data-API, Kalshi demo all
  reachable; `pmq markets` pulls real data; `pmq scan-negrisk` runs a full live cycle.
- `scripts/arb_watch.py` — continuous live arb scanner (binary YES+NO rebalancing +
  negRisk baskets), fee/depth-aware, parquet-logging, runnable with zero credentials.
  Live-tested 2026-07-23: clean run, zero qualifying hits at 30bps on top-volume markets —
  consistent with RESEARCH.md §2e (the naked-arb pool is bot-drained).
- Git: branch `main`, single root commit `13722d5` (36 files). Working tree has the
  post-commit doc fixes + this file — **your first action: commit them locally.**

Known seams (deliberately open):
1. `venues/polymarket_us.py` — Ed25519 signing implemented per documented pattern, but the
   exact message byte-format and endpoint paths are marked `TODO(verify)`: confirm against
   the docs.polymarket.us OpenAPI once real API keys exist. `place_order` raises
   `NotImplementedError` on purpose.
2. `pmq record` CLI does not exist yet — `ParquetRecorder` is a working library class with
   no long-running loop or market-watchlist config wired to it. This is roadmap M1 and a
   good first coding task.
3. No backtester. No maker module. No WebSocket consumers (REST polling only so far).
4. `config/pairs.yaml` and `config/whales.yaml` don't exist (only `.example` templates) —
   they're populated as part of M3, and whale addresses must be resolved from a live
   leaderboard (the example file explains how).
5. `_to_delete/` in repo root is gitignored scratch from the cloud delivery (tarball +
   swept git lock files). Alex can trash it; ignore it otherwise.

Environment note from the build session: the cloud↔Mac file bridge cannot delete files, so
git operations run through it strand `.lock` files. That's why the doc fixes arrived
uncommitted. You run locally with full permissions — this problem does not apply to you.

## 2. Doc-freshness / staleness protocol

Everything dated 2026-07-23 was verified that day against primary sources. Prediction-market
platforms are changing fast (fees introduced Jan–Mar 2026; full exchange rebuild Apr 2026).
Re-verify before trusting:

| What | Where it lives | Re-check | Source of truth |
|---|---|---|---|
| Fee thetas / category rates | `core/fees.py`, tests | monthly, and before ANY live order | docs.polymarket.com/trading/fees · docs.polymarket.us/fees · kalshi.com/docs/kalshi-fee-schedule.pdf |
| Rate limits, endpoints | `docs/API_NOTES.md` | when adding a new API surface | docs.polymarket.com/api-reference · docs.kalshi.com |
| US-access status / CFTC onshoring of the global venue | RESEARCH.md §3 | monthly — if the on-chain venue opens to US, priorities change materially | CFTC.gov, Polymarket announcements |
| Reward-pool sizes / maker programs | RESEARCH.md §2a | before starting M6 | docs.polymarket.com/market-makers · polymarket.us/rewards |
| Whale wallet list | `config/whales.yaml` | monthly (leaders rotate/evade) | live leaderboards |

When you re-verify, update the date stamps in the touched files. If a doc claim and reality
diverge, fix the doc in the same commit as the code change.

Standing warnings (do not relearn these the hard way):
- Your training data predates the 2026-04-28 V2 migration — v1 clients (`py-clob-client`,
  `@polymarket/clob-client`) and most online tutorials are dead. Trust `docs/API_NOTES.md`
  and current official docs over anything you "remember."
- `dev-polymarket/clob-client-v2` on GitHub is a typosquat; this niche is full of
  star-farmed scam repos. Dependencies only from pyproject.toml's pinned list or official
  orgs (Polymarket/*, ccxt).
- polymarket.com global is geo-blocked for US trading. It is a read-only data source here.
  Never suggest VPNs or geo-workarounds.

## 3. Session-1 interview — run this BEFORE writing strategy code

Ask Alex these, one block at a time (he answers fast, prefers blunt options with your
recommendation marked). Record the answers in a new `DECISIONS.md` so future sessions
inherit them.

**Q1 — Accounts (the long pole; gates everything).** Status on: (a) Kalshi account +
prod API keys, (b) Kalshi DEMO keys (instant, unblock paper trading — push to do this
today), (c) Polymarket US KYC started → polymarket.us/developer Ed25519 keys. If nothing
is started, make (b) today's homework and sequence (c) in parallel — KYC clock time is
dead time.

**Q2 — First sprint focus (the strategy question; nothing is pinned).** Present the
evidence honestly and force a choice for a 2-week sprint:
- (a) *Measurement-first (recommended):* wire `pmq record`, run all scanners on a cadence,
  zero trading, analyze after 2 weeks: where does net-of-fee edge actually appear, at what
  depth, around which events? Cheapest way to buy certainty; matches RESEARCH.md's finding
  that documented winners win on execution quality, which you can't improve blind.
- (b) *Cross-venue arb pipeline:* hand-build the pairs registry (5–10 verified pairs),
  harden two-leg fill sequencing against Kalshi demo. Pays off mainly around big events —
  the live screener found ~zero clean pairs on an ordinary day.
- (c) *Whale-signal evaluation:* populate whales.yaml, log signals for 2 weeks, test
  whether whale flow LEADS prices on US venues (that's the only version of copy-trading
  the evidence doesn't kill).
- (d) *Maker research spike:* study poly-maker's architecture (MIT), design the PMUS maker
  module. Where verified edge lives; also the knife fight. Realistic as sprint 2–3, not 1.
Note: (a) quietly feeds (b), (c), AND (d) — say so.

**Q3 — Recorder uptime.** A 2-week measurement is only as good as its uptime. MacBook cron
dies with the lid; options: always-on Mac, a ~$5–10/mo VPS, or a scheduled cloud task.
Which does he want? (Affects whether M1 ships a systemd unit / launchd plist / cron doc.)

**Q4 — Risk sign-off.** `.env.example` defaults are deliberately tiny vs his bankroll:
$500/market, $2k total, $200/day loss halt, 150bps min edge. Confirm these stand for
phase 1 and agree on the promotion criteria for raising them (e.g., after M4 fill
telemetry shows expected-vs-realized slippage within X bps).

**Q5 — Market-category focus.** Politics/econ (0.04 fee tier, slower, wording-stable,
good for pair verification) vs sports (0.05, fast, PMUS's native strength, where reward
pools live) vs crypto serials (0.07 + bot-saturated — evidence says avoid). Pick 1–2
categories for the watchlist; this scopes the pairs registry and the recorder.

If Alex is unavailable, do only non-committal work: commit the pending fixes, set up the
environment, wire `pmq record` behind a config, and leave the strategy fork explicitly open.

## 4. Session-1 definition of done

1. Pending doc fixes + HANDOFF.md committed; `pytest` green locally (expect 32 passing).
2. `pmq doctor` all green from Alex's machine.
3. Interview answers captured in `DECISIONS.md`.
4. `pmq record` wired: watchlist config + long-running loop + graceful shutdown + parquet
   output verified non-empty; scheduling per Q3 answer.
5. Sprint plan for the chosen focus written at the bottom of `DECISIONS.md` with a
   2-week end date and a falsifiable success metric (e.g., "≥N opportunities >150bps
   net-of-fee observed at ≥$100 depth, else we pivot").

Keep the invariants from CLAUDE.md: strategies never place orders; everything through
RiskManager; dry_run default; fees in every edge calculation; measurement before money.
