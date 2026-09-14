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
    """제주도의회(13대) 2026년 7월 1일 이후 발의된 의안 수집"""
    bills = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": LIST_URL
    }
    
    for page in range(1, 10):
        try:
            params = {"pageIndex": page}
            res = requests.get(LIST_URL, headers=headers, params=params, timeout=15)
            res.encoding = 'utf-8'
            
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 테이블 행 추출 (제주도의회 게시판 공통 셀렉터 탐색)
            rows = soup.select("table tbody tr")
            print(f"📄 {page}페이지 탐색 중... (발견된 행: {len(rows)}개)")
            
            if not rows:
                break
                
            stop_crawling = False
            for row in rows:
                cols = row.select("td")
                if len(cols) < 3:
                    continue
                
                # 의안 제목 및 링크 추출
                title_elem = row.select_one("a")
                if not title_elem:
                    continue
                    
                bill_title = title_elem.text.strip()
                href = title_elem.get('href', '')
                
                if href.startswith('javascript'):
                    # 자바스크립트 호출 형식일 경우 기본 URL로 대체
                    detail_link = LIST_URL
                elif href.startswith('/'):
                    detail_link = f"{BASE_URL}{href}"
                else:
                    detail_link = href

                # 날짜 및 발의자 추출 (정규식 활용)
                date_str = None
                proposer = "제주도의회"
                
                for col in cols:
                    text = col.text.strip()
                    # YYYY-MM-DD 또는 YYYY.MM.DD 형식 찾기
                    date_match = re.search(r'20\d{2}[-.\/]\d{2}[-.\/]\d{2}', text)
                    if date_match:
                        date_str = date_match.group(0).replace('.', '-').replace('/', '-')
                    elif any(k in text for k in ["의원", "지사", "교육감", "위원회"]):
                        proposer = text

                if not date_str:
                    continue
                    
                try:
                    bill_date = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    continue

                # 2026년 7월 1일 이전 안건 확인 시 수집 중단
                if bill_date < CUTOFF_DATE:
                    stop_crawling = True
                    break

                bill_id = f"{date_str}_{bill_title}".replace(" ", "_")
                bills.append({
                    "id": bill_id,
                    "title": bill_title,
                    "proposer": proposer,
                    "date": date_str,
                    "link": detail_link
                })
                
            if stop_crawling:
                print("✋ 2026년 7월 1일 이전 의안에 도달하여 수집을 완료합니다.")
                break
                
        except Exception as e:
            print(f"❌ {page}페이지 크롤링 중 오류 발생: {e}")
            break
            
    return bills

def summarize_with_gemini(bill_title, proposer):
    """Gemini AI 3줄 요약"""
    if not model:
        return "1. API 키 미설정으로 자동 요약 생략\n2. 원문 링크를 통해 세부 내용을 확인하세요.\n3. 상세 내용 확인 필요"
        
    prompt = f"""
    당신은 지자체 의정 데이터를 분석하는 전문 AI입니다.
    아래 제주도의회 안건 제목과 발의자 정보를 바탕으로, 일반 도민이 이해하기 쉬운 핵심 내용과 기대효과를 3줄로 작성해주세요.

    [안건 제목]: {bill_title}
    [발의자]: {proposer}

    작성 규칙:
    - 번호목록(1., 2., 3.) 형태로 3줄 작성할 것
    - 전문 용어는 쉬운 단어로 풀어쓸 것
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
    
    if os.path.exists(data_file):
        with open(data_file, 'r', encoding='utf-8') as f:
            try:
                existing_data = json.load(f)
            except json.JSONDecodeError:
                existing_data = []
    else:
        existing_data = []

    existing_ids = {item['id'] for item in existing_data}
    
    scraped_bills = fetch_bills_since_cutoff()
    print(f"📊 총 수집된 대상 안건 수: {len(scraped_bills)}개")
    
    new_items_added = False
    for bill in scraped_bills:
        if bill['id'] not in existing_ids:
            print(f"✨ 신규 의안 추가 중 ({bill['date']}): {bill['title']}")
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
            new_items_added = True

    # 항상 JSON 구조를 보장하여 생성/갱신
    existing_data.sort(key=lambda x: x['date'], reverse=True)
    with open(data_file, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=4)
        
    if new_items_added:
        print("✅ 신규 의안 데이터가 data.json에 추가되었습니다.")
    else:
        print("ℹ️ 기존 데이터 유지 완료 (신규 추가 없음)")

if __name__ == "__main__":
    main()
