# Verified Research: Polymarket / Prediction-Market Trading (compiled 2026-07-23)

Everything below was verified against primary sources on 2026-07-23 by three parallel research
passes (GitHub API sweep, strategy-evidence review, platform-mechanics review). Items are tagged
**VERIFIED** (paper / official docs / on-chain data) or **CLAIMED** (anecdote, unaudited).
Full source URLs at the bottom of each section.

---

## 1. The base rates (read this before writing any strategy)

- **68.8% of Polymarket users have lost money since 2022**; the top 1% of profitable users
  capture **76.5% of all profits**. Winners "provide liquidity using limit orders that resolve
  favorably"; losers "take liquidity using market orders." (VERIFIED — Akey, Grégoire, Harvie,
  Martineau, SSRN 6443103 / CEPR DP21615, $67B volume analyzed)
- **~5% of wallets are bot-like and generate 75% of volume. 823 bot accounts each netted
  >$100k — $131M collectively.** Bots win not by predicting better but "by getting into markets
  earlier and at better prices" (~2.5c/contract price improvement). Retail actually picked
  winners MORE often than bots. (VERIFIED — Bloomberg / Della Vedova, ~222M trades)
- WSJ: **0.1% of accounts took 67% of all profits**; >70% of users lost. (VERIFIED)
- 12.6% of addresses hold 81.4% of fill notional; Gini 0.932. (VERIFIED — arXiv:2605.11640)

**Implication:** the game is an execution game, not a prediction game. Retail loses on price,
not on opinions.

Sources: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6443103 ·
https://finance.yahoo.com/markets/crypto/articles/100-000-polymarket-accounts-booked-062234759.html ·
https://www.benzinga.com/markets/prediction-markets/26/05/52251195/0-1-of-polymarket-accounts-take-home-67-of-all-profits-investigation-finds ·
https://arxiv.org/pdf/2605.11640

## 2. Strategy evidence, ranked by verified dollars

### 2a. Passive liquidity provision + fee rebates + reward pools — STRONGEST EVIDENCE
- The winning cohort IS the passive-limit-order cohort (SSRN paper, §1).
- 2026 fee regime pays makers: global venue 0 maker fees + **15–25% of taker fees rebated to
  makers daily**; liquidity reward pools **>$5M/month across sports alone** (April 2026), e.g.
  $10k/EPL match; World Cup pools $6,110–$52,000/game. Polymarket US: **maker theta −0.0125 —
  makers are literally paid per fill.** (VERIFIED — official docs)
- Top lifetime LP-reward earner: $1.20M; top maker-rebate earner: $742k. (VERIFIED — tracker)
- BUT: naive reward farming is dead. poly-maker (the canonical open-source MM bot, 1.4k stars)
  says in its own README: **"In today's market, this bot is not profitable and will lose
  money."** Adverse selection around news is the killer; one 30–40% adverse move wipes weeks
  of rewards (tezlee postmortem, CLAIMED). Early-era 200–300 USDC/day per $10k is over;
  realistic naive baseline ~10%/yr (CLAIMED).
- Sources: https://docs.polymarket.com/market-makers/liquidity-rewards ·
  https://docs.polymarket.com/market-makers/maker-rebates.md · https://docs.polymarket.us/fees ·
  https://github.com/warproxxx/poly-maker · https://polyscalping.org/leaderboard ·
  https://tezlee.substack.com/p/i-cloned-a-polymarket-market-making

### 2b. Latency / live sports & esports — BIGGEST VERIFIED P&L, HARDEST TO ENTER
- Largest on-chain P&Ls live here: "swisstony" **$16.4M lifetime, +$8.6M in 30 days on $381M
  volume** (VERIFIED via tracker). Mechanism (CLAIMED): stadium-direct data feeds vs 15–40s
  broadcast delay.
- World Cup 2026: 194,422 addresses — 66.7% lost; median winner +$4.85; **54 addresses took
  60% of all winnings** (VERIFIED — Dune analysis). Three top wallets withdrew to the same
  Binance address — suspected insider (CLAIMED — Lookonchain).
- Arms race: GRID now pipes official low-latency esports data INTO Polymarket (VERIFIED);
  sports taker fees since Feb 2026; solo retail bots are documented mostly as the victim side.
- Honest solo benchmark: HN writeup — de-vigged sportsbook odds -> resting limit orders on
  esports, **+$8.3k risk-free in ~3 months, then edge decayed** (CLAIMED, detailed).
- Sources: https://polyscalping.org/leaderboard ·
  https://cryptoslate.com/most-world-cup-traders-won-less-than-5-on-polymarket-while-five-wallets-walked-away-with-millions/ ·
  https://grid.gg/polymarket-partners-with-grid/ · https://news.ycombinator.com/item?id=48461522

### 2c. Resolution literacy + bonding (97–99c) — REAL BUT TAIL-RISKED
- Buying near-certainties pre-resolution: fees ~zero at extreme prices (fee = Θ·p·(1−p));
  1–3% per cycle. **At 95c one loss erases 19 wins.**
- UMA oracle is the tail risk — VERIFIED incidents: $7M Ukraine-minerals market forced wrong
  by a UMA whale (Mar 2025, no refunds); $237M Zelenskyy-suit market resolved NO amid
  manipulation allegations (Jul 2025); $60M+ Strategy-BTC dispute (Jun 2026). WSJ: >50% of
  UMA dispute votes come from 10 wallets; ~1 in 5 disputes had a financially-conflicted voter.
  Reform: UMIP-189 (Aug 2025) — proposals now whitelisted to 37 addresses.
- Domer (#1-ranked, ~$300M lifetime volume, all manual): edge = reading resolution criteria
  better than the crowd + resting limit orders; "repeatedly burned by UMA." (VERIFIED interview)
- Sources: https://www.theblock.co/post/348171/ · https://decrypt.co/329210/ ·
  https://thedefiant.io/news/markets/usd85m-polymarket-dispute-over-strategy-s-may-bitcoin-sale-puts-uma-s-token-voting-oracle-on ·
  https://www.theblock.co/post/366507/ · https://www.onchaintimes.com/a-chat-with-domer-the-1-trader-on-polymarket/

### 2d. Cross-venue arb (Polymarket <-> Kalshi) — REAL, THIN, EPISODIC
- VERIFIED: persistent **2–4% execution-aware deviations** on cross-listed events
  (TU Munich, arXiv:2601.01706, 100k events, 10 platforms); only ~6% of events cross-listed;
  8.1pp Kalshi/Polymarket gap at the 2024 election peak.
- Frictions eat most of it: hold-to-resolution capital lockup on BOTH venues, both venues'
  fees, **resolution-wording mismatch (the #1 loss source)**, Kalshi withdrawal delays.
- Live screener check (2026-07-23): 3,363 markets scanned, **0 pairs cleared an executable
  floor** (VERIFIED snapshot). Spreads blow out around big events — that's when it pays.
- Sources: https://arxiv.org/html/2601.01706v1 ·
  https://sherwood.news/markets/kalshi-polymarket-presidential-election-prediction-markets/ ·
  https://ahasignals.com/research/prediction-market-arbitrage-strategies/ ·
  https://rajivsethi.substack.com/p/the-limits-of-arbitrage

### 2e. Single-venue arb (sum-to-one / negRisk) — HISTORICALLY HUGE, NOW SCRAPS
- VERIFIED: **$39.6M extracted Apr 2024–Apr 2025** (arXiv:2508.03474; AFT 2025): $29.0M from
  negRisk multi-outcome baskets, $10.6M single-market rebalancing; 41% of conditions showed
  windows; top 10 wallets took ~40%.
- VERIFIED 2026 reality check: NBA markets, 75M book snapshots, Feb–Mar 2026 — **7 executable
  single-market episodes in a month, median life 3.6s, total executable profit ~$770 including
  combinatorial**. The pool collapsed.
- Keep a scanner for chaotic new listings; do not build a business on it.
- Sources: https://arxiv.org/abs/2508.03474 · https://arxiv.org/html/2605.00864v1

### 2f. Whale copy-trading — TRANSPARENCY IS REAL, NAIVE COPYING IS A COIN FLIP
- All positions/fills are public on-chain (VERIFIED). Leader persistence exists (RN1: $7M
  sports P&L, "no meaningful dip" — VERIFIED via Polymarket's own newsletter, Stand.Trade data).
- BUT: of the most-copied wallets, many are bots; **55% of 5-minute-market participants are
  bots**; leaders evade copiers via iceberg entries, YES+NO **merge exits that fire no sale
  event**, and secondary accounts. Polycopy's own backtest across 687k resolved trades:
  **unfiltered copying ≈ coin flip**; only ~23% of wallets with ≥5 resolved trades have
  positive lifetime P&L. (VERIFIED as published; vendor data)
- Use as a signal INPUT with hard filters (this repo's whale_signal.py), never a mirror.
- Sources: https://news.polymarket.com/p/copycat · https://polycopy.app/best-polymarket-traders

### 2g. LLM forecasting — NO VERIFIED ALPHA AS OF MID-2026
- Halawi et al. (NeurIPS 2024): LLM Brier 0.179 vs crowd 0.149 — **crowd wins** except in
  selective regimes. Metaculus: pros beat bots EVERY quarter through Q2'25 (gap widening).
  Meta-review (11 analyses, to May 2026): **"no evidence that any LLM system has profitably
  traded prediction markets."** PolyBench (realistic execution sim, 38,666 live markets):
  5 of 7 LLMs lost money.
- Verified value: research force-multiplier for a human (24–28% accuracy lift) and automation
  glue — not the signal itself.
- Sources: https://arxiv.org/abs/2402.18563 · https://www.metaculus.com/aib/2025/q2/ ·
  https://forum.nunosempere.com/posts/Spyz3wESZu2eeqhDj/ai-forecasting-in-2026-what-11-analyses-say ·
  https://arxiv.org/html/2604.14199v1

### 2h. Case study: Théo (2024 election)
- VERIFIED: >$30M staked across 11 linked accounts, **>$85M profit** (Chainalysis). Edge was
  PRIVATE INFORMATION he manufactured legally: commissioned neighbor-question polls detecting
  shy-Trump effect. The lesson isn't "bet big" — it's that manufactured proprietary data beats
  public-data modeling.
- Sources: https://finance.yahoo.com/news/polymarket-whale-actually-made-85-050139914.html ·
  https://www.cbsnews.com/news/french-whale-made-over-80-million-on-polymarket-betting-on-trump-election-win-60-minutes/

## 3. Platform facts that shape this repo (verified July 2026)

- **US access:** polymarket.com (global, on-chain) **geo-blocks the US** (among 33 blocked
  jurisdictions). US-legal venues: **Polymarket US** (QCX LLC, CFTC DCM, launched Dec 3 2025,
  KYC w/ SSN via Socure, live in 49 states, Nevada out) and **Kalshi** (CFTC DCM; open API;
  now takes international users too; heavy state-level litigation ongoing). Polymarket has a
  **pending CFTC request to onshore the on-chain exchange** — if granted, the global CLOB
  opens to US traders (watch this; it changes everything in this repo's favor).
- **Fees (the zero-fee era is OVER):** global taker fee = C·rate·p·(1−p), rate: crypto 0.07,
  sports/econ/culture/weather/other 0.05, finance/politics/mentions/tech 0.04, geopolitics 0;
  makers 0 + 15–25% rebates + tiered taker-rebate ladder (to 50%). Polymarket US: taker 0.06,
  **maker −0.0125 (rebate)**, volume-tiered taker rebates 10/25/50% at $250k/$1M/$10M/mo.
  Kalshi: taker ceil(0.07·C·P·(1−P)), maker 0.0175 designated series only.
- **V2 migration (2026-04-28):** Polymarket global rebuilt on CTF Exchange V2 + pUSD
  collateral. **Every v1 client and tutorial is dead** (py-clob-client, clob-client, agents —
  all archived). Current official stack: `Polymarket/py-sdk` (pip `polymarket-client`) or
  `py-clob-client-v2`. LLM training data is full of dead v1 patterns — see CLAUDE.md warning.
- **Rate limits (global, generous for our use):** Gamma /markets 300/10s; CLOB /book 1,500/10s;
  Data API /trades 200/10s, /positions 150/10s. Polymarket US API: 20 req/s. Kalshi Basic:
  200 read/100 write tokens/s. Kalshi has a **demo environment** — our paper-trading backend.
- **UMA resolution:** proposal bond ~$500–750, 2h challenge window, disputes -> UMA token vote;
  serial crypto markets resolve via **Chainlink**, not UMA.
- Sources: https://help.polymarket.com/en/articles/13364163-geographic-restrictions ·
  https://docs.polymarket.com/trading/fees.md · https://docs.polymarket.us/fees ·
  https://kalshi.com/docs/kalshi-fee-schedule.pdf · https://docs.polymarket.com/v2-migration ·
  https://docs.polymarket.com/api-reference/rate-limits.md ·
  https://www.cftc.gov/csl/25-48/download ·
  https://finance.yahoo.com/markets/crypto/articles/polymarket-seeks-cftc-approval-bring-152113106.html

## 4. GitHub landscape (star counts verified via GitHub API 2026-07-23)

**No Polymarket-specific repo exceeds 5,000 stars.** Largest: Polymarket/agents ~3,747
(ARCHIVED), Jon-Becker/prediction-market-analysis ~3,653 (active, best dataset). The 5k+ club
is general infrastructure — and the single biggest find there: **ccxt (43,379 stars) now ships
first-class prediction-market support** — a `PredictionExchange` base class with full trading
connectors for polymarket AND kalshi (174KB implementation incl. EIP-712 signing). Also:
freqtrade 52.6k (strategy lifecycle patterns), nautilus_trader 24.9k (event-driven backtests;
already adapted to Polymarket by evan-kolberg/prediction-market-backtesting, 1k stars),
hummingbot 19.2k (MM patterns; **no prediction-market connector** — PR closed unmerged).

Key niche repos: warproxxx/poly-maker 1.4k (MM reference architecture: regime machine,
markout toxicity, dead-man switch — README says unprofitable as-is); warproxxx/poly_data 2.2k
(the only verified post-V2 on-chain fills pipeline); braedonsaunders/homerun 150 stars but the
broadest open strategy catalog (AGPL — copy ideas, not code); pmxt 2.0k ("ccxt for prediction
markets," hosted-service caveat); oracle3 265 (favorite-longshot-bias pricing model, Apache-2.0).

**Warnings:** `dev-polymarket/clob-client-v2` is a TYPOSQUAT of the official client — hostile,
do not install. A cluster of ~500-star "arbitrage bot" repos are SEO/star-farmed Telegram
sales funnels (casatrick/*, radioman/*, hubert20/*, etc.). Stars are a weak quality signal in
this niche.

## 5. Bottom line

Money on Polymarket in 2026 is made on **execution** (speed, passive fills, maker rebates,
reward pools), **private information** (manufactured polls, fast feeds, alleged insiders), and
**rules literacy** (resolution criteria, UMA politics) — in that order of documented dollars.
It is NOT made anymore on mechanical sum-to-one arb at scale, naive reward farming, naive
copying, or raw LLM forecasts. ~69% of participants fund the top 0.1–1%.

For a $10k–100k solo operator on US-legal rails, the evidence-ranked play:
1. Build the data/measurement layer first (this repo). Record everything for 2+ weeks.
2. Cross-venue scanner armed and waiting for the next big-event dislocation (that's when
   2–4% spreads appear) — with the pair registry doing resolution-wording diligence up front.
3. Whale flow as a filtered signal input to human/model judgment on US venues.
4. Graduate to maker-side flow (rebates + pools) once you have book-replay telemetry —
   that's where the verified structural edge lives, and it's a knife fight.

## 6. Deep-dive addendum: non-mainstream seams for a solo operator (2026-07-23, same session)

Targeted adversarial research pass beyond §1–5, hunting specifically for reproducible edges
a $10k–100k solo operator could enter (not just re-confirming the base rates above). 103
agents, 21 primary/secondary sources, 25 claims put through 3-vote adversarial verification:
**10 confirmed, 15 refuted, 0 left unverified.** Refuted items are listed, not memory-holed —
"not established" and "confirmed absent" are different findings and are labeled as such.

### 6a. CONFIRMED

- **Fee/rebate mechanics, precisely quantified.** Live-checked against docs.polymarket.us/fees
  during this session: PMUS taker theta 0.06 / maker theta −0.0125, effective July 1 2026 —
  **matches this repo's `core/fees.py` exactly, no fix needed.** Newly discovered: a taker-
  **rebate** ladder on top of the maker rebate — 10%/25%/50% back on taker fees at
  $250k/$1M/$10M trailing-calendar-month taker volume — plus an **"Accelerated Tier
  Placement"** clause, verbatim from the live page: *"A Participant may provide verifiable
  proof of their trailing-30-day notional trading volume on another prediction market and be
  assigned to the rebate tier corresponding to that volume."* Unconfirmed whether trailing
  Polymarket-global volume would qualify in practice — open question, not a green light.
  (VERIFIED — docs.polymarket.us/fees, live-checked 2026-07-23)
- Polymarket global's maker rebate is a **category-specific revenue-share of taker fees**, not
  a flat rate: Crypto 20%, Sports 15% (cut from 25% in a July 2026 update), Finance/Politics/
  Economics/Culture/Weather/Tech/Mentions/Other 25%, Geopolitics 0%. No confirmation this
  program extends to Polymarket US traders — different mechanic from PMUS's own theta.
  (VERIFIED — docs.polymarket.com/market-makers/maker-rebates)
- Global-venue bot dominance is a strong function of market **duration**: 55–62% of volume
  bot-controlled in 5/15-min markets (casual traders 4–5%), falling to ~31% bots / 41%
  casual+regular in 4H/daily/weekly markets. The human-competable zone is the slow end, not
  the fast end. (VERIFIED — Dune analysis, Feb 15–Mar 15 2026 window, corroborated by 3
  independent secondary outlets after the primary Dune URL 404'd on direct fetch)
- **Kalshi favorite-longshot bias is pervasive AND scale-invariant.** Present in nearly every
  category (weakest only in politics/entertainment), and — contrary to the standard "big
  money arbs this away" prior — does NOT shrink with trade size or market volume; the highest
  transaction-size quintile shows the *largest* bias coefficient in the dataset. Caveat: this
  is a **pre-fee** finding — net-of-2026-fee survival is the open question, and a blanket
  "makers earn +2.6% post-fee" claim was explicitly refuted (see 6b).
  (VERIFIED — Bürgi, Deng & Whelan working paper, GWU/UCD/CESifo, 300k+ Kalshi transactions,
  regression tables read directly)
- **Kalshi single-name-market maker edge, with a mechanism.** Makers earn ~2x per contract in
  single-name vs. broad-based markets (1.91¢ vs 0.82¢) — not from wider spreads, but because
  retail systematically overbets YES (~61% of buys) in markets that mostly resolve NO (~32–33%
  YES rate). The edge is being the *counterparty* to that behavioral surplus, not just betting
  the bias directionally. (VERIFIED — Bartlett (Stanford Law) & O'Hara (Cornell), 41.6M Kalshi
  trades / 478,167 markets, corroborated by an independent outlet reproducing the same figures)
- **Kalshi's Fed-funds/FOMC market is explicitly NOT an under-competed niche** — Susquehanna
  runs a named institutional MM desk there, ~100M contracts/meeting. Kills that candidate
  outright. (VERIFIED — Federal Reserve staff working paper FEDS 2026-010 / NBER w34702)
- Cross-market "combinatorial arbitrage" (beyond strict negRisk baskets) is an academically
  real, formally-defined category distinct from single-market rebalancing arb — but thin:
  ~$95k observed across only 4 of 13 examined dependent-market pairs, vs. ~$28M+ for ordinary
  single-market rebalancing arb in the same study. Not obviously scalable.
  (VERIFIED — AFT 2025/Dagstuhl LIPIcs, arXiv:2508.03474)

### 6b. REFUTED / NOT ESTABLISHED (say so plainly, don't round up to "confirmed absent")

- No surviving claim on **PMUS-vs-global spread/depth/fill-quality** comparison — still
  requires this repo's own M1 recorder data, not literature. Open gap.
- No reliable public dataset survived for **top-1%-wallet forensics** — the Jon Becker
  dataset's own description and a wallet-tier-archetype clustering claim were both refuted.
  Open empirical gap; do not build on this dataset without independent verification.
- "Kalshi makers beat fees AND the favorite-longshot bias, +2.6% net average return" — refuted
  (high variance, not a clean edge; do not treat maker-side as free money).
- Effective-spread-widens-in-longshot-markets (400bps center vs 1,300–1,800bps <10¢) — refuted.
- Cross-exchange political-market underconfidence bias, and a 4-factor calibration-variance
  decomposition (87.3% explained) — both refuted.
- Aggregate "$40M total realized arb profit" figure — refuted; the $28M/$95k split above
  (single-market vs. combinatorial) is the surviving, more precise version.

### 6c. Ranked 2-week sprint candidates (extends §3's Q2 options in HANDOFF.md)

1. **Kalshi favorite-longshot bias, scale-invariant persistence.** Measure net-of-live-fee
   returns by category and price bucket on real Kalshi order books. Falsifies if the edge
   dies once actual maker/taker fees and the tighter-ψ categories (politics/entertainment)
   are applied.
2. **Kalshi single-name-market maker/behavioral-overbetting edge.** Passively quote (or
   simulate fills) in single-name markets; track realized markout against the documented
   60.9%/32.5% pattern. Falsifies if your own fills don't reproduce ~1.91¢/contract once
   *your* adverse-selection exposure — not the published aggregate — is measured.
3. **PMUS Accelerated Tier Placement.** Confirm whether trailing Polymarket-global volume
   actually substitutes to unlock PMUS taker rebates at this bankroll. Falsifies if the
   mechanism doesn't apply cross-venue in practice, or the effective threshold is unreachable
   regardless of routing.

If none of these three survive their own net-of-fee measurement: read that as confirmation
the top-1% cohort's edge here is overwhelmingly execution/latency-based (§1–2b), not a
discoverable public-data mispricing — and redirect toward M6 (maker module) rather than
continued search for undiscovered statistical edges in public data.

Time-sensitivity: PMUS's fee schedule and Polymarket global's rebate programs are all very
recent (May–July 2026) and could change again before a 2-week sprint concludes — re-verify
current terms in-app before sizing any position.

Sources: https://docs.polymarket.us/fees · https://docs.polymarket.com/market-makers/maker-rebates ·
https://dune.com/blog/polymarket-fast-markets · https://www2.gwu.edu/~forcpgm/2026-001.pdf ·
https://www.karlwhelan.com/Papers/Kalshi.pdf ·
https://law.stanford.edu/2026/04/21/adverse-selection-in-prediction-markets-evidence-from-kalshi/ ·
https://www.federalreserve.gov/econres/feds/files/2026010pap.pdf · https://arxiv.org/abs/2508.03474
