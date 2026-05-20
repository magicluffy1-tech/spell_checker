"""
sheets_handler.py
데이터 입출력 핸들러
- gspread / google-auth 직접 쓰기 연동 완전 제거
- 지원 방식:
    1) 엑셀(.xlsx) / CSV 파일 업로드 (Streamlit UploadedFile 객체)
    2) 구글 시트 공유 링크 (뷰어 권한, 읽기 전용) CSV 내보내기 URL 변환
- 결과 DataFrame → 엑셀/CSV 바이트 다운로드 유틸리티 포함
"""

import io
import re
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
    구글의 다양한 세션, export 및 임시 서브도메인 다운로드 URL 등 모든 비표준 패턴을 완벽히 흡수한다.
    """
    cleaned_url = url.strip()
    
    # 1단계: 표준적인 /spreadsheets/d/{id} 패턴 매칭
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", cleaned_url)
    if m:
        return m.group(1)

    # 2단계: 표준 edit/view 컴파일 정규식 사용 시도
    for pattern in (_GSHEET_EDIT_PATTERN, _GSHEET_VIEW_PATTERN):
        m = pattern.match(cleaned_url)
        if m:
            return m.group(1)

    # 3단계: /d/{id} 형태 또는 경로 구분자 뒤의 40~50자리 고유 ID 강제 매칭
    # 구글 시트 ID는 기본적으로 약 44글자의 알파벳 대소문자, 숫자, -, _ 로 구성됨
    m = re.search(r"/d/([a-zA-Z0-9_-]{40,50})", cleaned_url)
    if m:
        return m.group(1)

    # 4단계: doc-XX-sheets.googleusercontent.com 등 비표준 URL에서 ID 단독 추출
    # (예: /o3lcptcusgodhh2c7e7ao7aglk/.../*/1zM7O82QzXHbuLEw4YgS3nCPAzEg5NarY9fYb5ZQTRPI 등)
    # 슬래시 뒤 또는 파일 경로 끝에 존재하는 40~50글자 ID 포착
    m = re.search(r"(?:/|\*=)([a-zA-Z0-9_-]{40,50})(?:[/?]|$)", cleaned_url)
    if m:
        return m.group(1)

    # 5단계: 정 안될 경우 URL 전체에서 40~50자리 글자군 최초 포착 매칭
    m = re.search(r"([a-zA-Z0-9_-]{40,50})", cleaned_url)
    if m:
        return m.group(1)

    return None


def _gsheet_url_to_csv_url(url: str, gid: Optional[str] = None) -> Optional[str]:
    """
    구글 시트 공유 링크를 표준 CSV 내보내기 URL로 완벽 세탁 및 변환.
    비표준 googleusercontent 등의 임시 도메인도 표준 docs.google.com으로 복원하여 400 에러를 원천 차단한다.
    """
    sheet_id = _extract_sheet_id(url)
    if not sheet_id:
        return None

    # gid 추출 (URL에 포함된 경우)
    if gid is None:
        m = re.search(r"[#&?]gid=(\d+)", url)
        gid = m.group(1) if m else "0"

    return (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}"
        f"/export?format=csv&gid={gid}"
    )


# ──────────────────────────────────────────────
# 2. 데이터 로드 함수
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
) -> tuple[pd.DataFrame, list[dict]]:
    """
    구글 시트 공유 링크(뷰어 권한 이상)에서 데이터를 로드한다.
    링크 공개 설정이 '링크가 있는 모든 사용자' 이상이어야 한다.

    Args:
        url: 구글 시트 공유 URL
        text_column: 검사할 열 이름. None이면 첫 번째 열 사용.
        gid: 특정 시트 탭의 gid (없으면 URL에서 자동 추출)

    Returns:
        (DataFrame 전체, records 리스트)
    """
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

    Args:
        uploaded_file: st.file_uploader에서 반환된 UploadedFile 객체
        text_column: 검사할 열 이름. None이면 첫 번째 열 사용.

    Returns:
        (DataFrame 전체, records 리스트)
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
# 3. 결과 다운로드 유틸리티
# ──────────────────────────────────────────────

def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    """
    DataFrame을 .xlsx 바이트로 변환 (st.download_button용).
    """
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="맞춤법검사결과")
    return buffer.getvalue()


def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    """
    DataFrame을 UTF-8 BOM CSV 바이트로 변환 (한글 엑셀 호환).
    """
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
