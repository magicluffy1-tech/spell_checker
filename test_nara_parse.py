import os
from bs4 import BeautifulSoup

def test_parse():
    html_path = r"C:\Users\user\.gemini\antigravity\brain\cc0d38ba-0532-4b0c-8071-d471bd5a20ea\scratch\actual_result.html"
    if not os.path.exists(html_path):
        print("HTML file not found!")
        return

    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()

    soup = BeautifulSoup(html, 'html.parser')
    
    # 1. 교정 문서 영역 파싱 (JS 시뮬레이션)
    # section 태그 찾기
    section = soup.find('section')
    if not section:
        print("Section not found!")
        return

    corrected_sentence = ""
    # 자식 노드들을 순회하며 교정 문장 복원
    # bs4 에서는 section.contents 또는 section.children 사용
    for child in section.children:
        # 텍스트 노드인 경우
        if child.name is None:
            corrected_sentence += str(child)
        # 태그 엘리먼트인 경우
        elif child.name == 'span':
            # relative 클래스가 있는지 확인
            classes = child.get('class', [])
            if 'relative' in classes:
                # 그 자식 중 button 텍스트(교정단어)를 선택
                btn = child.find('button')
                if btn:
                    corrected_sentence += btn.get_text()
                else:
                    corrected_sentence += child.get_text()
            else:
                # 일반 span인 경우 내부 텍스트 재귀 결합
                corrected_sentence += child.get_text()
        else:
            corrected_sentence += child.get_text()

    print("=== 교정 완료본 ===")
    print(corrected_sentence.strip())

    # 2. 맞춤법/문법 오류 카드 파싱
    # dl 태그들을 찾아서 입력내용, 대치어, 도움말(사유) 추출
    cards = soup.find_all('dl')
    reasons = []
    for card in cards:
        # 입력 내용 추출
        dt_list = card.find_all('dt')
        dd_list = card.find_all('dd')
        
        wrong = ""
        right = ""
        reason = ""
        
        for dt, dd in zip(dt_list, dd_list):
            dt_text = dt.get_text().strip()
            dd_text = dd.get_text().strip()
            
            if "입력 내용" in dt_text:
                # i 태그 등 비주얼 요소 제거를 위해 내부 span 텍스트만 추출
                span = dd.find('span')
                wrong = span.get_text().strip() if span else dd_text
            elif "대치어" in dt_text:
                # 대치어 직접 수정하기 텍스트 제거
                # button의 텍스트가 대치어임
                btn = dd.find('button')
                if btn:
                    right = btn.get_text().strip()
                    # 만약 대치어 직접 수정하기 버튼이면, 하위 div 내부의 button을 다시 찾음
                    if "대치어 직접 수정하기" in right:
                        # 하위 div에서 진짜 대치어 버튼을 찾음
                        real_btn = dd.find_all('button')
                        for b in real_btn:
                            b_txt = b.get_text().strip()
                            if b_txt and "대치어 직접 수정하기" not in b_txt:
                                right = b_txt
                                break
                else:
                    right = dd_text
            elif "도움말" in dt_text:
                # 자세히 보기 텍스트 제거
                p = dd.find('p')
                reason = p.get_text().strip() if p else dd_text
                if "자세히 보기" in reason:
                    reason = reason.replace("자세히 보기", "").strip()
        
        if wrong:
            # 깨끗한 이유 정리
            # 불필요한 줄바꿈 제거
            reason_clean = " ".join(reason.split())
            reasons.append(f"[{wrong} ➡️ {right}] : {reason_clean}")

    print("\n=== 교정 사유 ===")
    for r in reasons:
        print(r)

if __name__ == '__main__':
    test_parse()
