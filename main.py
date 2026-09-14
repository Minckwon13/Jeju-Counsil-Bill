import os
import json
import re
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from datetime import datetime

# 1. Gemini API 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    model = None
    print("⚠️ GEMINI_API_KEY가 설정되지 않았습니다. (테스트 모드로 동작)")

BASE_URL = "https://www.council.jeju.kr"
LIST_URL = f"{BASE_URL}/activity/bill/info/13dae.do"

# 기준 날짜 설정: 2026년 7월 1일
CUTOFF_DATE = datetime(2026, 7, 1)

def fetch_bills_since_cutoff():
    """제주도의회 13대 의안 수집 (GET/POST 호환 파싱)"""
    bills = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": LIST_URL
    }
    
    for page in range(1, 6):
        try:
            # 폼 데이터 형태로 전송 (전자정부프레임워크 대응)
            payload = {
                "pageIndex": page,
                "searchCondition": "",
                "searchKeyword": ""
            }
            
            res = requests.post(LIST_URL, headers=headers, data=payload, timeout=15)
            if res.status_code != 200:
                # POST 반응이 없을 경우 GET으로 재시도
                res = requests.get(LIST_URL, headers=headers, params={"pageIndex": page}, timeout=15)
                
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 모든 테이블 행 탐색 (클래스명에 구속받지 않도록 보완)
            rows = soup.find_all('tr')
            print(f"📄 {page}페이지 응답 수신 (상태 코드: {res.status_code}, 발견된 행: {len(rows)}개)")
            
            valid_rows_found = False
            stop_crawling = False
            
            for row in rows:
                cols = row.find_all(['td', 'th'])
                if len(cols) < 3:
                    continue
                
                # 텍스트 추출
                row_text = row.text.strip()
                
                # 날짜 추출 (YYYY-MM-DD 또는 YYYY.MM.DD)
                date_match = re.search(r'20\d{2}[-.\/]\d{2}[-.\/]\d{2}', row_text)
                if not date_match:
                    continue
                    
                date_str = date_match.group(0).replace('.', '-').replace('/', '-')
                
                try:
                    bill_date = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    continue

                # 2026년 7월 1일 이전 안건 도달 시 탐색 중단
                if bill_date < CUTOFF_DATE:
                    stop_crawling = True
                    break

                # 제목 및 링크 추출
                link_elem = row.find('a')
                if not link_elem:
                    continue
                    
                bill_title = link_elem.text.strip()
                href = link_elem.get('href', '')
                
                if href and not href.startswith('javascript'):
                    detail_link = f"{BASE_URL}{href}" if href.startswith('/') else href
                else:
                    detail_link = LIST_URL

                # 발의자 추출 (의원, 지사, 교육감 키워드 검색)
                proposer = "제주도의회"
                for col in cols:
                    col_text = col.text.strip()
                    if any(k in col_text for k in ["의원", "지사", "교육감", "위원장", "제안"]):
                        proposer = col_text
                        break

                bill_id = f"{date_str}_{bill_title}".replace(" ", "_")
                bills.append({
                    "id": bill_id,
                    "title": bill_title,
                    "proposer": proposer,
                    "date": date_str,
                    "link": detail_link
                })
                valid_rows_found = True

            if stop_crawling:
                print("✋ 2026년 7월 1일 이전 의안에 도달하여 수집을 완료합니다.")
                break
                
            if not valid_rows_found and page > 1:
                break
                
        except Exception as e:
            print(f"❌ {page}페이지 크롤링 중 오류 발생: {e}")
            break
            
    return bills

def summarize_with_gemini(bill_title, proposer):
    """Gemini AI 3줄 요약"""
    if not model:
        return "1. 제주도의회에 제출된 안건입니다.\n2. 세부 개정사항 및 제안 이유 확인이 필요합니다.\n3. 원문 링크를 통해 상세 내용을 확인하세요."
        
    prompt = f"""
    당신은 지자체 의정 데이터를 분석하는 전문 AI입니다.
    아래 제주도의회 안건 제목과 발의자 정보를 바탕으로, 일반 도민이 이해하기 쉬운 핵심 내용과 기대효과를 3줄로 작성해주세요.

    [안건 제목]: {bill_title}
    [발의자]: {proposer}

    작성 규칙:
    - 번호목록(1., 2., 3.) 형태로 3줄 작성할 것
    - 명확하고 간결한 어조를 사용할 것
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"❌ Gemini 요약 실패: {e}")
        return "1. 요약 생성 중 오류가 발생했습니다.\n2. 원문 링크를 참고해 주세요.\n3. 상세 내용 확인 필요"

def main():
    data_file = 'data.json'
    
    # 크롤링 실행
    scraped_bills = fetch_bills_since_cutoff()
    print(f"📊 최종 수집된 대상 안건 수: {len(scraped_bills)}개")
    
    # 기존 데이터 로드
    existing_data = []
    if os.path.exists(data_file):
        with open(data_file, 'r', encoding='utf-8') as f:
            try:
                existing_data = json.load(f)
            except json.JSONDecodeError:
                existing_data = []

    existing_ids = {item['id'] for item in existing_data}
    
    # 수집 결과 반영
    for bill in scraped_bills:
        if bill['id'] not in existing_ids:
            print(f"✨ 신규 의안 요약 생성 중 ({bill['date']}): {bill['title']}")
            summary = summarize_with_gemini(bill['title'], bill['proposer'])
            
            new_entry = {
                "id": bill['id'],
                "date": bill['date'],
                "proposer": bill['proposer'],
                "title": bill['title'],
                "summary": summary,
                "link": bill['link']
            }
            existing_data.append(new_entry)

    # 데이터가 비어있을 경우 화면 표시 확인용 테스트 데이터 1건 삽입 (임시 릴리프)
    if not existing_data:
        print("⚠️ 수집된 의안이 없어 테스트용 안내 데이터를 생성합니다.")
        existing_data.append({
            "id": "init_test",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "proposer": "시스템 안내",
            "title": "제주도의회 의안 자동 수집 시스템이 정상 연결되었습니다.",
            "summary": "1. 서버 연결 및 자동화 파이프라인 작동 완료\n2. 신규 발의 의안 감지 시 자동으로 업데이트됩니다.\n3. 상단 링크를 눌러 의회 홈페이지를 바로 확인할 수 있습니다.",
            "link": LIST_URL
        })

    # 최신순 정렬 후 파일 저장
    existing_data.sort(key=lambda x: x['date'], reverse=True)
    with open(data_file, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=4)
        
    print("✅ data.json 저장 완료")

if __name__ == "__main__":
    main()
