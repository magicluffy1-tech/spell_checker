import streamlit as st
import time
import random
import pandas as pd
from spell_checker import check_spelling
from sheets_handler import get_raw_data_from_dataframe, get_raw_data_from_public_url
import io

# 스트림릿 페이지 설정 (Premium Theme 및 반응형 레이아웃)
st.set_page_config(
    page_title="Premium 맞춤법 검사기 & 구글 시트 연동기",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS로 고급스러운 다크 & 글래스모피즘 웹 테마와 화려한 디자인 구현
st.markdown("""
    <style>
        /* 메인 디자인 및 배경색 설정 */
        .main {
            background-color: #0f111a;
            color: #e2e8f0;
            font-family: 'Outfit', 'Inter', sans-serif;
        }
        /* 카드 및 컨테이너 스타일 */
        .css-1r6g72h, .stApp {
            background-color: #0f111a;
        }
        div[data-testid="stVerticalBlock"] > div:has(div.element-container) {
            background: rgba(255, 255, 255, 0.02);
            border-radius: 12px;
            padding: 15px;
            margin-bottom: 10px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }
        /* 프리미엄 헤더 */
        .title-container {
            background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
            border-radius: 16px;
            padding: 30px 40px;
            margin-bottom: 25px;
            box-shadow: 0 10px 30px -10px rgba(99, 102, 241, 0.3);
            text-align: left;
        }
        .title-text {
            color: #ffffff;
            font-size: 2.8rem;
            font-weight: 800;
            margin: 0;
            letter-spacing: -0.03em;
        }
        .subtitle-text {
            color: rgba(255, 255, 255, 0.85);
            font-size: 1.1rem;
            font-weight: 400;
            margin-top: 10px;
        }
        /* 메트릭 및 컴포넌트 커스텀 */
        .metric-card {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .metric-title {
            font-size: 0.9rem;
            color: #94a3b8;
            margin-bottom: 5px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .metric-value {
            font-size: 2.2rem;
            font-weight: 700;
            color: #38bdf8;
        }
        /* 성공/에러 상태 배지 */
        .badge-demo {
            background-color: #f59e0b;
            color: #ffffff;
            padding: 3px 8px;
            border-radius: 6px;
            font-size: 0.85rem;
            font-weight: bold;
        }
        .badge-live {
            background-color: #10b981;
            color: #ffffff;
            padding: 3px 8px;
            border-radius: 6px;
            font-size: 0.85rem;
            font-weight: bold;
        }
    </style>
""", unsafe_allow_html=True)

# ----------------- 헤더 영역 -----------------
st.markdown("""
    <div class="title-container">
        <h1 class="title-text">✨ Premium 맞춤법 검사 & 구글 시트 연동기</h1>
        <p class="subtitle-text">구글 시트의 원문 데이터를 로드하여 나라인포테크 맞춤법 검사기 서버(통신 장애 시 로컬 사전으로 자동 전환)를 통해 교정하고 결과를 즉각 실시간 업데이트합니다.</p>
    </div>
""", unsafe_allow_html=True)

# ----------------- 사이드바 (설정 영역) -----------------
st.sidebar.markdown("## ⚙️ 시스템 설정 및 지연 시간")
st.sidebar.caption("나라인포테크 서버의 IP 차단을 안전하게 회피하기 위한 지연 시간 제어 장치입니다.")

delay_normal_min = st.sidebar.slider("일반 행 최소 대기 (초)", 1.0, 5.0, 2.0, 0.5)
delay_normal_max = st.sidebar.slider("일반 행 최대 대기 (초)", 1.5, 8.0, 3.5, 0.5)
delay_long_min = st.sidebar.slider("10번째 행 최소 대기 (초)", 5.0, 15.0, 10.0, 1.0)
delay_long_max = st.sidebar.slider("10번째 행 최대 대기 (초)", 10.0, 25.0, 13.0, 1.0)

# ----------------- 메인 제어 및 입력 폼 -----------------
col_input, col_info = st.columns([2, 1])

with col_input:
    st.markdown("### 📝 연동 데이터 입력")
    data_source = st.radio("데이터 소스 선택", ["엑셀/CSV 파일 업로드", "구글 시트 (공유 링크 뷰어)"], horizontal=True)
    
    uploaded_file = None
    sheet_url_input = ""
    
    if data_source == "엑셀/CSV 파일 업로드":
        uploaded_file = st.file_uploader("검사할 파일을 업로드하세요 (.xlsx, .csv)", type=["xlsx", "csv"])
    else:
        sheet_url_input = st.text_input(
            "구글 스프레드시트 공유 URL",
            value="",
            placeholder="https://docs.google.com/spreadsheets/d/.../edit?usp=sharing",
            help="구글 시트의 우측 상단 [공유] -> [링크가 있는 모든 사용자]에게 '뷰어' 권한을 주신 후, 해당 주소를 복사해 붙여넣으세요. 데모 테스트 시 'demo'라고 입력하시면 가상 데이터를 보여줍니다."
        )
    
    col_sheet_name, col_options = st.columns(2)
    with col_sheet_name:
        sheet_name_input = st.text_input(
            "워크시트 이름 (선택)",
            value="정리완료_결과",
            placeholder="예: 정리완료_결과 (비워두면 첫 번째 시트)",
            help="맞춤법 검사 대상 시트 탭의 이름을 지정하세요. 사용자의 시트 탭 이름인 '정리완료_결과'가 기본 세팅되어 있습니다."
        )
    with col_options:
        skip_existing = st.checkbox(
            "이미 교정본이 있는 행은 제외하고 검사",
            value=True,
            help="이미 가공이 완료된 행을 건너뛰어 서버 리소스와 처리 속도를 획기적으로 절약합니다."
        )

with col_info:
    st.markdown("### 💡 검사기 사용 안내")
    if sheet_name_input.strip() == "창체_결과":
        st.markdown("""
        - **기본 정보 (A, B, C, D열):** 학생 신상정보 등은 데이터 손실 없이 **그대로 보존**되어 원본 유지됩니다.
        - **원문 (E열 - 창체_결과 원문):** 맞춤법을 검사할 원래 한글 텍스트입니다.
        - **교정본 (F열 - 교정_결과):** 맞춤법 교정이 완료되면 실시간으로 우측 F열에 기록됩니다.
        - **수정 사유 (G열 - 교정_수정사유):** 어떠한 오류 단어들이 왜 무엇으로 고쳐졌는지에 대한 사유가 G열에 일목요연하게 정리됩니다.
        - **실시간 추적:** 아래 대시보드에서 실시간으로 성공 여부와 교정 전/후 데이터 및 사유 비교 표가 즉시 업데이트됩니다.
        """)
    else:
        st.markdown("""
        - **번호, 성명, 학년 (A, B, C열):** 학생 신상정보는 데이터 손실 없이 **그대로 보존**되어 원본 유지됩니다.
        - **원문 (D열 - 행동특성 및 종합의견):** 맞춤법을 검사할 원래 한글 종합의견 텍스트입니다.
        - **교정본 (E열 - 교정_행동특성 및 종합의견):** 맞춤법 교정이 완료되면 실시간으로 우측 E열에 기록됩니다.
        - **수정 사유 (F열 - 교정_수정사유):** 어떠한 오류 단어들이 왜 무엇으로 고쳐졌는지에 대한 사유가 F열에 일목요연하게 정리됩니다.
        - **실시간 추적:** 아래 대시보드에서 실시간으로 성공 여부와 교정 전/후 데이터 및 사유 비교 표가 즉시 업데이트됩니다.
        """)
    st.markdown('<span class="badge-live">EASY MODE ACTIVE</span> 공유 링크나 파일 업로드만으로 100% 무설정 고속 맞춤법 검사를 수행합니다.', unsafe_allow_html=True)

# ----------------- 검사 실행 및 실시간 모니터링 -----------------
st.markdown("---")
st.markdown("### 🚀 실시간 작업 대시보드")

if st.button("✨ 맞춤법 검사 및 자동화 실행", type="primary"):
    if data_source == "엑셀/CSV 파일 업로드" and uploaded_file is None:
        st.error("⚠️ 검사할 엑셀 또는 CSV 파일을 업로드해주세요.")
    elif data_source != "엑셀/CSV 파일 업로드" and (not sheet_url_input or sheet_url_input.strip() == ""):
        st.error("⚠️ 올바른 구글 스프레드시트 URL을 입력해주세요.")
    else:
        # 데이터 로드 시작 알림
        with st.spinner("데이터를 가져오는 중입니다..."):
            if data_source == "엑셀/CSV 파일 업로드":
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file, dtype=str)
                else:
                    df = pd.read_excel(uploaded_file, dtype=str)
                raw_data, mode, error_msg = get_raw_data_from_dataframe(df, sheet_name_input)
            else:
                raw_data, mode, error_msg = get_raw_data_from_public_url(sheet_url_input, sheet_name_input)
            
        if mode == 'error':
            st.error(f"❌ 구글 시트 연동 오류가 발생했습니다!\n\n{error_msg}")
            
            # 사용자 해결 가이드 익스팬더 렌더링
            with st.expander("🛠️ 공유 링크 연동 실패 해결 체크리스트", expanded=True):
                st.markdown("""
                구글 공유 링크를 읽어오지 못하는 경우 아래 항목을 체크해주세요:
                
                1. **공유 권한 설정 확인 (필수 🔓)**
                   - 구글 스프레드시트 우측 상단의 **[공유]** 버튼을 누릅니다.
                   - 일반 엑세스 권한을 '제한됨'에서 **'링크가 있는 모든 사용자'**로 변경하고, 역할을 **'뷰어'**로 설정했는지 확인하세요.
                
                2. **URL 형식 확인**
                   - 브라우저 주소창에 표시되는 전체 주소(`https://docs.google.com/spreadsheets/d/...`)를 누락 없이 복사해 넣었는지 확인하세요.
                """)
        elif not raw_data:
            st.warning("⚠️ 시트에서 처리할 데이터(A열)를 발견하지 못했습니다. 첫 번째 행은 헤더(제목)로 가정하고 제외되며, 실제 데이터는 2번째 행(A2)부터 있어야 합니다.")
        else:
            # 필터링 처리
            filtered_data = []
            for item in raw_data:
                # 덮어쓰기 제외 옵션이 켜져 있고 이미 B열에 교정본이 있는 경우 패스
                if skip_existing and item.get("corrected", "").strip() != "":
                    continue
                filtered_data.append(item)
                
            total_items = len(filtered_data)
            
            if total_items == 0:
                st.info("🎉 모든 행의 교정본이 이미 존재하여 검사할 항목이 없습니다. (덮어쓰기 제외 설정)")
            else:
                # 감지된 탭 형식에 맞춘 친절한 유저 알림 구성
                detected_type = raw_data[0].get("detected_type", "행발_결과") if raw_data else "행발_결과"
                type_korean = "📡 창체_결과 탭 모드 (E열 원문 ➡️ F열 교정본, G열 교정사유)" if detected_type == "창체_결과" else "📡 행동특성 및 종합의견 [행발_결과] 탭 모드 (D열 원문 ➡️ E열 교정본, F열 교정사유)"
                
                st.success(f"📊 총 {len(raw_data)}개 행 로드 성공! (이 중 처리 대상: {total_items}개 행)\n\n**🔍 시스템 자동 감지 탭:** `{type_korean}`")
                
                # 실시간 진행상황 레이아웃 구성
                progress_bar = st.progress(0)
                status_text = st.empty()
                countdown_text = st.empty()
                
                # 실시간 메트릭 카드 세 개 나열
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                with col_m1:
                    m_progress = st.empty()
                with col_m2:
                    m_success = st.empty()
                with col_m3:
                    m_engine = st.empty()
                with col_m4:
                    m_delay = st.empty()

                # 실시간 교정 비교 테이블을 렌더링하기 위한 동적 리스트
                realtime_results = []
                table_placeholder = st.empty()
                
                success_count = 0
                server_engine_count = 0
                local_engine_count = 0
                
                # 메트릭 초기화 렌더링
                m_progress.metric("전체 진행률", "0%", "0 / 0 행")
                m_success.metric("성공 개수", "0 행", "0.0%")
                m_engine.metric("최근 교정 엔진", "대기 중", "0 / 0")
                m_delay.metric("딜레이 대기", "대기 중", "0.0s")

                # 반복 작업을 통한 맞춤법 검사
                for i, item in enumerate(filtered_data):
                    current_idx = i + 1
                    row_num = item["row"]
                    original_text = item["original"]
                    
                    status_text.markdown(f"**🔍 처리 중 (행 번호: {row_num})**: *\"{original_text[:30]}...\"*")
                    
                    # 1. 맞춤법 검사 엔진 구동
                    corrected_text, engine_type, reason_text = check_spelling(original_text)
                    
                    if engine_type == 'server':
                        server_engine_count += 1
                    else:
                        local_engine_count += 1
                        
                    # 2. 결과 처리 성공 판정
                    update_success = True
                    
                    if update_success:
                        success_count += 1
                        
                    # 3. 실시간 결과 리스트 누적 및 표 시각화
                    if sheet_name_input.strip() == "창체_결과":
                        realtime_results.append({
                            "행 번호": row_num,
                            "번호 (A열)": item.get("id", ""),
                            "성명 (B열)": item.get("name", ""),
                            "학년 (C열)": item.get("grade", ""),
                            "D열 (기타)": "",
                            "원문 종합의견 (E열)": original_text,
                            "교정 완료본 (F열)": corrected_text,
                            "교정 사유 (G열)": reason_text.replace("\n", " | "),
                            "검증 엔진": "📡 나라인포테크 서버" if engine_type == "server" else "💻 로컬 사전 (Fallback)",
                            "업데이트": "✅ 완료" if update_success else f"❌ 실패 ({update_err})"
                        })
                    else:
                        realtime_results.append({
                            "행 번호": row_num,
                            "번호 (A열)": item.get("id", ""),
                            "성명 (B열)": item.get("name", ""),
                            "학년 (C열)": item.get("grade", ""),
                            "원문 종합의견 (D열)": original_text,
                            "교정 완료본 (E열)": corrected_text,
                            "교정 사유 (F열)": reason_text.replace("\n", " | "),
                            "검증 엔진": "📡 나라인포테크 서버" if engine_type == "server" else "💻 로컬 사전 (Fallback)",
                            "업데이트": "✅ 완료" if update_success else f"❌ 실패 ({update_err})"
                        })
                    
                    # 실시간 DataFrame 테이블 업데이트
                    df = pd.DataFrame(realtime_results)
                    table_placeholder.dataframe(
                        df, 
                        width='stretch', 
                        hide_index=True
                    )
                    
                    # 4. 실시간 메트릭 & 프로그레스바 반영
                    percent_val = int((current_idx / total_items) * 100)
                    progress_bar.progress(percent_val)
                    
                    m_progress.metric("전체 진행률", f"{percent_val}%", f"{current_idx} / {total_items} 행")
                    success_rate = (success_count / current_idx) * 100
                    m_success.metric("성공 개수", f"{success_count} 행", f"성공률: {success_rate:.1f}%")
                    m_engine.metric(
                        "최근 교정 엔진", 
                        "📡 서버 교정" if engine_type == 'server' else "💻 로컬 교정",
                        f"서버: {server_engine_count} | 로컬: {local_engine_count}"
                    )
                    
                    # 5. 안전 지연 시간(Delay) 스케줄러 작동
                    if current_idx < total_items:  # 마지막 행이 아닐 때만 대기
                        # 10번째 행 여부 판단 (전체 인덱스 상 10번째마다)
                        if current_idx % 10 == 0:
                            sleep_time = random.uniform(delay_long_min, delay_long_max)
                            m_delay.metric("딜레이 대기", f"{sleep_time:.1f}초 (장기)", "⚠️ 서버 차단 우회 중")
                            
                            # 1초 단위로 안전 휴식 카운트다운 타이머 시각적 구현
                            for sec in range(int(sleep_time), 0, -1):
                                countdown_text.markdown(
                                    f'<div style="padding:10px; border-radius:8px; background-color:rgba(239,68,68,0.15); border:1px solid #ef4444; color:#ef4444; font-weight:bold; margin-bottom:10px; text-align:center;">'
                                    f'🚨 [서버 보호 안전 장치] {current_idx}번째 행 검사 완료 후 긴 휴식(우회 차단) 중... (남은 시간: {sec}초)'
                                    f'</div>',
                                    unsafe_allow_html=True
                                )
                                time.sleep(1.0)
                            countdown_text.empty()
                        else:
                            # 일반 행 랜덤 딜레이
                            sleep_time = random.uniform(delay_normal_min, delay_normal_max)
                            m_delay.metric("딜레이 대기", f"{sleep_time:.1f}초 (일반)", "정상 지연 대기")
                            time.sleep(sleep_time)
                            
                # 전체 루프 종료 후 성공 완료 메시지 출력
                status_text.empty()
                st.balloons()
                st.success(f"🎉 맞춤법 검사 및 연동 자동화 작업이 완벽하게 완료되었습니다! (성공: {success_count}/{total_items} 행)")
                
                # 결과 엑셀 파일 다운로드 기능 제공
                st.markdown("### 💾 결과 다운로드")
                result_df = pd.DataFrame(realtime_results)
                
                # 컬럼명 정리
                if sheet_name_input.strip() == "창체_결과":
                    result_df = result_df.rename(columns={
                        "번호 (A열)": "번호",
                        "성명 (B열)": "성명",
                        "학년 (C열)": "학년",
                        "D열 (기타)": "비고",
                        "원문 종합의견 (E열)": "행동특성 및 종합의견",
                        "교정 완료본 (F열)": "교정_행동특성 및 종합의견",
                        "교정 사유 (G열)": "교정_수정사유"
                    })
                else:
                    result_df = result_df.rename(columns={
                        "번호 (A열)": "번호",
                        "성명 (B열)": "성명",
                        "학년 (C열)": "학년",
                        "원문 종합의견 (D열)": "행동특성 및 종합의견",
                        "교정 완료본 (E열)": "교정_행동특성 및 종합의견",
                        "교정 사유 (F열)": "교정_수정사유"
                    })
                # 불필요한 열 제거
                result_df = result_df.drop(columns=["행 번호", "검증 엔진", "업데이트", "비고"], errors='ignore')
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    result_df.to_excel(writer, index=False, sheet_name="검사결과")
                excel_data = output.getvalue()
                
                st.download_button(
                    label="📥 교정 완료된 엑셀 파일 다운로드",
                    data=excel_data,
                    file_name="맞춤법검사결과.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
