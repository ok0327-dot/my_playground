"""Step 1b: 네이버 경제 뉴스 인기 기사 수집 + 하위 카테고리 지원."""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from config.constants import (
    NAVER_NEWS_SUBCATEGORIES,
    NAVER_SEARCH_NEWS_URL,
    RETRY_ATTEMPTS,
    RETRY_MAX_WAIT_SECONDS,
    RETRY_WAIT_SECONDS,
)
from models import NewsItem

logger = logging.getLogger(__name__)

# HTML 태그 제거용 정규식 (모든 HTML 태그 대응)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _normalize_url(url: str) -> str:
    """URL에서 쿼리 파라미터와 프래그먼트를 제거하여 정규화.

    같은 기사가 다른 추적 파라미터(tracking parameter)로 중복 수집되는 것을 방지.
    예: article/001/123?from=search → article/001/123
    """
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def _normalize_title(title: str) -> str:
    """제목을 정규화하여 유사 중복(near-duplicate) 비교에 사용.

    공백 통일, 소문자 변환으로 같은 기사의 미세한 제목 차이를 잡아냄.
    """
    return " ".join(title.lower().split())


def _strip_html(text: str) -> str:
    """모든 HTML 태그를 제거하고 HTML 엔티티를 디코딩."""
    cleaned = _HTML_TAG_RE.sub("", text)
    # 흔한 HTML 엔티티 처리
    cleaned = cleaned.replace("&amp;", "&")
    cleaned = cleaned.replace("&lt;", "<")
    cleaned = cleaned.replace("&gt;", ">")
    cleaned = cleaned.replace("&quot;", '"')
    cleaned = cleaned.replace("&#39;", "'")
    return cleaned.strip()


@retry(
    stop=stop_after_attempt(RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=RETRY_WAIT_SECONDS, max=RETRY_MAX_WAIT_SECONDS),
    reraise=True,
)
def _search_naver_news(
    query: str,
    client_id: str,
    client_secret: str,
    display: int = 5,
    sort: str = "date",
) -> list[dict]:
    """네이버 검색 API로 뉴스 검색."""
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    params = {
        "query": query,
        "display": display,
        "sort": sort,
    }
    resp = requests.get(NAVER_SEARCH_NEWS_URL, headers=headers, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json().get("items", [])


def fetch_economy_news(
    client_id: str,
    client_secret: str,
    include_subcategories: bool = True,
) -> list[NewsItem]:
    """네이버 경제 뉴스 인기 기사를 수집. 하위 카테고리별 뉴스도 포함."""
    # 기본 검색 쿼리
    queries: list[tuple[str, str]] = [
        ("경제 주요 뉴스", ""),
        ("증시 오늘", ""),
        ("환율 전망", ""),
    ]

    # 하위 카테고리별 검색 추가
    if include_subcategories:
        for subcat_name in NAVER_NEWS_SUBCATEGORIES:
            queries.append((f"{subcat_name} 뉴스 오늘", subcat_name))

    seen_links: set[str] = set()     # URL 정규화 후 비교 (normalized URL dedup)
    seen_titles: set[str] = set()    # 제목 정규화 후 비교 (normalized title dedup)
    news_items: list[NewsItem] = []

    for query, subcategory in queries:
        try:
            items = _search_naver_news(query, client_id, client_secret)
            for item in items:
                link = item.get("link", "")

                # URL 정규화: 쿼리 파라미터 제거 후 비교
                norm_link = _normalize_url(link)
                if norm_link in seen_links:
                    continue

                # 정규식으로 모든 HTML 태그 제거 (기존 <b></b>만 제거하던 버그 수정)
                title = _strip_html(item.get("title", ""))
                desc = _strip_html(item.get("description", ""))

                # 제목 정규화 비교: 같은 기사가 다른 URL로 수집되는 것 방지
                norm_title = _normalize_title(title)
                if norm_title in seen_titles:
                    continue

                seen_links.add(norm_link)
                seen_titles.add(norm_title)

                news_items.append(
                    NewsItem(
                        title=title,
                        link=link,
                        source="naver_news",
                        description=desc,
                        pub_date=item.get("pubDate", ""),
                        subcategory=subcategory,
                    )
                )
            logger.info("네이버 뉴스 '%s' 검색: %d건", query, len(items))

        except Exception:
            logger.exception("네이버 뉴스 검색 실패: '%s'", query)

    return news_items
