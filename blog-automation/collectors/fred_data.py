"""FRED API 미국 경제지표 수집 (v1.0 복원)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from config.constants import (
    FRED_API_URL,
    FRED_SERIES,
    RETRY_ATTEMPTS,
    RETRY_MAX_WAIT_SECONDS,
    RETRY_WAIT_SECONDS,
)

logger = logging.getLogger(__name__)


@dataclass
class FredObservation:
    """FRED 경제지표 관측값."""
    series_id: str
    series_name: str
    date: str
    value: float


@retry(
    stop=stop_after_attempt(RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=RETRY_WAIT_SECONDS, max=RETRY_MAX_WAIT_SECONDS),
    reraise=True,
)
def _fetch_series(series_id: str, api_key: str) -> dict:
    """FRED API에서 최신 관측값 1건을 가져온다."""
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 1,
    }
    resp = requests.get(FRED_API_URL, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def fetch_fred_data(api_key: str) -> list[FredObservation]:
    """FRED에서 주요 미국 경제지표를 수집."""
    if not api_key:
        logger.info("FRED API 키 미설정 — 수집 건너뜀")
        return []

    observations: list[FredObservation] = []

    for name, series_id in FRED_SERIES.items():
        try:
            data = _fetch_series(series_id, api_key)
            obs_list = data.get("observations", [])
            if obs_list:
                obs = obs_list[0]
                value_str = obs.get("value", ".")
                if value_str == ".":
                    logger.warning("FRED %s (%s): 값 없음 (미발표)", name, series_id)
                    continue
                observations.append(
                    FredObservation(
                        series_id=series_id,
                        series_name=name,
                        date=obs.get("date", ""),
                        value=float(value_str),
                    )
                )
                logger.info("FRED 수집: %s = %.2f (%s)", name, float(value_str), obs.get("date", ""))
        except Exception:
            logger.exception("FRED 수집 실패: %s (%s)", name, series_id)

    return observations


def format_fred_summary(observations: list[FredObservation]) -> str:
    """FRED 데이터를 텍스트 요약으로 변환."""
    if not observations:
        return ""
    lines = ["[미국 경제지표 (FRED)]"]
    for obs in observations:
        lines.append(f"  {obs.series_name}: {obs.value:.2f} ({obs.date})")
    return "\n".join(lines)
