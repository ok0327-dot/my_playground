"""signal.bz 실시간 검색어 수집 (v1.0 복원)."""

from __future__ import annotations

import logging

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from config.constants import (
    RETRY_ATTEMPTS,
    RETRY_MAX_WAIT_SECONDS,
    RETRY_WAIT_SECONDS,
    SIGNAL_BZ_URL,
    USER_AGENT,
)

logger = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=RETRY_WAIT_SECONDS, max=RETRY_MAX_WAIT_SECONDS),
    reraise=True,
)
def _fetch_signal_page() -> str:
    """signal.bz 페이지를 가져온다."""
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(SIGNAL_BZ_URL, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.text


def fetch_signal_keywords() -> list[str]:
    """signal.bz에서 실시간 인기 검색어를 수집."""
    try:
        html = _fetch_signal_page()
        soup = BeautifulSoup(html, "lxml")

        keywords: list[str] = []

        # signal.bz 검색어 셀렉터 (여러 패턴 시도)
        selectors = [
            "a.rank-text",
            ".rank-collection a",
            "div.rank-keyword a",
            "[class*='rank'] a",
        ]

        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                keywords = [
                    el.get_text(strip=True) for el in elements
                    if el.get_text(strip=True)
                ]
                break

        # 셀렉터가 모두 실패하면 텍스트 기반으로 추출 시도
        if not keywords:
            for tag in soup.find_all("a", href=True):
                text = tag.get_text(strip=True)
                if text and len(text) > 1 and len(text) < 30:
                    href = tag.get("href", "")
                    if "search" in href or "query" in href:
                        keywords.append(text)

        # 중복 제거 + 상위 20개
        seen: set[str] = set()
        unique: list[str] = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique.append(kw)

        logger.info("signal.bz 수집: %d개 키워드", len(unique))
        return unique[:20]

    except Exception:
        logger.exception("signal.bz 수집 실패")
        return []
