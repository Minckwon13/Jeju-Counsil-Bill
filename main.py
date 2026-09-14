def main():
    data_file = 'data.json'
    
    # 1. 기존 data.json 데이터 불러오기 (없으면 빈 리스트로 시작)
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

    # 4. 파일이 없거나 새로운 데이터가 추가되었을 때 data.json 항상 생성/갱신
    if new_items_added or not os.path.exists(data_file):
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=4)
        print("✅ data.json 파일이 정상적으로 저장되었습니다.")
    else:
        print("ℹ️ 새로 추가된 의안이 없습니다.")

if __name__ == "__main__":
    main()
