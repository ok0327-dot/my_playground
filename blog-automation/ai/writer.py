"""Step 3: AI 기반 블로그 초안 생성 + SEO 메타데이터 파싱."""

from __future__ import annotations

import logging
import re
from datetime import datetime

from config.prompts import WRITER_SYSTEM, WRITER_USER
from models import BlogDraft, MarketSnapshot, NewsItem

from .providers import call_ai

logger = logging.getLogger(__name__)


# ── 후처리: 한자/외국어 제거 필터 ──
# CJK Unified Ideographs (한자), 히라가나, 가타카나 범위
_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\u3040-\u309f\u30a0-\u30ff]+")


def _sanitize_body(html: str) -> str:
    """본문에서 한자·일본어 등 금지 외국어 문자를 제거한다."""
    cleaned = _CJK_PATTERN.sub("", html)
    # 제거 후 빈 공백 정리 (연속 공백 → 단일 공백)
    cleaned = re.sub(r"  +", " ", cleaned)
    return cleaned


def _format_news_context(news_items: list[NewsItem]) -> str:
    if not news_items:
        return "관련 뉴스 기사 없음"
    lines = []
    for i, item in enumerate(news_items[:5], 1):
        lines.append(f"{i}. {item.title}")
        if item.description:
            lines.append(f"   {item.description[:200]}")
        lines.append(f"   출처: {item.link}")
    return "\n".join(lines)


def _format_market_data(snapshots: list[MarketSnapshot]) -> str:
    if not snapshots:
        return "시장 데이터 없음"
    return "\n".join(s.summary_line() for s in snapshots)


def _strip_code_blocks(text: str) -> str:
    """AI가 HTML을 코드 블록(```)으로 감싼 경우 제거."""
    return re.sub(r"```(?:html)?\s*\n?(.*?)\n?\s*```", r"\1", text, flags=re.DOTALL)


def _parse_draft(raw: str, topic: str) -> dict:
    """응답에서 제목, 본문, SEO 메타데이터를 분리."""
    raw = _strip_code_blocks(raw)
    title = topic
    body = raw
    tags: list[str] = []
    meta_description = ""
    estimated_reading_time = ""

    lines = raw.strip().split("\n")
    body_start = 0

    for i, line in enumerate(lines):
        stripped = line.strip()

        if stripped.startswith("제목:") or stripped.startswith("제목 :"):
            title = stripped.split(":", 1)[1].strip()
            body_start = i + 1

        elif stripped.startswith("태그:") or stripped.startswith("태그 :"):
            tag_text = stripped.split(":", 1)[1].strip()
            tags = [t.strip() for t in tag_text.split(",") if t.strip()]
            body_start = i + 1

        elif stripped.startswith("메타설명:") or stripped.startswith("메타설명 :"):
            meta_description = stripped.split(":", 1)[1].strip()
            body_start = i + 1

        elif stripped.startswith("예상 읽기시간:") or stripped.startswith("예상 읽기시간 :"):
            estimated_reading_time = stripped.split(":", 1)[1].strip()
            body_start = i + 1

        elif stripped.startswith("본문:") or stripped.startswith("본문 :"):
            body = "\n".join(lines[i + 1:]).strip()
            break
    else:
        body = "\n".join(lines[body_start:]).strip()

    return {
        "title": title,
        "body": body,
        "tags": tags,
        "meta_description": meta_description,
        "estimated_reading_time": estimated_reading_time,
    }


def _generate_placeholder_draft(topic: str, reason: str) -> BlogDraft:
    """AI 실패 시 플레이스홀더 초안을 생성."""
    body = (
        f"<h3>{topic}</h3>\n"
        f"<p><b>분류 사유:</b> {reason}</p>\n"
        "<p>[AI 초안 생성 실패 — 수동 작성 필요]</p>\n"
        "<p>이 글은 자동 생성에 실패하여 플레이스홀더로 대체되었습니다. "
        "관련 뉴스와 시장 데이터를 참고하여 직접 작성해주세요.</p>"
    )
    return BlogDraft(
        topic=topic,
        title=f"[작성 필요] {topic}",
        body_html=body,
        status="placeholder",
        tags=[topic],
        meta_description=f"{topic} 관련 경제 블로그 글",
        estimated_reading_time="3분",
    )


def generate_draft(
    topic: str,
    reason: str,
    news_items: list[NewsItem],
    market_snapshots: list[MarketSnapshot],
    gemini_api_key: str = "",
    groq_api_key: str = "",
    ai_provider: str = "gemini",
) -> BlogDraft:
    """주어진 토픽에 대한 블로그 초안을 생성. 실패 시 플레이스홀더 반환."""
    today_date = datetime.now().strftime("%Y년 %m월 %d일")
    user_prompt = WRITER_USER.format(
        topic=topic,
        reason=reason,
        today_date=today_date,
        news_context=_format_news_context(news_items),
        market_data=_format_market_data(market_snapshots),
    )

    try:
        raw = call_ai(
            system_prompt=WRITER_SYSTEM,
            user_prompt=user_prompt,
            gemini_api_key=gemini_api_key,
            groq_api_key=groq_api_key,
            ai_provider=ai_provider,
            temperature=0.7,
        )
        parsed = _parse_draft(raw, topic)

        draft = BlogDraft(
            topic=topic,
            title=_sanitize_body(parsed["title"]),
            body_html=_sanitize_body(parsed["body"]),
            market_data=market_snapshots,
            tags=parsed["tags"],
            meta_description=parsed["meta_description"],
            estimated_reading_time=parsed["estimated_reading_time"],
        )
        logger.info("블로그 초안 생성 완료: '%s'", draft.title)
        return draft

    except Exception:
        logger.exception("블로그 초안 생성 실패: '%s' — 플레이스홀더 생성", topic)
        return _generate_placeholder_draft(topic, reason)
