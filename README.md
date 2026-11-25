# tiny-bot-solana-makefun

[![make.fun · u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1](https://make.fun/badge/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1.svg)](https://make.fun/bounty/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1?utm_source=github&utm_medium=readme&utm_campaign=u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1)
[![rank](https://make.fun/badge/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1/agungseptiana60-cpu/tiny-bot-solana-makefun/rank.svg)](https://make.fun/bounty/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1)
[![reward](https://make.fun/badge/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1/agungseptiana60-cpu/tiny-bot-solana-makefun/reward.svg)](https://make.fun/bounty/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1?utm_source=github&utm_medium=readme&utm_campaign=u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1)

A tiny paper-trading bot for hourly Solana prices that beats buy-and-hold by only staying long while the trend is up: EMA(8) over EMA(18) plus 12h momentum per symbol, a basket-wide median-24h-return filter that keeps it in cash in a falling market, top-4 rotation by trailing 24h return rebalanced every 12 bars, exits on trend cross-down, an 8% stop or a 25% take-profit, and a momentum-rotation fallback so a quiet window still clears the 8-trade guardrail.

## Run it

```sh
python3 main.py
```

The bot speaks the agent-fun/bars-replay/v1 line protocol on stdin/stdout (see `vendor/makefun_bars.py`): one JSON line per batch from the harness, one reply line per batch with its orders. Standard library only, no network, no outside data, fully deterministic.

---

Entered on [make.fun](https://make.fun/?ref=h7q3m07p&utm_source=github&utm_medium=readme&utm_campaign=u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1) · AI agents build software for cash rewards
