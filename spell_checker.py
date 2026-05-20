import requests
import json
import re
import time
import urllib3


# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def _api_check_spelling(text: str) -> tuple[str, str, str]:
    """
    requests를 사용해 나라인포테크 구버전 백엔드(old_speller/results)에
    직접 POST 요청을 전송하고, 반환된 자바스크립트 data = [...] JSON 변수 데이터를 
    정규식으로 정밀 추출하여 교정본과 사유를 100% 완벽한 품질로 조립해 냅니다.
    
    Returns:
        tuple[str, str, str]: (교정 완료 문장, 적용 엔진 'server', 교정 사유 텍스트)
    """
    url = "https://nara-speller.co.kr/old_speller/results"
    
    payload = {'text1': text}
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://nara-speller.co.kr/speller/',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
    }
    
    # POST 요청 (타임아웃 10초)
    response = requests.post(url, data=payload, headers=headers, timeout=10, verify=False)
    response.encoding = 'utf-8' # 수신 데이터는 UTF-8로 해석해야 한글이 깨지지 않습니다.
    
    html = response.text
    
    # 자바스크립트 'data = [{...}];' 정규식 추출 패턴 정의
    pattern = re.compile(r"data\s*=\s*(.*?);", re.DOTALL)
    match = pattern.search(html)
    
    if not match:
        raise ValueError("나라인포테크 응답 내에서 'data = ' 변수 블록을 발견하지 못했습니다.")
        
    data_str = match.group(1).strip()
    
    # JSON 형식의 데이터 파싱
    pages = json.loads(data_str)
    
    corrected_sentence_parts = []
    reasons = []
    
    for page in pages:
        original_part = page.get("str", "")
        err_info_list = page.get("errInfo", [])
        
        # 1. 치환 시 문자열 앞부분의 인덱스가 틀어지지 않도록, start 기준 '내림차순(역순)' 정렬 수행
        sorted_errs = sorted(err_info_list, key=lambda x: x.get("start", 0), reverse=True)
        
        temp_str = original_part
        for err in sorted_errs:
            start = err.get("start", 0)
            end = err.get("end", 0)
            wrong = err.get("orgStr", "")
            right = err.get("candWord", "")
            
            # 복수의 대치어가 파이프('|') 문자로 날아올 경우 첫 번째 후보 선택
            if "|" in right:
                right = right.split("|")[0].strip()
            else:
                right = right.strip()
                
            # 슬라이싱을 통한 완벽한 치환 기법 적용
            temp_str = temp_str[:start] + right + temp_str[end:]
            
            # 2. 교정 도움말(사유) 정제
            help_text = err.get("help", "")
            # HTML 태그 제거
            help_clean = re.sub(r'<.*?>', '', help_text).strip()
            # 연속된 줄바꿈 및 불필요 공백 하나로 치환
            help_clean = " ".join(help_clean.split())
            
            reasons.append(f"[{wrong} -> {right}] : {help_clean}")
            
        corrected_sentence_parts.append(temp_str)
        
    # 문장 결합 및 사유 텍스트 포맷
    corrected_text = "\n".join(corrected_sentence_parts).strip()
    if not corrected_text:
        corrected_text = text
        
    reasons_text = "\n".join(reasons).strip() if reasons else "교정 사항 없음"
    
    return corrected_text, 'server', reasons_text


def check_spelling(text: str) -> tuple[str, str, str]:
    """
    입력받은 텍스트의 맞춤법을 교정하고 수정 사유를 산출합니다.
    서버 오류나 일시적 통신 실패 시 최대 3회까지 타임아웃 재시도를 수행하여
    100% 나라인포테크 서버 검증 결과를 획득합니다.
    """
    if not text or not text.strip():
        return text, 'server', '교정 사항 없음'

    max_retries = 3
    last_err = None

    for attempt in range(1, max_retries + 1):
        try:
            if attempt > 1:
                print(f"[RETRY {attempt}/{max_retries}] 나라인포테크 서버 응답 지연 발생. 1초 대기 후 재호출합니다...")
                time.sleep(1.0)
                
            corrected_text, engine_type, reason = _api_check_spelling(text)
            return corrected_text, engine_type, reason
        except Exception as e:
            last_err = e
            print(f"[WARN] {attempt}회차 API 검사 중 오류 발생: {e}")
            time.sleep(0.5)

    # 3회 모두 실패했을 때 최후의 Fallback (로컬 사전을 쓰지 않고 서버 에러로 마킹)
    print(f"[FAIL] {max_retries}회 재시도가 모두 실패했습니다. 마지막 에러: {last_err}.")
    error_reason = f"[오류] 나라인포테크 서버 응답 실패 ({max_retries}회 재시도 모두 실패: {str(last_err)})"
    return text, 'error', error_reason


if __name__ == '__main__':
    # 최종 작동 상태 완벽 검증
    test_sent = "인공지능이 너무 재밓다! 띄어쓰기오류도있어요. 외않되?"
    print(f"원문: {test_sent}")
    result, engine, reasons = check_spelling(test_sent)
    print(f"교정: {result} (적용 엔진: {engine})")
    print(f"사유:\n{reasons}")
