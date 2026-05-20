import sys
import io

# 윈도우 터미널 유니코드 인코딩 설정
if sys.platform.startswith('win'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from spell_checker import check_spelling
from sheets_handler import DEMO_SHEET_DATA

print("=== 맞춤법 검사기 [서버 교정] 미리보기 작동 테스트 ===")
print("-" * 80)

# 데모 데이터 중 3개 샘플링하여 검사 실행
sample_data = DEMO_SHEET_DATA[:3]

for item in sample_data:
    original = item["original"]
    print(f"📌 [행 {item['row']}] 학생: {item['name']} ({item['grade']}학년)")
    print(f"  📝 원문 의견 : {original}")
    
    corrected, engine_type, reason = check_spelling(original)
    
    print(f"  ✨ 교정 완료 : {corrected} (엔진: {engine_type})")
    print(f"  🔍 수정 사유 :")
    for r in reason.split('\n'):
        if r.strip():
            print(f"     - {r}")
    print("-" * 80)
