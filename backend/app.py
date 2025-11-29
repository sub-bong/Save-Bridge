#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask Application
모듈화된 구조로 리팩토링됨
"""

from flask import Flask
from flask_cors import CORS
from twilio.rest import Client as TwilioClient
import os
from typing import Optional

# 설정 파일 import
from config import (
    FLASK_PORT, CORS_ORIGINS, DATABASE_URI,
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_CALLER_NUMBER,
    OPENAI_API_KEY
)

# SQLAlchemy 모델 import
from models import db

# Flask 앱 초기화
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# CORS 설정
CORS(app, origins=CORS_ORIGINS, supports_credentials=True, methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'], allow_headers=['Content-Type', 'Authorization'])

# SQLAlchemy 설정
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# OpenAI API 클라이언트
openai_client = None
try:
    from openai import OpenAI
    if OPENAI_API_KEY:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
except ImportError:
    print("⚠️  OpenAI 패키지가 설치되지 않았습니다. STT 기능을 사용하려면 'pip install openai'를 실행하세요.")

# Twilio REST 클라이언트
twilio_client: Optional[TwilioClient] = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    try:
        twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    except Exception as exc:
        print(f"⚠️  Twilio 클라이언트를 초기화하지 못했습니다: {exc}")

# 전역 변수: 다이얼 입력 저장 (Twilio 콜백용)
call_responses = {}
active_mock_calls = {}
call_metadata = {}

# 라우트 등록 (모듈화된 라우트 사용)
from routes.geo import register_geo_routes
from routes.stt import register_stt_routes
from routes.telephony import register_telephony_routes
from routes.hospitals import register_hospitals_routes
from routes.emergency import register_emergency_routes
from routes.auth import register_auth_routes
from routes.chat import register_chat_routes
from routes.twilio import register_twilio_routes

# 라우트 등록
register_geo_routes(app)
register_stt_routes(app, openai_client)
register_telephony_routes(app, twilio_client, call_responses, active_mock_calls, call_metadata)
register_hospitals_routes(app)
register_emergency_routes(app)
register_auth_routes(app)
register_chat_routes(app)
register_twilio_routes(app, call_responses, call_metadata)

# 서버 상태 확인 페이지
@app.route('/')
def index():
    """서버 상태 확인"""
    return """
    <html>
    <head><title>Save Bridge Flask Server</title></head>
    <body style="font-family: Arial; padding: 2rem;">
        <h1>Save Bridge Flask Server 실행 중</h1>
        <p><b>포트:</b> {}</p>
        <p><b>엔드포인트:</b></p>
        <ul>
            <li><code>/api/geo/coord2address</code> - 좌표 → 주소 변환</li>
            <li><code>/api/geo/coord2region</code> - 좌표 → 행정구역 변환</li>
            <li><code>/api/geo/address2coord</code> - 주소 → 좌표 변환</li>
            <li><code>/api/geo/route</code> - 경로 조회</li>
            <li><code>/api/stt/transcribe</code> - 음성 → 텍스트 변환 (STT)</li>
            <li><code>/api/hospitals/top3</code> - 병원 Top3 조회</li>
            <li><code>/api/auth/login</code> - EMS 팀 로그인</li>
            <li><code>/api/auth/logout</code> - 로그아웃</li>
            <li><code>/api/auth/me</code> - 현재 로그인한 사용자 정보</li>
            <li><code>/api/emergency/request</code> - 응급실 입실 요청 생성</li>
            <li><code>/api/emergency/requests</code> - 응급 요청 목록 조회</li>
            <li><code>/api/emergency/call-hospital</code> - 병원에 전화 걸기</li>
            <li><code>/api/emergency/assignments</code> - RequestAssignment 목록 조회</li>
            <li><code>/api/emergency/update-response</code> - 병원 응답 상태 업데이트</li>
            <li><code>/api/chat/session</code> - 채팅 세션 조회</li>
            <li><code>/api/chat/sessions</code> - 채팅 세션 목록 조회</li>
            <li><code>/api/chat/messages</code> - 채팅 메시지 조회/생성</li>
            <li><code>/api/telephony/call</code> - 전화 걸기</li>
            <li><code>/twilio/gather</code> - Twilio 다이얼 입력 콜백</li>
            <li><code>/twilio/status</code> - Twilio 통화 상태 콜백</li>
        </ul>
    </body>
    </html>
    """.format(FLASK_PORT)

if __name__ == '__main__':
    PORT = FLASK_PORT
    
    print("=" * 60)
    print(" Save Bridge Flask Server 시작")
    print("=" * 60)
    print(f" URL: http://localhost:{PORT}")
    print(f" Gather Callback: http://localhost:{PORT}/twilio/gather")
    print(f" Status Callback: http://localhost:{PORT}/twilio/status")
    print("=" * 60)
    print("\n 다음 단계:")
    print(f"1. 새 터미널을 열어서 'ngrok http {PORT}' 실행")
    print("2. ngrok URL (예: https://xxxx.ngrok.io)을 복사")
    print("3. Streamlit 앱의 'Twilio 다이얼 입력 설정'에 URL 입력\n")
    print("=" * 60)
    print("서버 실행 중... (Ctrl+C로 종료)\n")
    
    # 데이터베이스 테이블 생성 (앱 시작 시)
    with app.app_context():
        db.create_all()
        print("✅ Database tables created!")
        print(f"📁 Database file: {DATABASE_URI}")
        print("💡 DBeaver 연결 정보:")
        print("   - Database Type: SQLite")
        db_path = os.path.abspath('site.db') if 'site.db' in DATABASE_URI else DATABASE_URI
        print(f"   - Path: {db_path}")
    
    # Flask 서버 실행
    app.run(
        host='0.0.0.0',
        port=PORT,
        debug=False,
        use_reloader=False
    )
