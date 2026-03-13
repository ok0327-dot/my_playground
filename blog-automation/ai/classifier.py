"""Step 2: AI 기반 토픽 분류 (피벗 가능성 평가)."""

from __future__ import annotations

import json
import logging
import re

from config.prompts import CLASSIFIER_SYSTEM, CLASSIFIER_USER
from models import Topic, TopicLabel

from .providers import call_ai

logger = logging.getLogger(__name__)


def _parse_response(raw: str) -> list[dict]:
    """AI 응답에서 JSON 배열을 추출."""
    text = raw.strip()

    # 코드 블록 감싸기 제거
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    # JSON 배열 부분만 추출
    bracket_match = re.search(r"\[.*\]", text, re.DOTALL)
    if bracket_match:
        text = bracket_match.group(0)

    return json.loads(text)


def classify_topics(
    keywords: list[str],
    market_summary: str,
    gemini_api_key: str = "",
    groq_api_key: str = "",
    ai_provider: str = "gemini",
    recent_topics: list[str] | None = None,
) -> list[Topic]:
    """키워드 목록을 피벗 가능성 기준으로 분류하여 Topic 리스트로 반환."""
    if not keywords:
        return []

    topics_json = json.dumps(keywords, ensure_ascii=False)
    recent_str = "없음 (첫 실행)"
    if recent_topics:
        recent_str = "\n".join(f"- {t}" for t in recent_topics)
    user_prompt = CLASSIFIER_USER.format(
        topics_json=topics_json,
        market_summary=market_summary,
        recent_topics=recent_str,
    )

    try:
        raw = call_ai(
            system_prompt=CLASSIFIER_SYSTEM,
            user_prompt=user_prompt,
            gemini_api_key=gemini_api_key,
            groq_api_key=groq_api_key,
            ai_provider=ai_provider,
            temperature=0.2,
        )
        parsed = _parse_response(raw)

        topics: list[Topic] = []
        for item in parsed:
            try:
                label = TopicLabel(item["label"])
            except (KeyError, ValueError):
                label = TopicLabel.SKIP
            score = item.get("score", 5)
            if not isinstance(score, int):
                try:
                    score = int(score)
                except (TypeError, ValueError):
                    score = 5
            score = max(1, min(10, score))
            topics.append(
                Topic(
                    keyword=item.get("topic", ""),
                    label=label,
                    reason=item.get("reason", ""),
                    score=score,
                    pivot_angle=item.get("pivot_angle", ""),
                )
            )
        logger.info(
            "AI 분류 완료: PRIORITY=%d, ADOPT=%d, SKIP=%d",
            sum(1 for t in topics if t.label == TopicLabel.PRIORITY),
            sum(1 for t in topics if t.label == TopicLabel.ADOPT),
            sum(1 for t in topics if t.label == TopicLabel.SKIP),
        )
        return topics

    except Exception:
        logger.exception("AI 분류 실패 — 모든 토픽을 ADOPT로 처리")
        return [
            Topic(keyword=kw, label=TopicLabel.ADOPT, reason="AI 분류 실패 — 기본 채택", score=5)
            for kw in keywords
        ]
