from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Literal

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    """Application configuration loaded from environment variables and defaults."""

    bybit_api_key: Optional[str]
    bybit_api_secret: Optional[str]
    bybit_testnet: bool

    max_position_size_percent: float
    max_simultaneous_positions: int
    price_change_threshold: float
    oi_change_threshold: float
    take_profit_percent: float
    monitoring_interval_seconds: int

    database_path: str
    account_equity_usdt: float
    trade_notional_usdt: float
    price_only_mode: bool
    price_only_breakout_threshold: float
    require_oi_for_signal: bool
    oi_negative_block_threshold: float
    signal_window_minutes: int
    min_unique_oi_bars: int
    emergency_stop: bool

    telegram_enabled: bool
    telegram_bot_token: Optional[str]
    telegram_chat_id: Optional[str]
    telegram_commands_enabled: bool
    telegram_allowed_user_id: Optional[str]

    stop_loss_percent: float
    trade_cooldown_minutes: int
    skip_below_min_notional: bool
    post_only_tp: bool
    place_exchange_sl: bool
    spot_market_unit: Literal["base", "quote"]
    switch_mode: str
    # Split (Spike Detector) params
    limit_order_offset: float
    target_profit_pct: float
    split_min_signal_strength: float
    cooldown_minutes_split: int
    order_timeout_seconds: int
    # Indicators params
    rsi_period: int
    rsi_oversold: float
    rsi_overbought: float
    macd_fast: int
    macd_slow: int
    macd_signal: int
    volume_spike_multiplier: float
    volume_lookback_periods: int
    orderbook_imbalance_threshold: float
    bid_ask_spread_threshold: float
    split_max_open_orders: int
    split_trading_pairs: Optional[str]
    # Fees
    fee_rate: float


def _get_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y"}


def load_settings() -> Config:
    """Load configuration from .env and environment variables."""
    load_dotenv()

    bybit_api_key = os.getenv("BYBIT_API_KEY")
    bybit_api_secret = os.getenv("BYBIT_API_SECRET")
    bybit_testnet = _get_bool(os.getenv("BYBIT_TESTNET"), True)

    max_position_size_percent = float(os.getenv("MAX_POSITION_SIZE_PERCENT", "1.0"))
    max_simultaneous_positions = int(os.getenv("MAX_SIMULTANEOUS_POSITIONS", "3"))
    price_change_threshold = float(os.getenv("PRICE_CHANGE_THRESHOLD", "2.5"))
    oi_change_threshold = float(os.getenv("OI_CHANGE_THRESHOLD", "1.5"))
    take_profit_percent = float(os.getenv("TAKE_PROFIT_PERCENT", "1.2"))
    monitoring_interval_seconds = int(os.getenv("MONITORING_INTERVAL", "60"))

    database_path = os.getenv(
        "DATABASE_PATH",
        os.path.join("bybit_trading_bot", "storage", "database.sqlite"),
    )

    account_equity_usdt = float(os.getenv("ACCOUNT_EQUITY_USDT", "10000"))
    trade_notional_usdt = float(os.getenv("TRADE_NOTIONAL_USDT", "0"))
    price_only_mode = _get_bool(os.getenv("PRICE_ONLY_MODE"), False)
    price_only_breakout_threshold = float(os.getenv("PRICE_ONLY_BREAKOUT_THRESHOLD", "4.0"))
    require_oi_for_signal = _get_bool(os.getenv("REQUIRE_OI_FOR_SIGNAL"), False)
    oi_negative_block_threshold = float(os.getenv("OI_NEGATIVE_BLOCK_THRESHOLD", "-2.0"))
    signal_window_minutes = int(os.getenv("SIGNAL_WINDOW_MINUTES", "5"))
    min_unique_oi_bars = int(os.getenv("MIN_UNIQUE_OI_BARS", "2"))
    emergency_stop = _get_bool(os.getenv("EMERGENCY_STOP"), False)

    telegram_enabled = _get_bool(os.getenv("TELEGRAM_ENABLED"), False)
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    telegram_commands_enabled = _get_bool(os.getenv("TELEGRAM_COMMANDS_ENABLED"), False)
    telegram_allowed_user_id = os.getenv("TELEGRAM_ALLOWED_USER_ID")

    stop_loss_percent = float(os.getenv("STOP_LOSS_PERCENT", "0"))
    trade_cooldown_minutes = int(os.getenv("TRADE_COOLDOWN_MINUTES", "2"))
    skip_below_min_notional = _get_bool(os.getenv("SKIP_BELOW_MIN_NOTIONAL"), False)
    post_only_tp = _get_bool(os.getenv("POST_ONLY_TP"), False)
    place_exchange_sl = _get_bool(os.getenv("PLACE_EXCHANGE_SL"), False)
    spot_market_unit: Literal["base", "quote"] = (os.getenv("SPOT_MARKET_UNIT", "base").strip().lower())  # type: ignore[assignment]
    switch_mode = os.getenv("SWITCH_MODE", "ordinary").strip().lower()
    limit_order_offset = float(os.getenv("LIMIT_ORDER_OFFSET", "0.0015"))
    target_profit_pct = float(os.getenv("TARGET_PROFIT_PCT", "0.01"))
    split_min_signal_strength = float(os.getenv("MIN_SIGNAL_STRENGTH", "0.7"))
    cooldown_minutes_split = int(os.getenv("COOLDOWN_MINUTES", "15"))
    order_timeout_seconds = int(os.getenv("ORDER_TIMEOUT_SECONDS", "300"))
    rsi_period = int(os.getenv("RSI_PERIOD", "14"))
    rsi_oversold = float(os.getenv("RSI_OVERSOLD", "30"))
    rsi_overbought = float(os.getenv("RSI_OVERBOUGHT", "70"))
    macd_fast = int(os.getenv("MACD_FAST", "12"))
    macd_slow = int(os.getenv("MACD_SLOW", "26"))
    macd_signal = int(os.getenv("MACD_SIGNAL", "9"))
    volume_spike_multiplier = float(os.getenv("VOLUME_SPIKE_MULTIPLIER", "2.5"))
    volume_lookback_periods = int(os.getenv("VOLUME_LOOKBACK_PERIODS", "20"))
    orderbook_imbalance_threshold = float(os.getenv("ORDERBOOK_IMBALANCE_THRESHOLD", "0.15"))
    bid_ask_spread_threshold = float(os.getenv("BID_ASK_SPREAD_THRESHOLD", "0.002"))
    split_max_open_orders = int(os.getenv("SPLIT_MAX_OPEN_ORDERS", "3"))
    split_trading_pairs = os.getenv("SPLIT_TRADING_PAIRS")
    fee_rate = float(os.getenv("FEE_RATE", "0.001"))

    return Config(
        bybit_api_key=bybit_api_key,
        bybit_api_secret=bybit_api_secret,
        bybit_testnet=bybit_testnet,
        max_position_size_percent=max_position_size_percent,
        max_simultaneous_positions=max_simultaneous_positions,
        price_change_threshold=price_change_threshold,
        oi_change_threshold=oi_change_threshold,
        take_profit_percent=take_profit_percent,
        monitoring_interval_seconds=monitoring_interval_seconds,
        database_path=database_path,
        account_equity_usdt=account_equity_usdt,
        trade_notional_usdt=trade_notional_usdt,
        price_only_mode=price_only_mode,
        price_only_breakout_threshold=price_only_breakout_threshold,
        require_oi_for_signal=require_oi_for_signal,
        oi_negative_block_threshold=oi_negative_block_threshold,
        signal_window_minutes=signal_window_minutes,
        min_unique_oi_bars=min_unique_oi_bars,
        emergency_stop=emergency_stop,
        telegram_enabled=telegram_enabled,
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
        telegram_commands_enabled=telegram_commands_enabled,
        telegram_allowed_user_id=telegram_allowed_user_id,
        stop_loss_percent=stop_loss_percent,
        trade_cooldown_minutes=trade_cooldown_minutes,
        skip_below_min_notional=skip_below_min_notional,
        post_only_tp=post_only_tp,
        place_exchange_sl=place_exchange_sl,
        spot_market_unit=spot_market_unit,  # type: ignore[arg-type]
        switch_mode=switch_mode,
        limit_order_offset=limit_order_offset,
        target_profit_pct=target_profit_pct,
        split_min_signal_strength=split_min_signal_strength,
        cooldown_minutes_split=cooldown_minutes_split,
        order_timeout_seconds=order_timeout_seconds,
        rsi_period=rsi_period,
        rsi_oversold=rsi_oversold,
        rsi_overbought=rsi_overbought,
        macd_fast=macd_fast,
        macd_slow=macd_slow,
        macd_signal=macd_signal,
        volume_spike_multiplier=volume_spike_multiplier,
        volume_lookback_periods=volume_lookback_periods,
        orderbook_imbalance_threshold=orderbook_imbalance_threshold,
        bid_ask_spread_threshold=bid_ask_spread_threshold,
        split_max_open_orders=split_max_open_orders,
        split_trading_pairs=split_trading_pairs,
        fee_rate=fee_rate,
    ) 