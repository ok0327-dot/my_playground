# kguide-macro

국립경주박물관 신라금관 예약 자동화 매크로

## 설치 방법

### 1. Python 패키지 설치

```bash
# 가상환경 생성 (권장)
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate  # Windows

# 패키지 설치
pip install -r requirements.txt
```

### 2. Chrome 브라우저 설치

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install chromium-browser
# 또는
sudo apt-get install google-chrome-stable
```

**WSL 환경:**
- WSL에서는 GUI 애플리케이션 실행이 제한될 수 있습니다
- Windows에서 Chrome을 사용하거나, X11 포워딩 설정이 필요합니다
- 또는 Windows에서 직접 실행하는 것을 권장합니다

## 사용법

1. `kguide_macro.py` 파일을 열어서 `Config` 섹션 수정:
   - `TARGET_DATE`: 원하는 관람일자 (예: "2026-02-21")
   - `TARGET_TIMES`: 원하는 시간대 리스트 (예: ["12:00", "13:00"])
   - `USER_NAME`: 본인 이름
   - `USER_PHONE`: 본인 전화번호
   - `USER_COUNT`: 인원수
   - `AUTO_SUBMIT`: 자동 신청 여부 (처음엔 False로 테스트)

2. 매크로 실행:
```bash
python kguide_macro.py
```

## 주의사항

- 너무 빠른 새로고침은 IP 차단의 원인이 될 수 있습니다
- `REFRESH_INTERVAL`을 적절히 설정하세요 (기본 5초)
- 처음 사용 시 `AUTO_SUBMIT=False`로 설정하여 수동으로 확인 후 사용하세요
- 예약 성공 시 브라우저에서 직접 확인하세요
