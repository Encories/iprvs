# Bybit Dual-Market Trading Bot

Python bot that monitors Bybit spot prices via WebSocket and futures Open Interest via HTTP, generates signals (+5% price and +5% OI over 5 minutes), and executes spot trades with a +2% take-profit.

## Setup

1. Create and activate a virtual environment (recommended).
2. Install dependencies:

```bash
pip install -r bybit_trading_bot/requirements.txt
```

3. Create `.env` in project root or set env vars:

```
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_api_secret_here
BYBIT_TESTNET=True
MAX_POSITION_SIZE_PERCENT=1.0
MAX_SIMULTANEOUS_POSITIONS=5
PRICE_CHANGE_THRESHOLD=5.0
OI_CHANGE_THRESHOLD=5.0
TAKE_PROFIT_PERCENT=2.0
MONITORING_INTERVAL=60
ACCOUNT_EQUITY_USDT=10000
# Prefer fixed notional per trade. If > 0, overrides percent sizing
TRADE_NOTIONAL_USDT=50
```

Sizing: if `TRADE_NOTIONAL_USDT > 0`, qty = TRADE_NOTIONAL_USDT / last_price. Otherwise qty = (ACCOUNT_EQUITY_USDT * MAX_POSITION_SIZE_PERCENT/100) / last_price.

## Run

```bash
python -m bybit_trading_bot.main
```

The current version includes real-time storage, signal checks, order placement (testnet-ready), and TP monitoring with simple protections. 