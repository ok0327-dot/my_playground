"""공유 데이터 클래스."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class TopicLabel(str, Enum):
    PRIORITY = "PRIORITY"
    ADOPT = "ADOPT"
    SKIP = "SKIP"
    MANUAL = "MANUAL"


@dataclass
class MarketSnapshot:
    """시장 지표 스냅샷."""
    symbol: str
    name: str
    price: float
    change_pct: float
    fetched_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def summary_line(self) -> str:
        sign = "+" if self.change_pct >= 0 else ""
        return f"{self.name}: {self.price:,.2f} ({sign}{self.change_pct:.2f}%)"


@dataclass
class NewsItem:
    """뉴스 기사 항목."""
    title: str
    link: str
    source: str
    description: str = ""
    pub_date: str = ""
    subcategory: str = ""


@dataclass
class Topic:
    """분류된 토픽."""
    keyword: str
    label: TopicLabel = TopicLabel.MANUAL
    reason: str = ""
    score: int = 0
    writing_angle: str = ""
    related_news: list[NewsItem] = field(default_factory=list)


@dataclass
class BlogImage:
    """블로그 이미지."""
    url: str
    alt_text: str
    source: str  # "giphy" or "ai"


@dataclass
class BlogDraft:
    """블로그 초안."""
    topic: str
    title: str
    body_html: str
    market_data: list[MarketSnapshot] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "draft"
    news_summary: str = ""
    image_prompt: str = ""
    images: list[BlogImage] = field(default_factory=list)
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
