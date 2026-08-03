from pmq.core.models import Side
from pmq.venues.polymarket_global import PolymarketGlobalData


async def test_wallet_trade_sides_are_normalized_to_enum():
    client = object.__new__(PolymarketGlobalData)
    client.data_api = "https://example.test"

    async def fake_get(url, params=None):
        return [
            {
                "conditionId": "market-1",
                "title": "Will the test pass?",
                "outcome": "Yes",
                "side": "BUY",
                "price": "0.40",
                "size": "10",
                "timestamp": "1",
            },
            {
                "conditionId": "market-1",
                "title": "Will the test pass?",
                "outcome": "No",
                "side": "SELL",
                "price": "0.60",
                "size": "5",
                "timestamp": "2",
            },
        ]

    client._get = fake_get
    signals = await client.get_wallet_trades("0xabc")

    assert [signal.side for signal in signals] == [Side.BUY, Side.SELL]
