"""GitHub Pages용 모바일 블로그 뷰어 HTML 생성."""

from __future__ import annotations

import html
import logging
import re
from pathlib import Path

from models import BlogDraft

logger = logging.getLogger(__name__)


def _strip_html_tags(raw: str) -> str:
    """HTML 태그를 제거하고 순수 텍스트만 반환."""
    text = re.sub(r"<br\s*/?>", "\n", raw)
    text = re.sub(r"</(?:p|div|tr)>", "\n\n", text)
    text = re.sub(r"</li>", "\n", text)
    text = re.sub(r"<li>", "• ", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    text = text.replace("&nbsp;", " ")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _build_draft_card(index: int, draft: BlogDraft) -> str:
    """개별 초안 카드 HTML을 생성."""
    title_escaped = html.escape(draft.title)
    clean_body = _strip_html_tags(draft.body_html)
    body_escaped = html.escape(clean_body)

    tags_html = ""
    if draft.tags:
        spans = "".join(
            f'<span class="tag">{html.escape(t)}</span>' for t in draft.tags
        )
        tags_html = spans

    reading_time = html.escape(draft.estimated_reading_time) if draft.estimated_reading_time else ""

    market_html = ""
    if draft.market_data:
        lines = "<br>".join(html.escape(s.summary_line()) for s in draft.market_data)
        market_html = f"""
    <button class="market-toggle" onclick="toggleMarket('market-{index}')">
        시장 데이터 보기/숨기기
    </button>
    <div class="market-data" id="market-{index}">{lines}</div>"""

    return f"""
    <div class="draft-card">
        <div class="title-row">
            <h2 id="title-{index}">{title_escaped}</h2>
            <button class="copy-btn" onclick="copyText('title-{index}')">제목 복사</button>
        </div>
        <div class="meta-info">
            {f'<span>읽기 {reading_time}</span>' if reading_time else ''}
            {tags_html}
        </div>
        <div class="body-section">
            <div class="body-text" id="body-{index}">{body_escaped}</div>
            <button class="copy-btn body-copy-btn" onclick="copyText('body-{index}')">본문 복사</button>
        </div>{market_html}
    </div>"""


def _build_html(drafts: list[BlogDraft], run_date: str) -> str:
    """전체 HTML 페이지를 생성."""
    cards = "\n".join(_build_draft_card(i, d) for i, d in enumerate(drafts))

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Blog Automation - {run_date}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont,
                         "Segoe UI", Roboto, "Noto Sans KR", sans-serif;
            background: #f5f5f5;
            color: #333;
            padding: 12px;
            max-width: 640px;
            margin: 0 auto;
        }}
        header {{
            text-align: center;
            padding: 16px 0;
            border-bottom: 2px solid #4CAF50;
            margin-bottom: 16px;
        }}
        header h1 {{ font-size: 1.4rem; color: #2e7d32; }}
        header .date {{ font-size: 0.85rem; color: #888; margin-top: 4px; }}

        .draft-card {{
            background: #fff;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.1);
        }}
        .draft-card .title-row {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 8px;
        }}
        .draft-card h2 {{
            font-size: 1.1rem;
            color: #1a1a1a;
            flex: 1;
            word-break: keep-all;
        }}
        .copy-btn {{
            flex-shrink: 0;
            background: #4CAF50;
            color: #fff;
            border: none;
            border-radius: 8px;
            padding: 8px 14px;
            font-size: 0.85rem;
            cursor: pointer;
            white-space: nowrap;
            -webkit-tap-highlight-color: transparent;
        }}
        .copy-btn:active {{ background: #388E3C; }}

        .meta-info {{
            display: flex;
            gap: 8px;
            font-size: 0.8rem;
            color: #888;
            margin: 8px 0;
            flex-wrap: wrap;
        }}
        .meta-info .tag {{
            background: #e8f5e9;
            color: #2e7d32;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.75rem;
        }}

        .body-section {{ position: relative; margin-top: 8px; }}
        .body-text {{
            background: #fafafa;
            border: 1px solid #eee;
            border-radius: 8px;
            padding: 12px;
            font-size: 0.95rem;
            line-height: 1.7;
            white-space: pre-wrap;
            word-break: keep-all;
            max-height: 400px;
            overflow-y: auto;
            -webkit-overflow-scrolling: touch;
        }}
        .body-copy-btn {{
            display: block;
            width: 100%;
            margin-top: 8px;
        }}

        .market-toggle {{
            background: none;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 8px;
            width: 100%;
            font-size: 0.85rem;
            color: #666;
            cursor: pointer;
            margin-top: 12px;
        }}
        .market-data {{
            display: none;
            margin-top: 8px;
            font-size: 0.8rem;
            color: #666;
            line-height: 1.6;
        }}
        .market-data.open {{ display: block; }}

        .toast {{
            position: fixed;
            bottom: 24px;
            left: 50%;
            transform: translateX(-50%);
            background: #333;
            color: #fff;
            padding: 10px 24px;
            border-radius: 20px;
            font-size: 0.9rem;
            opacity: 0;
            transition: opacity 0.3s;
            pointer-events: none;
            z-index: 1000;
        }}
        .toast.show {{ opacity: 1; }}
    </style>
</head>
<body>
    <header>
        <h1>Blog Automation</h1>
        <div class="date">{run_date}</div>
    </header>

{cards}

    <div class="toast" id="toast"></div>

    <script>
        async function copyText(elementId) {{
            var el = document.getElementById(elementId);
            var text = el.innerText || el.textContent;
            try {{
                await navigator.clipboard.writeText(text);
                showToast("복사 완료!");
            }} catch (err) {{
                var ta = document.createElement("textarea");
                ta.value = text;
                ta.style.position = "fixed";
                ta.style.opacity = "0";
                document.body.appendChild(ta);
                ta.select();
                document.execCommand("copy");
                document.body.removeChild(ta);
                showToast("복사 완료!");
            }}
        }}

        function showToast(msg) {{
            var toast = document.getElementById("toast");
            toast.textContent = msg;
            toast.classList.add("show");
            setTimeout(function() {{ toast.classList.remove("show"); }}, 1500);
        }}

        function toggleMarket(id) {{
            document.getElementById(id).classList.toggle("open");
        }}
    </script>
</body>
</html>"""


def generate_viewer_page(
    drafts: list[BlogDraft],
    docs_dir: str,
    run_date: str,
) -> Path:
    """블로그 초안 뷰어 HTML 페이지를 docs/ 폴더에 저장."""
    out_path = Path(docs_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    file_path = out_path / "index.html"

    if not drafts:
        logger.info("HTML 뷰어 생성 건너뜀: 초안 없음")
        return file_path

    content = _build_html(drafts, run_date)
    file_path.write_text(content, encoding="utf-8")
    logger.info("HTML 뷰어 저장: %s (%d개 초안)", file_path, len(drafts))
    return file_path
