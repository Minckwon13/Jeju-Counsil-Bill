import os
import json
import re
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from datetime import datetime
import urllib3

# SSL 인증서 관련 경고 억제 (지자체 서버 통신 보장)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 1. Gemini API 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    model = None
    print("⚠️ GEMINI_API_KEY 미설정: 기본 요약 텍스트로 대체됩니다.")

BASE_URL = "https://www.council.jeju.kr"
LIST_URL = f"{BASE_URL}/activity/bill/info/13dae.do"

def fetch_13th_council_bills(max_pages=25):
    """제13대 제주도의회 제출 의안 목록 수집"""
    bills = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": LIST_URL
    }

    for page in range(1, max_pages + 1):
        try:
            params = {
                "num": "013",
                "pageIndex": page,
                "page": page
            }
            res = requests.get(LIST_URL, headers=headers, params=params, verify=False, timeout=15)
            res.encoding = 'utf-8'
            
            soup = BeautifulSoup(res.text, 'html.parser')
            rows = soup.select("table tbody tr")
            print(f"📄 13대 의안 {page}페이지 수집 중... (탐색된 행: {len(rows)}개)")
            
            if not rows:
                break
                
            has_item = False
            for row in rows:
                cols = row.select("td")
                if len(cols) < 2:
                    continue
                
                link_elem = row.select_one("a")
                if not link_elem:
                    continue
                    
                title = link_elem.text.strip()
                if not title or title in ["제목", "의안명"]:
                    continue

                href = link_elem.get('href', '')
                if href.startswith('/'):
                    detail_link = f"{BASE_URL}{href}"
                elif href.startswith('http'):
                    detail_link = href
                else:
                    detail_link = LIST_URL

                row_text = row.text.strip()
                # 날짜 추출 (YYYY-MM-DD 또는 YYYY.MM.DD)
                date_match = re.search(r'20\d{2}[-.\/]\d{2}[-.\/]\d{2}', row_text)
                date_str = date_match.group(0).replace('.', '-').replace('/', '-') if date_match else datetime.now().strftime("%Y-%m-%d")

                # 발의자 추출
                proposer = "제주도의회"
                for col in cols:
                    ctext = col.text.strip()
                    if any(k in ctext for k in ["의원", "지사", "교육감", "위원장", "제안"]):
                        proposer = ctext
                        break

                bill_id = f"13th_{date_str}_{title}".replace(" ", "_").replace("/", "_")
                
                bills.append({
                    "id": bill_id,
                    "title": title,
                    "proposer": proposer,
                    "date": date_str,
                    "link": detail_link
                })
                has_item = True
                
            if not has_item:
                break
                
        except Exception as e:
            print(f"❌ {page}페이지 크롤링 중 오류: {e}")
            break
            
    return bills

def summarize_with_gemini(title, proposer):
    """Gemini AI 3줄 요약"""
    if not model:
        return f"1. 제13대 제주도의회 안건: {title}\n2. 세부 사항은 원문 링크 참조\n3. 발의자: {proposer}"
        
    prompt = f"""
    당신은 지자체 의정 데이터를 분석하는 전문 AI입니다.
    아래 제13대 제주도의회 안건 정보를 바탕으로 도민이 이해하기 쉬운 핵심 내용과 취지를 3줄로 요약해 주세요.

    - 안건명: {title}
    - 발의자: {proposer}

    작성 규칙:
    1. 1., 2., 3. 번호목록 형식으로 3줄만 작성할 것
    2. 전문용어는 쉬운 단어로 풀어쓸 것
    """
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"⚠️ AI 요약 실패 ({title[:15]}...): {e}")
        return f"1. 제13대 제주도의회 안건: {title[:25]}...\n2. 주요 발의 내용 원문 확인 필요\n3. 발의자: {proposer}"

def main():
    data_file = 'data.json'
    
    # 1. 기존 DB 읽기
    existing_data = []
    if os.path.exists(data_file):
        with open(data_file, 'r', encoding='utf-8') as f:
            try:
                existing_data = json.load(f)
            except json.JSONDecodeError:
                existing_data = []
                
    existing_ids = {item['id'] for item in existing_data}
    
    # 2. 크롤링 진행
    scraped_bills = fetch_13th_council_bills(max_pages=25)
    print(f"📊 총 탐색된 13대 의안 개수: {len(scraped_bills)}개")
    
    # 3. 미요약건 처리 (1회 실행 시 최대 25건 처리하여 안정성 확보)
    new_added = 0
    for bill in scraped_bills:
        if bill['id'] not in existing_ids:
            print(f"✨ [{new_added+1}] AI 요약 생성 중: {bill['title']}")
            summary = summarize_with_gemini(bill['title'], bill['proposer'])
            
            existing_data.append({
                "id": bill['id'],
                "date": bill['date'],
                "proposer": bill['proposer'],
                "title": bill['title'],
                "summary": summary,
                "link": bill['link']
            })
            existing_ids.add(bill['id'])
            new_added += 1
            
            if new_added >= 25:
                print("⏳ 1회 최대로 처리 가능한 25건을 요약했습니다. 나머지 항목은 다음 실행 때 계속 이어서 누적 처리됩니다.")
                break

    # 4. 날짜순 정렬 후 저장
    existing_data.sort(key=lambda x: x['date'], reverse=True)
    with open(data_file, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=4)
        
    print(f"✅ data.json 저장 완료 (현재 총 {len(existing_data)}건 보유 중)")

if __name__ == "__main__":
    main()
