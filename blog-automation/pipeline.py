"""전체 파이프라인 오케스트레이터 — v4.0 (피벗형 그림일기)."""

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
    logger.info("=== 블로그 자동화 파이프라인 v4.0 시작 (%s) ===", result.run_date)

    # ── Step 1: 데이터 수집 ──
    logger.info("── Step 1: 데이터 수집 ──")

    # 1a. 시장 데이터 (yfinance)
    try:
        from collectors.market_data import fetch_market_data
        result.market_snapshots = fetch_market_data()
        logger.info("시장 데이터: %d개 지표", len(result.market_snapshots))
    except Exception as e:
        logger.exception("시장 데이터 수집 실패")
        result.errors.append(f"market_data: {e}")

    # 1b. 네이버 경제 뉴스
    news_items = []
    try:
        from collectors.naver_news import fetch_economy_news
        news_items = fetch_economy_news(settings.naver_client_id, settings.naver_client_secret)
        logger.info("네이버 뉴스: %d건", len(news_items))
    except Exception as e:
        logger.exception("네이버 뉴스 수집 실패")
        result.errors.append(f"naver_news: {e}")

    # 1c. Google Trends RSS
    google_keywords = []
    try:
        from collectors.google_trends_rss import fetch_google_trends_rss
        google_keywords = fetch_google_trends_rss()
        logger.info("Google Trends RSS: %d개", len(google_keywords))
    except Exception as e:
        logger.exception("Google Trends RSS 수집 실패")
        result.errors.append(f"google_trends: {e}")

    # 1d. 네이버 급상승 검색어 (필터 없음 — 모든 트렌딩)
    naver_keywords = []
    try:
        from collectors.naver_trending import fetch_naver_trending
        naver_keywords = fetch_naver_trending()
        logger.info("네이버 급상승: %d개", len(naver_keywords))
    except Exception as e:
        logger.exception("네이버 급상승 수집 실패")
        result.errors.append(f"naver_trending: {e}")

    # 뉴스 제목에서 키워드 추출
    news_keywords = [" ".join(item.title.split()) for item in news_items[:10]]

    # 정규화 후 중복 제거
    raw_combined = naver_keywords + google_keywords + news_keywords
    seen_normalized: set[str] = set()
    all_keywords: list[str] = []
    for kw in raw_combined:
        norm = " ".join(kw.lower().split())
        if norm and norm not in seen_normalized:
            seen_normalized.add(norm)
            all_keywords.append(kw)

    result.raw_topics = all_keywords
    logger.info("총 수집 토픽: %d개 (원본 %d개에서 중복 제거)", len(all_keywords), len(raw_combined))

    if not all_keywords:
        logger.warning("수집된 토픽이 없습니다. 파이프라인 종료.")
        return result

    # ── Step 2: 토픽 분류 (피벗 가능성 평가) ──
    logger.info("── Step 2: 토픽 분류 ──")
    market_summary = ""
    if result.market_snapshots:
        from collectors.market_data import format_market_summary
        market_summary = format_market_summary(result.market_snapshots)

    # 최근 블로그 주제 로드 (중복 방지용)
    recent_topics: list[str] = []
    try:
        import json as _json
        from pathlib import Path as _Path
        data_dir = _Path(__file__).resolve().parent / "docs" / "data"
        if data_dir.exists():
            for jf in sorted(data_dir.glob("*.json"), reverse=True)[:7]:
                if jf.stem == result.run_date:
                    continue
                data = _json.loads(jf.read_text(encoding="utf-8"))
                for d in data:
                    recent_topics.append(f"[{jf.stem}] {d.get('title', d.get('topic', ''))}")
        if recent_topics:
            logger.info("중복 방지용 이전 주제 %d개 로드", len(recent_topics))
    except Exception:
        logger.warning("이전 주제 로드 실패 — 중복 방지 없이 진행")

    from ai.classifier import classify_topics
    result.classified_topics = classify_topics(
        all_keywords,
        market_summary,
        gemini_api_key=settings.gemini_api_key,
        groq_api_key=settings.groq_api_key,
        ai_provider=settings.ai_provider,
        recent_topics=recent_topics,
    )

    # ── Step 2.1: 결정론적 주제 중복 필터 ──
    if recent_topics:
        import re as _re
        recent_word_sets: list[set[str]] = []
        for rt in recent_topics:
            clean = _re.sub(r"^\[\d{4}-\d{2}-\d{2}\]\s*", "", rt)
            words = set(w for w in clean.lower().split() if len(w) >= 2)
            recent_word_sets.append(words)

        dedup_count = 0
        for topic in result.classified_topics:
            if topic.label == TopicLabel.SKIP:
                continue
            kw_words = set(w for w in topic.keyword.lower().split() if len(w) >= 2)
            if not kw_words:
                continue
            for rws in recent_word_sets:
                overlap = kw_words & rws
                if len(overlap) >= max(2, len(kw_words) * 0.5):
                    topic.label = TopicLabel.SKIP
                    topic.reason = f"이전 주제와 중복 (겹침: {', '.join(overlap)})"
                    dedup_count += 1
                    break
        if dedup_count:
            logger.info("결정론적 중복 필터: %d개 토픽 SKIP 처리", dedup_count)

    # ── Step 2.5: 수동 토픽 주입 ──
    if settings.manual_topics:
        logger.info("수동 토픽 %d개 주입: %s", len(settings.manual_topics), list(settings.manual_topics))
        existing_norms = {t.keyword.lower().strip() for t in result.classified_topics}
        for mt in settings.manual_topics:
            if mt.lower().strip() not in existing_norms:
                result.classified_topics.append(
                    Topic(keyword=mt, label=TopicLabel.MANUAL, reason="사용자 직접 지정", score=10)
                )
            else:
                for t in result.classified_topics:
                    if t.keyword.lower().strip() == mt.lower().strip():
                        t.label = TopicLabel.MANUAL
                        t.score = 10
                        t.reason = f"사용자 직접 지정 (AI 사유: {t.reason})"
                        break

    # 상위 N개 선정 + 중복 제거
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

    final_selected: list[Topic] = []
    for t in selected:
        if len(final_selected) >= MAX_TOPICS_PER_RUN:
            break
        t_words = set(w for w in t.keyword.lower().split() if len(w) >= 2)
        is_dup = False
        for kept in final_selected:
            kept_words = set(w for w in kept.keyword.lower().split() if len(w) >= 2)
            overlap = t_words & kept_words
            if overlap and len(overlap) >= max(2, min(len(t_words), len(kept_words)) * 0.5):
                logger.info("당일 내 중복 제거: '%s' ↔ '%s' (겹침: %s)", t.keyword, kept.keyword, overlap)
                is_dup = True
                break
        if not is_dup:
            final_selected.append(t)

    selected = final_selected

    logger.info(
        "선정된 토픽: %d개 — %s",
        len(selected),
        [(t.keyword, t.label.value, t.score) for t in selected],
    )

    if not selected:
        logger.warning("블로그 글로 채택된 토픽 없음. 파이프라인 종료.")
        return result

    # 선정 토픽에 관련 뉴스 매칭 + 토픽별 네이버 뉴스 검색
    for topic in selected:
        kw_parts = topic.keyword.lower().split()
        threshold = max(1, len(kw_parts) // 2 + 1)

        matched_news = []
        for n in news_items:
            text = f"{n.title} {n.description}".lower()
            hit_count = sum(1 for part in kw_parts if part in text)
            if hit_count >= threshold:
                matched_news.append(n)

        if len(matched_news) < 3:
            try:
                from collectors.naver_news import search_topic_news
                extra = search_topic_news(
                    topic.keyword, settings.naver_client_id, settings.naver_client_secret
                )
                existing_titles = {n.title.lower() for n in matched_news}
                for n in extra:
                    if n.title.lower() not in existing_titles:
                        matched_news.append(n)
                        existing_titles.add(n.title.lower())
            except Exception:
                logger.warning("토픽별 뉴스 검색 실패: '%s'", topic.keyword)

        topic.related_news = matched_news[:5]

    # ── Step 3: 블로그 초안 생성 ──
    logger.info("── Step 3: 블로그 초안 생성 ──")
    from ai.writer import generate_draft

    generated_titles: list[str] = []
    for i, topic in enumerate(selected):
        if settings.dry_run:
            logger.info("[DRY_RUN] 초안 생성 건너뜀: '%s'", topic.keyword)
            continue

        try:
            pivot_context = topic.pivot_angle if topic.pivot_angle else topic.reason
            draft = generate_draft(
                topic=topic.keyword,
                reason=pivot_context,
                news_items=topic.related_news,
                market_snapshots=result.market_snapshots,
                gemini_api_key=settings.gemini_api_key,
                groq_api_key=settings.groq_api_key,
                ai_provider=settings.writer_ai_provider,
                post_index=i,
                other_titles=generated_titles.copy(),
            )
            result.drafts.append(draft)
            generated_titles.append(draft.title)
        except Exception as e:
            logger.exception("초안 생성 실패: '%s'", topic.keyword)
            result.errors.append(f"writer({topic.keyword}): {e}")

    # ── Step 3.5: 리라이트 (재미 강화) ──
    if result.drafts and not settings.dry_run:
        logger.info("── Step 3.5: 리라이트 (재미 강화) ──")
        from ai.writer import rewrite_draft

        for draft in result.drafts:
            if draft.status == "placeholder":
                continue
            try:
                rewrite_draft(
                    draft,
                    gemini_api_key=settings.gemini_api_key,
                    groq_api_key=settings.groq_api_key,
                    ai_provider=settings.writer_ai_provider,
                )
            except Exception as e:
                logger.warning("리라이트 실패 (원본 유지): '%s' — %s", draft.title, e)

    # ── Step 4a: 마크다운 로컬 저장 ──
    if settings.save_local_markdown and result.drafts:
        logger.info("── Step 4a: 마크다운 로컬 저장 ──")
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

    # ── Step 4b: Google Sheets 저장 ──
    logger.info("── Step 4b: Google Sheets 저장 ──")
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

    # ── Step 4c: GitHub Pages 뷰어 HTML 생성 ──
    if settings.generate_html_viewer and result.drafts:
        logger.info("── Step 4c: GitHub Pages 뷰어 HTML 생성 ──")
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
    logger.info("=== 파이프라인 v4.0 완료 ===")
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
