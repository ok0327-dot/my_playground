"""GitHub Pages용 모바일 블로그 뷰어 HTML 생성."""

from __future__ import annotations

import html
import json
import logging
import re
from datetime import datetime, timedelta
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


def _inject_naver_styles(body_html: str, tags: list[str] | None = None) -> str:
    """네이버 블로그 모바일 앱 호환 HTML 생성.

    네이버 SmartEditor(모바일)는 <h3>, <p> 등 시맨틱 태그의 스타일을 무시하고,
    margin 기반 간격도 벗겨내는 경우가 많습니다.
    → <div> + 인라인 스타일 + 빈 줄(<br>) 간격으로 변환하여 안정적으로 서식 유지.
    """
    result = body_html

    # ── 소제목: <h3> → <blockquote> 인용구 스타일 (네이버 앱에서 눈에 띄는 형태) ──
    result = re.sub(
        r"<h3(?:\s[^>]*)?>(.+?)</h3>",
        r'<br><blockquote style="border-left:4px solid #4CAF50; '
        r"margin:20px 0 12px; padding:10px 16px; "
        r'background-color:#f8f9fa;">'
        r'<b style="font-size:18px; color:#2e7d32;">\1</b>'
        r"</blockquote>",
        result,
    )

    # ── 문단: <p> → <div> + <br> 간격 ──
    # 크레딧 문단(Photo by)은 별도 스타일 유지
    def _replace_p(m: re.Match) -> str:
        attrs = m.group(1) or ""
        content = m.group(2)
        # 이미지 크레딧 문단은 원본 스타일 보존
        if "font-size:12px" in attrs or "Photo by" in content:
            return (
                f'<div style="font-size:13px; color:#999; text-align:center; '
                f'line-height:1.4;">{content}</div>'
            )
        return (
            f'<div style="font-size:16px; line-height:1.9; color:#333;">'
            f"{content}</div><br>"
        )

    result = re.sub(
        r"<p(?:\s([^>]*))?>(.+?)</p>",
        _replace_p,
        result,
        flags=re.DOTALL,
    )

    # ── 강조 ──
    result = re.sub(
        r"<b(?:\s[^>]*)?>",
        '<b style="font-weight:bold; color:#1a1a1a;">',
        result,
    )

    # ── 표 ──
    result = re.sub(
        r"<table(?:\s[^>]*)?>",
        '<table style="width:100%; border-collapse:collapse; margin:16px 0; font-size:14px;">',
        result,
    )
    result = re.sub(
        r"<th(?:\s[^>]*)?>",
        '<th style="background:#f5f5f5; border:1px solid #ddd; padding:10px 12px; '
        'text-align:center; font-weight:bold;">',
        result,
    )
    result = re.sub(
        r"<td(?:\s[^>]*)?>",
        '<td style="border:1px solid #ddd; padding:10px 12px;">',
        result,
    )

    # ── 연속 <br> 정리 (3개 이상 → 2개로) ──
    result = re.sub(r"(<br\s*/?>){3,}", "<br><br>", result)

    # ── 하단에 태그(해시태그) 추가 ──
    if tags:
        tag_line = " ".join(f"#{t}" for t in tags)
        result += (
            f'<br><br><div style="font-size:14px; color:#888; '
            f'line-height:2;">{tag_line}</div>'
        )

    return result


def _draft_to_dict(draft: BlogDraft) -> dict:
    """BlogDraft 객체를 JSON 직렬화 가능한 dict로 변환."""
    return {
        "title": draft.title,
        "topic": draft.topic,
        "body_html": draft.body_html,
        "tags": list(draft.tags) if draft.tags else [],
        "estimated_reading_time": draft.estimated_reading_time or "",
        "market_summary_lines": [s.summary_line() for s in draft.market_data]
        if draft.market_data
        else [],
    }


def _save_daily_json(
    drafts: list[BlogDraft],
    data_dir: Path,
    run_date: str,
) -> Path:
    """당일 초안 데이터를 JSON으로 저장. 같은 날 재실행 시 덮어쓰기."""
    data_dir.mkdir(parents=True, exist_ok=True)
    file_path = data_dir / f"{run_date}.json"
    payload = [_draft_to_dict(d) for d in drafts]
    file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("일별 JSON 저장: %s (%d개 초안)", file_path, len(payload))
    return file_path


def _load_history(
    data_dir: Path,
    max_days: int = 7,
) -> list[tuple[str, list[dict]]]:
    """docs/data/ 내 JSON 파일들을 날짜 역순으로 로드하고, 오래된 파일은 삭제."""
    if not data_dir.exists():
        return []

    cutoff = (datetime.now() - timedelta(days=max_days)).strftime("%Y-%m-%d")
    result: list[tuple[str, list[dict]]] = []

    for json_file in sorted(data_dir.glob("*.json"), reverse=True):
        date_str = json_file.stem
        if date_str < cutoff:
            json_file.unlink()
            logger.info("오래된 아카이브 삭제 (cleanup): %s", json_file)
            continue
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            result.append((date_str, data))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("JSON 로드 실패: %s — %s", json_file, exc)

    return result


def _build_draft_card(uid: str, draft_dict: dict) -> str:
    """개별 초안 카드 HTML을 생성 (dict 기반, JSON 아카이브 호환)."""
    title_escaped = html.escape(draft_dict["title"])
    body_html_rendered = draft_dict["body_html"]
    tags = draft_dict.get("tags", [])
    naver_styled = _inject_naver_styles(body_html_rendered, tags=tags)

    tags_html = ""
    if tags:
        spans = "".join(
            f'<span class="tag">{html.escape(t)}</span>' for t in tags
        )
        tags_html = spans

    reading_time = html.escape(draft_dict.get("estimated_reading_time", ""))

    market_html = ""
    market_lines = draft_dict.get("market_summary_lines", [])
    if market_lines:
        lines = "<br>".join(html.escape(ln) for ln in market_lines)
        market_html = f"""
    <button class="market-toggle" onclick="toggleMarket('market-{uid}')">
        시장 데이터 보기/숨기기
    </button>
    <div class="market-data" id="market-{uid}">{lines}</div>"""

    return f"""
    <div class="draft-card">
        <div class="title-row">
            <h2 id="title-{uid}">{title_escaped}</h2>
            <button class="copy-btn" onclick="copyText('title-{uid}')">제목 복사</button>
        </div>
        <div class="meta-info">
            {f'<span>읽기 {reading_time}</span>' if reading_time else ''}
            {tags_html}
        </div>
        <div class="body-section">
            <div class="body-html" id="body-rendered-{uid}">{body_html_rendered}</div>
            <div id="body-naver-{uid}" style="display:none">{naver_styled}</div>
            <button class="copy-btn body-copy-btn" onclick="copyHtml('body-naver-{uid}')">본문 복사 (네이버)</button>
        </div>{market_html}
    </div>"""


def _build_html(daily_data: list[tuple[str, list[dict]]]) -> str:
    """전체 HTML 페이지를 생성 (다중 날짜 지원)."""
    sections: list[str] = []
    for date_str, drafts in daily_data:
        date_compact = date_str.replace("-", "")
        cards = "\n".join(
            _build_draft_card(f"{date_compact}-{i}", d)
            for i, d in enumerate(drafts)
        )
        sections.append(
            f'<div class="date-section">'
            f'<div class="date-header">{date_str}</div>'
            f"{cards}</div>"
        )

    all_sections = "\n".join(sections)
    latest_date = daily_data[0][0] if daily_data else ""

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Blog Automation — 최근 7일</title>
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

        .date-section {{ margin-bottom: 24px; }}
        .date-header {{
            font-size: 1rem;
            font-weight: bold;
            color: #2e7d32;
            padding: 8px 0;
            border-bottom: 2px solid #e0e0e0;
            margin-bottom: 12px;
        }}

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
        .body-html {{
            background: #fafafa;
            border: 1px solid #eee;
            border-radius: 8px;
            padding: 12px;
            font-size: 0.95rem;
            line-height: 1.7;
            word-break: keep-all;
            max-height: 800px;
            overflow-y: auto;
            -webkit-overflow-scrolling: touch;
        }}
        .body-html img {{ width: 100%; border-radius: 8px; margin: 12px 0; }}
        .body-html h3 {{ font-size: 1.05rem; margin: 16px 0 8px; color: #2e7d32; }}
        .body-html p {{ margin-bottom: 10px; }}
        .body-html table {{ width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 0.85rem; display: block; overflow-x: auto; }}
        .body-html th, .body-html td {{ border: 1px solid #ddd; padding: 6px 8px; text-align: left; }}
        .body-html th {{ background: #f0f0f0; }}
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
        <h1>Blog Automation — 최근 7일</h1>
        <div class="date">마지막 업데이트: {latest_date}</div>
    </header>

{all_sections}

    <div class="toast" id="toast"></div>

    <script>
        async function copyText(elementId) {{
            var el = document.getElementById(elementId);
            var text = el.innerText || el.textContent;
            try {{
                await navigator.clipboard.writeText(text);
                showToast("복사 완료!");
            }} catch (err) {{
                fallbackCopyText(text);
            }}
        }}

        function copyHtml(elementId) {{
            var el = document.getElementById(elementId);

            // Selection + execCommand: 모바일 리치텍스트 복사에 가장 안정적
            el.style.display = "block";
            el.style.position = "fixed";
            el.style.left = "-9999px";
            el.style.top = "0";
            el.style.width = "600px";

            var range = document.createRange();
            range.selectNodeContents(el);
            var sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);

            var ok = false;
            try {{
                ok = document.execCommand("copy");
            }} catch (e) {{}}

            sel.removeAllRanges();
            el.style.display = "none";
            el.style.position = "";
            el.style.left = "";
            el.style.top = "";
            el.style.width = "";

            if (ok) {{
                showToast("본문 복사 완료! 네이버에 붙여넣기 하세요");
            }} else {{
                try {{
                    var blob = new Blob([el.innerHTML], {{ type: "text/html" }});
                    var textBlob = new Blob([el.innerText], {{ type: "text/plain" }});
                    navigator.clipboard.write([new ClipboardItem({{ "text/html": blob, "text/plain": textBlob }})]);
                    showToast("본문 복사 완료!");
                }} catch (e2) {{
                    fallbackCopyText(el.innerText);
                    showToast("텍스트만 복사됨 (브라우저 제한)");
                }}
            }}
        }}

        function fallbackCopyText(text) {{
            var ta = document.createElement("textarea");
            ta.value = text;
            ta.style.position = "fixed";
            ta.style.opacity = "0";
            document.body.appendChild(ta);
            ta.select();
            document.execCommand("copy");
            document.body.removeChild(ta);
        }}

        function showToast(msg) {{
            var toast = document.getElementById("toast");
            toast.textContent = msg;
            toast.classList.add("show");
            setTimeout(function() {{ toast.classList.remove("show"); }}, 2000);
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
    """블로그 초안 뷰어 HTML 페이지를 docs/ 폴더에 저장 (7일 아카이브 포함)."""
    out_path = Path(docs_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    data_dir = out_path / "data"

    file_path = out_path / "index.html"

    # 1) 오늘 초안 → JSON 저장
    if drafts:
        _save_daily_json(drafts, data_dir, run_date)

    # 2) 최근 7일 아카이브 로드 + 오래된 파일 정리
    daily_data = _load_history(data_dir, max_days=7)

    if not daily_data:
        logger.info("HTML 뷰어 생성 건너뜀: 아카이브 데이터 없음")
        return file_path

    # 3) 전체 HTML 빌드
    content = _build_html(daily_data)
    file_path.write_text(content, encoding="utf-8")
    total = sum(len(d) for _, d in daily_data)
    logger.info(
        "HTML 뷰어 저장: %s (%d일, 총 %d개 초안)",
        file_path,
        len(daily_data),
        total,
    )
    return file_path
