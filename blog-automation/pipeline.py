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

    # 최근 블로그 주제 로드 (중복 방지용)
    recent_topics: list[str] = []
    try:
        import json as _json
        from pathlib import Path as _Path
        data_dir = _Path(__file__).resolve().parent / "docs" / "data"
        if data_dir.exists():
            for jf in sorted(data_dir.glob("*.json"), reverse=True)[:7]:
                if jf.stem == result.run_date:
                    continue  # 오늘 데이터는 제외
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

    # ── Step 2.1: 결정론적 주제 중복 필터 (Deterministic dedup) ──
    # AI 분류기가 놓칠 수 있는 유사 주제를 단어 겹침으로 강제 SKIP
    if recent_topics:
        # 이전 제목에서 핵심 단어 집합 추출 (날짜 태그 제거)
        import re as _re
        recent_word_sets: list[set[str]] = []
        for rt in recent_topics:
            # "[2026-03-01] 제목..." → 제목 부분만 추출
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
                # 키워드 단어의 50% 이상이 이전 제목과 겹치면 중복
                if len(overlap) >= max(2, len(kw_words) * 0.5):
                    topic.label = TopicLabel.SKIP
                    topic.reason = f"이전 주제와 중복 (겹침: {', '.join(overlap)})"
                    dedup_count += 1
                    break
        if dedup_count:
            logger.info("결정론적 중복 필터: %d개 토픽 SKIP 처리", dedup_count)

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

    # 같은 날 선정된 토픽 간 유사도 + 도메인 다양성 필터
    _DOMAIN_KEYWORDS = {
        "주식": ["주식", "증시", "코스피", "코스닥", "kospi", "kosdaq", "나스닥", "s&p",
                 "종목", "실적", "배당", "ipo", "공모주", "상장"],
        "부동산": ["부동산", "아파트", "전세", "월세", "분양", "재건축", "청약",
                  "주택", "매매", "집값", "전월세", "임대"],
        "코인": ["비트코인", "이더리움", "코인", "가상화폐", "암호화폐", "알트코인",
                "블록체인", "디파이", "nft", "bitcoin", "crypto"],
        "환율": ["환율", "달러", "엔화", "위안", "원달러", "외환", "환전"],
        "채권금리": ["채권", "국채", "금리", "기준금리", "예금", "적금", "예적금"],
        "원자재": ["금값", "유가", "금", "원유", "구리", "원자재", "wti", "금시세"],
        "생활재테크": ["절세", "연금", "보험", "경매", "공매", "부업", "세금", "연말정산"],
        "투자마인드": ["포트폴리오", "분산투자", "리밸런싱", "투자심리", "공포지수"],
    }

    def _detect_domain(keyword: str) -> str:
        kw = keyword.lower()
        for domain, patterns in _DOMAIN_KEYWORDS.items():
            if any(p in kw for p in patterns):
                return domain
        return "기타"

    final_selected: list[Topic] = []
    domain_count: dict[str, int] = {}
    for t in selected:
        # 유사도 체크
        t_words = set(w for w in t.keyword.lower().split() if len(w) >= 2)
        is_dup = False
        for kept in final_selected:
            kept_words = set(w for w in kept.keyword.lower().split() if len(w) >= 2)
            overlap = t_words & kept_words
            if overlap and len(overlap) >= max(2, min(len(t_words), len(kept_words)) * 0.5):
                logger.info("당일 내 중복 제거: '%s' ↔ '%s' (겹침: %s)", t.keyword, kept.keyword, overlap)
                is_dup = True
                break
        if is_dup:
            continue

        # 도메인 다양성 체크 (같은 도메인 최대 1편)
        domain = _detect_domain(t.keyword)
        if domain_count.get(domain, 0) >= 1 and domain != "기타":
            logger.info("도메인 중복 제거: '%s' (도메인: %s, 이미 1편 선정)", t.keyword, domain)
            continue

        final_selected.append(t)
        domain_count[domain] = domain_count.get(domain, 0) + 1

    selected = final_selected
    logger.info("도메인 분포: %s", dict(domain_count))

    # ── 다양성 시드 주입: 빈 도메인에서 시장 데이터 기반 토픽 자동 생성 ──
    if len(selected) < MAX_TOPICS_PER_RUN and result.market_snapshots:
        import random as _rand
        # 시장 데이터에서 변동이 큰 지표로 시드 토픽 생성
        _seed_map: dict[str, list[tuple[str, str]]] = {
            "환율": [],
            "코인": [],
            "원자재": [],
            "채권금리": [],
            "생활재테크": [("절세 전략과 연금 투자 점검", "생활 재테크 토픽 자동 주입")],
            "투자마인드": [("분산 투자 포트폴리오 점검", "투자 마인드 토픽 자동 주입")],
        }
        for snap in result.market_snapshots:
            name_lower = snap.name.lower()
            pct = f"{'+' if snap.change_pct >= 0 else ''}{snap.change_pct:.1f}%"
            if "usd_krw" in name_lower or "환율" in name_lower:
                _seed_map["환율"].append((f"원달러 환율 {snap.price:,.0f}원 시대 분석", f"환율 {pct} 변동"))
            elif "jpy" in name_lower or "eur" in name_lower:
                _seed_map["환율"].append((f"{snap.name} 환율 동향 분석", f"환율 {pct} 변동"))
            elif "btc" in name_lower or "비트코인" in name_lower:
                _seed_map["코인"].append((f"비트코인 ${snap.price:,.0f} 시대 투자 전략", f"BTC {pct}"))
            elif "gold" in name_lower or "금" in name_lower:
                _seed_map["원자재"].append((f"금값 ${snap.price:,.0f} 돌파 투자 가이드", f"금 {pct}"))
            elif "oil" in name_lower or "wti" in name_lower:
                _seed_map["원자재"].append((f"국제유가 ${snap.price:,.1f} 시대 영향 분석", f"유가 {pct}"))

        # 부동산은 시장 데이터 없으므로 고정 시드
        if "부동산" not in domain_count:
            _seed_map["부동산"] = [("2026년 부동산 시장 전망과 투자 전략", "부동산 다양성 주입")]

        for domain, seeds in _seed_map.items():
            if len(selected) >= MAX_TOPICS_PER_RUN:
                break
            if domain in domain_count:
                continue  # 이미 이 도메인 토픽이 있음
            if not seeds:
                continue
            kw, reason = _rand.choice(seeds)
            selected.append(Topic(
                keyword=kw,
                label=TopicLabel.ADOPT,
                reason=f"다양성 시드 주입 — {reason}",
                score=7,
            ))
            domain_count[domain] = 1
            logger.info("다양성 시드 주입: '%s' (도메인: %s)", kw, domain)

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
        import random
        from collectors.unsplash import search_image

        # 이전 아카이브에서 사용된 사진 URL 키 로드 (cross-day 중복 방지)
        used_photo_keys: set[str] = set()
        try:
            import re as _re
            data_dir_img = _Path(__file__).resolve().parent / "docs" / "data"
            if data_dir_img.exists():
                for jf in sorted(data_dir_img.glob("*.json"), reverse=True)[:7]:
                    jdata = _json.loads(jf.read_text(encoding="utf-8"))
                    for d in jdata:
                        # body_html에서 photo-xxxx URL 키 추출
                        keys = _re.findall(r"photo-[a-zA-Z0-9_-]+", d.get("body_html", ""))
                        used_photo_keys.update(keys)
            if used_photo_keys:
                logger.info("이전 아카이브 사진 키 %d개 로드 (중복 방지)", len(used_photo_keys))
        except Exception:
            logger.warning("이전 사진 키 로드 실패 — 중복 방지 없이 진행")

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

                pick_idx = random.randint(0, 2)  # 랜덤 선택으로 다양성 확보
                image_url, credit_text, photo_id = search_image(
                    en_keyword, settings.unsplash_access_key,
                    pick=pick_idx, exclude_urls=used_photo_keys,
                )

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
                    image_url, credit_text, photo_id = search_image(
                        fallback_keyword, settings.unsplash_access_key,
                        pick=pick_idx, exclude_urls=used_photo_keys,
                    )

                # ── 도입부 이미지 (정보성) ──
                if image_url:
                    draft.image_url = image_url
                    draft.image_credit = credit_text
                    # URL 키로 중복 추적 (photo-xxxx 형태)
                    img_key_match = _re.search(r"photo-[a-zA-Z0-9_-]+", image_url)
                    if img_key_match:
                        used_photo_keys.add(img_key_match.group(0))

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
                    # 다양한 감성 키워드를 위한 랜덤 스타일 힌트
                    style_hints = [
                        "hopeful sunrise, golden hour landscape",
                        "city skyline at dusk, urban evening",
                        "calm ocean waves, serene coast",
                        "mountain peak, misty valley",
                        "rainy window, cozy atmosphere",
                        "autumn leaves, warm colors",
                        "night sky stars, contemplative mood",
                        "coffee shop morning, warm light",
                    ]
                    hint = random.choice(style_hints)
                    end_keyword = call_ai(
                        system_prompt=(
                            "Given the blog topic below, suggest an English keyword (1-3 words) "
                            "for searching a beautiful, aesthetic photo on Unsplash "
                            "that would make a great closing image for the article. "
                            f"Style direction: {hint}. "
                            "Be creative and AVOID generic keywords like 'stock market', 'finance', 'economy'. "
                            "Reply with ONLY the keyword."
                        ),
                        user_prompt=draft.topic,
                        gemini_api_key=settings.gemini_api_key,
                        groq_api_key=settings.groq_api_key,
                        ai_provider=settings.ai_provider,
                        temperature=0.8,
                    ).strip()
                    logger.info("마무리 이미지 키워드: '%s' → '%s'", draft.topic, end_keyword)

                    end_pick = random.randint(0, 2)
                    end_url, end_credit, end_pid = search_image(
                        end_keyword, settings.unsplash_access_key,
                        pick=end_pick, exclude_urls=used_photo_keys,
                    )
                    if end_url:
                        end_key_match = _re.search(r"photo-[a-zA-Z0-9_-]+", end_url)
                        if end_key_match:
                            used_photo_keys.add(end_key_match.group(0))
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

    # ── Step 3.6: GIPHY GIF 마커 교체 (선택) ──
    import re as _re_gif

    _GIPHY_MARKER_RE = _re_gif.compile(
        r"\[GIPHY:\s*(.+?)\s*\|\s*(.+?)\s*\]"
    )

    if settings.giphy_api_key and result.drafts:
        logger.info("── Step 3.6: GIPHY GIF 마커 교체 ──")
        import random as _rand_gif
        from collectors.giphy import search_gif

        # 아카이브에서 사용된 GIF ID 로드 (cross-day 중복 방지)
        used_gif_ids: set[str] = set()
        try:
            data_dir_gif = _Path(__file__).resolve().parent / "docs" / "data"
            if data_dir_gif.exists():
                for jf in sorted(data_dir_gif.glob("*.json"), reverse=True)[:7]:
                    jdata = _json.loads(jf.read_text(encoding="utf-8"))
                    for d in jdata:
                        used_gif_ids.update(d.get("gif_ids", []))
            if used_gif_ids:
                logger.info("이전 아카이브 GIF ID %d개 로드 (중복 방지)", len(used_gif_ids))
        except Exception:
            logger.warning("이전 GIF ID 로드 실패 — 중복 방지 없이 진행")

        for draft in result.drafts:
            if settings.dry_run:
                continue
            markers = list(_GIPHY_MARKER_RE.finditer(draft.body_html))
            if not markers:
                continue

            logger.info("GIF 마커 %d개 발견: '%s'", len(markers), draft.topic)
            new_body = draft.body_html
            for m in reversed(markers):  # 뒤에서부터 교체 (인덱스 밀림 방지)
                keyword = m.group(1).strip()
                caption = m.group(2).strip()
                pick_idx = _rand_gif.randint(0, 3)
                gif_url, gif_title, gif_id = search_gif(
                    keyword, settings.giphy_api_key,
                    pick=pick_idx, exclude_ids=used_gif_ids,
                )
                if gif_url and gif_id:
                    used_gif_ids.add(gif_id)
                    draft.gif_ids.append(gif_id)
                    gif_html = (
                        f'<div style="text-align:center; margin:16px 0;">'
                        f'<img src="{gif_url}" alt="{gif_title}" '
                        f'style="max-width:100%; border-radius:8px;" />'
                        f'<p style="font-size:13px; color:#888; margin:4px 0 0; '
                        f'font-style:italic;">{caption}</p>'
                        f'<p style="font-size:10px; color:#bbb; margin:2px 0 0;">'
                        f'Powered by GIPHY</p>'
                        f'</div>'
                    )
                    new_body = new_body[:m.start()] + gif_html + new_body[m.end():]
                    logger.info("GIF 삽입: '%s' → %s", keyword, gif_id)
                else:
                    # 검색 실패 → 마커만 제거
                    new_body = new_body[:m.start()] + new_body[m.end():]
                    logger.warning("GIF 검색 실패, 마커 제거: '%s'", keyword)

            draft.body_html = new_body

    else:
        # GIPHY 키 미설정 시 모든 [GIPHY: ...] 마커 제거 (graceful degradation)
        for draft in result.drafts:
            draft.body_html = _GIPHY_MARKER_RE.sub("", draft.body_html)

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
