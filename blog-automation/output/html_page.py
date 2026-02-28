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

    # ── 이미지: 네이버 앱은 <img> 붙여넣기 불가 → 삽입 위치 안내로 교체 ──
    result = re.sub(
        r'<div[^>]*>\s*<img[^>]*>\s*</div>\s*'
        r'(?:<div[^>]*>Photo by[^<]*</div>|<p[^>]*>Photo by[^<]*</p>)?',
        '<div style="text-align:center; margin:16px 0; padding:12px; '
        'background:#f0f7f0; border:1px dashed #4CAF50; border-radius:8px; '
        'font-size:14px; color:#666;">'
        '📷 이미지 저장 후 여기에 삽입</div><br>',
        result,
    )
    # 래핑 안 된 단독 img+credit도 처리
    result = re.sub(
        r'<img[^>]*style="[^"]*width:100%[^>]*/>\s*'
        r'(?:<p[^>]*>Photo by[^<]*</p>)?',
        '<div style="text-align:center; margin:16px 0; padding:12px; '
        'background:#f0f7f0; border:1px dashed #4CAF50; border-radius:8px; '
        'font-size:14px; color:#666;">'
        '📷 이미지 저장 후 여기에 삽입</div><br>',
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


def _extract_image_urls(body_html: str) -> list[tuple[str, str]]:
    """본문 HTML에서 Unsplash 이미지 URL과 크레딧을 추출."""
    images = []
    for m in re.finditer(
        r'<img[^>]*src="(https://images\.unsplash\.com/[^"]+)"[^>]*/>'
        r'\s*<p[^>]*>(Photo by [^<]+)</p>',
        body_html,
    ):
        images.append((m.group(1), m.group(2)))
    return images


def _build_draft_card(index: int, draft: BlogDraft) -> str:
    """개별 초안 카드 HTML을 생성."""
    title_escaped = html.escape(draft.title)
    # 뷰어 렌더링용 HTML
    body_html_rendered = draft.body_html
    # 네이버 복사용 인라인 스타일 HTML (hidden)
    naver_styled = _inject_naver_styles(draft.body_html, tags=draft.tags)

    # 이미지 저장 버튼 생성
    image_urls = _extract_image_urls(draft.body_html)
    image_buttons = ""
    if image_urls:
        buttons = []
        for img_idx, (url, credit) in enumerate(image_urls):
            label = "도입부 이미지" if img_idx == 0 else "마무리 이미지"
            buttons.append(
                f'<button class="img-save-btn" onclick="saveImage(\'{url}\', '
                f'\'blog_img_{index}_{img_idx}.jpg\')">'
                f'{label} 저장</button>'
            )
        image_buttons = (
            '<div class="img-save-row">'
            + "".join(buttons)
            + "</div>"
        )

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
            <div class="body-html" id="body-rendered-{index}">{body_html_rendered}</div>
            <div id="body-naver-{index}" style="display:none">{naver_styled}</div>
            <button class="copy-btn body-copy-btn" onclick="copyHtml('body-naver-{index}')">본문 복사 (네이버)</button>
            {image_buttons}
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
        .body-html {{
            background: #fafafa;
            border: 1px solid #eee;
            border-radius: 8px;
            padding: 12px;
            font-size: 0.95rem;
            line-height: 1.7;
            word-break: keep-all;
            max-height: 500px;
            overflow-y: auto;
            -webkit-overflow-scrolling: touch;
        }}
        .body-html img {{ width: 100%; border-radius: 8px; margin: 12px 0; }}
        .body-html h3 {{ font-size: 1.05rem; margin: 16px 0 8px; color: #2e7d32; }}
        .body-html p {{ margin-bottom: 10px; }}
        .body-html table {{ width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 0.85rem; }}
        .body-html th, .body-html td {{ border: 1px solid #ddd; padding: 6px 8px; text-align: left; }}
        .body-html th {{ background: #f0f0f0; }}
        .body-copy-btn {{
            display: block;
            width: 100%;
            margin-top: 8px;
        }}
        .img-save-row {{
            display: flex;
            gap: 8px;
            margin-top: 8px;
        }}
        .img-save-btn {{
            flex: 1;
            background: #1976D2;
            color: #fff;
            border: none;
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 0.85rem;
            cursor: pointer;
            -webkit-tap-highlight-color: transparent;
        }}
        .img-save-btn:active {{ background: #1565C0; }}

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

        // ── 이미지 저장: fetch → blob → download (갤러리에 저장 후 네이버 앱에서 삽입) ──
        async function saveImage(url, filename) {{
            showToast("이미지 다운로드 중...");
            try {{
                var resp = await fetch(url);
                var blob = await resp.blob();
                var a = document.createElement("a");
                a.href = URL.createObjectURL(blob);
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(a.href);
                showToast("저장 완료! 네이버 앱에서 이미지 추가하세요");
            }} catch (e) {{
                // 폴백: 새 탭에서 이미지 열기 (길게 눌러서 저장)
                window.open(url, "_blank");
                showToast("이미지가 열렸습니다. 길게 눌러 저장하세요");
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
