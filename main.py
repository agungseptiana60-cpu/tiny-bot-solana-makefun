"""Tiny trend-rotation bot for hourly Solana bars (agent-fun/bars-replay/v1).

Idea, in one paragraph: buy-and-hold loses whenever the whole Solana basket
drifts down, so this bot only stays long while the trend is actually up. Each
symbol is judged on its own EMA(8) vs EMA(8/18) trend plus its 12h momentum,
and the whole basket is judged by the median 24h return: when the median is
negative the bot sits in cash instead of catching falling knives. It holds at
most the top 4 symbols by trailing 24h return (25% of equity each, the weight
cap), rebalances every 12 bars, exits on a trend cross-down, on an 8% stop or
on a 25% take-profit, and — so a quiet window still clears the 8-trade
guardrail — falls back to plain top-4 momentum rotation when fewer than 6
orders have gone out by bar 24. Everything is deterministic: closes and EMAs
in float64, no clock, no randomness, no network, no outside data.

Run locally with the kit grader:
    node cli/makefun.mjs grade-local --kit <kit> --bot <this repo> --driver process
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

FAST_BARS = 8
SLOW_BARS = 18
TOP_N = 4
REBALANCE_BARS = 12
LOOKBACK_BARS = 24
MOM_MIN = 0.02          # 12h return needed to enter (2%)
MOM6_MIN = 0.0          # 6h return needed to enter
MED_MIN = 0.0           # median 24h return of the basket needed to enter
STOP_RATIO = 0.92       # exit when a position is worth 92% of its cost
TP_RATIO = 1.25         # exit when a position is worth 125% of its cost
FALLBACK_SEQ = 24       # if fewer than FALLBACK_TRADES orders by this bar, rotate
FALLBACK_TRADES = 6
MAX_SLIPPAGE_BPS = 100  # 1% past the close the order was decided on

# Per-symbol state, built from the closes in every batch the harness sends.
closes = {}
fast_ema = {}   # symbol -> {"warm": [...], "value": float | None}
slow_ema = {}
prev_gap = {}   # symbol -> fast - slow after the previous batch, or None
orders_sent = 0
next_rebalance = None


def _ema_step(slot, close, span):
    if slot["value"] is not None:
        slot["value"] += (2.0 / (span + 1)) * (close - slot["value"])
        return slot["value"]
    slot["warm"].append(close)
    if len(slot["warm"]) == span:
        slot["value"] = sum(slot["warm"]) / span
    return slot["value"]


def _return(sym, bars_back):
    hist = closes.get(sym)
    if hist is None or len(hist) <= bars_back:
        return None
    return hist[-1] / hist[-1 - bars_back] - 1.0


def _gap(sym):
    fast = fast_ema[sym]["value"]
    slow = slow_ema[sym]["value"]
    if fast is None or slow is None:
        return None
    return fast - slow


def on_batch(state, batch):
    global next_rebalance, orders_sent

    # Fold this batch's bars into the per-symbol close history and EMAs.
    # Warm-up batches count too: their orders would be rejected, but their
    # closes seed the indicators for the first tradable bar.
    for bar in batch["bars"]:
        sym = bar["symbol"]
        close = int(bar["c"])
        closes.setdefault(sym, []).append(close)
        _ema_step(fast_ema.setdefault(sym, {"warm": [], "value": None}), close, FAST_BARS)
        _ema_step(slow_ema.setdefault(sym, {"warm": [], "value": None}), close, SLOW_BARS)

    if state.warming_up:
        return []

    symbols = [s["symbol"] for s in state.hello["symbols"]]
    caps = state.hello["caps"]
    min_notional = int(state.hello["fees"]["min_notional_quote_units"])

    # Basket regime: the median trailing-24h return across the universe.
    rets24 = [r for r in (_return(s, LOOKBACK_BARS) for s in symbols) if r is not None]
    median24 = sorted(rets24)[len(rets24) // 2] if rets24 else 0.0

    # Quiet-window fallback: rotate by momentum alone so the entry still
    # clears the minimum-trade guardrail instead of sitting idle.
    fallback = state.seq >= FALLBACK_SEQ and orders_sent < FALLBACK_TRADES

    # --- exits: trend cross-down, stop-loss, take-profit -------------------
    # A position of zero quantity is not a holding (defensive: the harness
    # never sends one, but a dust remainder must not block re-entry).
    live = {s: h for s, h in state.positions.items() if h.qty > 0}
    sells = []
    for sym, held in live.items():
        gap = _gap(sym)
        pgap = prev_gap.get(sym)
        cross_down = gap is not None and pgap is not None and gap < 0 and pgap >= 0
        value = state.value(sym, held.qty)
        stop = value * 100 <= held.cost * 92
        take_profit = value * 100 >= held.cost * 125
        if cross_down or stop or take_profit:
            sells.append(sym)

    # --- rebalance: top TOP_N by trailing 24h return ----------------------
    target = None
    if next_rebalance is None:
        next_rebalance = state.seq + max(SLOW_BARS, LOOKBACK_BARS)
    if state.seq >= next_rebalance:
        ranked = []
        for sym in symbols:
            r24 = _return(sym, LOOKBACK_BARS)
            r12 = _return(sym, 12)
            if r24 is None or r12 is None or _gap(sym) is None:
                continue
            if fallback or (_gap(sym) > 0 and r12 > MOM_MIN and r24 > 0):
                ranked.append((r24, sym))
        ranked.sort(reverse=True)
        target = [sym for _, sym in ranked[:TOP_N]]
        next_rebalance = state.seq + REBALANCE_BARS
        for sym in list(live):
            if sym not in target and sym not in sells:
                sells.append(sym)

    orders = []
    for sym in sells:
        orders.append({
            "side": "sell", "symbol": sym, "qty": live[sym].qty,
            "max_slippage_bps": MAX_SLIPPAGE_BPS,
        })

    # --- entries ------------------------------------------------------------
    held_after = set(live) - set(sells)
    want = []
    if target is not None:
        want = [s for s in target if s not in held_after]
    else:
        cands = []
        for sym in symbols:
            if sym in held_after:
                continue
            r12 = _return(sym, 12)
            r6 = _return(sym, 6)
            gap = _gap(sym)
            if gap is None or r12 is None or r6 is None:
                continue
            if gap > 0 and r12 > MOM_MIN and r6 > MOM6_MIN:
                cands.append((_return(sym, LOOKBACK_BARS) or 0.0, sym))
        cands.sort(reverse=True)
        want = [s for _, s in cands[: max(0, TOP_N - len(held_after))]]

    if want and (fallback or median24 >= MED_MIN):
        stake = min(state.equity // TOP_N, 2500 * state.equity // 10000)
        cash = state.cash
        for sym in want:
            if len(orders) >= caps["max_orders_per_bar"]:
                break
            amount = min(stake, cash)
            if amount < min_notional:
                break
            orders.append({
                "side": "buy", "symbol": sym, "notional_quote_units": amount,
                "max_slippage_bps": MAX_SLIPPAGE_BPS,
            })
            cash -= amount

    # Remember this batch's trend gaps for the next batch's cross detection.
    for sym in symbols:
        prev_gap[sym] = _gap(sym)

    orders_sent += len(orders)
    return orders[: caps["max_orders_per_bar"]]


makefun_bars.run(on_batch)
