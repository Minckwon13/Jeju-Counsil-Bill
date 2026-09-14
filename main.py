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
    # Gemini 2.5 Flash 모델 사용
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    model = None
    print("⚠️ GEMINI_API_KEY가 설정되지 않았습니다. (테스트 모드로 동작)")

# 제주도의회 의안 정보 URL
BASE_URL = "https://www.jejucouncil.go.kr"
LIST_URL = f"{BASE_URL}/open/bill/list.do"  # 의안 목록 페이지

def fetch_recent_bills():
    """제주도의회 최신 의안 목록 수집"""
    bills = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        res = requests.get(LIST_URL, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 게시판 테이블 목록 가져오기 (게시판 HTML 구조에 맞게 셀렉터 지정)
        rows = soup.select("table.tb_list tbody tr, table.board_list tbody tr")
        
        for row in rows[:5]:  # 상위 5개 최신 안건 수집
            cols = row.select("td")
            if len(cols) < 3:
                continue
                
            title_elem = row.select_one("a")
            if not title_elem:
                continue
                
            bill_title = title_elem.text.strip()
            href = title_elem.get('href', '')
            detail_link = f"{BASE_URL}{href}" if href.startswith('/') else href
            
            # 날짜 및 발의자 추출 (기본값 설정)
            date = datetime.now().strftime("%Y-%m-%d")
            proposer = "제주도의회"
            
            for col in cols:
                text = col.text.strip()
                # YYYY-MM-DD 형식 추출
                if len(text) == 10 and text.count('-') == 2:
                    date = text
                elif "의원" in text or "지사" in text or "교육감" in text:
                    proposer = text

            # 중복 체크용 고유 ID 생성
            bill_id = f"{date}_{bill_title}".replace(" ", "_")
            
            bills.append({
                "id": bill_id,
                "title": bill_title,
                "proposer": proposer,
                "date": date,
                "link": detail_link
            })
    except Exception as e:
        print(f"❌ 크롤링 중 오류 발생: {e}")
        
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
    
    # 1. 기존 data.json 데이터 불러오기
    if os.path.exists(data_file):
        with open(data_file, 'r', encoding='utf-8') as f:
            try:
                existing_data = json.load(f)
            except json.JSONDecodeError:
                existing_data = []
    else:
        existing_data = []

    existing_ids = {item['id'] for item in existing_data}
    
    # 2. 크롤링 수행
    scraped_bills = fetch_recent_bills()
    new_items_added = False
    
    # 3. 신규 안건만 AI 요약 후 추가
    for bill in scraped_bills:
        if bill['id'] not in existing_ids:
            print(f"✨ 신규 의안 발견: {bill['title']}")
            
            # AI 요약 생성
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
    
    # 4. 저장 (신규 의안이 있을 때만 data.json 갱신)
    if new_items_added:
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=4)
        print("✅ data.json 파일 업데이트 완료!")
    else:
        print("ℹ️ 새로 추가된 의안이 없습니다.")

if __name__ == "__main__":
    main()
