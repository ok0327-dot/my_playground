"""Unsplash 이미지 검색 모듈 — 토픽 관련 무료 사진 자동 검색."""

from __future__ import annotations

import logging

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from config.constants import (
    RETRY_ATTEMPTS,
    RETRY_MAX_WAIT_SECONDS,
    RETRY_WAIT_SECONDS,
    UNSPLASH_API_URL,
)

logger = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=RETRY_WAIT_SECONDS, max=RETRY_MAX_WAIT_SECONDS),
    reraise=True,
)
def _search_photos(query: str, access_key: str) -> dict:
    """Unsplash 검색 API 호출."""
    headers = {"Authorization": f"Client-ID {access_key}"}
    params = {
        "query": query,
        "orientation": "landscape",
        "per_page": 10,
    }
    resp = requests.get(UNSPLASH_API_URL, headers=headers, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _trigger_download(download_url: str, access_key: str) -> None:
    """Unsplash 가이드라인 준수: 이미지 선택 시 download endpoint 호출 (Download tracking).

    Unsplash API 정책상, 사용자가 이미지를 선택(표시)할 때
    download_location URL로 GET 요청을 보내야 합니다.
    """
    try:
        headers = {"Authorization": f"Client-ID {access_key}"}
        requests.get(download_url, headers=headers, timeout=5)
    except Exception:
        logger.debug("Unsplash download tracking 실패 (비필수)", exc_info=True)


def search_image(
    query: str,
    access_key: str,
    pick: int = 0,
    exclude_ids: set[str] | None = None,
) -> tuple[str, str, str]:
    """Unsplash에서 이미지를 검색하여 1장을 반환.

    Args:
        query: 영어 검색 키워드 (English search keyword)
        access_key: Unsplash API 액세스 키
        pick: 검색 결과 중 선택할 인덱스 (0부터 시작)
        exclude_ids: 제외할 photo ID 집합 (중복 이미지 방지)

    Returns:
        (image_url, credit_text, photo_id) 또는 실패 시 ("", "", "")
    """
    if not access_key:
        logger.debug("Unsplash API 키 미설정 — 이미지 검색 건너뜀")
        return ("", "", "")

    try:
        data = _search_photos(query, access_key)
        results = data.get("results", [])

        # 제외 목록 필터링 (이미 사용된 사진 제거)
        if exclude_ids:
            results = [r for r in results if r["id"] not in exclude_ids]

        if not results:
            logger.info("Unsplash 검색 결과 없음: '%s'", query)
            return ("", "", "")

        photo = results[min(pick, len(results) - 1)]
        photo_id = photo["id"]
        # 적절한 해상도 사용 (regular ≈ 1080px 너비)
        image_url = photo["urls"]["regular"]
        photographer = photo["user"]["name"]
        credit_text = f"Photo by {photographer} on Unsplash"

        # Unsplash 가이드라인: download tracking 호출
        download_url = photo.get("links", {}).get("download_location", "")
        if download_url:
            _trigger_download(download_url, access_key)

        logger.info("Unsplash 이미지 선택: '%s' — %s", query, credit_text)
        return (image_url, credit_text, photo_id)

    except Exception:
        logger.exception("Unsplash 이미지 검색 실패: '%s'", query)
        return ("", "", "")
