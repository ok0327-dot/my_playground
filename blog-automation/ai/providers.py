"""Gemini + Groq 통합 AI 호출기 (Primary → Fallback 자동 전환)."""

from __future__ import annotations

import logging

import requests
from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential

from config.constants import (
    GEMINI_MODEL,
    GROQ_API_URL,
    GROQ_MODEL,
    RETRY_ATTEMPTS,
    RETRY_MAX_WAIT_SECONDS,
    RETRY_WAIT_SECONDS,
)

logger = logging.getLogger(__name__)


@retry(
    stop=stop_after_attempt(RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=RETRY_WAIT_SECONDS, max=RETRY_MAX_WAIT_SECONDS),
    reraise=True,
)
def _call_gemini(
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.5,
) -> str:
    """Gemini API 호출."""
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user_prompt,
        config={
            "system_instruction": system_prompt,
            "temperature": temperature,
        },
    )
    return response.text


@retry(
    stop=stop_after_attempt(RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=RETRY_WAIT_SECONDS, max=RETRY_MAX_WAIT_SECONDS),
    reraise=True,
)
def _call_groq(
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.5,
) -> str:
    """Groq API 호출 (OpenAI 호환 형식)."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
    }
    resp = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def call_ai(
    system_prompt: str,
    user_prompt: str,
    gemini_api_key: str = "",
    groq_api_key: str = "",
    ai_provider: str = "gemini",
    temperature: float = 0.5,
) -> str:
    """통합 AI 호출: Primary 실패 시 Fallback 자동 전환.

    ai_provider가 "gemini"이면 Gemini → Groq 순서,
    ai_provider가 "groq"이면 Groq → Gemini 순서로 시도.
    """
    if ai_provider == "groq":
        providers = [
            ("groq", groq_api_key, _call_groq),
            ("gemini", gemini_api_key, _call_gemini),
        ]
    else:
        providers = [
            ("gemini", gemini_api_key, _call_gemini),
            ("groq", groq_api_key, _call_groq),
        ]

    last_error: Exception | None = None

    for name, key, func in providers:
        if not key:
            logger.debug("AI 제공자 '%s' — API 키 미설정, 건너뜀", name)
            continue
        try:
            result = func(key, system_prompt, user_prompt, temperature)
            logger.info("AI 호출 성공: %s", name)
            return result
        except Exception as e:
            logger.warning("AI 호출 실패 (%s): %s — 다음 제공자로 전환", name, e)
            last_error = e

    raise RuntimeError(
        "모든 AI 제공자 호출 실패. Gemini/Groq API 키를 확인하세요."
    ) from last_error
