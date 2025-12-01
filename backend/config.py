#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backend 설정 파일
"""

import os
from pathlib import Path

# .env 파일 로드 (상위 디렉토리에서 찾기)
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(dotenv_path=env_path)
except ImportError:
    # python-dotenv가 없으면 환경변수에서 직접 읽기
    pass

# API 키 설정 (환경변수에서 읽기, 없으면 에러)
KAKAO_KEY = os.getenv("KAKAO_REST_API_KEY")
if not KAKAO_KEY:
    raise ValueError("KAKAO_REST_API_KEY 환경변수가 설정되지 않았습니다. .env 파일을 확인하세요.")

DATA_GO_KR_KEY = os.getenv("DATA_GO_KR_SERVICE_KEY")
if not DATA_GO_KR_KEY:
    raise ValueError("DATA_GO_KR_SERVICE_KEY 환경변수가 설정되지 않았습니다. .env 파일을 확인하세요.")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다. .env 파일을 확인하세요.")

# Twilio 설정 (선택 사항)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_CALLER_NUMBER = os.getenv("TWILIO_CALLER_NUMBER")
TWILIO_FALLBACK_TARGET = os.getenv("TWILIO_FALLBACK_TARGET", "01049323766")
TWILIO_CALLBACK_BASE_URL = os.getenv("TWILIO_CALLBACK_BASE_URL")

# API URL
ER_BED_URL = "https://apis.data.go.kr/B552657/ErmctInfoInqireService/getEmrrmRltmUsefulSckbdInfoInqire"
EGET_BASE_URL = "https://apis.data.go.kr/B552657/ErmctInfoInqireService/getEgytBassInfoInqire"
EGET_LIST_URL = "https://apis.data.go.kr/B552657/ErmctInfoInqireService/getEgytListInfoInqire"
STRM_LIST_URL = "https://apis.data.go.kr/B552657/ErmctInfoInqireService/getStrmListInfoInqire"
KAKAO_DIRECTIONS_URL = "https://apis-navi.kakaomobility.com/v1/directions"

# 카카오 API URL
KAKAO_COORD2REGION_URL = "https://dapi.kakao.com/v2/local/geo/coord2regioncode.json"
KAKAO_COORD2ADDR_URL = "https://dapi.kakao.com/v2/local/geo/coord2address.json"
KAKAO_ADDRESS_URL = "https://dapi.kakao.com/v2/local/search/address.json"

# 증상별 필수 요구사항
SYMPTOM_RULES = {
    "뇌졸중 의심(FAST+)": {"bool_any":[("hvctayn","Y")], "min_ge1":[("hvicc",1)], "nice_to_have":[("hv5",1),("hv6",1)]},
    "심근경색 의심(STEMI)": {"bool_any":[("hvangioayn","Y")], "min_ge1":[("hvoc",1),("hvicc",1)], "nice_to_have":[]},
    "다발성 외상/중증 외상": {"bool_any":[("hvventiayn","Y")], "min_ge1":[("hvoc",1),("hvicc",1)], "nice_to_have":[("hv9",1)]},
    "성인 호흡곤란": {"bool_any":[("hvventiayn","Y")], "min_ge1":[("hvicc",1),("hvcc",1)], "nice_to_have":[]},
    "소아 호흡곤란": {"bool_any":[("hv10","Y"),("hv11","Y")], "min_ge1":[("hvncc",1)], "nice_to_have":[]},
    "성인 경련": {"bool_any":[("hvctayn","Y")], "min_ge1":[("hvicc",1),("hv5",1)], "nice_to_have":[]},
    "소아 경련": {"bool_any":[("hv10","Y"),("hv11","Y")], "min_ge1":[("hvncc",1)], "nice_to_have":[]},
    "정형외과 중증(대형골절/절단)": {"bool_any":[], "min_ge1":[("hvoc",1),("hv3",1),("hv4",1)], "nice_to_have":[]},
    "신경외과 응급(의식저하/외상성출혈)": {"bool_any":[("hvctayn","Y")], "min_ge1":[("hv6",1),("hvicc",1)], "nice_to_have":[]},
    "소아 중증(신생아/영아)": {"bool_any":[("hv10","Y"),("hv11","Y")], "min_ge1":[("hvncc",1)], "nice_to_have":[]},
}

# 지역 매핑
METRO_FALLBACK_PROVINCE: dict = {
    "서울특별시": "경기도",
    "인천광역시": "경기도",
    "광주광역시": "전라남도",
    "대전광역시": "충청남도",
    "울산광역시": "경상남도",
    "부산광역시": "경상남도",
    "대구광역시": "경상북도",
    "세종특별자치시": "충청남도",
}

PROVINCE_INCLUDE_METROS: dict = {
    "경기도": ["서울특별시", "인천광역시"],
    "전라남도": ["광주광역시"],
    "충청남도": ["대전광역시", "세종특별자치시"],
    "경상남도": ["부산광역시", "울산광역시"],
    "경상북도": ["대구광역시"],
}

# Flask 서버 설정
FLASK_PORT = 5001
CORS_ORIGINS = [
    "http://localhost:5173", 
    "http://localhost:5174", 
    "http://localhost:3000",
    "https://localhost:5173",  # HTTPS localhost 추가
    "https://localhost:5174",
    "http://10.50.1.62:5173",  
    "http://10.50.1.62:5174",
    "https://10.50.1.62:5173",  # HTTPS 로컬 IP 추가
    "https://10.50.1.62:5174",
    "http://sondongbin-ui-MacBookPro.local:5173",  # .local 도메인 (모바일 카메라 접근용)
    "http://sondongbin-ui-MacBookPro.local:5174",
]
# 데이터베이스 설정
# SQLite 데이터베이스 파일 경로
# - 기본값: backend/instance/site.db (이 파일 기준 상대 경로)
# - DBeaver에서 접속할 때: 프로젝트 루트 기준으로 backend/instance/site.db 선택
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "instance" / "site.db"
DATABASE_URI = os.getenv("DATABASE_URI", f"sqlite:///{DEFAULT_DB_PATH}")

