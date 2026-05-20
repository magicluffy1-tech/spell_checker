"""
app.py
생기부 맞춤법 검사기 - Streamlit 메인 앱
- Selenium / gspread 직접 쓰기 UI 완전 제거
- 순수 requests REST API 기반 초고속 맞춤법 검사
- 입력: 엑셀/CSV 업로드 OR 구글 시트 공유 링크(읽기 전용)
- 출력: 교정 결과 테이블 + 엑셀/CSV 다운로드
- Premium Glassmorphism Dark Theme & Micro-animations 적용
"""

import time
import random

import pandas as pd
import streamlit as st

from spell_checker import check_spelling
from sheets_handler import (
    df_to_csv_bytes,
    df_to_excel_bytes,
    get_raw_data_from_dataframe,
    get_raw_data_from_public_url,
    load_uploaded_file,
)

# ──────────────────────────────────────────────
# 페이지 설정 (Premium Theme & Responsive Layout)
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="Premium 생기부 맞춤법 검사기",
    page_icon="✏️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# 커스텀 Premium CSS 디자인 스타일링
# ──────────────────────────────────────────────
st.markdown("""
    <style>
        /* 메인 다크 웹 테마 및 폰트 */
        .main {
            background-color: #0d0e15;
            color: #f1f5f9;
            font-family: 'Outfit', 'Inter', 'Noto Sans KR', sans-serif;
        }
        .stApp {
            background-color: #0d0e15;
        }
        
        /* Glassmorphism 카드 컨테이너 */
        div[data-testid="stVerticalBlock"] > div:has(div.element-container) {
            background: rgba(255, 255, 255, 0.02);
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 16px;
            border: 1px solid rgba(255, 255, 255, 0.05);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        div[data-testid="stVerticalBlock"] > div:has(div.element-container):hover {
            border-color: rgba(99, 102, 241, 0.2);
            box-shadow: 0 8px 32px 0 rgba(99, 102, 241, 0.05);
            transform: translateY(-2px);
        }
        
        /* 프리미엄 그라데이션 헤더 배너 */
        .title-container {
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 50%, #c084fc 100%);
            border-radius: 20px;
            padding: 40px;
            margin-bottom: 30px;
            box-shadow: 0 20px 40px -15px rgba(79, 70, 229, 0.4);
            position: relative;
            overflow: hidden;
        }
        .title-container::before {
            content: "";
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 60%);
            animation: rotate 20s linear infinite;
        }
        @keyframes rotate {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .title-text {
            color: #ffffff;
            font-size: 2.8rem;
            font-weight: 800;
            margin: 0;
            letter-spacing: -0.03em;
            text-shadow: 0 2px 10px rgba(0,0,0,0.2);
            position: relative;
            z-index: 1;
        }
        .subtitle-text {
            color: rgba(255, 255, 255, 0.9);
            font-size: 1.15rem;
            font-weight: 400;
            margin-top: 12px;
            position: relative;
            z-index: 1;
            letter-spacing: -0.01em;
        }
        
        /* 메트릭 카드 시각화 */
        .metric-card {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 16px;
            padding: 24px;
            text-align: center;
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.15);
            transition: all 0.3s ease;
        }
        .metric-card:hover {
            border-color: rgba(56, 189, 248, 0.3);
            transform: translateY(-3px);
        }
        
        /* 프리미엄 배지 스타일 */
        .badge-live {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: #ffffff;
            padding: 4px 10px;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 700;
            letter-spacing: 0.05em;
            display: inline-block;
            margin-bottom: 10px;
            box-shadow: 0 4px 12px rgba(16, 185, 129, 0.2);
        }
        
        /* 버튼 & 슬라이더 모던화 */
        .stButton>button {
            border-radius: 12px !important;
            padding: 12px 24px !important;
            font-weight: 600 !important;
            transition: all 0.2s ease !important;
        }
        .stButton>button:hover {
            transform: scale(1.01);
            box-shadow: 0 8px 20px rgba(79, 70, 229, 0.2) !important;
        }
    </style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# 사이드바: 설정 및 제어판
# ──────────────────────────────────────────────
with st.sidebar:
    st.markdown('<span class="badge-live">SYSTEM CONTROL</span>', unsafe_allow_html=True)
    st.title("⚙️ 설정 및 옵션")
    
    st.subheader("📂 데이터 입력 방식")
    input_mode = st.radio(
        "입력 방식 선택",
        options=["파일 업로드 (엑셀/CSV)", "구글 시트 공유 링크"],
        index=0,
        help="엑셀(.xlsx), CSV 파일 업로드 또는 '링크가 있는 모든 사용자' 권한의 구글 시트 URL 사용",
    )

    st.divider()

    st.subheader("🔧 검사 옵션")
    delay_sec = st.slider(
        "청크 간 대기 시간 (초)",
        min_value=0.1,
        max_value=2.0,
        value=0.3,
        step=0.1,
        help="REST API 방식으로 서버 차단 위험이 매우 낮습니다. 0.3초 권장.",
    )
    chunk_delay_every = st.slider(
        "N줄마다 추가 휴식",
        min_value=5,
        max_value=50,
        value=20,
        step=5,
        help="지정한 줄 수마다 3초 추가 휴식. 대량 처리 시 서버 부하 방지용.",
    )
    use_old_api = st.toggle(
        "구버전 API 사용 (안정적)",
        value=True,
        help="old_speller 엔드포인트 사용. 차단 없이 가장 안정적으로 작동합니다.",
    )

    st.divider()
    st.caption(
        "ℹ️ 본 앱은 가상 브라우저 없이 나라인포테크 REST API 백엔드를 최적화 우회 호출하여 "
        "서버 리소스를 보호하며 광속으로 처리를 수행합니다."
    )


# ──────────────────────────────────────────────
# 메인 프리미엄 헤더 배너
# ──────────────────────────────────────────────
st.markdown("""
    <div class="title-container">
        <h1 class="title-text">✏️ 생기부 맞춤법 검사기</h1>
        <p class="subtitle-text">초고속 비-브라우저 REST API 우회 기술 탑재 · 500자 단위 자동 문장 분할 매직 및 실시간 결과 대시보드</p>
    </div>
""", unsafe_allow_html=True)

# ── 세션 상태 초기화 ───────────────────────────
for key, default in {
    "df_original": None,
    "df_result": None,
    "text_column": None,
    "processing": False,
    "done": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ──────────────────────────────────────────────
# 1단계: 데이터 로드
# ──────────────────────────────────────────────
st.header("1️⃣ 데이터 불러오기")

df_loaded: pd.DataFrame | None = None
load_error: str = ""

col_load_1, col_load_2 = st.columns([2, 1])

with col_load_1:
    if input_mode == "파일 업로드 (엑셀/CSV)":
        uploaded = st.file_uploader(
            "엑셀(.xlsx) 또는 CSV 파일 업로드",
            type=["xlsx", "xls", "csv"],
            help="첫 번째 행이 헤더(열 이름)여야 합니다.",
        )
        if uploaded:
            try:
                df_loaded, _ = load_uploaded_file(uploaded)
                st.success(f"✅ 파일 로드 완료: {len(df_loaded)}행 × {len(df_loaded.columns)}열")
            except Exception as e:
                load_error = str(e)
    else:  # 구글 시트 공유 링크
        sheet_url = st.text_input(
            "구글 시트 공유 링크 입력",
            placeholder="https://docs.google.com/spreadsheets/d/...",
            help="파일 → 공유 → '링크가 있는 모든 사용자' 뷰어 권한으로 설정 후 링크 복사",
        )
        if sheet_url:
            with st.spinner("구글 시트 로드 중..."):
                try:
                    df_loaded, _ = get_raw_data_from_public_url(sheet_url)
                    st.success(f"✅ 구글 시트 로드 완료: {len(df_loaded)}행 × {len(df_loaded.columns)}열")
                except PermissionError as e:
                    load_error = f"🔒 접근 권한 오류: {e}"
                except Exception as e:
                    load_error = str(e)

with col_load_2:
    st.markdown("### 💡 연동 꿀팁")
    st.info(
        "임의의 행이나 열도 완벽히 지원합니다. "
        "파일 또는 구글 시트의 헤더를 감지하여 원하는 텍스트 컬럼을 자유롭게 타겟 지정할 수 있습니다."
    )

if load_error:
    st.error(f"❌ {load_error}")
    with st.expander("🛠️ 공유 링크 연동 실패 해결법", expanded=True):
        st.markdown("""
        1. **구글 시트 공유 범위가 올바른가요?**
           - 구글 시트 우측 상단 **[공유]** -> 일반 액세스가 **'링크가 있는 모든 사용자'**로 되어 있으며 권한이 **'뷰어'**인지 꼭 확인하세요.
        2. **올바른 URL 형식인가요?**
           - 주소창 전체 주소를 누락 없이 붙여넣으셨는지 점검하세요.
        """)

# 데이터 프리뷰 + 열 선택
if df_loaded is not None:
    with st.expander("📋 데이터 미리보기 (상위 5행)", expanded=True):
        st.dataframe(df_loaded.head(5), use_container_width=True)

    text_col = st.selectbox(
        "맞춤법을 검사할 열(컬럼) 선택",
        options=list(df_loaded.columns),
        index=0,
        help="맞춤법 검사를 수행할 한글 텍스트(종합의견/특기사항 등)가 들어 있는 열을 선택하세요.",
    )
    st.session_state["df_original"] = df_loaded
    st.session_state["text_column"] = text_col


# ──────────────────────────────────────────────
# 2단계: 맞춤법 검사 실행
# ──────────────────────────────────────────────
st.header("2️⃣ 맞춤법 검사 실행")

can_run = st.session_state["df_original"] is not None

run_btn = st.button(
    "🚀 맞춤법 검사 시작",
    disabled=not can_run,
    use_container_width=True,
    type="primary",
)

if run_btn and can_run:
    df_src = st.session_state["df_original"].copy()
    col = st.session_state["text_column"]

    try:
        records = get_raw_data_from_dataframe(df_src, col)
    except ValueError as e:
        st.error(str(e))
        st.stop()

    total = len(records)
    if total == 0:
        st.warning("검사할 텍스트가 없습니다. 선택한 열에 내용이 있는지 확인하세요.")
        st.stop()

    # 결과 열 추가
    result_col = col + "_교정"
    error_col = col + "_오류수"
    reason_col = col + "_교정사유"
    df_src[result_col] = ""
    df_src[error_col] = 0
    df_src[reason_col] = ""

    progress_bar = st.progress(0, text="검사 준비 중...")
    status_area = st.empty()
    start_total = time.time()

    # 실시간 모니터링 테이블용 
    realtime_results = []
    table_placeholder = st.empty()

    for i, record in enumerate(records):
        row_idx = record["row_index"]
        original = record["original_text"]

        status_area.info(
            f"🔍 [{i + 1}/{total}] 맞춤법 스캔 중: \"{original[:45]}{'...' if len(original) > 45 else ''}\""
        )

        # 고성능 500자 자동 분할 맞춤법 검사 수행
        result = check_spelling(original, delay=delay_sec, use_old_api=use_old_api)

        # 교정 결과 및 오류 데이터 정리
        df_src.at[row_idx, result_col] = result["corrected"]
        df_src.at[row_idx, error_col] = len(result["errors"])
        
        # 교정 사유 문자열 취합
        reasons_list = [f"[{err['original']} -> {err['corrected']}] {err['reason']}" for err in result["errors"]]
        reasons_str = " | ".join(reasons_list) if reasons_list else "교정 사항 없음"
        df_src.at[row_idx, reason_col] = reasons_str

        # 실시간 프리뷰 표 업데이트
        realtime_results.append({
            "행 인덱스": row_idx + 1,
            "원문 텍스트": original,
            "교정 완료본": result["corrected"],
            "총 오류 수": len(result["errors"]),
            "상세 교정사유": reasons_str
        })
        
        # 실시간 테이블 렌더링
        table_placeholder.dataframe(pd.DataFrame(realtime_results), use_container_width=True, hide_index=True)

        progress_bar.progress(
            (i + 1) / total,
            text=f"진행 중: {i + 1}/{total}행 완료",
        )

        # N줄마다 추가 휴식 (서버 보호 및 차단 완전 차단 장치)
        if (i + 1) % chunk_delay_every == 0 and (i + 1) < total:
            status_area.warning(f"⏸️ 서버 보호 장치: {chunk_delay_every}줄 처리 완료 - 3초간 안전 휴식 중...")
            time.sleep(3)
        else:
            jitter = random.uniform(0, 0.1)
            time.sleep(delay_sec + jitter)

    elapsed = time.time() - start_total
    status_area.success(
        f"✅ 맞춤법 검사가 완전히 끝났습니다! 총 {total}행 처리 · 누적 소요시간 {elapsed:.1f}초"
    )
    progress_bar.progress(1.0, text="검사 완료!")

    st.session_state["df_result"] = df_src
    st.session_state["done"] = True


# ──────────────────────────────────────────────
# 3단계: 결과 확인 및 다운로드
# ──────────────────────────────────────────────
if st.session_state["done"] and st.session_state["df_result"] is not None:
    st.header("3️⃣ 결과 확인 및 다운로드")

    df_res = st.session_state["df_result"]
    col = st.session_state["text_column"]
    result_col = col + "_교정"
    error_col = col + "_오류수"

    # 요약 메트릭 계산
    total_rows = len(df_res[df_res[col].notna() & (df_res[col].astype(str).str.strip() != "")])
    error_rows = int((df_res[error_col] > 0).sum())
    total_errors = int(df_res[error_col].sum())

    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">📊 총 검사 행 수</div>
            <div class="metric-value">{total_rows}행</div>
        </div>
        """, unsafe_allow_html=True)
    with col_m2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">⚠️ 오류 발견 행 수</div>
            <div class="metric-value" style="color: #f43f5e;">{error_rows}행</div>
        </div>
        """, unsafe_allow_html=True)
    with col_m3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">✏️ 누적 검출 오류 수</div>
            <div class="metric-value" style="color: #eab308;">{total_errors}개</div>
        </div>
        """, unsafe_allow_html=True)

    st.write("")
    
    # 오류 있는 행 필터링 토글
    show_errors_only = st.checkbox("⚠️ 맞춤법 오류가 발견된 행만 필터링해서 보기", value=False)
    display_df = df_res if not show_errors_only else df_res[df_res[error_col] > 0]

    st.dataframe(display_df, use_container_width=True, height=400)

    # 다운로드 버튼 영역 (화려한 카드 형태 구현)
    st.markdown("### 💾 완성 파일 내보내기")
    dl_col1, dl_col2 = st.columns(2)

    with dl_col1:
        excel_bytes = df_to_excel_bytes(df_res)
        st.download_button(
            label="📥 엑셀 파일(.xlsx)로 내려받기",
            data=excel_bytes,
            file_name="생기부_맞춤법검사결과.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    with dl_col2:
        csv_bytes = df_to_csv_bytes(df_res)
        st.download_button(
            label="📥 CSV 파일(.csv)로 내려받기",
            data=csv_bytes,
            file_name="생기부_맞춤법검사결과.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # 다시 검사하기 초기화
    st.divider()
    if st.button("🔄 새로운 문서 또는 시트로 처음부터 다시 시작", use_container_width=True):
        for key in ["df_original", "df_result", "text_column", "processing", "done"]:
            st.session_state[key] = None if key not in ("processing", "done") else False
        st.rerun()
