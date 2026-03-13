"""마크다운(.md) 파일 출력 — 사람이 읽기 쉬운 로컬 출력 (v1.0 복원)."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from models import BlogDraft

logger = logging.getLogger(__name__)


def _sanitize_filename(title: str) -> str:
    """파일명에 사용할 수 없는 문자를 제거."""
    cleaned = re.sub(r'[<>:"/\\|?*]', "", title)
    cleaned = cleaned.replace(" ", "_")
    return cleaned[:80]  # 파일명 길이 제한


def _html_to_markdown(html: str) -> str:
    """간단한 HTML → Markdown 변환."""
    text = html

    # 헤딩 변환
    text = re.sub(r"<h1[^>]*>(.*?)</h1>", r"# \1", text, flags=re.DOTALL)
    text = re.sub(r"<h2[^>]*>(.*?)</h2>", r"## \1", text, flags=re.DOTALL)
    text = re.sub(r"<h3[^>]*>(.*?)</h3>", r"### \1", text, flags=re.DOTALL)
    text = re.sub(r"<h4[^>]*>(.*?)</h4>", r"#### \1", text, flags=re.DOTALL)

    # 볼드/이탤릭
    text = re.sub(r"<b>(.*?)</b>", r"**\1**", text, flags=re.DOTALL)
    text = re.sub(r"<strong>(.*?)</strong>", r"**\1**", text, flags=re.DOTALL)
    text = re.sub(r"<i>(.*?)</i>", r"*\1*", text, flags=re.DOTALL)
    text = re.sub(r"<em>(.*?)</em>", r"*\1*", text, flags=re.DOTALL)

    # 링크
    text = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r"[\2](\1)", text, flags=re.DOTALL)

    # 줄바꿈
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<p[^>]*>(.*?)</p>", r"\1\n\n", text, flags=re.DOTALL)

    # 테이블은 그대로 유지 (복잡한 변환 대신 코드 블록으로 감싸기)
    if "<table" in text:
        text = re.sub(
            r"<table[^>]*>(.*?)</table>",
            lambda m: "\n```html\n<table>" + m.group(1) + "</table>\n```\n",
            text,
            flags=re.DOTALL,
        )

    # 나머지 HTML 태그 제거
    text = re.sub(r"<[^>]+>", "", text)

    # HTML 엔티티
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")

    # 연속 빈 줄 정리
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def save_draft_as_markdown(
    draft: BlogDraft,
    output_dir: str,
    run_date: str,
) -> Path:
    """블로그 초안을 마크다운 파일로 저장."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    filename = f"{run_date}_{_sanitize_filename(draft.title)}.md"
    file_path = out_path / filename

    # 마크다운 내용 구성
    lines: list[str] = []

    # YAML Front Matter
    lines.append("---")
    lines.append(f"title: \"{draft.title}\"")
    lines.append(f"date: {run_date}")
    lines.append(f"topic: \"{draft.topic}\"")
    lines.append(f"status: {draft.status}")
    if draft.tags:
        lines.append(f"tags: [{', '.join(draft.tags)}]")
    if draft.meta_description:
        lines.append(f"description: \"{draft.meta_description}\"")
    if draft.estimated_reading_time:
        lines.append(f"reading_time: \"{draft.estimated_reading_time}\"")
    lines.append("---")
    lines.append("")

    # 제목
    lines.append(f"# {draft.title}")
    lines.append("")

    # SEO 메타 정보
    if draft.tags or draft.meta_description or draft.estimated_reading_time:
        lines.append("> **SEO 정보**")
        if draft.tags:
            lines.append(f"> - 태그: {', '.join(draft.tags)}")
        if draft.meta_description:
            lines.append(f"> - 메타 설명: {draft.meta_description}")
        if draft.estimated_reading_time:
            lines.append(f"> - 예상 읽기시간: {draft.estimated_reading_time}")
        lines.append("")

    # 본문 (HTML → Markdown 변환)
    body_md = _html_to_markdown(draft.body_html)
    lines.append(body_md)
    lines.append("")

    # 시장 데이터
    if draft.market_data:
        lines.append("---")
        lines.append("")
        lines.append("## 오늘의 시장 데이터")
        lines.append("")
        lines.append("| 지표 | 가격 | 변동률 |")
        lines.append("|------|------|--------|")
        for s in draft.market_data:
            sign = "+" if s.change_pct >= 0 else ""
            lines.append(f"| {s.name} | {s.price:,.2f} | {sign}{s.change_pct:.2f}% |")
        lines.append("")

    # 생성 시각
    lines.append("---")
    lines.append(f"*생성 시각: {draft.created_at}*")

    content = "\n".join(lines)
    file_path.write_text(content, encoding="utf-8")
    logger.info("마크다운 저장: %s", file_path)
    return file_path


def save_all_drafts(
    drafts: list[BlogDraft],
    output_dir: str,
    run_date: str,
) -> list[Path]:
    """모든 초안을 마크다운으로 저장."""
    if not drafts:
        logger.info("저장할 초안 없음")
        return []

    paths: list[Path] = []
    for draft in drafts:
        try:
            path = save_draft_as_markdown(draft, output_dir, run_date)
            paths.append(path)
        except Exception:
            logger.exception("마크다운 저장 실패: '%s'", draft.title)

    logger.info("마크다운 파일 %d개 저장 완료 → %s", len(paths), output_dir)
    return paths
