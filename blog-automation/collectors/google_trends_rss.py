"""Google Trends RSS 수집 (pytrends보다 안정적인 대안)."""

from __future__ import annotations

import logging
from xml.etree import ElementTree

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from config.constants import (
    GOOGLE_TRENDS_RSS_URL,
    RETRY_ATTEMPTS,
    RETRY_MAX_WAIT_SECONDS,
    RETRY_WAIT_SECONDS,
    USER_AGENT,
)

logger = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=RETRY_WAIT_SECONDS, max=RETRY_MAX_WAIT_SECONDS),
    reraise=True,
)
def _fetch_rss() -> str:
    """Google Trends RSS 피드를 가져온다."""
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(GOOGLE_TRENDS_RSS_URL, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.text


def fetch_google_trends_rss() -> list[str]:
    """Google Trends RSS에서 한국 인기 검색어를 수집."""
    try:
        xml_text = _fetch_rss()
        root = ElementTree.fromstring(xml_text)

        keywords: list[str] = []

        # RSS 2.0 형식: channel > item > title
        for item in root.iter("item"):
            title_el = item.find("title")
            if title_el is not None and title_el.text:
                keywords.append(title_el.text.strip())

        # Atom 형식 폴백: entry > title
        if not keywords:
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
                title_el = entry.find("atom:title", ns) or entry.find("{http://www.w3.org/2005/Atom}title")
                if title_el is not None and title_el.text:
                    keywords.append(title_el.text.strip())

        # 중복 제거 (dedup — RSS에서 같은 키워드가 여러 시간대에 반복될 수 있음)
        unique = list(dict.fromkeys(keywords))
        logger.info("Google Trends RSS 수집: %d개 키워드 (원본 %d개)", len(unique), len(keywords))
        return unique[:20]

    except Exception:
        logger.exception("Google Trends RSS 수집 실패")
        return []
