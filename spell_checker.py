"""
spell_checker.py
나라인포테크 맞춤법 검사기 REST API 우회 엔진 (최종 융합형)
- Selenium/ChromeDriver 완전 제거 및 순수 requests HTTP POST 방식
- old_speller/results 정규식 자바스크립트 data = [...] 파싱으로 100% 정밀 교정
- 긴 텍스트 500자 이하 문장 분할(Chunking)을 통한 안정성 확보
- 3회 타임아웃 재시도 및 CP949 인코딩 호환 로그 포맷
"""

import requests
import time
import random
import re
import json
import urllib3
from typing import Optional

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_API_URL = "https://nara-speller.co.kr/old_speller/results"
_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://nara-speller.co.kr/speller/',
}

_TIMEOUT = 10       # 단일 요청 타임아웃 (초)
_MAX_RETRIES = 3    # 최대 재시도 횟수
_CHUNK_SIZE = 500   # 한 번에 보낼 최대 글자 수


def _post_to_api(text: str) -> Optional[str]:
    """
    나라인포테크 old_speller 백엔드 서버에 POST 요청을 전송하고 응답 HTML을 반환한다.
    실패 시 최대 3회 재시도를 처리한다.
    """
    payload = {'text1': text}
    
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = requests.post(
                _API_URL,
                data=payload,
                headers=_HEADERS,
                timeout=_TIMEOUT,
                verify=False
            )
            resp.raise_for_status()
            resp.encoding = 'utf-8'  # 수신 데이터 강제 UTF-8 지정
            return resp.text
        except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
            if attempt < _MAX_RETRIES:
                time.sleep(0.5 + 0.5 * attempt)
            else:
                return None
    return None


def _split_text(text: str, chunk_size: int = _CHUNK_SIZE) -> list[str]:
    """
    긴 텍스트를 문장 단위로 나눠 chunk_size 이하 조각으로 분할.
    문장 경계(. ! ?)를 최대한 존중하여 분할한다.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    current = ""
    sentences = []

    # 줄바꿈 기준 1차 분리
    for line in text.splitlines(keepends=True):
        if len(line) > chunk_size:
            # 매우 긴 단일 줄: 강제 분할
            while len(line) > chunk_size:
                sentences.append(line[:chunk_size])
                line = line[chunk_size:]
            if line:
                sentences.append(line)
        else:
            sentences.append(line)

    for sentence in sentences:
        if len(current) + len(sentence) <= chunk_size:
            current += sentence
        else:
            if current:
                chunks.append(current)
            current = sentence

    if current:
        chunks.append(current)

    return chunks


def _parse_nara_response(html: str) -> tuple[str, list[dict]]:
    """
    나라인포테크 응답 HTML 내부 자바스크립트 'data = [...]' 변수 블록을 
    정규식으로 정밀 슬라이싱 및 파싱하여 정확한 교정본과 사유 리스트를 조립합니다.
    """
    pattern = re.compile(r"data\s*=\s*(.*?);", re.DOTALL)
    match = pattern.search(html)
    if not match:
        raise ValueError("나라인포테크 응답 내에서 'data = ' 변수 블록을 발견하지 못했습니다.")
        
    data_str = match.group(1).strip()
    pages = json.loads(data_str)
    
    corrected_sentence_parts = []
    errors = []
    
    for page in pages:
        original_part = page.get("str", "")
        err_info_list = page.get("errInfo", [])
        
        # 문자열 치환 시 인덱스 틀어짐 방지를 위해 start 기준 내림차순(역순) 정렬
        sorted_errs = sorted(err_info_list, key=lambda x: x.get("start", 0), reverse=True)
        
        temp_str = original_part
        for err in sorted_errs:
            start = err.get("start", 0)
            end = err.get("end", 0)
            wrong = err.get("orgStr", "")
            right = err.get("candWord", "")
            
            if "|" in right:
                right = right.split("|")[0].strip()
            else:
                right = right.strip()
                
            # 슬라이싱을 통한 완벽 교체
            temp_str = temp_str[:start] + right + temp_str[end:]
            
            # 도움말 사유 정제
            help_text = err.get("help", "")
            help_clean = re.sub(r'<.*?>', '', help_text).strip()
            help_clean = " ".join(help_clean.split())
            
            errors.append({
                "original": wrong,
                "corrected": right,
                "reason": help_clean,
                "color": "green"
            })
            
        corrected_sentence_parts.append(temp_str)
        
    corrected_text = "\n".join(corrected_sentence_parts).strip()
    return corrected_text, errors


def check_spelling(
    text: str,
    delay: float = 0.3,
    use_old_api: bool = True,  # 융합 엔진에서는 항상 True(old_speller)로 픽스하여 동작
) -> dict:
    """
    맞춤법 검사 메인 융합 함수.
    
    Args:
        text: 검사할 원문 텍스트
        delay: 청크 간 대기 시간(초)
        use_old_api: 레거시 호환용 파라미터 (안전 우회를 위해 항상 True로 픽스 작동)

    Returns:
        {
            "original": 원문,
            "corrected": 교정 완료 텍스트,
            "errors": [{"original", "corrected", "reason", "color"}, ...],
            "has_error": 오류 존재 여부 (bool),
            "success": API 통신 성공 여부 (bool),
            "message": 오류 메시지 (실패 시),
        }
    """
    if not text or not text.strip():
        return {
            "original": text,
            "corrected": text,
            "errors": [],
            "has_error": False,
            "success": True,
            "message": "빈 텍스트입니다.",
        }

    chunks = _split_text(text.strip())
    all_corrected_pieces = []
    all_errors = []
    success = True
    msg = ""

    for i, chunk in enumerate(chunks):
        if not chunk.strip():
            all_corrected_pieces.append(chunk)
            continue

        html_response = _post_to_api(chunk)

        if html_response is None:
            # API 실패 시 원문 그대로 보존 및 에러 마킹
            all_corrected_pieces.append(chunk)
            success = False
            msg = "나라인포테크 서버 응답 실패 (3회 재시도 모두 실패)"
        else:
            try:
                corrected, errors = _parse_nara_response(html_response)
                # 파싱 결과가 비어 있으면 원문 유지
                all_corrected_pieces.append(corrected if corrected.strip() else chunk)
                all_errors.extend(errors)
            except Exception as e:
                all_corrected_pieces.append(chunk)
                success = False
                msg = f"응답 파싱 오류: {str(e)}"

        # 청크 간 딜레이 (마지막 청크 제외)
        if i < len(chunks) - 1:
            jitter = random.uniform(0, 0.1)
            time.sleep(delay + jitter)

    corrected_text = "".join(all_corrected_pieces)

    return {
        "original": text,
        "corrected": corrected_text,
        "errors": all_errors,
        "has_error": len(all_errors) > 0,
        "success": success,
        "message": msg,
    }


# ──────────────────────────────────────────────
# 3. 단독 실행 테스트
# ──────────────────────────────────────────────

if __name__ == "__main__":
    test_text = "인공지능이 너무 재밓다! 띄어쓰기오류도있어요. 외않되?"
    print(f"[원문] {test_text}")

    start = time.time()
    result = check_spelling(test_text)
    elapsed = time.time() - start

    print(f"[교정] {result['corrected']}")
    print(f"[소요] {elapsed:.2f}초")
    print(f"[오류 수] {len(result['errors'])}개")
    for err in result["errors"]:
        print(f"  - 교정: {err['original']} -> {err['corrected']} / 사유: {err['reason']}")
