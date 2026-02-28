"""전체 파이프라인 오케스트레이터 — v2.0 (모든 신규 수집기/기능 통합)."""

from __future__ import annotations

import logging
import sys
from datetime import datetime

from config.constants import MAX_TOPICS_PER_RUN
from config.settings import Settings
from models import PipelineResult, Topic, TopicLabel

logger = logging.getLogger(__name__)


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def run() -> PipelineResult:
    """파이프라인 전체 실행."""
    settings = Settings.from_env()
    _setup_logging(settings.log_level)

    result = PipelineResult()
    logger.info("=== 블로그 자동화 파이프라인 v2.0 시작 (%s) ===", result.run_date)

    # ── Step 1: 데이터 수집 ──
    logger.info("── Step 1: 데이터 수집 ──")

    # 1a. 시장 데이터 (yfinance)
    try:
        from collectors.market_data import fetch_market_data, format_market_summary
        result.market_snapshots = fetch_market_data()
        logger.info("시장 데이터: %d개 지표", len(result.market_snapshots))
    except Exception as e:
        logger.exception("시장 데이터 수집 실패")
        result.errors.append(f"market_data: {e}")

    # 1b. FRED 미국 경제지표 (선택)
    fred_summary = ""
    if settings.fred_api_key:
        try:
            from collectors.fred_data import fetch_fred_data, format_fred_summary
            fred_observations = fetch_fred_data(settings.fred_api_key)
            fred_summary = format_fred_summary(fred_observations)
            logger.info("FRED 데이터: %d개 지표", len(fred_observations))
        except Exception as e:
            logger.exception("FRED 데이터 수집 실패")
            result.errors.append(f"fred_data: {e}")

    # 1c. 네이버 경제 뉴스 (하위 카테고리 포함)
    news_items = []
    try:
        from collectors.naver_news import fetch_economy_news
        news_items = fetch_economy_news(settings.naver_client_id, settings.naver_client_secret)
        logger.info("네이버 뉴스: %d건", len(news_items))
    except Exception as e:
        logger.exception("네이버 뉴스 수집 실패")
        result.errors.append(f"naver_news: {e}")

    # 1d. Google Trends — RSS (Primary) + pytrends (Fallback)
    google_keywords = []
    try:
        from collectors.google_trends_rss import fetch_google_trends_rss
        google_keywords = fetch_google_trends_rss()
        logger.info("Google Trends RSS: %d개", len(google_keywords))
    except Exception as e:
        logger.warning("Google Trends RSS 실패: %s — pytrends 폴백 시도", e)

    if not google_keywords:
        try:
            from collectors.google_trends import fetch_google_trends
            google_keywords = fetch_google_trends()
            logger.info("Google Trends (pytrends 폴백): %d개", len(google_keywords))
        except Exception as e:
            logger.exception("구글 트렌드 수집 전체 실패")
            result.errors.append(f"google_trends: {e}")

    # 1e. signal.bz 실시간 검색어
    signal_keywords = []
    try:
        from collectors.signal_bz import fetch_signal_keywords
        signal_keywords = fetch_signal_keywords()
        logger.info("signal.bz: %d개", len(signal_keywords))
    except Exception as e:
        logger.exception("signal.bz 수집 실패")
        result.errors.append(f"signal_bz: {e}")

    # 1f. 네이버 급상승 검색어
    naver_keywords = []
    try:
        from collectors.naver_trending import fetch_naver_trending
        naver_keywords = fetch_naver_trending()
        logger.info("네이버 급상승: %d개", len(naver_keywords))
    except Exception as e:
        logger.exception("네이버 급상승 수집 실패")
        result.errors.append(f"naver_trending: {e}")

    # 뉴스 제목에서 키워드 추출 (공백 정규화 적용)
    news_keywords = [" ".join(item.title.split()) for item in news_items[:10]]

    # 정규화 후 중복 제거 (normalize + dedup across all sources)
    raw_combined = signal_keywords + naver_keywords + google_keywords + news_keywords
    seen_normalized: set[str] = set()
    all_keywords: list[str] = []
    for kw in raw_combined:
        norm = " ".join(kw.lower().split())  # 소문자 + 공백 정규화
        if norm and norm not in seen_normalized:
            seen_normalized.add(norm)
            all_keywords.append(kw)  # 원본 형태 유지, 정규화 키로 비교

    result.raw_topics = all_keywords
    logger.info("총 수집 토픽: %d개 (원본 %d개에서 중복 제거)", len(all_keywords), len(raw_combined))

    if not all_keywords:
        logger.warning("수집된 토픽이 없습니다. 파이프라인 종료.")
        return result

    # ── Step 2: 토픽 분류 ──
    logger.info("── Step 2: 토픽 분류 ──")
    market_summary = ""
    if result.market_snapshots:
        from collectors.market_data import format_market_summary
        market_summary = format_market_summary(result.market_snapshots)
    if fred_summary:
        market_summary = f"{market_summary}\n\n{fred_summary}" if market_summary else fred_summary

    from ai.classifier import classify_topics
    result.classified_topics = classify_topics(
        all_keywords,
        market_summary,
        gemini_api_key=settings.gemini_api_key,
        groq_api_key=settings.groq_api_key,
        ai_provider=settings.ai_provider,
    )

    # ── Step 2.5: 수동 토픽 주입 (Manual topic injection) ──
    if settings.manual_topics:
        logger.info("수동 토픽 %d개 주입: %s", len(settings.manual_topics), list(settings.manual_topics))
        existing_norms = {t.keyword.lower().strip() for t in result.classified_topics}
        for mt in settings.manual_topics:
            if mt.lower().strip() not in existing_norms:
                result.classified_topics.append(
                    Topic(
                        keyword=mt,
                        label=TopicLabel.MANUAL,
                        reason="사용자 직접 지정",
                        score=10,
                    )
                )
            else:
                # 이미 AI가 분류한 토픽이면 MANUAL로 승격 + score=10
                for t in result.classified_topics:
                    if t.keyword.lower().strip() == mt.lower().strip():
                        t.label = TopicLabel.MANUAL
                        t.score = 10
                        t.reason = f"사용자 직접 지정 (AI 사유: {t.reason})"
                        break

    # MANUAL + PRIORITY + ADOPT 중 상위 N개 선정
    # 정렬: MANUAL > PRIORITY > ADOPT, 같은 등급 내에서는 score 높은 순
    selected = [
        t for t in result.classified_topics
        if t.label in (TopicLabel.PRIORITY, TopicLabel.ADOPT, TopicLabel.MANUAL)
    ]
    selected.sort(key=lambda t: (
        t.label != TopicLabel.MANUAL,
        t.label != TopicLabel.PRIORITY,
        t.label != TopicLabel.ADOPT,
        -t.score,
    ))
    selected = selected[:MAX_TOPICS_PER_RUN]
    logger.info(
        "선정된 토픽: %d개 — %s",
        len(selected),
        [(t.keyword, t.label.value, t.score) for t in selected],
    )

    if not selected:
        logger.warning("블로그 글로 채택된 토픽 없음. 파이프라인 종료.")
        return result

    # 선정 토픽에 관련 뉴스 매칭 (개선된 매칭 로직)
    # - 단일 단어 키워드: 제목/설명에 해당 단어가 포함되면 매칭
    # - 복합 키워드 (2단어 이상): 과반수 이상 단어가 매칭되어야 관련 뉴스로 인정
    for topic in selected:
        kw_parts = topic.keyword.lower().split()
        threshold = max(1, len(kw_parts) // 2 + 1)  # 과반수 (majority threshold)

        matched_news = []
        for n in news_items:
            text = f"{n.title} {n.description}".lower()
            hit_count = sum(1 for part in kw_parts if part in text)
            if hit_count >= threshold:
                matched_news.append(n)

        topic.related_news = matched_news[:5]

    # ── Step 3: 블로그 초안 생성 ──
    logger.info("── Step 3: 블로그 초안 생성 ──")
    from ai.writer import generate_draft

    for topic in selected:
        if settings.dry_run:
            logger.info("[DRY_RUN] 초안 생성 건너뜀: '%s'", topic.keyword)
            continue

        try:
            draft = generate_draft(
                topic=topic.keyword,
                reason=topic.reason,
                news_items=topic.related_news,
                market_snapshots=result.market_snapshots,
                gemini_api_key=settings.gemini_api_key,
                groq_api_key=settings.groq_api_key,
                ai_provider=settings.writer_ai_provider,
            )
            result.drafts.append(draft)
        except Exception as e:
            logger.exception("초안 생성 실패: '%s'", topic.keyword)
            result.errors.append(f"writer({topic.keyword}): {e}")

    # ── Step 3.5: Unsplash 이미지 검색 (선택) ──
    if settings.unsplash_access_key and result.drafts:
        logger.info("── Step 3.5: Unsplash 이미지 검색 ──")
        from collectors.unsplash import search_image

        for draft in result.drafts:
            if settings.dry_run:
                logger.info("[DRY_RUN] 이미지 검색 건너뜀: '%s'", draft.topic)
                continue

            try:
                # 토픽 키워드를 영어로 번역 (AI 사용)
                from ai.providers import call_ai
                en_keyword = call_ai(
                    system_prompt="Translate the following Korean keyword to English for image search. Reply with ONLY the English keyword, nothing else.",
                    user_prompt=draft.topic,
                    gemini_api_key=settings.gemini_api_key,
                    groq_api_key=settings.groq_api_key,
                    ai_provider=settings.ai_provider,
                    temperature=0.0,
                ).strip()
                logger.info("이미지 키워드 번역: '%s' → '%s'", draft.topic, en_keyword)

                image_url, credit_text, photo_id = search_image(en_keyword, settings.unsplash_access_key)

                # Fallback: 검색 결과 없으면 더 일반적인 키워드로 재시도
                if not image_url:
                    fallback_keyword = call_ai(
                        system_prompt=(
                            "The Unsplash image search returned no results for the keyword below. "
                            "Suggest a shorter, more generic English keyword (1-3 words) that would "
                            "find a relevant, visually appealing photo. Reply with ONLY the keyword."
                        ),
                        user_prompt=en_keyword,
                        gemini_api_key=settings.gemini_api_key,
                        groq_api_key=settings.groq_api_key,
                        ai_provider=settings.ai_provider,
                        temperature=0.3,
                    ).strip()
                    logger.info("이미지 키워드 fallback: '%s' → '%s'", en_keyword, fallback_keyword)
                    image_url, credit_text, photo_id = search_image(fallback_keyword, settings.unsplash_access_key)

                # ── 도입부 이미지 (정보성) ──
                used_photo_ids: set[str] = set()
                if image_url:
                    draft.image_url = image_url
                    draft.image_credit = credit_text
                    used_photo_ids.add(photo_id)

                    img_html = (
                        f'<img src="{image_url}" alt="{draft.topic}" '
                        f'style="width:100%; border-radius:8px; margin:16px 0 4px;" />'
                        f'<p style="font-size:12px; color:#999; text-align:center; '
                        f'margin:0 0 16px;">{credit_text}</p>'
                    )
                    first_p_end = draft.body_html.find("</p>")
                    if first_p_end != -1:
                        insert_pos = first_p_end + len("</p>")
                        draft.body_html = (
                            draft.body_html[:insert_pos] + "\n" + img_html + "\n" + draft.body_html[insert_pos:]
                        )
                    else:
                        draft.body_html = img_html + "\n" + draft.body_html

                # ── 마무리 이미지 (감성적/심미적) ──
                try:
                    end_keyword = call_ai(
                        system_prompt=(
                            "Given the blog topic below, suggest an English keyword (1-3 words) "
                            "for searching a beautiful, aesthetic, emotional photo on Unsplash "
                            "that would make a great closing image for the article. "
                            "Think: hopeful sunrise, city skyline at night, peaceful nature, "
                            "person looking at horizon, etc. Reply with ONLY the keyword."
                        ),
                        user_prompt=draft.topic,
                        gemini_api_key=settings.gemini_api_key,
                        groq_api_key=settings.groq_api_key,
                        ai_provider=settings.ai_provider,
                        temperature=0.5,
                    ).strip()
                    logger.info("마무리 이미지 키워드: '%s' → '%s'", draft.topic, end_keyword)

                    end_url, end_credit, end_pid = search_image(
                        end_keyword, settings.unsplash_access_key, exclude_ids=used_photo_ids,
                    )
                    if end_url:
                        end_img_html = (
                            f'<img src="{end_url}" alt="{draft.topic}" '
                            f'style="width:100%; border-radius:8px; margin:24px 0 4px;" />'
                            f'<p style="font-size:12px; color:#999; text-align:center; '
                            f'margin:0 0 8px;">{end_credit}</p>'
                        )
                        draft.body_html = draft.body_html.rstrip() + "\n" + end_img_html
                        logger.info("마무리 이미지 삽입 완료: %s", end_credit)
                except Exception as e2:
                    logger.warning("마무리 이미지 검색 실패: '%s' — %s", draft.topic, e2)

            except Exception as e:
                logger.warning("이미지 검색/삽입 실패: '%s' — %s", draft.topic, e)

    # ── Step 4a: 쿠팡 링크 (선택) ──
    if settings.coupang_access_key and result.drafts:
        logger.info("── Step 4a: 쿠팡 링크 생성 ──")
        try:
            from output.coupang import generate_coupang_links
            for draft in result.drafts:
                links = generate_coupang_links(
                    [draft.topic],
                    settings.coupang_access_key,
                    settings.coupang_secret_key,
                )
                draft.coupang_links = links
        except Exception as e:
            logger.exception("쿠팡 링크 생성 실패")
            result.errors.append(f"coupang: {e}")

    # ── Step 4b: 마크다운 로컬 저장 ──
    if settings.save_local_markdown and result.drafts:
        logger.info("── Step 4b: 마크다운 로컬 저장 ──")
        if settings.dry_run:
            logger.info("[DRY_RUN] 마크다운 저장 건너뜀. 초안 %d개", len(result.drafts))
        else:
            try:
                from output.markdown import save_all_drafts
                md_paths = save_all_drafts(result.drafts, settings.output_dir, result.run_date)
                logger.info("마크다운 파일 %d개 저장 완료", len(md_paths))
            except Exception as e:
                logger.exception("마크다운 저장 실패")
                result.errors.append(f"markdown: {e}")

    # ── Step 4c: Google Sheets 저장 ──
    logger.info("── Step 4c: Google Sheets 저장 ──")
    if settings.dry_run:
        logger.info("[DRY_RUN] Sheets 저장 건너뜀. 초안 %d개", len(result.drafts))
    elif result.drafts:
        try:
            from output.sheets import save_drafts
            save_drafts(
                result.drafts,
                settings.google_sheets_credentials,
                settings.google_sheet_id,
                result.run_date,
            )
        except Exception as e:
            logger.exception("Sheets 저장 실패")
            result.errors.append(f"sheets: {e}")

    # ── Step 4d: GitHub Pages 뷰어 HTML 생성 ──
    if settings.generate_html_viewer and result.drafts:
        logger.info("── Step 4d: GitHub Pages 뷰어 HTML 생성 ──")
        if settings.dry_run:
            logger.info("[DRY_RUN] HTML 뷰어 생성 건너뜀. 초안 %d개", len(result.drafts))
        else:
            try:
                from pathlib import Path

                from output.html_page import generate_viewer_page
                docs_dir = str(Path(__file__).resolve().parent / "docs")
                generate_viewer_page(result.drafts, docs_dir, result.run_date)
            except Exception as e:
                logger.exception("HTML 뷰어 생성 실패")
                result.errors.append(f"html_page: {e}")

    # ── 결과 요약 ──
    logger.info("=== 파이프라인 v2.0 완료 ===")
    logger.info("시장 지표: %d개", len(result.market_snapshots))
    logger.info("수집 토픽: %d개", len(result.raw_topics))
    logger.info("분류 토픽: %d개", len(result.classified_topics))
    logger.info("생성 초안: %d개", len(result.drafts))
    if result.errors:
        logger.warning("에러: %d건 — %s", len(result.errors), result.errors)

    return result


if __name__ == "__main__":
    result = run()
    if result.errors:
        sys.exit(1)
