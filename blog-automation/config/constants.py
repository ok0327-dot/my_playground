"""URL, CSS 셀렉터, 키워드 필터 상수."""

# ── AI 모델 ──
GEMINI_MODEL = "gemini-2.5-flash"
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# ── 네이버 API ──
NAVER_SEARCH_NEWS_URL = "https://openapi.naver.com/v1/search/news.json"
# 네이버 실시간 검색어 URL 체인 (서비스 변경/폐지 대비)
NAVER_DATALAB_URLS = [
    "https://datalab.naver.com/keyword/realtimeList.naver",
    "https://datalab.naver.com/keyword/trendSearch.naver",
    "https://m.search.naver.com/search.naver?where=m&query=%EC%8B%A4%EC%8B%9C%EA%B0%84+%EA%B2%80%EC%83%89%EC%96%B4",
]

# ── 네이버 경제 뉴스 섹션 ──
NAVER_ECONOMY_NEWS_URL = "https://news.naver.com/section/101"  # 경제 섹션

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

# ── signal.bz 실시간 검색어 ──
SIGNAL_BZ_URL = "https://signal.bz/news"

# ── Google Trends RSS ──
GOOGLE_TRENDS_RSS_URL = "https://trends.google.co.kr/trending/rss?geo=KR"

# ── Unsplash API (이미지 검색) ──
UNSPLASH_API_URL = "https://api.unsplash.com/search/photos"

# ── FRED API (미국 경제지표) ──
FRED_API_URL = "https://api.stlouisfed.org/fred/series/observations"
FRED_SERIES = {
    "Federal Funds Rate": "FEDFUNDS",
    "US CPI": "CPIAUCSL",
    "US Unemployment": "UNRATE",
    "US 10Y Treasury": "DGS10",
    "US GDP Growth": "A191RL1Q225SBEA",
}

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

# ── 경제 키워드 필터 ──
ECONOMY_KEYWORDS = [
    "경제", "주식", "코스피", "코스닥", "환율", "금리", "물가", "인플레이션",
    "부동산", "아파트", "전세", "월세", "대출", "금융", "은행", "투자",
    "ETF", "펀드", "채권", "증시", "상장", "IPO", "배당",
    "유가", "원유", "금값", "비트코인", "가상화폐", "암호화폐",
    "GDP", "기준금리", "한국은행", "연준", "Fed", "나스닥", "S&P",
    "다우", "무역", "수출", "수입", "관세", "재정", "세금",
    "연금", "퇴직", "저축", "보험", "카드", "핀테크",
    "삼성전자", "SK하이닉스", "현대차", "LG에너지솔루션",
    "테슬라", "엔비디아", "애플",
]

# ── 우선순위 키워드 (규칙 기반 분류용) ──
PRIORITY_KEYWORDS = [
    "금리", "기준금리", "환율", "급등", "급락", "폭락", "폭등",
    "인플레이션", "디플레이션", "연준", "Fed", "한국은행",
    "GDP", "고용", "실업", "CPI", "물가",
    "코스피", "코스닥", "나스닥", "S&P", "다우",
]

# ── 스킵 패턴 (규칙 기반 분류용) ──
SKIP_PATTERNS = [
    # 스포츠 (Sports) — 한국어 + 영어
    "날씨", "스포츠", "야구", "축구", "농구", "올림픽", "배구", "테니스",
    "cricket", "football", "baseball", "basketball", "soccer", "tennis",
    "women vs", "men vs", "match", "world cup", "league",
    # 연예 (Entertainment)
    "아이돌", "드라마", "예능", "영화", "연예", "콘서트", "뮤직",
    # 사건/사고 (Incidents)
    "사건", "사고", "범죄", "살인", "폭행", "화재",
    # 게임 (Games)
    "게임", "롤", "리그오브레전드", "배그", "게이밍",
    # 기타 비경제 (Other non-economy)
    "날씨", "기상", "태풍", "지진",
]

# ── 구글 트렌드 ──
GOOGLE_TRENDS_GEO = "KR"

# ── 블로그 초안 설정 ──
DRAFT_MIN_WORDS = 800
DRAFT_MAX_WORDS = 1500
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
