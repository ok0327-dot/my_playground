"""Step 4 (선택): 쿠팡 파트너스 링크 생성."""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from datetime import datetime, timezone

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from config.constants import RETRY_ATTEMPTS, RETRY_MAX_WAIT_SECONDS, RETRY_WAIT_SECONDS

logger = logging.getLogger(__name__)

COUPANG_API_URL = "https://api-gateway.coupang.com/v2/providers/affiliate_open_api/apis/openapi/deeplink"


def _generate_hmac(method: str, url_path: str, secret_key: str, access_key: str) -> str:
    """쿠팡 파트너스 API HMAC 서명 생성."""
    dt = datetime.now(tz=timezone.utc).strftime("%y%m%dT%H%M%SZ")
    message = f"{dt}{method}{url_path}"
    signature = hmac.new(
        secret_key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"CEA algorithm=HmacSHA256, access-key={access_key}, signed-date={dt}, signature={signature}"


@retry(
    stop=stop_after_attempt(RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=RETRY_WAIT_SECONDS, max=RETRY_MAX_WAIT_SECONDS),
    reraise=True,
)
def _create_deeplink(product_url: str, access_key: str, secret_key: str) -> str | None:
    """쿠팡 상품 URL을 파트너스 딥링크로 변환."""
    url_path = "/v2/providers/affiliate_open_api/apis/openapi/deeplink"
    authorization = _generate_hmac("POST", url_path, secret_key, access_key)

    headers = {
        "Authorization": authorization,
        "Content-Type": "application/json",
    }
    payload = {
        "coupangUrls": [product_url],
    }

    resp = requests.post(COUPANG_API_URL, headers=headers, json=payload, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    if data.get("rCode") == "0" and data.get("data"):
        return data["data"][0].get("shortenUrl")
    return None


def generate_coupang_links(
    keywords: list[str],
    access_key: str,
    secret_key: str,
) -> list[str]:
    """키워드 기반 쿠팡 파트너스 링크 생성. 실패 시 빈 리스트 반환."""
    if not access_key or not secret_key:
        logger.info("쿠팡 파트너스 키 미설정 — 링크 생성 건너뜀")
        return []

    links: list[str] = []
    for keyword in keywords[:3]:  # 최대 3개
        try:
            search_url = f"https://www.coupang.com/np/search?q={keyword}"
            deeplink = _create_deeplink(search_url, access_key, secret_key)
            if deeplink:
                links.append(deeplink)
                logger.info("쿠팡 링크 생성: %s → %s", keyword, deeplink)
        except Exception:
            logger.exception("쿠팡 링크 생성 실패: '%s'", keyword)

    return links
