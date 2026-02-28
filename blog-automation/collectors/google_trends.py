"""Step 1c: 구글 트렌드 (한국) 실시간 인기 검색어 수집."""

from __future__ import annotations

import logging

from pytrends.request import TrendReq
from tenacity import retry, stop_after_attempt, wait_exponential

from config.constants import (
    GOOGLE_TRENDS_GEO,
    RETRY_ATTEMPTS,
    RETRY_MAX_WAIT_SECONDS,
    RETRY_WAIT_SECONDS,
)

logger = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=RETRY_WAIT_SECONDS, max=RETRY_MAX_WAIT_SECONDS),
    reraise=True,
)
def _get_trending_searches(geo: str) -> list[str]:
    """구글 트렌드에서 실시간 인기 검색어를 가져온다."""
    pytrends = TrendReq(hl="ko", tz=540)  # KST = UTC+9
    df = pytrends.trending_searches(pn=geo)
    return df[0].tolist() if not df.empty else []


def fetch_google_trends() -> list[str]:
    """구글 트렌드 한국 인기 검색어 목록 반환."""
    try:
        keywords = _get_trending_searches(GOOGLE_TRENDS_GEO)
        # 중복 제거 (dedup)
        unique = list(dict.fromkeys(keywords))
        logger.info("구글 트렌드 수집: %d개 키워드", len(unique))
        return unique[:20]  # 상위 20개
    except Exception:
        logger.exception("구글 트렌드 수집 실패")
        return []
