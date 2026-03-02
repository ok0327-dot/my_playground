"""GIPHY GIF 검색 모듈 — 토픽 관련 움짤 자동 검색."""

from __future__ import annotations

import logging

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from config.constants import (
    GIPHY_API_URL,
    GIPHY_RATING,
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
def _search_gifs(query: str, api_key: str, limit: int = 10) -> dict:
    """GIPHY 검색 API 호출."""
    params = {
        "api_key": api_key,
        "q": query,
        "limit": limit,
        "rating": GIPHY_RATING,
        "lang": "en",
    }
    resp = requests.get(GIPHY_API_URL, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def search_gif(
    query: str,
    api_key: str,
    pick: int = 0,
    exclude_ids: set[str] | None = None,
) -> tuple[str, str, str]:
    """GIPHY에서 GIF를 검색하여 1개를 반환.

    Args:
        query: 영어 검색 키워드 (English search keyword)
        api_key: GIPHY API 키
        pick: 검색 결과 중 선택할 인덱스 (0부터 시작)
        exclude_ids: 제외할 GIF ID 집합 (중복 GIF 방지)

    Returns:
        (gif_url, gif_title, gif_id) 또는 실패 시 ("", "", "")
    """
    if not api_key:
        logger.debug("GIPHY API 키 미설정 — GIF 검색 건너뜀")
        return ("", "", "")

    try:
        data = _search_gifs(query, api_key)
        results = data.get("data", [])

        # 제외 목록 필터링 (이미 사용된 GIF 제거 — ID 기반)
        if exclude_ids:
            results = [r for r in results if r.get("id", "") not in exclude_ids]

        if not results:
            logger.info("GIPHY 검색 결과 없음 (제외 후): '%s'", query)
            return ("", "", "")

        gif = results[min(pick, len(results) - 1)]
        gif_id = gif["id"]
        # downsized 포맷 사용 (품질/파일크기 균형)
        gif_url = gif["images"]["downsized"]["url"]
        gif_title = gif.get("title", query)

        logger.info("GIPHY GIF 선택: '%s' — %s (id: %s)", query, gif_title, gif_id)
        return (gif_url, gif_title, gif_id)

    except Exception:
        logger.exception("GIPHY GIF 검색 실패: '%s'", query)
        return ("", "", "")
