# Safe Bridge - 응급실 병상 찾기 서비스

응급 상황에서 최적의 병원을 찾아주는 실시간 서비스입니다.

## 프로젝트 구조

```
Save-Bridge/
├── backend/              # Flask 백엔드 서버
│   ├── app.py           # Flask 메인 앱
│   ├── config.py        # 설정 파일
│   ├── routes/          # API 라우트 (모듈화 예정)
│   ├── services/        # 비즈니스 로직 (모듈화 예정)
│   ├── models/          # 데이터베이스 모델 (SQLAlchemy ORM)
│   │   └── models.py    # ORM 모델 정의
│   ├── utils/           # 유틸리티 함수
│   ├── requirements.txt # Python 의존성
│   └── site.db          # SQLite 데이터베이스 파일 (자동 생성)
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
    ├── start_all.sh     # 전체 서비스 실행 (구급대원 앱)
    └── start_er_dashboard.sh  # 응급실 대시보드 실행
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

### 4. 응급실 대시보드 실행

응급실 대시보드를 별도로 실행하려면:

```bash
bash scripts/start_er_dashboard.sh
```

이 스크립트는:
- Flask 서버를 백그라운드로 실행 (포트 5001)
- React 앱을 응급실 대시보드 모드로 실행 (포트 5173, `?mode=er` 파라미터 포함)
- 브라우저에서 `http://localhost:5173?mode=er` 자동 열기

**참고:**
- 구급대원 앱과 응급실 대시보드는 같은 백엔드 API를 공유합니다
- 두 앱을 동시에 실행하려면 각각 다른 포트에서 실행하거나, 하나의 React 앱에서 URL 파라미터로 모드를 전환할 수 있습니다

## 🗄️ 데이터베이스 설정

### SQLAlchemy ORM 사용

프로젝트는 Flask-SQLAlchemy를 사용하여 데이터베이스를 관리합니다.

### 데이터베이스 파일 생성

Flask 앱을 실행하면 자동으로 `site.db` 파일이 생성됩니다:

```bash
cd backend
python app.py
```

데이터베이스 파일 위치: `/Users/tasha/Projects/Save-Bridge/site.db`

### 시드 데이터 생성 (목업 데이터)

구급차 팀 목업 데이터를 생성하려면:

```bash
cd backend
python scripts/seed_data.py
```

이 스크립트는 다음을 수행합니다:
- 데이터베이스 테이블 자동 생성
- 구급차 팀 목업 데이터 생성 (비밀번호는 해시로 저장)
- 병원 데이터는 국립중앙의료원 API에서 실시간으로 조회되므로 시드 데이터로 생성하지 않습니다

**참고:**
- 구급차 팀 기본 비밀번호: `password123`
- 비밀번호는 해시되어 저장됩니다
- 실제 운영 시에는 더 강력한 비밀번호를 사용하세요

### DBeaver 연결 방법

1. **DBeaver 실행**
   - DBeaver를 실행합니다

2. **새 연결 생성**
   - `Database` → `New Database Connection` 클릭
   - 또는 상단 툴바의 `새 연결` 아이콘 클릭

3. **SQLite 선택**
   - 데이터베이스 목록에서 `SQLite` 선택
   - `Next` 클릭

4. **경로 설정**
   - **Path**: `/Users/tasha/Projects/Save-Bridge/backend/instance/site.db`
   - 또는 `Browse...` 버튼을 클릭하여 파일 직접 선택
   - `Test Connection` 클릭하여 연결 테스트
   - 만약 시퀄 없으면 `Download SQLite driver files` 링크를 클릭하거나 하단의 `Download` 버튼

5. **완료**
   - `Finish` 클릭하여 연결 완료

### 데이터베이스 구조

다음 테이블들이 생성됩니다:

- `ems_team` - 구급차 정보
- `hospital` - 병원 정보
- `emergency_request` - 응급실 입실 요청
- `request_assignment` - 요청-병원 매칭 및 응답 기록
- `chat_session` - 채팅 세션 정보
- `chat_message` - 채팅 메시지 내용

### 참고사항

- SQLite는 파일 기반 데이터베이스이므로 별도의 서버 설치가 필요 없습니다
- DBeaver에서 테이블 구조 확인, 데이터 조회, SQL 쿼리 실행이 가능합니다
- 데이터베이스 URI는 `backend/config.py`의 `DATABASE_URI`에서 설정할 수 있습니다

## 📖 상세 문서

- [SETUP.md](./SETUP.md) - 설치 및 실행 가이드
- [00_document/](./00_document/) - 프로젝트 문서

## 아키텍처

- **Backend**: Flask + SQLAlchemy ORM (RESTful API) + WebSocket (예정)
- **Database**: SQLite (개발 환경)
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
- `/api/emergency/request` - 응급실 입실 요청 생성
- `/api/emergency/call-hospital` - 병원에 전화 걸기 및 RequestAssignment 생성
- `/api/emergency/update-response` - 병원 응답 상태 업데이트 (승인/거절)
- `/api/chat/session` - ChatSession 조회 (request_id 또는 assignment_id로)
- `/api/chat/sessions` - ChatSession 목록 조회 (응급실 대시보드용)
- `/api/chat/messages` - 채팅 메시지 조회(GET) 및 전송(POST)

### Frontend 기능
- 실시간 위치 기반 병원 검색
- 증상별 최적 병원 추천
- 병원 정보 카드 및 지도 표시
- 음성 입력 지원 (STT)
- 구급대원 채팅 인터페이스
- 응급실 대시보드 (양방향 채팅 지원)

## 환경 변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 다음 변수를 설정하세요:

```
KAKAO_REST_API_KEY=your_kakao_api_key
DATA_GO_KR_SERVICE_KEY=your_data_go_kr_key
OPENAI_API_KEY=your_openai_api_key
```

## 라이선스

MIT
