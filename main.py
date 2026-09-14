import os
import json
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from datetime import datetime

# 1. Gemini API 설정 (GitHub Secrets 환경변수 읽기)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    model = None
    print("⚠️ GEMINI_API_KEY가 설정되지 않았습니다. (테스트 모드로 동작)")

BASE_URL = "https://www.jejucouncil.go.kr"
LIST_URL = f"{BASE_URL}/open/bill/list.do"

# 기준 날짜 설정: 2026년 7월 1일
CUTOFF_DATE = datetime(2026, 7, 1)

def fetch_bills_since_cutoff():
    """2026년 7월 1일 이후 발의된 의안 수집"""
    bills = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    # 1페이지부터 최대 10페이지까지 순회하며 탐색
    for page in range(1, 11):
        try:
            params = {"pageIndex": page}
            res = requests.get(LIST_URL, headers=headers, params=params, timeout=10)
            soup = BeautifulSoup(res.text, 'html.parser')
            rows = soup.select("table.tb_list tbody tr, table.board_list tbody tr")
            
            if not rows:
                break
                
            stop_crawling = False
            for row in rows:
                cols = row.select("td")
                if len(cols) < 3:
                    continue
                    
                title_elem = row.select_one("a")
                if not title_elem:
                    continue
                    
                bill_title = title_elem.text.strip()
                href = title_elem.get('href', '')
                detail_link = f"{BASE_URL}{href}" if href.startswith('/') else href
                
                # 날짜 및 발의자 추출
                date_str = None
                proposer = "제주도의회"
                
                for col in cols:
                    text = col.text.strip()
                    if len(text) == 10 and text.count('-') == 2:
                        date_str = text
                    elif any(k in text for k in ["의원", "지사", "교육감"]):
                        proposer = text

                if not date_str:
                    continue
                    
                try:
                    bill_date = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    continue

                # 2026년 7월 1일 이전 안건이 나오면 크롤링 종료
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
                break
                
        except Exception as e:
            print(f"❌ {page}페이지 수집 중 오류 발생: {e}")
            break
            
    return bills

def summarize_with_gemini(bill_title, proposer):
    """Gemini AI를 이용한 3줄 요약 생성"""
    if not model:
        return "1. API 키 미설정으로 자동 요약 생략\n2. 원문 링크를 통해 세부 내용을 확인하세요.\n3. 본문 확인 필요"
        
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
        print(f"❌ Gemini 요약 생성 실패: {e}")
        return "1. 요약 생성 중 오류가 발생했습니다.\n2. 원문 링크를 참고해 주세요.\n3. 상세 내용 확인 필요"

def main():
    data_file = 'data.json'
    
    # 기존 파일 로드
    if os.path.exists(data_file):
        with open(data_file, 'r', encoding='utf-8') as f:
            try:
                existing_data = json.load(f)
            except json.JSONDecodeError:
                existing_data = []
    else:
        existing_data = []

    existing_ids = {item['id'] for item in existing_data}
    
    # 2026년 7월 1일 이후 의안 탐색
    scraped_bills = fetch_bills_since_cutoff()
    new_items_added = False
    
    for bill in scraped_bills:
        if bill['id'] not in existing_ids:
            print(f"✨ 대상 의안 수집 ({bill['date']}): {bill['title']}")
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

    # 최신 순 정렬 후 저장
    if new_items_added or not os.path.exists(data_file):
        existing_data.sort(key=lambda x: x['date'], reverse=True)
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=4)
        print("✅ 2026년 7월 1일 이후 의안 데이터가 성공적으로 저장되었습니다.")
    else:
        print("ℹ️ 새로 추가할 의안이 없습니다.")

if __name__ == "__main__":
    main()
