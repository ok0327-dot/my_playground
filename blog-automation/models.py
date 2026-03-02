"""공유 데이터 클래스."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class TopicLabel(str, Enum):
    PRIORITY = "PRIORITY"
    ADOPT = "ADOPT"
    SKIP = "SKIP"
    MANUAL = "MANUAL"  # 사용자 직접 지정 토픽 (User-specified topic)


@dataclass
class MarketSnapshot:
    """시장 지표 스냅샷."""
    symbol: str
    name: str
    price: float
    change_pct: float  # 전일 대비 변동률 (%)
    fetched_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def summary_line(self) -> str:
        sign = "+" if self.change_pct >= 0 else ""
        return f"{self.name}: {self.price:,.2f} ({sign}{self.change_pct:.2f}%)"


@dataclass
class NewsItem:
    """뉴스 기사 항목."""
    title: str
    link: str
    source: str  # "naver_news", "naver_trending", "google_trends", "signal_bz"
    description: str = ""
    pub_date: str = ""
    subcategory: str = ""  # 네이버 뉴스 하위 카테고리 (금융, 증권 등)


@dataclass
class Topic:
    """분류된 토픽."""
    keyword: str
    label: TopicLabel = TopicLabel.MANUAL
    reason: str = ""
    score: int = 0  # AI가 부여한 트래픽 잠재력 점수 1~10 (Traffic potential score)
    related_news: list[NewsItem] = field(default_factory=list)


@dataclass
class BlogDraft:
    """블로그 초안."""
    topic: str
    title: str
    body_html: str
    market_data: list[MarketSnapshot] = field(default_factory=list)
    coupang_links: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "draft"  # draft / reviewed / published
    # Unsplash 이미지
    image_url: str = ""           # Unsplash 이미지 URL
    image_credit: str = ""        # "Photo by {name} on Unsplash"
    # GIPHY GIF 추적 (중복 방지용 / GIF dedup tracking)
    gif_ids: list[str] = field(default_factory=list)
    # SEO 메타데이터
    tags: list[str] = field(default_factory=list)
    meta_description: str = ""
    estimated_reading_time: str = ""


@dataclass
class PipelineResult:
    """파이프라인 실행 결과."""
    run_date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    market_snapshots: list[MarketSnapshot] = field(default_factory=list)
    raw_topics: list[str] = field(default_factory=list)
    classified_topics: list[Topic] = field(default_factory=list)
    drafts: list[BlogDraft] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
