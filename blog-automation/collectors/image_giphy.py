"""Giphy API로 주제 관련 재미있는 GIF를 검색."""

from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

GIPHY_SEARCH_URL = "https://api.giphy.com/v1/gifs/search"
GIPHY_TRENDING_URL = "https://api.giphy.com/v1/gifs/trending"

# 재미있고 긍정적인 GIF를 위한 검색어 접미사
_FUN_SUFFIXES = ["funny", "cute", "happy", "excited", "reaction"]


def search_giphy(keyword: str, api_key: str, limit: int = 3) -> list[dict]:
    """주제 키워드로 Giphy GIF를 검색. 재미있고 긍정적인 결과 우선."""
    if not api_key:
        logger.warning("GIPHY_API_KEY가 설정되지 않음")
        return []

    try:
        # 키워드 + "funny" 로 재미있는 GIF 우선 검색
        fun_query = f"{keyword} funny"
        resp = requests.get(
            GIPHY_SEARCH_URL,
            params={
                "api_key": api_key,
                "q": fun_query,
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

        # 재미있는 결과가 없으면 원본 키워드로 재검색
        if not results:
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
