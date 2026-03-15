"""Giphy API로 주제 관련 재미있는 GIF를 검색."""

from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

GIPHY_SEARCH_URL = "https://api.giphy.com/v1/gifs/search"


def search_giphy(keyword: str, api_key: str, limit: int = 3) -> list[dict]:
    """주제 키워드로 Giphy GIF를 검색하여 상위 결과를 반환."""
    if not api_key:
        logger.warning("GIPHY_API_KEY가 설정되지 않음")
        return []

    try:
        resp = requests.get(
            GIPHY_SEARCH_URL,
            params={
                "api_key": api_key,
                "q": keyword,
                "limit": limit,
                "rating": "g",
                "lang": "ko",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for gif in data.get("data", []):
            results.append({
                "url": gif["images"]["fixed_height"]["url"],
                "width": gif["images"]["fixed_height"]["width"],
                "height": gif["images"]["fixed_height"]["height"],
                "title": gif.get("title", ""),
            })

        logger.info("Giphy 검색 '%s': %d개 결과", keyword, len(results))
        return results

    except Exception:
        logger.exception("Giphy 검색 실패: '%s'", keyword)
        return []
