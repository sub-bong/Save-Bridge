# Safe Bridge - 응급실 병상 찾기 서비스

응급 상황에서 최적의 병원을 찾아주는 실시간 서비스입니다.

## 프로젝트 구조

```
Save-Bridge/
├── backend/              # Flask 백엔드 서버
│   ├── app.py           # Flask 메인 앱
│   ├── config.py        # 설정 파일
│   ├── utils/           # 유틸리티 함수
│   └── requirements.txt # Python 의존성
│
├── frontend/            # React 프론트엔드
│   ├── src/
│   │   ├── components/  # React 컴포넌트
│   │   ├── services/     # API 서비스
│   │   ├── types/        # TypeScript 타입 정의
│   │   ├── constants/    # 상수 정의
│   │   └── utils/       # 유틸리티
│   ├── index.html
│   └── package.json
│
├── 00_document/         # 프로젝트 문서
│   ├── hospital_selection_pipeline.md
│   └── ...
│
└── scripts/             # 실행 스크립트
    └── start_all.sh     # 전체 서비스 실행
```

## 빠른 시작

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

## 상세 문서

- [SETUP.md](./SETUP.md) - 설치 및 실행 가이드
- [00_document/](./00_document/) - 프로젝트 문서

## 아키텍처

- **Backend**: Flask (RESTful API)
- **Frontend**: React + TypeScript + Vite
- **AI/LLM**: OpenAI (Whisper-1, GPT-4)
- **External APIs**: 국립중앙의료원, Kakao Map, Twilio

## 주요 기능

### Backend API
- `/api/hospitals/top3` - 최적 병원 Top 3 조회
- `/api/geo/coord2address` - 좌표를 주소로 변환
- `/api/geo/coord2region` - 좌표를 행정구역으로 변환
- `/api/geo/address2coord` - 주소를 좌표로 변환
- `/api/geo/route` - 경로 및 소요시간 조회
- `/api/stt/transcribe` - 음성을 텍스트로 변환 (STT)

### Frontend 기능
- 실시간 위치 기반 병원 검색
- 증상별 최적 병원 추천
- 병원 정보 카드 및 지도 표시
- 음성 입력 지원 (STT)
- 구급대원 채팅 인터페이스

## 환경 변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 다음 변수를 설정하세요:

```
KAKAO_REST_API_KEY=your_kakao_api_key
DATA_GO_KR_SERVICE_KEY=your_data_go_kr_key
OPENAI_API_KEY=your_openai_api_key
```

## 라이선스

MIT
