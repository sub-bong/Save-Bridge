# Safe Bridge - 응급실 병상 찾기 서비스

응급 상황에서 최적의 병원을 찾아주는 실시간 서비스입니다.

## 프로젝트 구조

```
Save-Bridge/
├── backend/              # Flask 백엔드 서버
│   ├── app.py           # Flask 메인 앱 (라우트 등록만)
│   ├── config.py        # 설정 파일
│   ├── routes/          # API 라우트 (모듈화 완료)
│   │   ├── auth.py      # 인증 (EMS/Hospital 로그인)
│   │   ├── chat.py      # 채팅 세션/메시지
│   │   ├── emergency.py # 응급 요청 관리
│   │   ├── geo.py       # 지리 정보 (좌표, 주소, 경로)
│   │   ├── hospitals.py # 병원 검색 및 추천
│   │   ├── stt.py       # 음성 인식 (STT)
│   │   ├── telephony.py # 전화 걸기
│   │   └── twilio.py    # Twilio 콜백
│   ├── services/        # 비즈니스 로직 (모듈화 완료)
│   │   └── hospital_service.py  # 병원 관련 비즈니스 로직
│   ├── utils/           # 유틸리티 함수 (모듈화 완료)
│   │   ├── geo.py       # 지리 정보 유틸리티
│   │   ├── http.py      # HTTP 요청 유틸리티
│   │   ├── password.py  # 비밀번호 해싱/검증
│   │   └── phone.py     # 전화번호 정규화
│   ├── models/          # 데이터베이스 모델 (SQLAlchemy ORM)
│   │   └── models.py    # ORM 모델 정의
│   ├── scripts/         # 스크립트
│   │   └── seed_data.py # 시드 데이터 생성
│   ├── instance/        # 인스턴스 폴더
│   │   └── site.db      # SQLite 데이터베이스 파일 (자동 생성)
│   └── requirements.txt # Python 의존성
│
├── frontend/            # React 프론트엔드
│   ├── src/
│   │   ├── components/  # React 컴포넌트
│   │   │   ├── SafeBridgeApp.tsx      # 구급대원 메인 앱
│   │   │   ├── ERDashboard.tsx        # 응급실 대시보드
│   │   │   ├── ParamedicChatSlideOver.tsx  # 구급대원 채팅
│   │   │   └── ...
│   │   ├── services/    # API 서비스
│   │   │   └── api.ts   # API 클라이언트
│   │   ├── types/       # TypeScript 타입 정의
│   │   ├── constants/   # 상수 정의
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

데이터베이스 파일 위치: `backend/instance/site.db`

### 시드 데이터 생성 (목업 데이터)

구급차 팀 및 병원 비밀번호 설정을 위해:

```bash
cd backend
python scripts/seed_data.py
```

이 스크립트는 다음을 수행합니다:
- 데이터베이스 테이블 자동 생성
- 구급차 팀 목업 데이터 생성 (비밀번호는 해시로 저장)
- 기존 병원에 기본 비밀번호 설정 (비밀번호가 없는 경우만)

**참고:**
- 구급차 팀 기본 비밀번호: `password123`
- 병원 기본 비밀번호: `hospital123`
- 모든 비밀번호는 해시되어 저장됩니다 (Werkzeug의 `generate_password_hash` 사용)
- 실제 운영 시에는 각 병원별로 고유한 강력한 비밀번호를 설정하세요
- 병원 데이터는 국립중앙의료원 API에서 실시간으로 조회되므로 시드 데이터로 생성하지 않습니다

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

- `ems_team` - 구급차 정보 (ems_id, password 해시, region)
- `hospital` - 병원 정보 (hospital_id, name, address, password 해시 등)
- `emergency_request` - 응급실 입실 요청 (request_id, team_id, 환자 정보 등)
- `request_assignment` - 요청-병원 매칭 및 응답 기록 (승인/거절/대기중 상태 포함)
- `chat_session` - 채팅 세션 정보 (request_id와 assignment_id 연결)
- `chat_message` - 채팅 메시지 내용 (EMS/HOSPITAL 구분)

**관계:**
- `EmergencyRequest` 1:N `RequestAssignment` (하나의 요청에 여러 병원 매칭 가능)
- `RequestAssignment` 1:1 `ChatSession` (승인된 경우에만 생성)
- `ChatSession` 1:N `ChatMessage` (하나의 세션에 여러 메시지)

### 참고사항

- SQLite는 파일 기반 데이터베이스이므로 별도의 서버 설치가 필요 없습니다
- DBeaver에서 테이블 구조 확인, 데이터 조회, SQL 쿼리 실행이 가능합니다
- 데이터베이스 URI는 `backend/config.py`의 `DATABASE_URI`에서 설정할 수 있습니다

## 📖 상세 문서

- [SETUP.md](./SETUP.md) - 설치 및 실행 가이드
- [00_document/](./00_document/) - 프로젝트 문서

## 아키텍처

### Backend 구조 (모듈화 완료)
- **Flask App**: `app.py` - Flask 앱 초기화 및 라우트 등록만 담당
- **Routes**: `routes/` - API 엔드포인트별로 모듈화
  - `auth.py` - 인증 관련
  - `chat.py` - 채팅 관련
  - `emergency.py` - 응급 요청 관련
  - `geo.py` - 지리 정보 관련
  - `hospitals.py` - 병원 검색 관련
  - `stt.py` - 음성 인식 관련
  - `telephony.py` - 전화 걸기 관련
  - `twilio.py` - Twilio 콜백 관련
- **Services**: `services/` - 비즈니스 로직
  - `hospital_service.py` - 병원 검색, 필터링, 우선순위 결정 로직
- **Utils**: `utils/` - 유틸리티 함수
  - `geo.py` - 지리 정보 계산 (거리, 좌표 변환 등)
  - `http.py` - HTTP 요청 유틸리티
  - `password.py` - 비밀번호 해싱/검증
  - `phone.py` - 전화번호 정규화
- **Models**: `models/models.py` - SQLAlchemy ORM 모델

### 기술 스택
- **Backend**: Flask + SQLAlchemy ORM (RESTful API)
- **Database**: SQLite (개발 환경) - `instance/site.db`
- **Frontend**: React + TypeScript + Vite
- **AI/LLM**: OpenAI (Whisper-1, GPT-4-turbo)
- **External APIs**: 
  - 국립중앙의료원 API (병원 정보, 병상 정보)
  - Kakao Map API (지도, 경로, 좌표 변환)
  - Twilio (전화 걸기, ARS)

## 주요 기능

### Backend API

#### 인증 (routes/auth.py)
- `POST /api/auth/login` - EMS 팀 로그인
- `POST /api/auth/hospital-login` - 병원 로그인
- `POST /api/auth/logout` - 로그아웃
- `GET /api/auth/me` - 현재 로그인한 사용자 정보 (EMS 또는 Hospital)
- `POST /api/auth/set-hospital-password` - 병원 비밀번호 설정 (관리자용)

#### 지리 정보 (routes/geo.py)
- `GET /api/geo/coord2address` - 좌표를 주소로 변환
- `GET /api/geo/coord2region` - 좌표를 행정구역으로 변환
- `GET /api/geo/address2coord` - 주소를 좌표로 변환
- `GET /api/geo/route` - 경로 및 소요시간 조회

#### 병원 검색 (routes/hospitals.py)
- `POST /api/hospitals/top3` - 최적 병원 Top 3 조회 (증상, 위치 기반)

#### 음성 인식 (routes/stt.py)
- `POST /api/stt/transcribe` - 음성을 텍스트로 변환 (OpenAI Whisper)

#### 응급 요청 (routes/emergency.py)
- `POST /api/emergency/request` - 응급실 입실 요청 생성
- `GET /api/emergency/requests` - 응급 요청 목록 조회 (assignments 포함)
- `GET /api/emergency/request/<request_id>` - 특정 응급 요청 조회 (assignments 포함)
- `POST /api/emergency/call-hospital` - 병원에 전화 걸기 및 RequestAssignment 생성
- `GET /api/emergency/assignments` - RequestAssignment 목록 조회 (request_id별 수용/거절 병원 목록)
- `POST /api/emergency/update-response` - 병원 응답 상태 업데이트 (승인/거절, ChatSession 자동 생성)

#### 채팅 (routes/chat.py)
- `GET /api/chat/session` - ChatSession 조회 (request_id 또는 assignment_id로)
- `GET /api/chat/sessions` - ChatSession 목록 조회 (응급실 대시보드용, hospital_id 필터링 가능)
- `GET /api/chat/messages?session_id=<id>` - 채팅 메시지 조회
- `POST /api/chat/messages` - 채팅 메시지 전송

#### 전화 (routes/telephony.py, routes/twilio.py)
- `POST /api/telephony/call` - 전화 걸기
- `GET /api/telephony/response/<call_sid>` - 전화 응답 확인
- `POST /twilio/gather` - Twilio 다이얼 입력 콜백
- `POST /twilio/status` - Twilio 통화 상태 콜백

### Frontend 기능

#### 구급대원 앱 (SafeBridgeApp.tsx)
- 실시간 위치 기반 병원 검색
- 증상별 최적 병원 추천
- 병원 정보 카드 및 지도 표시
- 음성 입력 지원 (STT)
- 병원 승인/거절 처리
- 구급대원 채팅 인터페이스 (ParamedicChatSlideOver.tsx)
  - 초기 STT 메시지 자동 저장
  - 실시간 양방향 채팅 (3초마다 자동 새로고침)
  - 이미지 첨부 지원

#### 응급실 대시보드 (ERDashboard.tsx)
- 병원 로그인 화면 (hospital_id + password)
- 로그인한 병원의 채팅 세션 목록 조회
- 양방향 채팅 지원 (실시간 메시지 교환)
- 환자 정보 및 인계 체크포인트 표시
- 세션별 메시지 자동 새로고침 (3초마다)

## 환경 변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 다음 변수를 설정하세요:

```
KAKAO_REST_API_KEY=your_kakao_api_key
DATA_GO_KR_SERVICE_KEY=your_data_go_kr_key
OPENAI_API_KEY=your_openai_api_key
```

## 라이선스

MIT
