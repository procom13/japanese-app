# 매일 밤 자동 생성 규칙 (예약 작업용)

1. `days.json`의 마지막 Day 번호 + 1 = 오늘 만들 Day(N). `dayN.html`이 이미 있으면 아무것도 하지 말고 끝낸다.
2. `CURRICULUM.md`에서 Day N의 글자를 확인한다.
3. 가장 최근 Day 파일 `day(N-1).html`을 복사해 `dayN.html`을 만든다.
   - 바꾸는 곳: `<title>`의 Day 번호, `<span class="day">Day N</span>`, `var DAY = N;`,
     그리고 `/* @@DAY-DATA-START@@ */` ~ `/* @@DAY-DATA-END@@ */` 구역만.
   - 학습 로직·디자인·음성 코드는 건드리지 않는다.
4. 데이터 구역 작성 규칙
   - CHARS 앞쪽 LEARN_N개 = 오늘 글자 (c, k=한글 발음, r=로마자, row, pos, w/wk/wp/wm = 예시 단어, tip = 연상 팁, 필요하면 note).
   - CHARS 뒤쪽 = 전날 글자 (rev:true, w/wk/wm).
   - 예시 단어(w)는 `kana_data.py`의 HIRA_EX / KATA_EX에 있는 단어를 우선 쓴다.
   - 두 번째 예시 단어(EX)는 4개 목소리 manifest(`audio/v8|v13|v14|v20/manifest.json`)에 모두 있는 단어만. 없으면 null.
   - `results.md`의 가장 최근 기록에서 틀린 글자를 REVIEW_PLAN에 넣는다 (복습 4~5문제). 기록이 없으면 헷갈리기 쉬운 글자 위주.
   - CONFUSE에 헷갈리기 쉬운 짝을 넣는다 (인덱스 기준).
   - JPOP 3개: 오늘 배운 단어가 제목에 들어간, 실제로 존재하는 유명 곡만. 곡 제목·아티스트는 확실한 것만 쓰고, 가사는 옮겨 적지 않는다. w는 manifest에 있는 단어만.
   - 설명은 쉽고 짧은 한국어.
5. 모든 일본어 음성 텍스트(c, w, x, JPOP의 w)가 v8 manifest에 있는지 스크립트로 확인한다.
   - Day 19 이후처럼 새 단어가 꼭 필요하면 `words.txt` 끝에 `# Day N` 아래로 추가한다 (음원은 사용자가 PC/NAS에서 `python generate_audio.py`로 만든다. 그 전까지 앱은 기기 음성으로 대체 재생).
6. `days.json`의 days에 Day N을 추가하고, next를 Day N+1 정보로 바꾼다.
7. 확인: `node --check`로 스크립트 문법 검사, Playwright(393x852)로 복습→학습→연습→J-pop→결과까지 클릭해서 오류가 없는지 확인한다.
8. main 브랜치에 커밋하고 push 한다. 커밋 메시지: `Day N: <글자 요약>`.
