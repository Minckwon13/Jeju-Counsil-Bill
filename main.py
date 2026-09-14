import json
import os
from datetime import datetime

# -------------------------------------------------------------
# [이 부분에 실제 크롤링 및 Gemini AI 요약 코드가 들어갑니다]
# 예시를 위해 가상의 크롤링/요약 데이터를 생성하겠습니다.
# -------------------------------------------------------------
new_bill = {
    "id": datetime.now().strftime("%Y%md%H%M%S"),
    "date": datetime.now().strftime("%Y-%m-%d"),
    "proposer": "제주특별자치도지사",
    "title": "제주특별자치도 전기자동차 보급 촉진 및 이용 활성화에 관한 조례 일부개정조례안",
    "summary": "1. 전기차 충전구역 내 화재 예방 시설 설치 의무화\n2. 충전방해행위 단속 기준 명확화\n3. 도민 안전 확보 및 전기차 보급 활성화 도모",
    "link": "https://www.jejucouncil.go.kr/..."
}

# 1. 기존 데이터 불러오기 (파일이 없으면 빈 리스트로 시작)
data_file = 'data.json'
if os.path.exists(data_file):
    with open(data_file, 'r', encoding='utf-8') as f:
        try:
            bills_data = json.load(f)
        except json.JSONDecodeError:
            bills_data = []
else:
    bills_data = []

# 2. 새 데이터 추가 (실제로는 중복 체크 로직이 들어가야 함)
bills_data.append(new_bill)

# 3. JSON 파일로 저장
with open(data_file, 'w', encoding='utf-8') as f:
    json.dump(bills_data, f, ensure_ascii=False, indent=4)

print("데이터가 성공적으로 업데이트 되었습니다.")
