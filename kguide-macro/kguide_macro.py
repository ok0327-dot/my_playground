"""
=============================================================
  국립경주박물관 [특별전] 신라금관 예약 자동화 매크로
  사이트: https://kguide.kr/gjnm/
=============================================================

사용법:
  1. pip install selenium webdriver-manager plyer
  2. config 섹션에서 원하는 날짜, 시간, 개인정보 설정
  3. python kguide_macro.py 실행

주의사항:
  - 예약 시 개인정보 입력이 필요할 수 있습니다
  - 너무 빠른 새로고침은 IP 차단의 원인이 될 수 있으므로
    REFRESH_INTERVAL을 적절히 설정하세요 (기본 5초)
"""

import time
import datetime
import platform
import sys
from dataclasses import dataclass, field
from typing import Optional

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import (
        TimeoutException, 
        NoSuchElementException,
        ElementClickInterceptedException,
        StaleElementReferenceException,
    )
except ImportError:
    print("❌ selenium이 설치되어 있지 않습니다.")
    print("   pip install selenium 을 실행해주세요.")
    sys.exit(1)

try:
    from webdriver_manager.chrome import ChromeDriverManager
    USE_WEBDRIVER_MANAGER = True
except ImportError:
    USE_WEBDRIVER_MANAGER = False
    print("⚠️  webdriver_manager가 없습니다. 시스템 chromedriver를 사용합니다.")
    print("   자동 설치를 원하면: pip install webdriver-manager")


# ═══════════════════════════════════════════════════════════
#  ✏️  설정 (여기를 수정하세요)
# ═══════════════════════════════════════════════════════════

@dataclass
class Config:
    # --- 예약 대상 ---
    URL: str = "https://kguide.kr/gjnm/"
    TARGET_DATE: str = "2026-02-21"       # 원하는 관람일자 (YYYY-MM-DD)
    TARGET_TIMES: list = field(default_factory=lambda: [])
    # 원하는 관람시간 목록 (빈 리스트면 아무 시간이나 잡음)
    # 예: ["10:00", "10:30", "11:00"]

    # --- 개인정보 (예약 폼에 필요한 경우) ---
    USER_NAME: str = ""                   # 이름
    USER_PHONE: str = ""                  # 전화번호
    USER_COUNT: int = 1                   # 인원수

    # --- 매크로 설정 ---
    REFRESH_INTERVAL: float = 5.0         # 새로고침 간격 (초) - 너무 짧으면 차단 위험
    MAX_ATTEMPTS: int = 0                 # 최대 시도 횟수 (0=무한)
    AUTO_SUBMIT: bool = False             # True면 자동으로 신청하기 클릭
    HEADLESS: bool = True                 # True면 브라우저 숨김 (WSL 환경에서는 True 권장)

    # --- 알림 ---
    SOUND_ALERT: bool = True              # 빈자리 발견 시 소리 알림
    DESKTOP_NOTIFICATION: bool = True     # 데스크탑 알림


config = Config(
    TARGET_DATE="2026-02-21",
    TARGET_TIMES=["12:00", "12:30", "13:00", "13:30", "14:00", "14:30",
                  "15:00", "15:30"],  # 12:00 ~ 15:30
    USER_NAME="강민욱",              # ← 본인 이름 입력
    USER_PHONE="010-2300-0327",     # ← 본인 전화번호 입력
    USER_COUNT=4,                   # 4명
    REFRESH_INTERVAL=5.0,
    AUTO_SUBMIT=False,              # 처음엔 False로 테스트 후 True로 변경
    HEADLESS=True,                   # WSL 환경에서는 headless 모드 권장
)


# ═══════════════════════════════════════════════════════════
#  유틸리티 함수
# ═══════════════════════════════════════════════════════════

def log(msg: str, level: str = "INFO"):
    """타임스탬프 포함 로그 출력"""
    now = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    icons = {"INFO": "ℹ️", "OK": "✅", "WARN": "⚠️", "ERR": "❌", "FIND": "🎯"}
    icon = icons.get(level, "•")
    print(f"[{now}] {icon} {msg}")


def play_alert_sound():
    """빈자리 발견 시 알림음"""
    if not config.SOUND_ALERT:
        return
    try:
        if platform.system() == "Darwin":  # macOS
            import subprocess
            subprocess.Popen(["afplay", "/System/Library/Sounds/Glass.aiff"])
        elif platform.system() == "Windows":
            import winsound
            for _ in range(5):
                winsound.Beep(1000, 300)
                time.sleep(0.1)
        else:  # Linux
            print("\a" * 5)  # terminal bell
    except Exception:
        print("\a")


def send_desktop_notification(title: str, message: str):
    """데스크탑 알림 전송"""
    if not config.DESKTOP_NOTIFICATION:
        return
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            timeout=10,
        )
    except ImportError:
        log("plyer가 없어 데스크탑 알림을 보낼 수 없습니다. pip install plyer", "WARN")
    except Exception as e:
        log(f"알림 전송 실패: {e}", "WARN")


# ═══════════════════════════════════════════════════════════
#  브라우저 초기화
# ═══════════════════════════════════════════════════════════

def create_driver() -> webdriver.Chrome:
    """Chrome WebDriver 생성"""
    import shutil
    
    # Chrome 설치 확인
    chrome_paths = [
        shutil.which("google-chrome"),
        shutil.which("chromium-browser"),
        shutil.which("chromium"),
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
    ]
    chrome_path = next((p for p in chrome_paths if p), None)
    
    if not chrome_path:
        log("❌ Chrome 또는 Chromium이 설치되어 있지 않습니다!", "ERR")
        log("   설치 방법:", "WARN")
        log("   Ubuntu/Debian: sudo apt-get install chromium-browser", "WARN")
        log("   또는: sudo apt-get install google-chrome-stable", "WARN")
        log("   WSL 환경에서는 X11 포워딩이 필요할 수 있습니다.", "WARN")
        raise RuntimeError("Chrome이 설치되어 있지 않습니다.")
    
    chrome_options = Options()
    
    if chrome_path:
        chrome_options.binary_location = chrome_path

    if config.HEADLESS:
        chrome_options.add_argument("--headless=new")

    # 기본 옵션
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--window-size=430,932")  # 모바일 사이즈 (사이트가 모바일 UI)

    # 모바일 에뮬레이션 (kguide.kr은 모바일 반응형)
    mobile_emulation = {
        "deviceMetrics": {"width": 430, "height": 932, "pixelRatio": 3.0},
        "userAgent": (
            "Mozilla/5.0 (Linux; Android 13; SM-S918N) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Mobile Safari/537.36"
        ),
    }
    chrome_options.add_experimental_option("mobileEmulation", mobile_emulation)

    # 자동화 탐지 우회
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    try:
        if USE_WEBDRIVER_MANAGER:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            driver = webdriver.Chrome(options=chrome_options)
    except Exception as e:
        log(f"❌ Chrome WebDriver 생성 실패: {e}", "ERR")
        log("   Chrome이 제대로 설치되어 있는지 확인하세요.", "WARN")
        raise

    # webdriver 속성 숨기기
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )

    return driver


# ═══════════════════════════════════════════════════════════
#  핵심 매크로 로직
# ═══════════════════════════════════════════════════════════

class ReservationMacro:
    def __init__(self, driver: webdriver.Chrome):
        self.driver = driver
        self.wait = WebDriverWait(driver, 10)
        self.attempt = 0

    def open_page(self):
        """예약 페이지 열기"""
        log(f"페이지 접속 중: {config.URL}")
        self.driver.get(config.URL)
        time.sleep(2)  # 초기 로딩 대기

    def select_date(self) -> bool:
        """
        관람일자 선택 (날짜 드롭다운 또는 input 클릭 후 선택)
        사이트 구조에 따라 수정이 필요할 수 있습니다.
        """
        try:
            # 방법 1: 날짜 드롭다운/선택자가 있는 경우
            date_elements = self.driver.find_elements(
                By.XPATH, 
                f"//*[contains(text(), '{config.TARGET_DATE}')]"
            )
            if date_elements:
                date_elements[0].click()
                log(f"날짜 선택: {config.TARGET_DATE}", "OK")
                time.sleep(1)
                return True

            # 방법 2: 날짜가 이미 선택되어 있는지 확인
            page_source = self.driver.page_source
            if config.TARGET_DATE in page_source:
                log(f"날짜 {config.TARGET_DATE} 확인됨", "OK")
                return True

            log(f"날짜 {config.TARGET_DATE}를 찾을 수 없습니다", "WARN")
            return False

        except Exception as e:
            log(f"날짜 선택 오류: {e}", "ERR")
            return False

    def open_reservation_panel(self) -> bool:
        """
        예약신청 패널 열기
        스크린샷 기준: '예약신청' 버튼이나 관람시간 섹션을 열어야 함
        """
        try:
            # 예약신청 버튼 찾기 (여러 가능한 셀렉터 시도)
            selectors = [
                "//button[contains(text(), '예약신청')]",
                "//button[contains(text(), '예약')]",
                "//a[contains(text(), '예약신청')]",
                "//div[contains(text(), '예약신청')]",
                "//*[contains(@class, 'reserve')]",
                "//*[contains(@class, 'booking')]",
            ]
            
            for sel in selectors:
                elements = self.driver.find_elements(By.XPATH, sel)
                for el in elements:
                    if el.is_displayed():
                        el.click()
                        log("예약 패널 열기 시도", "INFO")
                        time.sleep(1)
                        return True
            
            # 이미 열려 있을 수 있음
            return True
            
        except Exception as e:
            log(f"예약 패널 열기 오류: {e}", "ERR")
            return False

    def check_available_slots(self) -> list:
        """
        예약 가능한 시간대 확인
        '매진'이 아닌 시간대를 찾아 반환
        """
        available = []
        
        try:
            # 페이지 소스에서 시간대 정보 파싱
            # kguide.kr 사이트 구조에 따라 다양한 방법 시도

            # 방법 1: 시간대 항목들을 찾아서 '매진' 여부 확인
            # 스크린샷 기준으로 시간(09:30, 10:00 등)과 매진 텍스트가 같은 행에 있음
            time_rows = self.driver.find_elements(
                By.XPATH,
                "//*[contains(text(), ':30') or contains(text(), ':00')]/.."
            )

            for row in time_rows:
                try:
                    row_text = row.text
                    # 시간 추출
                    import re
                    time_match = re.search(r'(\d{1,2}:\d{2})', row_text)
                    if not time_match:
                        continue
                    
                    slot_time = time_match.group(1)
                    is_sold_out = "매진" in row_text

                    if not is_sold_out:
                        # 타겟 시간 필터링
                        if config.TARGET_TIMES and slot_time not in config.TARGET_TIMES:
                            continue
                        available.append({"time": slot_time, "element": row})
                        log(f"🎉 빈자리 발견! {slot_time}", "FIND")

                except StaleElementReferenceException:
                    continue

            # 방법 2: 클릭 가능한 (비활성화되지 않은) 시간 버튼 찾기
            if not available:
                clickable_buttons = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "button:not([disabled]), .time-slot:not(.disabled):not(.sold-out)"
                )
                for btn in clickable_buttons:
                    try:
                        btn_text = btn.text
                        import re
                        time_match = re.search(r'(\d{1,2}:\d{2})', btn_text)
                        if time_match and "매진" not in btn_text:
                            slot_time = time_match.group(1)
                            if config.TARGET_TIMES and slot_time not in config.TARGET_TIMES:
                                continue
                            available.append({"time": slot_time, "element": btn})
                            log(f"🎉 빈자리 발견! {slot_time}", "FIND")
                    except StaleElementReferenceException:
                        continue

        except Exception as e:
            log(f"슬롯 확인 오류: {e}", "ERR")

        return available

    def click_slot(self, slot: dict) -> bool:
        """빈자리 시간대 클릭"""
        try:
            element = slot["element"]

            # 클릭 가능한 자식 요소 찾기 (체크박스, 버튼 등)
            clickables = element.find_elements(By.TAG_NAME, "button") + \
                         element.find_elements(By.TAG_NAME, "input") + \
                         element.find_elements(By.TAG_NAME, "a") + \
                         element.find_elements(By.CSS_SELECTOR, "[role='button']")

            if clickables:
                clickables[0].click()
            else:
                element.click()

            log(f"시간 {slot['time']} 클릭 완료!", "OK")
            time.sleep(1)
            return True

        except ElementClickInterceptedException:
            # JavaScript로 클릭 시도
            try:
                self.driver.execute_script("arguments[0].click();", slot["element"])
                log(f"시간 {slot['time']} JS 클릭 완료!", "OK")
                return True
            except Exception as e:
                log(f"클릭 실패: {e}", "ERR")
                return False
        except Exception as e:
            log(f"클릭 오류: {e}", "ERR")
            return False

    def fill_form_and_submit(self) -> bool:
        """
        개인정보 입력 및 신청하기 버튼 클릭
        사이트 구조에 따라 수정이 필요합니다.
        """
        try:
            # 이름 입력
            if config.USER_NAME:
                name_fields = self.driver.find_elements(
                    By.XPATH,
                    "//input[@type='text' and ("
                    "contains(@placeholder, '이름') or "
                    "contains(@name, 'name') or "
                    "contains(@id, 'name')"
                    ")]"
                )
                for field in name_fields:
                    if field.is_displayed():
                        field.clear()
                        field.send_keys(config.USER_NAME)
                        log(f"이름 입력: {config.USER_NAME}", "OK")
                        break

            # 전화번호 입력
            if config.USER_PHONE:
                phone_fields = self.driver.find_elements(
                    By.XPATH,
                    "//input[("
                    "contains(@placeholder, '전화') or "
                    "contains(@placeholder, '연락') or "
                    "contains(@placeholder, '휴대') or "
                    "contains(@name, 'phone') or "
                    "contains(@name, 'tel') or "
                    "contains(@type, 'tel') or "
                    "contains(@id, 'phone')"
                    ")]"
                )
                for field in phone_fields:
                    if field.is_displayed():
                        field.clear()
                        field.send_keys(config.USER_PHONE)
                        log(f"전화번호 입력: {config.USER_PHONE[:3]}****", "OK")
                        break

            # 인원수 입력 (필요한 경우)
            if config.USER_COUNT > 1:
                count_fields = self.driver.find_elements(
                    By.XPATH,
                    "//input[("
                    "contains(@name, 'count') or "
                    "contains(@name, 'num') or "
                    "contains(@id, 'count')"
                    ")]"
                )
                for field in count_fields:
                    if field.is_displayed():
                        field.clear()
                        field.send_keys(str(config.USER_COUNT))
                        log(f"인원수 입력: {config.USER_COUNT}", "OK")
                        break

            # 동의 체크박스 (있는 경우)
            checkboxes = self.driver.find_elements(
                By.XPATH,
                "//input[@type='checkbox' and ("
                "contains(@name, 'agree') or "
                "contains(@id, 'agree') or "
                "contains(@name, 'consent')"
                ")]"
            )
            for cb in checkboxes:
                if not cb.is_selected():
                    cb.click()
                    log("동의 체크박스 클릭", "OK")

            # 신청하기 버튼
            if config.AUTO_SUBMIT:
                submit_buttons = self.driver.find_elements(
                    By.XPATH,
                    "//button[contains(text(), '신청')] | "
                    "//button[contains(text(), '예약')] | "
                    "//input[@type='submit']"
                )
                for btn in submit_buttons:
                    if btn.is_displayed() and btn.is_enabled():
                        btn.click()
                        log("🚀 신청하기 클릭!", "OK")
                        time.sleep(2)
                        return True
            else:
                log("⏸️  AUTO_SUBMIT=False → 수동 신청 필요! 브라우저를 확인하세요.", "WARN")
                return True

        except Exception as e:
            log(f"폼 입력 오류: {e}", "ERR")

        return False

    def refresh_slots(self):
        """
        시간대 목록 새로고침
        페이지 전체 새로고침 또는 새로고침 버튼 클릭
        """
        try:
            # 방법 1: '새로고침' 버튼 찾기 (스크린샷에 보임)
            refresh_buttons = self.driver.find_elements(
                By.XPATH,
                "//*[contains(text(), '새로고침') or contains(text(), '새로 고침')]"
            )
            for btn in refresh_buttons:
                if btn.is_displayed():
                    btn.click()
                    time.sleep(1)
                    return

            # 방법 2: 페이지 전체 새로고침
            self.driver.refresh()
            time.sleep(2)

        except Exception as e:
            log(f"새로고침 오류: {e}", "WARN")
            self.driver.refresh()
            time.sleep(2)

    def run(self):
        """메인 루프"""
        log("=" * 50)
        log("🏛️  국립경주박물관 신라금관 예약 매크로 시작")
        log(f"   대상 날짜: {config.TARGET_DATE}")
        log(f"   대상 시간: {config.TARGET_TIMES or '모든 시간'}")
        log(f"   새로고침 간격: {config.REFRESH_INTERVAL}초")
        log(f"   자동 신청: {'ON' if config.AUTO_SUBMIT else 'OFF'}")
        log("=" * 50)

        self.open_page()
        time.sleep(2)

        while True:
            self.attempt += 1

            if config.MAX_ATTEMPTS > 0 and self.attempt > config.MAX_ATTEMPTS:
                log(f"최대 시도 횟수({config.MAX_ATTEMPTS})에 도달했습니다.", "WARN")
                break

            log(f"--- 시도 #{self.attempt} ---")

            # 빈자리 확인
            available = self.check_available_slots()

            if available:
                slot = available[0]  # 첫 번째 빈자리 선택
                log(f"🎯 {slot['time']} 시간대 예약 시도!", "FIND")

                # 알림
                play_alert_sound()
                send_desktop_notification(
                    "🎉 빈자리 발견!",
                    f"신라금관 {config.TARGET_DATE} {slot['time']} 예약 가능!"
                )

                # 슬롯 클릭
                if self.click_slot(slot):
                    # 폼 작성 및 제출
                    self.fill_form_and_submit()

                    if not config.AUTO_SUBMIT:
                        log("=" * 50)
                        log("🖱️  브라우저에서 직접 신청을 완료해주세요!", "WARN")
                        log("   매크로를 종료하려면 Ctrl+C를 누르세요.")
                        log("=" * 50)
                        # 수동 신청 대기
                        try:
                            while True:
                                time.sleep(1)
                        except KeyboardInterrupt:
                            pass
                    break
            else:
                log(f"빈자리 없음. {config.REFRESH_INTERVAL}초 후 재시도...")

            # 새로고침
            time.sleep(config.REFRESH_INTERVAL)
            self.refresh_slots()
            time.sleep(1)


# ═══════════════════════════════════════════════════════════
#  실행
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    driver = None
    try:
        driver = create_driver()
        macro = ReservationMacro(driver)
        macro.run()
    except KeyboardInterrupt:
        log("\n사용자가 매크로를 중지했습니다.", "WARN")
    except Exception as e:
        log(f"예상치 못한 오류: {e}", "ERR")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            input("\nEnter를 누르면 브라우저를 닫습니다...")
            driver.quit()
        log("매크로 종료", "INFO")
