"""Step 1d: 환율/유가/KOSPI 시장 데이터 수집 (yfinance)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import yfinance as yf
from tenacity import retry, stop_after_attempt, wait_exponential

from config.constants import (
    MARKET_SYMBOLS,
    RETRY_ATTEMPTS,
    RETRY_MAX_WAIT_SECONDS,
    RETRY_WAIT_SECONDS,
)
from models import MarketSnapshot

logger = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=RETRY_WAIT_SECONDS, max=RETRY_MAX_WAIT_SECONDS),
    reraise=True,
)
def _fetch_ticker(symbol: str) -> yf.Ticker:
    return yf.Ticker(symbol)


def fetch_market_data() -> list[MarketSnapshot]:
    """모든 시장 지표를 수집하여 MarketSnapshot 리스트로 반환."""
    snapshots: list[MarketSnapshot] = []
    end = datetime.now()
    start = end - timedelta(days=5)  # 주말/공휴일 대비 여유

    for name, symbol in MARKET_SYMBOLS.items():
        try:
            ticker = _fetch_ticker(symbol)
            hist = ticker.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))

            if hist.empty:
                logger.warning("시장 데이터 없음: %s (%s)", name, symbol)
                continue

            latest_close = hist["Close"].iloc[-1]

            if len(hist) >= 2:
                prev_close = hist["Close"].iloc[-2]
                change_pct = ((latest_close - prev_close) / prev_close) * 100
            else:
                change_pct = 0.0

            snapshots.append(
                MarketSnapshot(
                    symbol=symbol,
                    name=name,
                    price=round(float(latest_close), 2),
                    change_pct=round(change_pct, 2),
                )
            )
            logger.info("수집 완료: %s = %.2f (%.2f%%)", name, latest_close, change_pct)

        except Exception:
            logger.exception("시장 데이터 수집 실패: %s (%s)", name, symbol)

    return snapshots


def format_market_summary(snapshots: list[MarketSnapshot]) -> str:
    """시장 데이터를 텍스트 요약으로 변환."""
    if not snapshots:
        return "시장 데이터를 가져올 수 없습니다."
    return "\n".join(s.summary_line() for s in snapshots)
