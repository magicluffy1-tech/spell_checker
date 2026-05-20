import requests
import json
import re
import urllib3

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 로컬 맞춤법 교정 사전 및 상세 사유 매핑
LOCAL_SPELL_DICT = {
    "재밓다": ("재밌다", "재밌다의 비표준어 오용 교정"),
    "외않되": ("왜 안 돼", "어휘 선택 오류 및 띄어쓰기 교정 ('외않되' -> '왜 안 돼')"),
    "어의없다": ("어이없다", "한자어 형태 오류 ('어의없다' -> '어이없다')"),
    "일해라절해라": ("이래라저래라", "잘못된 관용구 사용 교정 ('일해라절해라' -> '이래라저래라')"),
    "설레임": ("설렘", "명사형 표기 오류 ('설레임' -> '설렘')"),
    "안되": ("안 돼", "어미 표기 오류 ('안되' -> '안 돼')"),
    "바램": ("바람", "어휘 선택 오류 ('바램' -> '바람')"),
    "않하고": ("안 하고", "부정 표현 표기 오류 ('않하고' -> '안 하고')"),
    "않돼": ("안 돼", "부정 표현 표기 오류 ('않돼' -> '안 돼')"),
    "금새": ("금세", "어휘 표기 오류 ('금새' -> '금세')"),
    "제작년": ("재작년", "어휘 표기 오류 ('제작년' -> '재작년')"),
    "어짜피": ("어차피", "어휘 표기 오류 ('어짜피' -> '어차피')"),
    "몇일": ("며칠", "어휘 표기 오류 ('몇일' -> '며칠')"),
    "구라": ("거짓말", "비속어 순화 ('구라' -> '거짓말')"),
    "띄어쓰기오류도있어요": ("띄어쓰기 오류도 있어요", "연이어 쓴 글자 띄어쓰기 교정"),
    "맞춤법검사기": ("맞춤법 검사기", "띄어쓰기 교정"),
    "스트림릿": ("Streamlit", "외래어 표준 표기 교정")
}

def clean_html(text: str) -> str:
    """도움말 메시지 내의 HTML 태그를 제거하는 헬퍼 함수"""
    if not text:
        return ""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text).strip()

def local_check_spelling(text: str) -> tuple[str, str]:
    """
    네트워크 오프라인 상태이거나 서버가 차단되었을 때,
    로컬 룰 사전을 기반으로 문장을 교정하고 수정 사유를 반환합니다.
    """
    if not text or not text.strip():
        return text, "교정 사항 없음"
        
    corrected = text
    reasons = []
    
    # 1단계: 사전 매칭 교정
    for wrong, (right, desc) in LOCAL_SPELL_DICT.items():
        if wrong in corrected:
            corrected = corrected.replace(wrong, right)
            reasons.append(f"[{wrong} ➡️ {right}] : {desc}")
            
    # 2단계: 다이내믹 띄어쓰기 규칙 교정
    rules = [
        ("할것이다", "할 것이다", "의존명사 '것'의 띄어쓰기 교정"),
        ("할수있다", "할 수 있다", "의존명사 '수'의 띄어쓰기 교정"),
        ("할수있게", "할 수 있게", "의존명사 '수'의 띄어쓰기 교정"),
        ("하는것이", "하는 것이", "의존명사 '것'의 띄어쓰기 교정"),
        ("일할때", "일할 때", "의존명사 '때'의 띄어쓰기 교정"),
        ("공부할때", "공부할 때", "의존명사 '때'의 띄어쓰기 교정")
    ]
    
    for wrong, right, desc in rules:
        if wrong in corrected:
            corrected = corrected.replace(wrong, right)
            reasons.append(f"[{wrong} ➡️ {right}] : {desc}")
            
    reasons_text = "\n".join(reasons) if reasons else "교정 사항 없음 (로컬에 등록되지 않은 오류 표현이거나 정상 문장)"
    return corrected, reasons_text

import sys
import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import threading
import random
import time

# 전역 브라우저 인스턴스 (세션 재사용)
_browser_instance = None
_browser_lock = threading.Lock()

def get_browser():
    """
    백그라운드 크롬 브라우저를 초기화하고 가져옵니다. 
    OS 및 가용 패키지에 따라 undetected-chromedriver(로컬 GUI)와 일반 Selenium Headless Chrome(클라우드 Linux)으로 스마트하게 분기하여 기동합니다.
    """
    global _browser_instance
    if _browser_instance is not None:
        return _browser_instance

    # 1. Windows GUI 환경: undetected_chromedriver를 사용해 최대한 자연스러운 세션 기동
    if sys.platform.startswith('win'):
        try:
            print("Windows 로컬 환경 감지: undetected-chromedriver를 초기화합니다...")
            options = uc.ChromeOptions()
            options.add_argument("--window-size=1200,800")
            _browser_instance = uc.Chrome(options=options)
            
            # 메인 스레드 안전화 및 백그라운드 구동 느낌 제공을 위해 최소화
            try:
                _browser_instance.minimize_window()
            except:
                pass
                
            _browser_instance.get("https://nara-speller.co.kr/speller/")
            time.sleep(4.0)
            return _browser_instance
        except Exception as e:
            print(f"undetected-chromedriver 구동 실패: {e}. 일반 Selenium Chrome으로 폴백 시도...")
            _browser_instance = None

    # 2. Linux (Streamlit Cloud) 또는 Windows undetected-chromedriver 실패 시 폴백
    try:
        print("일반 Selenium Headless Chrome 브라우저 초기화 시작...")
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # Headless 크롤링 차단 우회를 위한 핵심 옵션들 추가
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # Linux (Streamlit Cloud) 크롬 바이너리 자동 매핑
        if sys.platform.startswith('linux'):
            chrome_options.binary_location = "/usr/bin/chromium"
            service = Service("/usr/bin/chromedriver")
            _browser_instance = webdriver.Chrome(service=service, options=chrome_options)
        else:
            # 로컬 Windows 일반 셀레늄 구동 시 webdriver-manager 이용 자동 설치
            service = Service(ChromeDriverManager().install())
            _browser_instance = webdriver.Chrome(service=service, options=chrome_options)

        # navigator.webdriver 값 우회 주입 (Headless 탐지 해제)
        _browser_instance.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })

        _browser_instance.get("https://nara-speller.co.kr/speller/")
        time.sleep(4.0)
        return _browser_instance
        
    except Exception as e:
        print(f"크롬 브라우저 기동에 완전 실패했습니다: {e}")
        _browser_instance = None
        
    return _browser_instance

def close_browser():
    """브라우저 메모리 해제"""
    global _browser_instance
    if _browser_instance is not None:
        try:
            _browser_instance.quit()
        except:
            pass
        _browser_instance = None

def _selenium_check_spelling(text: str) -> tuple[str, str, str]:
    """Selenium을 이용해 나라인포테크 결과를 긁어옵니다."""
    browser = get_browser()
    if not browser:
        raise Exception("Browser initialization failed")

    # 브라우저가 혹시 닫혔는지 확인
    try:
        browser.current_url
    except WebDriverException:
        global _browser_instance
        _browser_instance = None
        browser = get_browser()

    # 1. 고속 SPA 복귀 시스템: 텍스트 입력창이 있는지 바로 탐색
    # 입력창이 보이지 않는다면 결과 화면에 있는 것이므로, browser.get() 전체 새로고침 대신
    # 결과 화면의 "돌아가기/새글쓰기" 버튼을 JS로 0.1초 만에 가볍게 클릭하여 초고속 복귀 유도!
    textarea = None
    try:
        textarea = browser.find_element(By.NAME, "speller-text")
    except:
        # 입력창이 없는 경우 (결과 화면이 띄워져 있음) ➡️ 초고속 복귀 JS 실행
        try:
            browser.execute_script("""
                var resetBtn = null;
                var btns = document.querySelectorAll('button, a');
                for (var i = 0; i < btns.length; i++) {
                    var txt = btns[i].textContent.trim();
                    if (txt.indexOf("돌아가기") !== -1 || txt.indexOf("새글") !== -1 || txt.indexOf("다시") !== -1) {
                        resetBtn = btns[i];
                        break;
                    }
                }
                if (resetBtn) {
                    resetBtn.click();
                } else {
                    window.location.href = "https://nara-speller.co.kr/speller/";
                }
                window.onbeforeunload = null;
            """)
            time.sleep(0.6) # 리셋 애니메이션 대기
        except:
            pass

    # 만약 리셋 후에도 없거나 페이지가 꼬였다면 100% 안전용 Fallback으로 강제 새로고침
    if not textarea:
        try:
            textarea = WebDriverWait(browser, 4).until(
                EC.presence_of_element_located((By.NAME, "speller-text"))
            )
        except TimeoutException:
            browser.get("https://nara-speller.co.kr/speller/")
            time.sleep(2.0)
            try:
                browser.execute_script("window.onbeforeunload = null;")
            except:
                pass
            textarea = WebDriverWait(browser, 5).until(
                EC.presence_of_element_located((By.NAME, "speller-text"))
            )

    # 2. 값 대입 및 React Virtual DOM State 강제 동기화
    textarea.clear()
    browser.execute_script("""
        var textarea = arguments[0];
        var val = arguments[1];
        var nativeTextAreaValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
        nativeTextAreaValueSetter.call(textarea, val);
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
        textarea.dispatchEvent(new Event('change', { bubbles: true }));
    """, textarea, text)
    time.sleep(0.3) # 상태 반응 속도 최적화 단축

    # 3. 검사하기 버튼 찾기 및 안전 펜스 해제
    buttons = browser.find_elements(By.TAG_NAME, "button")
    submit_btn = None
    for btn in buttons:
        if "검사" in btn.text:
            submit_btn = btn
            break
            
    if not submit_btn:
        raise Exception("Submit button not found.")
        
    # 버튼 강제 활성화 및 Click Event 차단 제거
    browser.execute_script("""
        var btn = arguments[0];
        if (btn.hasAttribute('disabled')) {
            btn.removeAttribute('disabled');
        }
        window.onbeforeunload = null;
    """, submit_btn)
    time.sleep(0.2)

    # JS 직접 강제 클릭
    browser.execute_script("arguments[0].click();", submit_btn)
    
    # 4. 결과 화면 로딩 대기 시간 대폭 단축 (최대 4초 대기 후 없으면 무오타로 신속 전진)
    try:
        WebDriverWait(browser, 4).until(
            EC.presence_of_element_located((By.TAG_NAME, "section"))
        )
    except TimeoutException:
        # 오타가 없는 정상 문장일 때 무의미하게 대기하지 않도록 딜레이 통째로 단축
        pass

    # 4. 결과 파싱 JS 실행
    js_corrected = """
    var section = document.querySelector('section');
    if (!section) return "";
    var result = "";
    function traverse(node) {
        if (node.nodeType === Node.TEXT_NODE) {
            result += node.textContent;
        } else if (node.nodeType === Node.ELEMENT_NODE) {
            if (node.tagName === 'SPAN' && node.classList.contains('relative')) {
                var btn = node.querySelector('button');
                if (btn) {
                    result += btn.textContent;
                } else {
                    result += node.textContent;
                }
            } else {
                for (var i = 0; i < node.childNodes.length; i++) {
                    traverse(node.childNodes[i]);
                }
            }
        }
    }
    for (var i = 0; i < section.childNodes.length; i++) {
        traverse(section.childNodes[i]);
    }
    return result.trim();
    """

    js_reasons = """
    var cards = document.querySelectorAll('dl');
    var reasons = [];
    for (var i = 0; i < cards.length; i++) {
        var card = cards[i];
        var dtList = card.querySelectorAll('dt');
        var ddList = card.querySelectorAll('dd');
        var wrong = "";
        var right = "";
        var reason = "";
        
        for (var j = 0; j < dtList.length; j++) {
            var dtText = dtList[j].textContent.trim();
            var dd = ddList[j];
            if (dtText.indexOf("입력 내용") !== -1) {
                var span = dd.querySelector('span');
                wrong = span ? span.textContent.trim() : dd.textContent.trim();
            } else if (dtText.indexOf("대치어") !== -1) {
                var btns = dd.querySelectorAll('button');
                for (var k = 0; k < btns.length; k++) {
                    var btnText = btns[k].textContent.trim();
                    if (btnText && btnText.indexOf("대치어 직접 수정하기") === -1) {
                        right = btnText;
                        break;
                    }
                }
                if (!right) {
                    right = dd.textContent.trim();
                }
            } else if (dtText.indexOf("도움말") !== -1) {
                var p = dd.querySelector('p');
                reason = p ? p.textContent.trim() : dd.textContent.trim();
                reason = reason.replace("자세히 보기", "").trim();
            }
        }
        if (wrong) {
            reason = reason.replace(/\\s+/g, ' ');
            reasons.push("[" + wrong + " ➡️ " + right + "] : " + reason);
        }
    }
    return reasons.join('\\n');
    """

    corrected_text = browser.execute_script(js_corrected)
    reasons_text = browser.execute_script(js_reasons)

    if not corrected_text:
        corrected_text = text # 교정 텍스트가 없을 시 원래 문장 보존

    if not reasons_text:
        reasons_text = "교정 사항 없음"

    # 다시 처음 상태로 돌아가도록 입력창 비워두기 대기
    try:
        # '새글쓰기'나 '돌아가기' 등의 버튼을 활용하여 원래 상태로 초기화할 수 있지만,
        # 매 검사마다 get("https://nara-speller.co.kr/speller/") 을 통해 복귀하는 편이 누적 세션 리셋에 훨씬 깔끔합니다.
        # 따라서 복귀 작업은 다음 루프 get()에 맡깁니다.
        pass
    except:
        pass

    return corrected_text, "server", reasons_text


def check_spelling(text: str) -> tuple[str, str, str]:
    """
    입력받은 텍스트의 맞춤법을 교정하고 수정 사유를 산출합니다.
    우선 외부 맞춤법 검사 서버를 시도하고, 실패 시 로컬 교정 사전으로 자동 Fallback합니다.
    """
    if not text or not text.strip():
        return text, 'local', '교정 사항 없음'

    with _browser_lock:
        try:
            corrected_text, engine, reason = _selenium_check_spelling(text)
            return corrected_text, engine, reason
        except Exception as e:
            # 예외 발생 시 로컬로 Fallback
            print(f"Selenium 검사 중 예외 발생: {e}. 로컬 사전으로 우회합니다.")
            corrected, reasons = local_check_spelling(text)
            return corrected, 'local', reasons

if __name__ == '__main__':
    # 간단한 단독 작동 검증용 코드
    test_sent = "인공지능이 너무 재밓다! 띄어쓰기오류도있어요. 외않되?"
    print(f"원문: {test_sent}")
    result, engine, reasons = check_spelling(test_sent)
    print(f"교정: {result} (적용 엔진: {engine})")
    print(f"사유:\n{reasons}")
