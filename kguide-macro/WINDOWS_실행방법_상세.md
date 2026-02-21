# Windows에서 실행하는 상세 방법

## 방법 1: PowerShell 사용 (권장)

### 1단계: PowerShell 열기
- Windows 키 + X
- "Windows PowerShell" 또는 "터미널" 선택

### 2단계: WSL 폴더로 이동
```powershell
cd \\wsl$\Ubuntu\home\kang\my_playground\kguide-macro
```

### 3단계: Windows 폴더로 복사
```powershell
# Windows 폴더 생성
New-Item -ItemType Directory -Force -Path "C:\Users\dk032\my_playground\kguide-macro"

# 파일 복사
Copy-Item -Path "\\wsl$\Ubuntu\home\kang\my_playground\kguide-macro\*" -Destination "C:\Users\dk032\my_playground\kguide-macro" -Recurse -Force
```

### 4단계: Windows에서 실행
```powershell
cd C:\Users\dk032\my_playground\kguide-macro
python -m venv venv
venv\Scripts\Activate.ps1
pip install selenium webdriver-manager plyer
python kguide_macro.py
```

---

## 방법 2: Windows 탐색기 사용 (가장 쉬움)

### 1단계: Windows 탐색기 열기
- Windows 키 + E

### 2단계: WSL 폴더 접근
- 주소창에 입력: `\\wsl$\Ubuntu\home\kang\my_playground\kguide-macro`
- Enter

### 3단계: 파일 복사
- 모든 파일 선택 (Ctrl+A)
- 복사 (Ctrl+C)
- Windows 폴더로 이동: `C:\Users\dk032\my_playground\kguide-macro` (폴더가 없으면 생성)
- 붙여넣기 (Ctrl+V)

### 4단계: 배치 파일 실행
- 복사한 폴더에서 `run_windows.bat` 파일을 더블클릭

---

## 방법 3: 직접 Python 실행

Windows PowerShell에서:

```powershell
# 1. WSL 폴더로 이동
cd \\wsl$\Ubuntu\home\kang\my_playground\kguide-macro

# 2. 가상환경 생성
python -m venv venv

# 3. 가상환경 활성화
venv\Scripts\Activate.ps1

# 4. 패키지 설치
pip install selenium webdriver-manager plyer

# 5. 매크로 실행
python kguide_macro.py
```

---

## 주의사항

- Python이 Windows에 설치되어 있어야 합니다
- Chrome 브라우저가 설치되어 있어야 합니다
- PowerShell 실행 정책이 제한되어 있으면 `Set-ExecutionPolicy RemoteSigned` 실행 필요
