#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""전화 관련 라우트 (Twilio Bridge)"""

from flask import request, jsonify, url_for
import uuid
import time
from datetime import datetime
from models import db, RequestAssignment
from utils.phone import normalize_phone_number, resolve_callback_base
from config import (
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_CALLER_NUMBER,
    TWILIO_FALLBACK_TARGET
)


def register_telephony_routes(app, twilio_client, call_responses, active_mock_calls, call_metadata):
    """전화 관련 라우트 등록"""
    
    @app.route('/api/telephony/call', methods=['POST', 'OPTIONS'])
    def api_telephony_call():
        if request.method == 'OPTIONS':
            return '', 200
        
        data = request.get_json(force=True, silent=True) or {}
        hospital_tel = data.get('hospital_tel') or TWILIO_FALLBACK_TARGET
        hospital_name = data.get('hospital_name') or "미상 응급의료기관"
        patient_info = data.get('patient_info')
        callback_base_override = data.get('callback_url')
        
        normalized_to = normalize_phone_number(hospital_tel) or normalize_phone_number(TWILIO_FALLBACK_TARGET)
        normalized_from = normalize_phone_number(TWILIO_CALLER_NUMBER) if TWILIO_CALLER_NUMBER else None
        
        if not normalized_to:
            return jsonify({"error": "연결할 응급실 전화번호를 확인할 수 없습니다."}), 400
        
        call_sid = str(uuid.uuid4())
        used_twilio = False
        
        print(f"\n📞 전화 발신 시도:")
        print(f"   병원: {hospital_name}")
        print(f"   전화번호: {normalized_to}")
        print(f"   Twilio 클라이언트: {'있음' if twilio_client else '없음'}")
        print(f"   발신 번호: {normalized_from}")
        
        if twilio_client and normalized_from:
            callback_base = resolve_callback_base(callback_base_override)
            print(f"   콜백 URL: {callback_base}")
            
            if callback_base:
                voice_url = f"{callback_base}/twilio/gather"
                status_url = f"{callback_base}/twilio/status"
                print(f"   Voice URL: {voice_url}")
                print(f"   Status URL: {status_url}")
                
                try:
                    print(f"   ⏳ Twilio API 호출 중...")
                    call = twilio_client.calls.create(
                        to=normalized_to,
                        from_=normalized_from,
                        url=voice_url,
                        method="POST",
                        status_callback=status_url,
                        status_callback_method="POST",
                        status_callback_event=["initiated", "ringing", "answered", "completed"],
                        record=False
                    )
                    call_sid = call.sid
                    used_twilio = True
                    print(f"   ✅ Twilio 전화 발신 성공! Call SID: {call_sid}")
                    print(f"   📱 {normalized_to}로 전화가 발신되었습니다.")
                except Exception as exc:
                    print(f"   ❌ Twilio 전화 연결 실패: {exc}")
                    import traceback
                    print(f"   상세 오류:\n{traceback.format_exc()}")
            else:
                # 콜백 URL이 없어도 전화를 발신 시도 (공개 URL이 필요하지만 일단 시도)
                print(f"   ⚠️ Twilio 콜백 URL이 없습니다. 전화 발신을 시도합니다.")
                
                # Twilio는 공개 URL이 필요하지만, 일단 localhost를 시도해봅니다
                # 실제로는 ngrok 등 공개 터널이 필요합니다
                try:
                    callback_base = request.host_url.rstrip('/')
                    voice_url = f"{callback_base}/twilio/gather"
                    status_url = f"{callback_base}/twilio/status"
                    
                    print(f"   콜백 URL (시도): {voice_url}")
                    print(f"   ⚠️ 경고: localhost URL은 Twilio가 접근할 수 없습니다.")
                    print(f"   전화는 발신되지만 ARS 기능은 작동하지 않을 수 있습니다.")
                    print(f"   공개 URL을 사용하려면 ngrok을 실행하고 TWILIO_CALLBACK_BASE_URL 환경변수를 설정하세요.")
                    
                    call = twilio_client.calls.create(
                        to=normalized_to,
                        from_=normalized_from,
                        url=voice_url,
                        method="POST",
                        status_callback=status_url,
                        status_callback_method="POST",
                        status_callback_event=["initiated", "ringing", "answered", "completed"],
                        record=False
                    )
                    call_sid = call.sid
                    used_twilio = True
                    print(f"   ✅ Twilio 전화 발신 성공! Call SID: {call_sid}")
                    print(f"   📱 {normalized_to}로 전화가 발신되었습니다.")
                except Exception as exc2:
                    print(f"   ❌ 콜백 URL 없이 전화 발신 실패: {exc2}")
                    import traceback
                    print(f"   상세 오류:\n{traceback.format_exc()}")
                    # 실패해도 Mock Call 대신 실제 전화 발신 시도 (간단한 TwiML 사용)
                    try:
                        print(f"   🔄 간단한 TwiML로 전화 발신 재시도...")
                        # TwiML을 직접 제공하는 대신, 최소한의 URL로 전화 발신 시도
                        # 공개 URL이 필요하므로 여전히 실패할 수 있음
                        from twilio.twiml.voice_response import VoiceResponse
                        twiml = VoiceResponse()
                        twiml.say("응급환자 수용 요청입니다. 1번을 누르시면 수용, 2번을 누르시면 거절입니다.", language="ko-KR", voice="Polly.Seoyeon")
                        twiml.gather(numDigits=1, action=f"{callback_base}/twilio/gather", method="POST", timeout=10)
                        
                        # TwiML을 직접 사용할 수 없으므로, 공개 URL이 필수
                        print(f"   ❌ TwiML 직접 제공은 불가능합니다. 공개 URL(ngrok)이 필요합니다.")
                        print(f"   ⚠️ Mock Call로 처리합니다. 실제 전화가 발신되지 않습니다.")
                    except Exception as exc3:
                        print(f"   ❌ 전화 발신 재시도도 실패: {exc3}")
                        print(f"   ⚠️ Mock Call로 처리합니다. 실제 전화가 발신되지 않습니다.")
        else:
            if not twilio_client:
                print(f"   ⚠️ Twilio 클라이언트가 초기화되지 않았습니다.")
            if not normalized_from:
                print(f"   ⚠️ 발신 번호(TWILIO_CALLER_NUMBER)가 설정되지 않았습니다.")
        
        if not used_twilio:
            active_mock_calls[call_sid] = {
                "hospital_tel": normalized_to,
                "hospital_name": hospital_name,
                "patient_info": patient_info,
                "timestamp": time.time(),
            }
            print(f" [Mock Call] {hospital_name} ({normalized_to}) 대상 호출. call_sid={call_sid}")
        
        # 초기 상태 저장 (Twilio 콜백에서 digit 업데이트) - 메모리 (하위 호환성)
        call_metadata[call_sid] = {
            "patient_info": patient_info or "",
            "hospital_name": hospital_name,
            "hospital_tel": normalized_to,
            "timestamp": time.time(),
        }
        call_responses[call_sid] = {
            "digit": None,
            "timestamp": time.time(),
            "patient_info": patient_info or "",
            "status": "initiated"
        }
        
        # DB에 저장: assignment_id가 제공된 경우 RequestAssignment 업데이트
        assignment_id = data.get('assignment_id')
        if assignment_id:
            try:
                assignment_id = int(assignment_id)
            except (ValueError, TypeError):
                assignment_id = None
        if assignment_id:
            try:
                assignment = RequestAssignment.query.get(assignment_id)
                if assignment:
                    assignment.twillio_sid = call_sid
                    assignment.called_at = datetime.now()
                    db.session.commit()
                    print(f" RequestAssignment {assignment_id}에 Call SID {call_sid} 저장됨")
            except Exception as e:
                db.session.rollback()
                import traceback
                print(f" DB 저장 오류: {traceback.format_exc()}")
        
        return jsonify({"call_sid": call_sid}), 200

    @app.route('/api/telephony/response/<call_sid>', methods=['GET'])
    def api_telephony_response(call_sid: str):
        """전화 응답 조회"""
        record = call_responses.get(call_sid)
        if record:
            return jsonify({
                "digit": record.get("digit"),
                "status": record.get("status")
            }), 200
        mock = active_mock_calls.get(call_sid)
        if mock:
            return jsonify({
                "digit": mock.get("digit"),
                "status": mock.get("status")
            }), 200
        return jsonify({"digit": None, "status": None}), 404

