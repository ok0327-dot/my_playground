"""HuggingFace FLUX 모델로 크래파스 스타일 이미지를 생성."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

HF_INFERENCE_URL = (
    "https://router.huggingface.co/hf-inference/models/"
    "black-forest-labs/FLUX.1-schnell"
)

STYLE_PREFIX = (
    "kids crayon and colored pencil drawing on white sketchbook paper, "
    "bright cheerful colors, happy cute funny scene, smiling faces, "
    "childlike simple art, no text, no words, "
    "drawn by 8 year old child, warm joyful mood, "
)


def generate_ai_image(
    scene_description: str,
    hf_api_token: str,
    output_dir: str,
    filename_prefix: str = "",
) -> str | None:
    """크래파스 스타일 이미지를 생성하고 로컬에 저장. 파일 경로를 반환."""
    if not hf_api_token:
        logger.warning("HF_API_TOKEN이 설정되지 않음")
        return None

    prompt = STYLE_PREFIX + scene_description

    try:
        resp = requests.post(
            HF_INFERENCE_URL,
            headers={
                "Authorization": f"Bearer {hf_api_token}",
                "Content-Type": "application/json",
            },
            json={"inputs": prompt},
            timeout=90,
        )
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "image" not in content_type and len(resp.content) < 1000:
            logger.error("AI 이미지 생성 실패: 응답이 이미지가 아님")
            return None

        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        desc_hash = hashlib.md5(scene_description.encode()).hexdigest()[:8]
        filename = f"{filename_prefix}_{desc_hash}.jpg" if filename_prefix else f"{desc_hash}.jpg"
        file_path = out_path / filename

        file_path.write_bytes(resp.content)
        logger.info("AI 이미지 생성 완료: %s (%d bytes)", file_path, len(resp.content))
        return str(file_path)

    except Exception:
        logger.exception("AI 이미지 생성 실패")
        return None
