import os
from html.parser import HTMLParser

class NaraHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.path = []
        
        # 교정본 추출용 상태 변수들
        self.in_section = False
        self.section_depth = 0
        self.corrected_text_list = []
        self.current_span_relative = False
        self.span_depth = 0
        self.skip_text_for_original = False
        
        # 교정 사유 추출용 상태 변수들
        self.in_dl = False
        self.dl_depth = 0
        self.current_dt = False
        self.current_dd = False
        self.current_tag = None
        self.dt_text = ""
        self.dd_text_list = []
        self.dd_button_texts = []
        
        self.cards = [] # 각 dl 카드별 dt-dd 리스트

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        self.path.append((tag, attr_dict))
        
        # --- 1. 교정 문장 추출 상태 추적 ---
        if tag == 'section':
            self.in_section = True
            self.section_depth = len(self.path)
            
        if self.in_section:
            if tag == 'span':
                classes = attr_dict.get('class', '')
                if 'relative' in classes:
                    self.current_span_relative = True
                    self.span_depth = len(self.path)
                    
            if self.current_span_relative:
                # relative span 내부일 때
                if tag == 'span':
                    classes = attr_dict.get('class', '')
                    # 원래 틀린 글자는 버림 (예: text-red-100 이나 text-blue-400 등의 span 안의 텍스트는 건너뜀)
                    if 'text-red-100' in classes or 'text-blue-400' in classes:
                        self.skip_text_for_original = True
                # button의 텍스트(교정단어)는 취함
                
        # --- 2. 교정 사유 추출 상태 추적 ---
        if tag == 'dl':
            self.in_dl = True
            self.dl_depth = len(self.path)
            self.cards.append([])
            
        if self.in_dl:
            if tag == 'dt':
                self.current_dt = True
                self.dt_text = ""
            elif tag == 'dd':
                self.current_dd = True
                self.dd_text_list = []
                self.dd_button_texts = []
            self.current_tag = tag

    def handle_endtag(self, tag):
        if self.in_section and len(self.path) == self.section_depth:
            self.in_section = False
            
        if self.current_span_relative and len(self.path) == self.span_depth:
            self.current_span_relative = False
            
        if self.in_section and self.current_span_relative:
            # relative span 내의 특정 태그 종료 처리
            if tag == 'span':
                self.skip_text_for_original = False
                
        if self.in_dl:
            if tag == 'dl' and len(self.path) == self.dl_depth:
                self.in_dl = False
            elif tag == 'dt':
                self.current_dt = False
            elif tag == 'dd':
                self.current_dd = False
                # dd 수집 종료 시 카드에 추가
                if self.cards:
                    self.cards[-1].append((self.dt_text, "".join(self.dd_text_list).strip(), self.dd_button_texts))
                    
        if self.path:
            self.path.pop()

    def handle_data(self, data):
        # --- 1. 교정 문장 데이터 추출 ---
        if self.in_section:
            if self.current_span_relative:
                # relative span 내부일 때
                # 원래 글자 span은 건너뛰고, button 내부의 글자(교정본)나 일반 텍스트만 취합
                parent_tag, parent_attrs = self.path[-1] if self.path else (None, {})
                if parent_tag == 'button':
                    self.corrected_text_list.append(data)
                elif not self.skip_text_for_original and parent_tag != 'span':
                    self.corrected_text_list.append(data)
            else:
                # relative span 밖의 일반 텍스트는 그대로 취함
                self.corrected_text_list.append(data)
                
        # --- 2. 교정 사유 데이터 추출 ---
        if self.in_dl:
            if self.current_dt:
                self.dt_text += data
            elif self.current_dd:
                self.dd_text_list.append(data)
                parent_tag, parent_attrs = self.path[-1] if self.path else (None, {})
                if parent_tag == 'button':
                    self.dd_button_texts.append(data.strip())

def parse_html_file():
    html_path = r"C:\Users\user\.gemini\antigravity\brain\cc0d38ba-0532-4b0c-8071-d471bd5a20ea\scratch\actual_result.html"
    if not os.path.exists(html_path):
        print("HTML file not found!")
        return

    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()

    parser = NaraHTMLParser()
    parser.feed(html)

    # 결과 취합 및 출력
    corrected_sentence = "".join(parser.corrected_text_list).strip()
    print("=== 교정 완료본 ===")
    print(corrected_sentence)

    print("\n=== 교정 사유 ===")
    reasons = []
    for card in parser.cards:
        wrong = ""
        right = ""
        reason = ""
        
        for dt_t, dd_t, dd_btns in card:
            dt_t = dt_t.strip()
            if "입력 내용" in dt_t:
                wrong = dd_t
            elif "대치어" in dt_t:
                # 대치어 직접 수정하기가 아닌 첫 번째 버튼의 텍스트가 대치어임
                for btn in dd_btns:
                    if btn and "대치어 직접 수정하기" not in btn:
                        right = btn
                        break
                if not right:
                    right = dd_t
            elif "도움말" in dt_t:
                reason = dd_t.replace("자세히 보기", "").strip()
                reason = " ".join(reason.split()) # 공백 및 개행 정규화
                
        if wrong:
            reasons.append(f"[{wrong} ➡️ {right}] : {reason}")
            
    for r in reasons:
        print(r)

if __name__ == '__main__':
    parse_html_file()
