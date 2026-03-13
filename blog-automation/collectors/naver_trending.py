"""Step 1a: 네이버 급상승 검색어 — 모든 트렌딩 키워드 수집 (필터 없음)."""

from __future__ import annotations

import logging

import requests
from bs4 import BeautifulSoup

from config.constants import (
    NAVER_DATALAB_URLS,
    USER_AGENT,
)

logger = logging.getLogger(__name__)

# CSS 셀렉터 체인: 첫 번째 매칭되는 셀렉터 사용 (사이트 구조 변경 대비)
_SELECTOR_CHAIN = [
    ".keyword_rank .list_keyword_rank .item_keyword_rank .title",
    ".keyword_rank .item_keyword_rank a",
    "[class*='keyword'] [class*='item'] a",
    "[class*='keyword'] [class*='item'] .title",
    "[class*='rank'] .title",
    "[class*='rank'] a",
    "li[class*='item'] a",
    ".lst_relate a",           # 네이버 모바일 검색 관련 검색어
    ".related_srch a",         # 네이버 연관 검색어
]


def _fetch_datalab_page() -> str:
    """네이버 데이터랩/검색 페이지를 가져온다. 여러 URL을 순서대로 시도."""
    headers = {"User-Agent": USER_AGENT}

    for url in NAVER_DATALAB_URLS:
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            logger.debug("네이버 URL 성공: %s", url)
            return resp.text
        except Exception:
            logger.debug("네이버 URL 실패: %s — 다음 URL 시도", url)
            continue

    raise RuntimeError("모든 네이버 데이터랩 URL 접근 실패")


def fetch_naver_trending() -> list[str]:
    """네이버 급상승 검색어를 필터 없이 전부 반환."""
    try:
        html = _fetch_datalab_page()
        soup = BeautifulSoup(html, "lxml")

        keyword_elements = []

        # CSS 셀렉터 체인 순회: 첫 번째 성공하는 셀렉터 사용
        for selector in _SELECTOR_CHAIN:
            keyword_elements = soup.select(selector)
            if keyword_elements:
                logger.debug("CSS 셀렉터 매칭: '%s' (%d개)", selector, len(keyword_elements))
                break

        raw_keywords = [el.get_text(strip=True) for el in keyword_elements if el.get_text(strip=True)]

        # 공백 정규화 + 중복 제거 (whitespace normalization + dedup)
        seen: set[str] = set()
        all_keywords: list[str] = []
        for kw in raw_keywords:
            normalized = " ".join(kw.split())
            if normalized and normalized not in seen:
                seen.add(normalized)
                all_keywords.append(normalized)

        logger.info("네이버 급상승: %d개 (중복 제거 후)", len(all_keywords))
        return all_keywords

    except Exception:
        logger.exception("네이버 급상승 검색어 수집 실패")
        return []
