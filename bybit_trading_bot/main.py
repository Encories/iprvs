from __future__ import annotations

import signal
import sys
import time

from bybit_trading_bot.config.settings import load_settings
from bybit_trading_bot.core.market_monitor import MarketMonitor
from bybit_trading_bot.utils.logger import get_logger


logger = get_logger(__name__)


def main() -> None:
    config = load_settings()
    monitor = MarketMonitor(config)

    def _shutdown(signum: int, frame) -> None:  # type: ignore[override]
        logger.info("Received shutdown signal. Stopping monitor...")
        monitor.stop_monitoring()
        sys.exit(0)

    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    monitor.start_monitoring()

    # Keep the main thread alive while background threads run
    try:
        while monitor.is_running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        _shutdown(signal.SIGINT, None)


if __name__ == "__main__":
    main() 