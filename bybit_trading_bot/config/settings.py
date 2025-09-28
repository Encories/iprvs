from __future__ import annotations

import os
from dataclasses import dataclass
import re
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
    safety50_enabled: bool
    stop_sl: bool

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
    enable_rsi_filter: bool
    trade_rsi_overbought: float
    macd_fast: int
    macd_slow: int
    macd_signal: int
    enable_macd_filter: bool
    trade_macd_require_above_signal: bool
    trade_macd_require_above_zero: bool
    trade_macd_min_bars: int
    volume_spike_multiplier: float
    volume_lookback_periods: int
    # RVOL filter
    enable_rvol_filter: bool
    rvol_period: int
    rvol_threshold: float
    rvol_breakout_min: float
    min_quote_volume_5m_usdt: float
    orderbook_imbalance_threshold: float
    bid_ask_spread_threshold: float
    split_max_open_orders: int
    split_trading_pairs: Optional[str]
    # Fees
    fee_rate: float
    drawdown_exit_threshold_pct: float
    # Panic sell on small drop
    panic_enabled: bool
    panic_sell_enabled: bool
    panic_sell_drop_pct: float
    # OCO orders
    oco_enabled: bool
    oco_profit_percentage: float
    oco_loss_percentage: float
    # Order cancellation control
    cancel_orders_enabled: bool
    # Software SL params
    software_sl_check_interval: float
    software_sl_price_cache_ttl: float
    software_sl_heartbeat_enabled: bool
    software_sl_heartbeat_interval: float
    software_sl_price_fail_threshold: int
    software_sl_activation_delay_seconds: float
    software_sl_hysteresis_pct: float
    software_sl_max_retries: int
    software_sl_retry_backoff_base: float


def _get_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y"}


def _get_int_env(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None:
        return default
    try:
        return int(v.strip())
    except Exception:
        m = re.search(r"-?\d+", v)
        return int(m.group(0)) if m else default


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
    safety50_enabled = _get_bool(os.getenv("SAFETY50"), True)
    stop_sl = _get_bool(os.getenv("STOP_SL"), False)

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
    enable_rsi_filter = _get_bool(os.getenv("ENABLE_RSI_FILTER"), True)
    trade_rsi_overbought = float(os.getenv("TRADE_RSI_OVERBOUGHT", "74"))
    macd_fast = _get_int_env("MACD_FAST", 12)
    macd_slow = _get_int_env("MACD_SLOW", 26)
    macd_signal = _get_int_env("MACD_SIGNAL", 9)
    enable_macd_filter = _get_bool(os.getenv("ENABLE_MACD_FILTER"), True)
    trade_macd_require_above_signal = _get_bool(os.getenv("TRADE_MACD_REQUIRE_ABOVE_SIGNAL"), True)
    trade_macd_require_above_zero = _get_bool(os.getenv("TRADE_MACD_REQUIRE_ABOVE_ZERO"), True)
    trade_macd_min_bars = int(os.getenv("TRADE_MACD_MIN_BARS", "2"))
    volume_spike_multiplier = float(os.getenv("VOLUME_SPIKE_MULTIPLIER", "2.5"))
    volume_lookback_periods = int(os.getenv("VOLUME_LOOKBACK_PERIODS", "20"))
    # RVOL filter
    enable_rvol_filter = _get_bool(os.getenv("ENABLE_RVOL_FILTER"), True)
    rvol_period = int(os.getenv("RVOL_PERIOD", "20"))
    rvol_threshold = float(os.getenv("RVOL_THRESHOLD", "1.8"))
    rvol_breakout_min = float(os.getenv("RVOL_BREAKOUT_MIN", "1.2"))
    min_quote_volume_5m_usdt = float(os.getenv("MIN_QUOTE_VOLUME_5M_USDT", "10000"))
    orderbook_imbalance_threshold = float(os.getenv("ORDERBOOK_IMBALANCE_THRESHOLD", "0.15"))
    bid_ask_spread_threshold = float(os.getenv("BID_ASK_SPREAD_THRESHOLD", "0.002"))
    split_max_open_orders = int(os.getenv("SPLIT_MAX_OPEN_ORDERS", "3"))
    split_trading_pairs = os.getenv("SPLIT_TRADING_PAIRS")
    fee_rate = float(os.getenv("FEE_RATE", "0.001"))
    drawdown_exit_threshold_pct = float(os.getenv("DRAWDOWN_EXIT_THRESHOLD_PCT", "10.0"))
    # Panic sell on small drop after entry
    panic_enabled = _get_bool(os.getenv("PANIC"), True)
    panic_sell_enabled = _get_bool(os.getenv("ENABLE_PANIC_SELL"), True)
    panic_sell_drop_pct = float(os.getenv("PANIC_SELL_DROP_PCT", "2.0"))
    # OCO orders
    oco_enabled = _get_bool(os.getenv("OCO_ENABLED"), False)
    oco_profit_percentage = float(os.getenv("OCO_PROFIT_PERCENTAGE", "2.0"))
    oco_loss_percentage = float(os.getenv("OCO_LOSS_PERCENTAGE", "2.0"))
    # Order cancellation control
    cancel_orders_enabled = _get_bool(os.getenv("CANCEL_ORDERS_ENABLED"), True)
    # Software SL
    software_sl_check_interval = float(os.getenv("SOFTWARE_SL_CHECK_INTERVAL", "1.0"))
    software_sl_price_cache_ttl = float(os.getenv("SOFTWARE_SL_PRICE_CACHE_TTL", "5.0"))
    software_sl_heartbeat_enabled = _get_bool(os.getenv("SOFTWARE_SL_HEARTBEAT_ENABLED"), True)
    software_sl_heartbeat_interval = float(os.getenv("SOFTWARE_SL_HEARTBEAT_INTERVAL", "60.0"))
    software_sl_price_fail_threshold = int(os.getenv("SOFTWARE_SL_PRICE_FAIL_THRESHOLD", "5"))
    # Delay activation after ORDER FILLED (minutes -> seconds)
    _sl_delay_min = float(os.getenv("SOFTWARE_SL_ACTIVATION_DELAY_MINUTES", "5.0"))
    software_sl_activation_delay_seconds = max(0.0, _sl_delay_min * 60.0)
    # Hysteresis and retries
    software_sl_hysteresis_pct = float(os.getenv("SOFTWARE_SL_HYSTERESIS_PCT", "0.05"))
    software_sl_max_retries = int(os.getenv("SOFTWARE_SL_MAX_RETRIES", "3"))
    software_sl_retry_backoff_base = float(os.getenv("SOFTWARE_SL_RETRY_BACKOFF_BASE", "0.5"))
    if drawdown_exit_threshold_pct <= 0 or drawdown_exit_threshold_pct > 50:
        try:
            print(f"WARNING: Invalid DRAWDOWN_EXIT_THRESHOLD_PCT={drawdown_exit_threshold_pct}, using 10.0%")
        except Exception:
            pass
        drawdown_exit_threshold_pct = 10.0

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
        safety50_enabled=safety50_enabled,
        stop_sl=stop_sl,
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
        enable_rsi_filter=enable_rsi_filter,
        trade_rsi_overbought=trade_rsi_overbought,
        macd_fast=macd_fast,
        macd_slow=macd_slow,
        macd_signal=macd_signal,
        enable_macd_filter=enable_macd_filter,
        trade_macd_require_above_signal=trade_macd_require_above_signal,
        trade_macd_require_above_zero=trade_macd_require_above_zero,
        trade_macd_min_bars=trade_macd_min_bars,
        volume_spike_multiplier=volume_spike_multiplier,
        volume_lookback_periods=volume_lookback_periods,
        enable_rvol_filter=enable_rvol_filter,
        rvol_period=rvol_period,
        rvol_threshold=rvol_threshold,
        rvol_breakout_min=rvol_breakout_min,
        min_quote_volume_5m_usdt=min_quote_volume_5m_usdt,
        orderbook_imbalance_threshold=orderbook_imbalance_threshold,
        bid_ask_spread_threshold=bid_ask_spread_threshold,
        split_max_open_orders=split_max_open_orders,
        split_trading_pairs=split_trading_pairs,
        fee_rate=fee_rate,
        drawdown_exit_threshold_pct=drawdown_exit_threshold_pct,
        panic_enabled=panic_enabled,
        panic_sell_enabled=panic_sell_enabled,
        panic_sell_drop_pct=panic_sell_drop_pct,
        oco_enabled=oco_enabled,
        oco_profit_percentage=oco_profit_percentage,
        oco_loss_percentage=oco_loss_percentage,
        cancel_orders_enabled=cancel_orders_enabled,
        software_sl_check_interval=software_sl_check_interval,
        software_sl_price_cache_ttl=software_sl_price_cache_ttl,
        software_sl_heartbeat_enabled=software_sl_heartbeat_enabled,
        software_sl_heartbeat_interval=software_sl_heartbeat_interval,
        software_sl_price_fail_threshold=software_sl_price_fail_threshold,
        software_sl_activation_delay_seconds=software_sl_activation_delay_seconds,
        software_sl_hysteresis_pct=software_sl_hysteresis_pct,
        software_sl_max_retries=software_sl_max_retries,
        software_sl_retry_backoff_base=software_sl_retry_backoff_base,
    ) 