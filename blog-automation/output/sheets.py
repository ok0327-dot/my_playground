"""Step 4: Google Sheets 저장 — SEO 칼럼 추가."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials
from tenacity import retry, stop_after_attempt, wait_exponential

from config.constants import RETRY_ATTEMPTS, RETRY_MAX_WAIT_SECONDS, RETRY_WAIT_SECONDS
from models import BlogDraft

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# 시트 헤더 (첫 행) — SEO 칼럼 추가
HEADERS = [
    "날짜",
    "토픽",
    "제목",
    "본문 (HTML)",
    "시장 데이터",
    "상태",
    "태그",
    "메타 설명",
    "읽기 시간",
    "생성 시각",
]

FALLBACK_DIR = Path(__file__).resolve().parent.parent / "logs"


def _get_client(credentials_dict: dict) -> gspread.Client:
    creds = Credentials.from_service_account_info(credentials_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def _ensure_headers(worksheet: gspread.Worksheet) -> None:
    """첫 행에 헤더가 없으면 추가."""
    first_row = worksheet.row_values(1)
    if first_row != HEADERS:
        worksheet.update("A1", [HEADERS])
        logger.info("시트 헤더 추가 완료")


@retry(
    stop=stop_after_attempt(RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=RETRY_WAIT_SECONDS, max=RETRY_MAX_WAIT_SECONDS),
    reraise=True,
)
def _append_row(worksheet: gspread.Worksheet, row: list[str]) -> None:
    worksheet.append_row(row, value_input_option="USER_ENTERED")


def save_drafts(
    drafts: list[BlogDraft],
    credentials_dict: dict,
    sheet_id: str,
    run_date: str,
) -> bool:
    """블로그 초안을 Google Sheets에 저장. 성공 여부 반환."""
    if not drafts:
        logger.info("저장할 초안 없음")
        return True

    try:
        client = _get_client(credentials_dict)
        spreadsheet = client.open_by_key(sheet_id)

        # 워크시트: "Blog Drafts" 이름으로 찾거나 첫 번째 시트 사용
        try:
            worksheet = spreadsheet.worksheet("Blog Drafts")
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.sheet1
            worksheet.update_title("Blog Drafts")

        _ensure_headers(worksheet)

        for draft in drafts:
            market_str = " | ".join(
                s.summary_line() for s in draft.market_data
            )
            tags_str = ", ".join(draft.tags) if draft.tags else ""

            row = [
                run_date,
                draft.topic,
                draft.title,
                draft.body_html,
                market_str,
                draft.status,
                tags_str,
                draft.meta_description,
                draft.estimated_reading_time,
                draft.created_at,
            ]
            _append_row(worksheet, row)
            logger.info("시트 저장: '%s'", draft.title)

        return True

    except Exception:
        logger.exception("Google Sheets 저장 실패 — 로컬 백업으로 전환")
        _save_fallback(drafts, run_date)
        return False


def _save_fallback(drafts: list[BlogDraft], run_date: str) -> None:
    """Sheets 실패 시 로컬 JSON 파일로 백업."""
    FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
    path = FALLBACK_DIR / f"fallback_drafts_{run_date}.json"

    data = []
    for d in drafts:
        data.append({
            "topic": d.topic,
            "title": d.title,
            "body_html": d.body_html,
            "market_data": [s.summary_line() for s in d.market_data],
            "status": d.status,
            "tags": d.tags,
            "meta_description": d.meta_description,
            "estimated_reading_time": d.estimated_reading_time,
            "created_at": d.created_at,
        })

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("로컬 백업 저장: %s", path)
