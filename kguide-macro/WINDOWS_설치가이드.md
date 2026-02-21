# Windows 실행 가이드

## 1. Python 설치 확인

Windows PowerShell 또는 CMD에서 확인:
```bash
python --version
```

Python이 설치되어 있지 않다면:
- https://www.python.org/downloads/ 에서 Python 3.11 이상 다운로드
- 설치 시 "Add Python to PATH" 체크 필수!

## 2. Chrome 브라우저 확인

Chrome이 설치되어 있는지 확인:
- Chrome이 설치되어 있어야 합니다
- https://www.google.com/chrome/ 에서 다운로드 가능

## 3. 매크로 실행 방법

### 방법 A: 배치 파일 실행 (가장 쉬움)
1. `run_windows.bat` 파일을 더블클릭
2. 자동으로 가상환경 생성 및 패키지 설치 후 실행됩니다

### 방법 B: 수동 실행
1. PowerShell 또는 CMD 열기
2. 프로젝트 폴더로 이동:
```bash
cd C:\Users\kang\my_playground\kguide-macro
```

3. 가상환경 생성 및 활성화:
```bash
python -m venv venv
venv\Scripts\activate
```

4. 패키지 설치:
```bash
pip install -r requirements.txt
```

5. 매크로 실행:
```bash
python kguide_macro.py
```

## 4. 설정 확인

`kguide_macro.py` 파일을 열어서 다음 정보가 올바르게 설정되어 있는지 확인:
- `USER_NAME`: "강민욱"
- `USER_PHONE`: "010-2300-0327"
- `USER_COUNT`: 4
- `TARGET_DATE`: "2026-02-21"
- `TARGET_TIMES`: ["12:00", "12:30", ..., "15:30"]

## 5. 문제 해결

### Chrome이 실행되지 않는 경우
- Chrome이 최신 버전인지 확인
- Chrome을 한 번 실행해보기

### Python을 찾을 수 없는 경우
- Python 설치 시 "Add Python to PATH"를 체크했는지 확인
- 또는 전체 경로로 실행: `C:\Python3XX\python.exe kguide_macro.py`

### 패키지 설치 오류
- 인터넷 연결 확인
- 방화벽 설정 확인
