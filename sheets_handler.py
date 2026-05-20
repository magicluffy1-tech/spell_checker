"""
sheets_handler.py

데이터 입출력 핸들러
- gspread / google-auth 직접 쓰기 연동 완전 제거
- 지원 방식:
  1) 엑셀(.xlsx) / CSV 파일 업로드 (Streamlit UploadedFile 객체)
  2) 구글 시트 공유 링크 (뷰어 권한, 읽기 전용) CSV 내보내기 URL 변환
     → 탭(시트) 이름으로 특정 탭 지정 가능
- 결과 DataFrame → 엑셀/CSV 바이트 다운로드 유틸리티 포함
"""

import io
import re
import html
from typing import Optional
import pandas as pd
import requests

# 공유 링크 → CSV 내보내기 URL 변환에 사용하는 정규식 패턴
_GSHEET_EDIT_PATTERN = re.compile(
    r"https://docs\.google\.com/spreadsheets/d/([^/]+)/edit.*"
)
_GSHEET_VIEW_PATTERN = re.compile(
    r"https://docs\.google\.com/spreadsheets/d/([^/]+)/view.*"
)

# ──────────────────────────────────────────────
# 1. 구글 시트 공유 링크 → CSV URL 변환
# ──────────────────────────────────────────────

def _extract_sheet_id(url: str) -> Optional[str]:
    """
    구글 시트 공유 URL에서 스프레드시트 ID를 추출한다.
    """
    cleaned_url = url.strip()

    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", cleaned_url)
    if m:
        return m.group(1)

    for pattern in (_GSHEET_EDIT_PATTERN, _GSHEET_VIEW_PATTERN):
        m = pattern.match(cleaned_url)
        if m:
            return m.group(1)

    m = re.search(r"/d/([a-zA-Z0-9_-]{40,50})", cleaned_url)
    if m:
        return m.group(1)

    m = re.search(r"(?:/|\*=)([a-zA-Z0-9_-]{40,50})(?:[/?]|$)", cleaned_url)
    if m:
        return m.group(1)

    m = re.search(r"([a-zA-Z0-9_-]{40,50})", cleaned_url)
    if m:
        return m.group(1)

    return None


def _gsheet_url_to_csv_url(url: str, gid: Optional[str] = None) -> Optional[str]:
    """
    구글 시트 공유 링크를 표준 CSV 내보내기 URL로 변환.
    gid가 주어지면 해당 탭, 없으면 URL의 gid 파라미터 사용 (기본값 "0").
    """
    sheet_id = _extract_sheet_id(url)
    if not sheet_id:
        return None

    if gid is None:
        m = re.search(r"[#&?]gid=(\d+)", url)
        gid = m.group(1) if m else "0"

    return (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}"
        f"/export?format=csv&gid={gid}"
    )


# ──────────────────────────────────────────────
# 2. 탭(시트) 목록 조회 기능 (NEW)
# ──────────────────────────────────────────────

def get_sheet_tabs(url: str) -> list[dict]:
    """
    구글 시트 공유 링크에서 모든 탭(시트) 이름과 gid 목록을 조회한다.
    
    HTML을 파싱하여 탭 정보를 추출한다.
    공유 설정이 '링크가 있는 모든 사용자'이어야 한다.
    
    Returns:
        [{"name": "시트이름", "gid": "숫자"}, ...]
        조회 실패 시 빈 리스트 반환
    """
    sheet_id = _extract_sheet_id(url)
    if not sheet_id:
        return []

    # 구글 시트 HTML 페이지에서 시트 탭 정보 파싱
    html_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
    
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(html_url, headers=headers, timeout=15, verify=True)
        resp.raise_for_status()
        content = resp.text

        tabs = []

        # 방법 1: bootstrapData 또는 sheets 배열에서 gid + name 추출
        # 구글 시트 HTML에는 JSON 형태로 시트 정보가 내장되어 있음
        # 패턴: ["시트이름",null,null,null,null,null,null,null,null,숫자gid]
        pattern1 = re.findall(
            r'"([^"]+)",(?:null,){5,10}(\d{5,})',
            content
        )
        if pattern1:
            seen = set()
            for name, gid in pattern1:
                key = f"{name}:{gid}"
                if key not in seen and len(name) < 50:
                    seen.add(key)
                    tabs.append({"name": html.unescape(name), "gid": gid})
            if tabs:
                return tabs

        # 방법 2: data-id 속성과 aria-label 조합 (구버전 HTML 구조)
        pattern2 = re.findall(
            r'data-id="(\d+)"[^>]*aria-label="([^"]+)"',
            content
        )
        if not pattern2:
            pattern2 = re.findall(
                r'aria-label="([^"]+)"[^>]*data-id="(\d+)"',
                content
            )
            pattern2 = [(gid, name) for name, gid in pattern2]

        if pattern2:
            seen = set()
            for gid, name in pattern2:
                if gid not in seen:
                    seen.add(gid)
                    tabs.append({"name": html.unescape(name), "gid": gid})
            if tabs:
                return tabs

        # 방법 3: gid=숫자 패턴만이라도 추출 (탭 이름 없이)
        gids_found = re.findall(r'[#&?]gid=(\d+)', content)
        seen_gids = set()
        for gid in gids_found:
            if gid not in seen_gids:
                seen_gids.add(gid)
                tabs.append({"name": f"시트 (gid={gid})", "gid": gid})
        
        return tabs

    except Exception:
        return []


def find_gid_by_sheet_name(url: str, sheet_name: str) -> Optional[str]:
    """
    탭 이름으로 해당 탭의 gid를 찾는다.
    
    Args:
        url: 구글 시트 공유 URL
        sheet_name: 찾고자 하는 탭 이름 (예: "창체_완료")
    
    Returns:
        gid 문자열 또는 None (탭을 찾지 못한 경우)
    """
    tabs = get_sheet_tabs(url)
    
    # 완전 일치 우선
    for tab in tabs:
        if tab["name"] == sheet_name:
            return tab["gid"]
    
    # 대소문자 무시 매칭
    lower_name = sheet_name.lower()
    for tab in tabs:
        if tab["name"].lower() == lower_name:
            return tab["gid"]
    
    # 부분 일치 (포함 여부)
    for tab in tabs:
        if sheet_name in tab["name"] or tab["name"] in sheet_name:
            return tab["gid"]
    
    return None


# ──────────────────────────────────────────────
# 3. 데이터 로드 함수
# ──────────────────────────────────────────────

def get_raw_data_from_dataframe(df: pd.DataFrame, text_column: str) -> list[dict]:
    """
    이미 로드된 DataFrame에서 검사 대상 텍스트 목록을 추출한다.

    Args:
        df: 업로드된 파일에서 읽어온 DataFrame
        text_column: 맞춤법 검사를 수행할 열 이름

    Returns:
        [{"row_index": int, "original_text": str}, ...]
    """
    if text_column not in df.columns:
        raise ValueError(f"'{text_column}' 열을 찾을 수 없습니다. 실제 열 이름을 확인하세요.")

    records = []
    for idx, row in df.iterrows():
        cell_value = row[text_column]
        if pd.isna(cell_value) or str(cell_value).strip() == "":
            continue
        records.append({
            "row_index": idx,
            "original_text": str(cell_value).strip(),
        })
    return records


def get_raw_data_from_public_url(
    url: str,
    text_column: Optional[str] = None,
    gid: Optional[str] = None,
    sheet_name: Optional[str] = None,
) -> tuple[pd.DataFrame, list[dict]]:
    """
    구글 시트 공유 링크(뷰어 권한 이상)에서 데이터를 로드한다.
    
    sheet_name이 주어지면 해당 이름의 탭을 자동으로 찾아 로드한다.
    gid가 주어지면 sheet_name보다 우선 적용된다.

    Args:
        url: 구글 시트 공유 URL
        text_column: 검사할 열 이름. None이면 첫 번째 열 사용.
        gid: 특정 시트 탭의 gid (없으면 URL에서 자동 추출)
        sheet_name: 탭 이름으로 gid를 자동 검색 (gid가 없을 때 사용)

    Returns:
        (DataFrame 전체, records 리스트)
    """
    # sheet_name이 주어졌고 gid가 없으면 이름으로 gid 탐색
    if sheet_name and not gid:
        found_gid = find_gid_by_sheet_name(url, sheet_name)
        if found_gid is not None:
            gid = found_gid
        else:
            raise ValueError(
                f"'{sheet_name}' 탭을 찾을 수 없습니다.\n"
                "탭 이름이 정확한지 확인하거나, 시트 공유 설정을 점검하세요."
            )

    csv_url = _gsheet_url_to_csv_url(url, gid=gid)
    if not csv_url:
        raise ValueError("유효한 구글 시트 URL이 아닙니다. 공유 링크를 다시 확인하세요.")

    try:
        # Streamlit Cloud 등 프로덕션 환경의 안전한 리다이렉션 처리를 위해 verify=True를 기본으로 수행
        resp = requests.get(csv_url, timeout=15, verify=True)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        status_code = resp.status_code if 'resp' in locals() else None
        if status_code in (400, 403):
            raise PermissionError(
                "구글 시트 데이터를 로드하지 못했습니다.\n\n"
                "스프레드시트의 일반 액세스 권한이 '링크가 있는 모든 사용자' (뷰어)로 열려 있는지 꼭 확인해 주세요!\n\n"
                "💡 **해결 방법 (30초 소요):**\n"
                "1. 구글 시트 우측 상단의 **[공유]** 버튼 클릭\n"
                "2. 일반 액세스를 **'링크가 있는 모든 사용자'**로 변경\n"
                "3. **[링크 복사]**를 누르고 해당 표준 공유 주소를 복사해 넣어주세요."
            ) from e
        raise ConnectionError(f"구글 시트를 불러오지 못했습니다: {e}") from e
    except requests.exceptions.RequestException as e:
        # 혹시 모를 로컬 SSL 인증서 만료 등 오류 시 verify=False로 자동 폴백 재시도하여 상호 호환성 극대화
        try:
            resp = requests.get(csv_url, timeout=15, verify=False)
            resp.raise_for_status()
        except Exception as fallback_e:
            raise ConnectionError(f"네트워크 오류: {fallback_e}") from fallback_e

    df = pd.read_csv(io.StringIO(resp.text), dtype=str)
    if df.empty:
        raise ValueError("구글 시트가 비어 있습니다.")

    col = text_column if text_column and text_column in df.columns else df.columns[0]
    records = get_raw_data_from_dataframe(df, col)
    return df, records


def load_uploaded_file(
    uploaded_file,
    text_column: Optional[str] = None,
) -> tuple[pd.DataFrame, list[dict]]:
    """
    Streamlit UploadedFile 객체(.xlsx, .xls, .csv)를 DataFrame으로 변환하고
    검사 대상 records를 추출한다.
    """
    filename = uploaded_file.name.lower()
    if filename.endswith(".csv"):
        df = pd.read_csv(uploaded_file, encoding="utf-8-sig", dtype=str)
    elif filename.endswith((".xlsx", ".xls")):
        df = pd.read_excel(uploaded_file, engine="openpyxl", dtype=str)
    else:
        raise ValueError("지원하지 않는 파일 형식입니다. .xlsx, .xls, .csv 파일을 업로드하세요.")

    if df.empty:
        raise ValueError("파일이 비어 있습니다.")

    col = text_column if text_column and text_column in df.columns else df.columns[0]
    records = get_raw_data_from_dataframe(df, col)
    return df, records


# ──────────────────────────────────────────────
# 4. 결과 다운로드 유틸리티
# ──────────────────────────────────────────────

def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    """DataFrame을 .xlsx 바이트로 변환 (st.download_button용)."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="맞춤법검사결과")
    return buffer.getvalue()


def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    """DataFrame을 UTF-8 BOM CSV 바이트로 변환 (한글 엑셀 호환)."""
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
