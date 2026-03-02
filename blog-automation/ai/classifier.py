"""Step 2: AI 기반 토픽 분류 (SKIP / ADOPT / PRIORITY) + 규칙 기반 폴백."""

from __future__ import annotations

import json
import logging
import re

from config.constants import PRIORITY_KEYWORDS, SKIP_PATTERNS
from config.prompts import CLASSIFIER_SYSTEM, CLASSIFIER_USER
from models import Topic, TopicLabel

from .providers import call_ai

logger = logging.getLogger(__name__)


def _parse_response(raw: str) -> list[dict]:
    """AI 응답에서 JSON 배열을 추출."""
    text = raw.strip()

    # 코드 블록 감싸기 제거 (```json ... ``` 또는 ``` ... ```)
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    # JSON 배열 부분만 추출
    bracket_match = re.search(r"\[.*\]", text, re.DOTALL)
    if bracket_match:
        text = bracket_match.group(0)

    return json.loads(text)


def _rule_based_classify(keyword: str) -> Topic:
    """규칙 기반 분류: AI 전체 실패 시 PRIORITY_KEYWORDS/SKIP_PATTERNS로 분류."""
    kw_lower = keyword.lower()

    # 스킵 패턴 체크
    for pattern in SKIP_PATTERNS:
        if pattern.lower() in kw_lower:
            return Topic(
                keyword=keyword,
                label=TopicLabel.SKIP,
                reason=f"규칙 기반 스킵 (매칭: {pattern})",
                score=1,
            )

    # 우선순위 키워드 체크
    for pk in PRIORITY_KEYWORDS:
        if pk.lower() in kw_lower:
            return Topic(
                keyword=keyword,
                label=TopicLabel.PRIORITY,
                reason=f"규칙 기반 우선순위 (매칭: {pk})",
                score=7,
            )

    # 기본값: ADOPT
    return Topic(
        keyword=keyword,
        label=TopicLabel.ADOPT,
        reason="규칙 기반 기본 분류",
        score=5,
    )


def classify_topics(
    keywords: list[str],
    market_summary: str,
    gemini_api_key: str = "",
    groq_api_key: str = "",
    ai_provider: str = "gemini",
    recent_topics: list[str] | None = None,
) -> list[Topic]:
    """키워드 목록을 분류하여 Topic 리스트로 반환."""
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
                label = TopicLabel.MANUAL
            score = item.get("score", 5)  # 기본값 5 (backward compat)
            if not isinstance(score, int):
                try:
                    score = int(score)
                except (TypeError, ValueError):
                    score = 5
            score = max(1, min(10, score))  # 1~10 범위 보정 (clamp)
            topics.append(
                Topic(
                    keyword=item.get("topic", ""),
                    label=label,
                    reason=item.get("reason", ""),
                    score=score,
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
        logger.exception("AI 분류 전체 실패 — 규칙 기반 폴백으로 전환")
        topics = [_rule_based_classify(kw) for kw in keywords]
        logger.info(
            "규칙 기반 분류 완료: PRIORITY=%d, ADOPT=%d, SKIP=%d",
            sum(1 for t in topics if t.label == TopicLabel.PRIORITY),
            sum(1 for t in topics if t.label == TopicLabel.ADOPT),
            sum(1 for t in topics if t.label == TopicLabel.SKIP),
        )
        return topics
