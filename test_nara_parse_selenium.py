import os
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import time

def test_parse():
    html_path = r"C:\Users\user\.gemini\antigravity\brain\cc0d38ba-0532-4b0c-8071-d471bd5a20ea\scratch\actual_result.html"
    if not os.path.exists(html_path):
        print("HTML file not found!")
        return

    options = uc.ChromeOptions()
    options.add_argument("--window-size=1024,768")
    
    # GUI 크롬 구동
    driver = uc.Chrome(options=options)
    try:
        # file:// 프로토콜로 로컬 HTML 파일 로드
        file_url = "file:///" + html_path.replace("\\", "/")
        driver.get(file_url)
        time.sleep(2)

        # 1. 교정 완료본 추출 JS 실행
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
        corrected_sentence = driver.execute_script(js_corrected)
        print("=== 교정 완료본 ===")
        print(corrected_sentence)

        # 2. 교정 사유 추출 JS 실행
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
        reasons_text = driver.execute_script(js_reasons)
        print("\n=== 교정 사유 ===")
        print(reasons_text)
        
    finally:
        driver.quit()

if __name__ == '__main__':
    test_parse()
