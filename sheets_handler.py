import os
import urllib.parse
import re

# 1. 탭별 시뮬레이션용 가상 데모 데이터 구성 (인증서가 없을 때 유저 체험용)
DEMO_HAENGBAL_DATA = [
    {"row": 2, "id": "1", "name": "김민수", "grade": "3", "original": "매사에 긍정적이며 친구들과 잘 어울림. 그러나 가끔 띄어쓰기오류도있어요.", "corrected": "", "reason": ""},
    {"row": 3, "id": "2", "name": "박서연", "grade": "3", "original": "학업 성적이 매우 우수하고 발표력이 조내요. 앞으로 대성할것이다.", "corrected": "", "reason": ""},
    {"row": 4, "id": "3", "name": "최준우", "grade": "3", "original": "책임감이 강하고 솔선수범함. 외않되? 어의업는 실수를 고칠수있게 지도바람.", "corrected": "", "reason": ""},
    {"row": 5, "id": "4", "name": "정예은", "grade": "3", "original": "예술적 감각이 뛰어나며 설레임 가득한 목소리로 발표에 참여함.", "corrected": "", "reason": ""},
    {"row": 6, "id": "5", "name": "한지우", "grade": "3", "original": "동아리 활동을 열심히 않하고 시간표전문가프로그램만 돌리는 경향이 있음.", "corrected": "", "reason": ""},
]

DEMO_CHANGCHE_DATA = [
    {"row": 2, "id": "1", "name": "김민수", "grade": "창의적체험활동", "original": "매사에 긍정적이며 창의적 동아리 활동에서 띄어쓰기오류도있어요.", "corrected": "", "reason": ""},
    {"row": 3, "id": "2", "name": "박서연", "grade": "창의적체험활동", "original": "진로 활동에 적극적으로 임하며 탐구 능력이 조내요. 앞으로 대성할것이다.", "corrected": "", "reason": ""},
    {"row": 4, "id": "3", "name": "최준우", "grade": "창의적체험활동", "original": "자율 활동 반장으로서 책임감이 강함. 외않되? 어의업는 실수를 고칠수있게 지도바람.", "corrected": "", "reason": ""},
    {"row": 5, "id": "4", "name": "정예은", "grade": "창의적체험활동", "original": "봉사 활동에 적극적으로 참여하며 설레임 가득한 배려를 실천함.", "corrected": "", "reason": ""},
]

def detect_sheet_type(sheet_name: str, header_cols: list[str]) -> str:
    """
    시트 탭 이름 및 로드된 실제 데이터의 컬럼 헤더들을 종합 스캔하여
    '창체_결과' 또는 '행발_결과' 탭 형식을 자동으로 판별하는 지능형 시스템입니다.
    """
    name_lower = sheet_name.lower().strip() if sheet_name else ""
    
    # 1. 탭 이름에 명시적인 키워드가 있을 경우 최우선 판별
    if "창체" in name_lower or "창의" in name_lower:
        return "창체_결과"
    if "행발" in name_lower or "행동" in name_lower or "종합" in name_lower:
        return "행발_결과"
        
    # 2. 컬럼 헤더명의 한글 키워드 존재 여부로 자동 탐지 (이름이 모호하거나 누락된 경우)
    headers_str = "".join([str(col).lower().strip() for col in header_cols])
    if "특기사항" in headers_str or "이수시간" in headers_str:
        return "창체_결과"
    if "행동특성" in headers_str or "종합의견" in headers_str:
        return "행발_결과"
        
    # 3. 최후의 보루: 열의 개수와 내용 특징으로 추정
    if len(header_cols) >= 5:
        # 4번째(index 3) 또는 5번째(index 4) 컬럼명에 '시간'이나 '사항'이 있으면 창체
        col3_str = str(header_cols[3]) if len(header_cols) > 3 else ""
        col4_str = str(header_cols[4]) if len(header_cols) > 4 else ""
        if "시간" in col3_str or "사항" in col4_str or "특기" in col4_str:
            return "창체_결과"
            
    # 기본값은 행동특성 및 종합의견(행발_결과) 모드로 적용
    return "행발_결과"


def get_raw_data_from_dataframe(df, sheet_name: str = None) -> tuple[list[dict], str, str | None]:
    """
    Pandas DataFrame에서 데이터를 읽어와서 앱에서 사용하는 포맷으로 변환합니다. (지능형 판별 적용)
    """
    try:
        if df.empty:
            return [], 'error', "데이터가 비어 있습니다."
            
        target_sheet_name = sheet_name.strip() if sheet_name and sheet_name.strip() != "" else "정리완료_결과"
        
        # 1. 컬럼 헤더들을 기반으로 지능형 탭 종류 식별
        header_cols = df.columns.tolist()
        detected_type = detect_sheet_type(target_sheet_name, header_cols)
        
        # 2. 필요한 열 크기를 맞추기 위해 빈 열 추가 (창체는 최소 7개, 행발은 최소 6개 열 필요)
        required_cols = 7 if detected_type == "창체_결과" else 6
        while len(df.columns) < required_cols:
            df[f"Unnamed_New_{len(df.columns)}"] = ""
                
        # 리스트로 데이터 변환 (fillna 적용하여 빈 셀은 빈문자열로 처리)
        all_records = df.fillna("").values.tolist()
        
        data_list = []
        for idx in range(len(all_records)):
            row_num = idx + 2 # 헤더 제외 2행부터 시작
            row_data = all_records[idx]
            
            student_id = str(row_data[0]).strip() if len(row_data) > 0 else ""
            student_name = str(row_data[1]).strip() if len(row_data) > 1 else ""
            student_grade = str(row_data[2]).strip() if len(row_data) > 2 else ""
            
            # 감지된 탭 형식에 맞춘 원문/교정/사유 동적 맵핑
            if detected_type == "창체_결과":
                original_val = str(row_data[4]).strip() if len(row_data) > 4 else ""
                corrected_val = str(row_data[5]).strip() if len(row_data) > 5 else ""
                reason_val = str(row_data[6]).strip() if len(row_data) > 6 else ""
            else:
                original_val = str(row_data[3]).strip() if len(row_data) > 3 else ""
                corrected_val = str(row_data[4]).strip() if len(row_data) > 4 else ""
                reason_val = str(row_data[5]).strip() if len(row_data) > 5 else ""
            
            if not original_val:
                continue
                
            data_list.append({
                "row": row_num,
                "id": student_id,
                "name": student_name,
                "grade": student_grade,
                "original": original_val,
                "corrected": corrected_val,
                "reason": reason_val,
                "detected_type": detected_type
            })
            
        return data_list, 'upload', None
        
    except Exception as e:
        import traceback
        tb_str = traceback.format_exc()
        return [], 'error', f"데이터 파싱 오류: {str(e)}\n\n**🔍 디버깅용 에러 트레이스백:**\n```\n{tb_str}\n```"


def get_raw_data_from_public_url(sheet_url: str, sheet_name: str = None) -> tuple[list[dict], str, str | None]:
    """
    공유 링크(뷰어 권한) URL을 CSV 포맷으로 변환하여 pandas로 직접 읽습니다. (지능형 탭 인지 연동)
    """
    try:
        import pandas as pd
        import urllib.parse
        
        # 데모 처리
        if sheet_url.strip().lower() == "demo":
            target_sheet_name = sheet_name.strip() if sheet_name and sheet_name.strip() != "" else "정리완료_결과"
            detected_type = detect_sheet_type(target_sheet_name, [])
            if detected_type == "창체_결과":
                copied_data = [dict(row) for row in DEMO_CHANGCHE_DATA]
            else:
                copied_data = [dict(row) for row in DEMO_HAENGBAL_DATA]
            
            for item in copied_data:
                item["detected_type"] = detected_type
            return copied_data, 'demo', None

        # URL에서 시트 ID 추출
        match = re.search(r'/d/([a-zA-Z0-9-_]+)', sheet_url)
        if not match:
            return [], 'error', "구글 시트 URL 형식이 올바르지 않습니다."
            
        sheet_id = match.group(1)
        
        # gid(시트 탭 ID) 추출
        gid_match = re.search(r'gid=([0-9]+)', sheet_url)
        
        # CSV 다운로드 URL 생성
        if sheet_name and sheet_name.strip() != "":
            quoted_sheet_name = urllib.parse.quote(sheet_name.strip())
            csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={quoted_sheet_name}"
        elif gid_match:
            gid = gid_match.group(1)
            csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
        else:
            csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        
        # pandas로 데이터 읽기
        df = pd.read_csv(csv_url, dtype=str)
        
        # 데이터프레임 구조를 파싱하여 탭 구조를 감지 및 리스트 반환
        return get_raw_data_from_dataframe(df, sheet_name)
        
    except Exception as e:
        return [], 'error', f"공유 뷰어 링크를 읽을 수 없습니다. 파일이 '링크가 있는 모든 사용자'에게 공개되어 있는지 확인해주세요.\n오류 상세: {str(e)}"


if __name__ == '__main__':
    # 간단한 단독 테스트
    print("구글 시트 연동 모듈 로컬 테스트...")
    data, mode, err = get_raw_data_from_public_url("demo", "창체_결과")
    print(f"작동 모드: {mode}, 에러: {err}")
    print(f"가져온 데이터 개수: {len(data)}")
    if data:
        print(f"감지된 탭 형식: {data[0]['detected_type']}")
        print(f"첫 행 데이터: {data[0]}")
