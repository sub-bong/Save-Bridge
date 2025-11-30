#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask Application
모듈화된 구조로 리팩토링됨
"""

from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from twilio.rest import Client as TwilioClient
import os
from pathlib import Path
from typing import Optional

# 설정 파일 import
from config import (
    FLASK_PORT, CORS_ORIGINS, DATABASE_URI,
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_CALLER_NUMBER,
    OPENAI_API_KEY
)
"""
Flask Application
모듈화된 구조로 리팩토링됨

Last updated: 2025-12-01
"""
# SQLAlchemy 모델 import
from models import db

# Flask 앱 초기화
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# 업로드 디렉토리 설정
UPLOAD_FOLDER = Path(__file__).parent / 'uploads' / 'images'
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB 최대 파일 크기


# CORS 설정
CORS(app, origins=CORS_ORIGINS, supports_credentials=True, methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'], allow_headers=['Content-Type', 'Authorization'])

# SocketIO 초기화 (WebSocket 지원)
# eventlet/gevent를 사용하면 WebSocket이 제대로 작동함
# threading 모드를 사용하면 WebSocket이 polling으로 fallback됨
# 라우트 등록은 앱 초기화 시점에 완료되므로, monkey patch는 라우트에 영향을 주지 않음
async_mode = None
# async_mode 결정
try:
    import eventlet
    async_mode = 'eventlet'
except ImportError:
    try:
        import gevent
        async_mode = 'gevent'
    except ImportError:
        async_mode = 'threading'

# SocketIO 초기화 (monkey patch 전에, 라우트 등록 전에)
# async_mode는 서버 시작 시 최종 결정됨
socketio = SocketIO(
    app, 
    cors_allowed_origins=CORS_ORIGINS,
    async_mode=async_mode,
    logger=False,  # 로그를 줄여서 성능 개선
    engineio_logger=False,
    ping_timeout=60,
    ping_interval=25,
    allow_upgrades=True,
    transports=['websocket', 'polling']  # WebSocket을 우선 시도, 실패 시 polling으로 fallback
)

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
register_chat_routes(app, socketio)
register_twilio_routes(app, call_responses, call_metadata, socketio)

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
    
    # eventlet/gevent monkey patch는 서버 시작 직전에만 수행
    # 라우트 등록은 이미 완료되었으므로 monkey patch는 라우트에 영향을 주지 않음
    final_async_mode = async_mode
    if async_mode == 'eventlet':
        try:
            import eventlet
            # monkey patch는 서버 시작 직전에만 적용
            # 라우트 등록은 이미 완료되었으므로 문제 없음
            # socket은 제외하여 DNS 해석 문제 방지
            eventlet.monkey_patch(socket=False, dns=False)
            print("✅ eventlet monkey patch 적용됨 (socket, dns 제외)")
            final_async_mode = 'eventlet'
        except Exception as e:
            print(f"⚠️  eventlet monkey patch 실패: {e}")
            final_async_mode = 'threading'
    elif async_mode == 'gevent':
        try:
            import gevent
            from gevent import monkey
            # monkey patch는 서버 시작 직전에만 적용
            monkey.patch_all()
            print("✅ gevent monkey patch 적용됨")
            final_async_mode = 'gevent'
        except Exception as e:
            print(f"⚠️  gevent monkey patch 실패: {e}")
            final_async_mode = 'threading'
    else:
        final_async_mode = 'threading'
    
    # SocketIO의 async_mode 업데이트
    socketio.async_mode = final_async_mode
    
    # Flask-SocketIO 서버 실행
    print(f"🚀 SocketIO 서버 시작 (모드: {final_async_mode})")
    if final_async_mode in ['eventlet', 'gevent']:
        print(f"📡 WebSocket 지원: ✅ 활성화 (실제 WebSocket 연결)")
        print("✅ 모든 HTTP 라우트와 WebSocket이 정상 작동합니다.")
    else:
        print(f"📡 WebSocket 지원: ⚠️ polling fallback (threading 모드)")
        print("💡 WebSocket을 제대로 사용하려면 'pip install eventlet'을 실행하세요.")
        print("✅ 모든 HTTP 라우트가 정상 작동합니다.")
    
    # 출력 버퍼링 비활성화 (로그가 즉시 표시되도록)
    import sys
    sys.stdout.flush()
    sys.stderr.flush()
    
    try:
        socketio.run(
            app,
            host='0.0.0.0',
            port=PORT,
            debug=False,
            allow_unsafe_werkzeug=True,
            use_reloader=False
        )
    except Exception as e:
        import traceback
        print(f"❌ SocketIO 서버 시작 실패: {e}")
        traceback.print_exc()
        sys.exit(1)
