@echo off
echo ============================================================
echo   국립경주박물관 신라금관 예약 매크로 실행
echo ============================================================
echo.

REM 가상환경이 없으면 생성
if not exist "venv" (
    echo 가상환경 생성 중...
    python -m venv venv
)

REM 가상환경 활성화
echo 가상환경 활성화 중...
call venv\Scripts\activate.bat

REM 패키지 설치 확인
echo 패키지 설치 확인 중...
pip install -q selenium webdriver-manager plyer

REM 매크로 실행
echo.
echo 매크로 시작...
echo.
python kguide_macro.py

pause
