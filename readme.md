# 🚑 Safe Bridge - 응급실 병상 찾기 서비스

응급 상황에서 최적의 병원을 찾아주는 실시간 서비스입니다.

## 📁 프로젝트 구조

```
safe_bridge_react/
├── backend/              # Flask 백엔드 서버
│   ├── app.py           # Flask 메인 앱
│   ├── config.py        # 설정 파일
│   ├── routes/          # API 라우트 (모듈화 예정)
│   ├── services/        # 비즈니스 로직 (모듈화 예정)
│   ├── models/          # 데이터베이스 모델 (예정)
│   ├── utils/           # 유틸리티 함수
│   └── requirements.txt # Python 의존성
│
├── frontend/            # React 프론트엔드
│   ├── src/
│   │   ├── components/  # React 컴포넌트
│   │   ├── services/     # API 서비스
│   │   └── utils/       # 유틸리티
│   └── package.json
│
├── streamlit-demo/      # Streamlit 목업 앱
│   ├── app.py
│   └── requirements.txt
│
├── docs/                # 문서
│   └── 00_document/     # 프로젝트 문서
│
└── scripts/             # 실행 스크립트
    └── start_all.sh     # 전체 서비스 실행
```

## 🚀 빠른 시작

### 1. Backend 설정

```bash
cd backend
conda create -n off_hack python=3.10 -y
conda activate off_hack
pip install -r requirements.txt
python app.py
```

### 2. Frontend 설정

```bash
cd frontend
npm install
npm run dev
```

### 3. 전체 실행 (자동)

```bash
bash scripts/start_all.sh
```

## 📖 상세 문서

- [SETUP.md](./SETUP.md) - 설치 및 실행 가이드
- [docs/](./docs/) - 프로젝트 문서

## 🏗️ 아키텍처

- **Backend**: Flask + WebSocket (예정)
- **Frontend**: React + TypeScript + Vite
- **AI/LLM**: OpenAI (Whisper-1, GPT-4)
- **External APIs**: 국립중앙의료원, Kakao Map, Twilio

## 📝 라이선스

MIT
