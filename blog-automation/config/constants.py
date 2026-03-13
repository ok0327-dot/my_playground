"""URL, 모델, 설정 상수."""

# ── AI 모델 ──
GEMINI_MODEL = "gemini-2.5-flash"
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# ── 네이버 API ──
NAVER_SEARCH_NEWS_URL = "https://openapi.naver.com/v1/search/news.json"
NAVER_DATALAB_URLS = [
    "https://datalab.naver.com/keyword/realtimeList.naver",
    "https://datalab.naver.com/keyword/trendSearch.naver",
    "https://m.search.naver.com/search.naver?where=m&query=%EC%8B%A4%EC%8B%9C%EA%B0%84+%EA%B2%80%EC%83%89%EC%96%B4",
]

# ── 네이버 경제 뉴스 하위 카테고리 ──
NAVER_NEWS_SUBCATEGORIES = {
    "금융": 259,
    "증권": 258,
    "산업/재계": 261,
    "중기/벤처": 771,
    "부동산": 260,
    "글로벌경제": 262,
    "생활경제": 310,
    "경제일반": 263,
}

# ── Google Trends RSS ──
GOOGLE_TRENDS_RSS_URL = "https://trends.google.co.kr/trending/rss?geo=KR"

# ── 시장 데이터 심볼 (yfinance) ──
MARKET_SYMBOLS = {
    "KOSPI": "^KS11",
    "KOSDAQ": "^KQ11",
    "USD_KRW": "KRW=X",
    "EUR_KRW": "EURKRW=X",
    "JPY_KRW": "JPYKRW=X",
    "WTI_OIL": "CL=F",
    "GOLD": "GC=F",
    "BTC_USD": "BTC-USD",
}

# ── 블로그 설정 ──
MAX_TOPICS_PER_RUN = 3

# ── 재시도 설정 ──
RETRY_ATTEMPTS = 3
RETRY_WAIT_SECONDS = 2
RETRY_MAX_WAIT_SECONDS = 30

# ── HTTP ──
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
