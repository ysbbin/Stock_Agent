# 📈 주식 리서치 에이전트 — 웹 대시보드 버전

브라우저에서 모든 설정을 관리하는 웹 기반 대시보드입니다.
Gemini 2.0 Flash (무료) + Google Search로 매일 아침 자동 리서치 → Gmail 전송

---

## 특징

- 🌐 **웹 대시보드** — 브라우저에서 모든 설정 (터미널 불필요)
- 📧 **Gmail 알림** — HTML 이메일로 예쁘게 전송
- ⏰ **자동 실행** — Windows 작업 스케줄러로 매일 지정 시간 실행
- 💰 **완전 무료** — Gemini API 무료 티어 (하루 1,500회)

---

## VS Code에서 실행하는 법

### 1단계: 패키지 설치

VS Code 터미널(Ctrl + `) 열고:

```bash
pip install flask google-generativeai
```

### 2단계: Gemini API 키 발급 (무료)

1. https://aistudio.google.com/app/apikey 접속
2. **Create API Key** 클릭
3. `AIza...` 키 복사

### 3단계: 웹 서버 실행

```bash
python app.py
```

터미널에 이렇게 뜹니다:

```
  🌐 브라우저에서 접속하세요:
     http://localhost:5000
```

### 4단계: 브라우저에서 설정

브라우저에서 **http://localhost:5000** 접속

웹 페이지에서:

1. **🔑 Gemini API 키** 입력 → 💾 저장
2. **📧 Gmail 설정**
   - Gmail 주소 입력
   - 앱 비밀번호 16자리 입력 (발급: https://myaccount.google.com/security → 앱 비밀번호)
   - 💾 저장 → 📨 테스트 전송
3. **📌 관심 종목** 추가 (삼성전자, NVIDIA 등)
4. **🏭 관심 산업** 추가 (반도체, AI 등)
5. **⏰ 자동 실행 시간** 설정 (예: 9시 0분) → 💾 시간 저장
6. **🗓️ Windows 작업 스케줄러 등록** 버튼 클릭

---

## 파일 구조

```
stock_agent\
  ├── app.py                  ← Flask 웹 서버
  ├── scheduler.py            ← 자동 실행 스크립트
  ├── templates\
  │   └── index.html          ← 웹 대시보드 HTML
  ├── setup_scheduler.bat     ← 작업 스케줄러 등록 (자동 생성)
  └── stock_agent_data\
        ├── config.json       ← 모든 설정 저장
        ├── watchlist.json    ← 관심 종목/산업
        ├── scheduler.log     ← 자동 실행 로그
        └── reports\
              └── *.md        ← 저장된 리포트
```

---

## 사용 흐름

```
1. python app.py 실행 → 웹서버 시작
2. 브라우저에서 localhost:5000 접속
3. 웹에서 모든 설정 (API 키, Gmail, 종목, 시간)
4. "Windows 작업 스케줄러 등록" 버튼 클릭
5. 웹 서버 종료해도 OK (작업 스케줄러가 알아서 실행)
6. 매일 설정한 시간에 자동으로 이메일 도착!
```

---

## 주의사항

- Gmail 앱 비밀번호는 `config.json`에 저장되므로 파일을 외부에 공유하지 마세요.
- 웹 대시보드(`app.py`)는 설정 변경할 때만 실행하면 됩니다. 설정 후 종료해도 자동 실행은 계속 작동합니다.
- Gemini 무료 티어: 분당 15회, 하루 1,500회 제한
