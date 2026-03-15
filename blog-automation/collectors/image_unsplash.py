"""Unsplash API로 주제 관련 사진을 검색."""

from __future__ import annotations

import logging
import re

import requests

logger = logging.getLogger(__name__)

UNSPLASH_SEARCH_URL = "https://api.unsplash.com/search/photos"

# 한국어 키워드 → 영어 검색어 매핑 (자주 등장하는 주제)
_KO_TO_EN = {
    "유가": "oil price",
    "기름값": "gas station",
    "환율": "currency exchange",
    "금리": "interest rate bank",
    "주식": "stock market",
    "증시": "stock market",
    "비트코인": "bitcoin",
    "부동산": "real estate",
    "반도체": "semiconductor chip",
    "AI": "artificial intelligence",
    "인공지능": "artificial intelligence",
    "BTS": "BTS concert",
    "마라톤": "marathon running",
    "축구": "soccer football",
    "야구": "baseball",
    "태풍": "typhoon storm",
    "폭우": "heavy rain flood",
    "지진": "earthquake",
    "날씨": "weather sky",
    "물가": "grocery shopping",
    "인플레이션": "inflation price",
    "금값": "gold bars",
}


def _to_english_query(keyword: str) -> str:
    """한국어 키워드를 영어 검색어로 변환. 매핑에 없으면 원본 반환."""
    # 정확히 매핑에 있으면 사용
    for ko, en in _KO_TO_EN.items():
        if ko in keyword:
            return en
    # 영어가 이미 포함되어 있으면 영어 부분만 추출
    en_words = re.findall(r"[A-Za-z]+", keyword)
    if en_words:
        return " ".join(en_words)
    return keyword


def search_unsplash(
    keyword: str,
    access_key: str,
    limit: int = 1,
) -> list[dict]:
    """주제 키워드로 Unsplash 사진을 검색하여 상위 결과를 반환."""
    if not access_key:
        logger.warning("UNSPLASH_ACCESS_KEY가 설정되지 않음")
        return []

    # 영어 쿼리로 변환 (Unsplash는 영어 검색이 결과가 훨씬 많음)
    query = _to_english_query(keyword)

    try:
        resp = requests.get(
            UNSPLASH_SEARCH_URL,
            params={
                "query": query,
                "per_page": limit,
                "orientation": "landscape",
            },
            headers={"Authorization": f"Client-ID {access_key}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for photo in data.get("results", []):
            photographer = photo.get("user", {}).get("name", "Unknown")
            results.append({
                "url": photo["urls"]["regular"],
                "alt_text": photo.get("alt_description", keyword),
                "photographer": photographer,
                "link": photo["links"]["html"],
            })

        # 영어 변환 결과도 없으면 원본 키워드로 재시도
        if not results and query != keyword:
            logger.info("Unsplash 영어 검색 결과 없음, 원본 키워드로 재시도: '%s'", keyword)
            resp = requests.get(
                UNSPLASH_SEARCH_URL,
                params={
                    "query": keyword,
                    "per_page": limit,
                    "orientation": "landscape",
                },
                headers={"Authorization": f"Client-ID {access_key}"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            for photo in data.get("results", []):
                photographer = photo.get("user", {}).get("name", "Unknown")
                results.append({
                    "url": photo["urls"]["regular"],
                    "alt_text": photo.get("alt_description", keyword),
                    "photographer": photographer,
                    "link": photo["links"]["html"],
                })

        logger.info("Unsplash 검색 '%s' → '%s': %d개 결과", keyword, query, len(results))
        return results

    except Exception:
        logger.exception("Unsplash 검색 실패: '%s'", keyword)
        return []
