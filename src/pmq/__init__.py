"""pmq — prediction-market quant system.

Venues:
- Polymarket global (Polygon CLOB): READ-ONLY data source for US operators (geo-blocked for
  US trading). Gamma/CLOB/Data APIs are public — used for whale tracking and negRisk scanning.
- Polymarket US (api.polymarket.us): CFTC-regulated DCM. US-legal execution venue. KYC required.
- Kalshi (external-api.kalshi.com): CFTC-regulated DCM. US-legal execution venue. KYC required.
  Has a demo environment — used as the paper-trading backend.
"""

__version__ = "0.1.0"
