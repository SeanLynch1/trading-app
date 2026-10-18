"""P&L maths, checked against numbers worked out by hand. No database needed."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

from portfolio import FillRow, build_position, cash_balance, daily_pnl, day_figures

T0 = datetime(2026, 10, 1, tzinfo=timezone.utc)


def fill(id, side, qty, price, fee, minutes=0):
    return FillRow(id, id, side, D(qty), D(price), D(fee), T0 + timedelta(minutes=minutes))


def test_buy_then_partial_sell():
    # buy 1 BTC at $100 + $0.25 fee -> it cost $100.25
    # sell 0.5 BTC at $120 - $0.15 fee -> received $59.85 for half of it, which cost $50.125
    pos = build_position([fill(1, "buy", "1", "100", "0.25"), fill(2, "sell", "0.5", "120", "0.15", 1)])
    assert pos.qty == D("0.5")
    assert pos.cost_basis == D("50.125")
    assert pos.realized == D("9.725")                         # 59.85 - 50.125
    assert pos.avg_price == D("100.25")                       # per BTC, fee included
    assert pos.unrealized(D("110")) == D("4.875")             # 0.5 × 110 - 50.125
    assert pos.total_pnl(D("110")) == D("14.600")
    assert pos.fees == D("0.40")
    buy = pos.fills[1]
    assert (buy.remaining, buy.realized) == (D("0.5"), D("9.725"))   # half of this buy sold, at a profit


def test_sells_use_up_the_oldest_buy_first():
    pos = build_position([
        fill(1, "buy", "1", "100", "0"),
        fill(2, "buy", "1", "200", "0", 1),
        fill(3, "sell", "1.5", "150", "0", 2),                # all of buy 1, then half of buy 2
    ])
    assert pos.fills[1].remaining == D("0")
    assert pos.fills[2].remaining == D("0.5")
    assert pos.fills[3].realized == D("25")                   # (150-100)×1 + (150-200)×0.5 = 50 - 25
    assert pos.cost_basis == D("100")                         # half of the $200 buy is left
    assert pos.qty == D("0.5")


def test_cash_follows_buys_sells_and_fees():
    fills = [fill(1, "buy", "1", "100", "0.25"), fill(2, "sell", "0.5", "120", "0.15", 1)]
    assert cash_balance(D("1000"), D("0"), fills) == D("959.60")   # 1000 - 100.25 + 59.85


def test_daily_pnl():
    # held 1 BTC since yesterday (bought at 90); price was 100 at midnight and is 110 now; bought 1 more at 105 today
    day_start = T0 + timedelta(days=1)
    fills = [fill(1, "buy", "1", "90", "0"), fill(2, "buy", "1", "105", "0", 24 * 60 + 30)]
    qty_start, net_flow, bought = day_figures(fills, day_start)
    assert (qty_start, net_flow, bought) == (D("1"), D("105"), D("105"))
    # value now 2 × 110 = 220; value at midnight 100; put in 105 today -> 220 - 100 - 105 = 15
    assert daily_pnl(D("2"), D("110"), qty_start, D("100"), net_flow) == D("15")   # +10 on the old coin, +5 on the new
