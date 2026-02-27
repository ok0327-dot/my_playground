"""환경변수 기반 설정 로더."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# 프로젝트 루트의 .env 파일 로드 (로컬 개발용)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


def _require(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise EnvironmentError(f"환경변수 '{name}'이 설정되지 않았습니다.")
    return val


@dataclass(frozen=True)
class Settings:
    # Gemini
    gemini_api_key: str = field(repr=False, default="")
    # Groq (폴백 AI / Fallback AI)
    groq_api_key: str = field(repr=False, default="")
    # AI 제공자 선택 ("gemini", "groq") / AI provider preference
    ai_provider: str = "gemini"
    # Naver
    naver_client_id: str = ""
    naver_client_secret: str = field(repr=False, default="")
    # Google Sheets
    google_sheets_credentials: dict = field(default_factory=dict, repr=False)
    google_sheet_id: str = ""
    # Coupang (선택)
    coupang_access_key: str = ""
    coupang_secret_key: str = field(repr=False, default="")
    # FRED API (선택 / Optional)
    fred_api_key: str = field(repr=False, default="")
    # 출력 설정 / Output settings
    output_dir: str = "outputs"
    save_local_markdown: bool = True
    # GitHub Pages HTML 뷰어 / GitHub Pages HTML viewer
    generate_html_viewer: bool = True
    # 수동 토픽 지정 (Manual topic override)
    manual_topics: tuple[str, ...] = ()
    # 옵션
    dry_run: bool = False
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> Settings:
        creds_raw = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "{}")
        try:
            creds = json.loads(creds_raw)
        except json.JSONDecodeError:
            creds = {}

        # gemini_api_key는 선택 (groq만 사용 가능)
        gemini_key = os.getenv("GEMINI_API_KEY", "")

        return cls(
            gemini_api_key=gemini_key,
            groq_api_key=os.getenv("GROQ_API_KEY", ""),
            ai_provider=os.getenv("AI_PROVIDER", "gemini").lower(),
            naver_client_id=_require("NAVER_CLIENT_ID"),
            naver_client_secret=_require("NAVER_CLIENT_SECRET"),
            google_sheets_credentials=creds,
            google_sheet_id=_require("GOOGLE_SHEET_ID"),
            coupang_access_key=os.getenv("COUPANG_ACCESS_KEY", ""),
            coupang_secret_key=os.getenv("COUPANG_SECRET_KEY", ""),
            fred_api_key=os.getenv("FRED_API_KEY", ""),
            output_dir=os.getenv("OUTPUT_DIR", "outputs"),
            save_local_markdown=os.getenv("SAVE_LOCAL_MARKDOWN", "true").lower() == "true",
            generate_html_viewer=os.getenv("GENERATE_HTML_VIEWER", "true").lower() == "true",
            manual_topics=tuple(
                t.strip() for t in os.getenv("MANUAL_TOPICS", "").split(",") if t.strip()
            ),
            dry_run=os.getenv("DRY_RUN", "false").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
