# Backend 코드 리팩토링 계획

## 현재 상태
- `app.py`: 2209줄의 모든 코드가 한 파일에 집중
- 코드 리뷰가 어려움

## 목표 구조

```
backend/
├── app.py                    # Flask 앱 초기화만 (간소화)
├── routes/                   # 라우트 핸들러들
│   ├── __init__.py
│   ├── geo.py               # 지오코딩 API
│   ├── stt.py               # STT API
│   ├── telephony.py         # Twilio 전화 API
│   ├── hospitals.py         # 병원 조회 API
│   ├── emergency.py         # 응급 요청 API
│   ├── auth.py              # 인증 API
│   ├── chat.py              # 채팅 API
│   └── twilio.py            # Twilio 콜백
├── services/                # 비즈니스 로직
│   ├── __init__.py
│   └── hospital_service.py  # 병원 조회, 필터링, 정렬 로직
└── utils/                   # 유틸리티 함수
    ├── http.py              # HTTP 유틸리티 (완료)
    ├── geo.py               # 지오코딩 유틸리티 (완료)
    └── phone.py             # 전화번호 유틸리티 (완료)
```

## 진행 상황

### ✅ 완료
- `utils/http.py` - HTTP 유틸리티 함수
- `utils/geo.py` - 지오코딩 유틸리티 함수
- `utils/phone.py` - 전화번호 유틸리티 함수
- `routes/__init__.py` - 라우트 모듈 초기화
- `services/__init__.py` - 서비스 모듈 초기화

### 🔄 진행 중
- `services/hospital_service.py` - 병원 관련 비즈니스 로직 분리
- `routes/geo.py` - 지오코딩 라우트 분리
- `routes/stt.py` - STT 라우트 분리
- `routes/emergency.py` - 응급 요청 라우트 분리
- `routes/chat.py` - 채팅 라우트 분리
- `routes/auth.py` - 인증 라우트 분리

### 📝 다음 단계
1. `app.py`에서 분리된 모듈들을 import하여 사용
2. Blueprint를 사용하여 라우트 등록
3. 점진적으로 `app.py`의 코드를 새 파일들로 이동

## 참고사항
- 기존 `app.py`는 유지 (기능 보장)
- 새 파일들은 점진적으로 통합
- 테스트 후 기존 코드 제거

