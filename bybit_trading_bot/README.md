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
FEE_RATE=0.001

# Split mode (probabilistic + ATR)
SWITCH_MODE=split
LIMIT_ORDER_OFFSET=0.0015
TARGET_PROFIT_PCT=0.022
ORDER_TIMEOUT_SECONDS=120
SPLIT_MAX_OPEN_ORDERS=2

# Dynamic offset
DYNAMIC_OFFSET_ENABLED=true
OFFSET_VOL_K=0.6
OFFSET_SPREAD_K=0.5

# ATR risk management
ATR_ENABLED=true
ATR_PERIOD=14
ATR_SL_MULTIPLIER=2.0
ATR_TRAIL_MULTIPLIER=2.5
DYNAMIC_SL_ENABLED=true
TP1_PERCENT=0.012
TP1_ATR_MULTIPLIER=1.5
BREAK_EVEN_ENABLED=true

# OBV/MTF filters
OBV_ENABLED=true
OBV_TREND_PERIODS=10
VOLUME_QUALITY_CHECK=true
REQUIRE_OBV_CONFIRMATION=true
MTF_ENABLED=true
MTF_REQUIRE_CONFIRMATION=true

# Gate
TP_PROB_THRESHOLD=0.72
TP_PROB_MIN_DELTA=0.05
```

Sizing: if `TRADE_NOTIONAL_USDT > 0`, qty = TRADE_NOTIONAL_USDT / last_price. Otherwise qty = (ACCOUNT_EQUITY_USDT * MAX_POSITION_SIZE_PERCENT/100) / last_price.

## Run

```bash
python -m bybit_trading_bot.main
```

The current version includes real-time storage, signal checks, order placement (testnet-ready), dynamic offset, ATR-based SL estimation, partial TP/BE management, OBV/MTF filters, and TP monitoring.

### Quickstart (Split / Testnet)

1) Ensure `.env` contains the split settings above and `BYBIT_TESTNET=True`.
2) Install deps: `pip install -r bybit_trading_bot/requirements.txt`
3) Run: `python -m bybit_trading_bot.main`
4) Observe logs: `SPLIT ORDER`, `ORDER FILLED`, `BE SL SET`. Tune `TP1_PERCENT`, `TARGET_PROFIT_PCT`, `LIMIT_ORDER_OFFSET`.