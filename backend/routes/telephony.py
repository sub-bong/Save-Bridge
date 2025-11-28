#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""전화 관련 라우트 (Twilio Bridge)"""

from flask import request, jsonify
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
        if twilio_client and normalized_from:
            callback_base = resolve_callback_base(callback_base_override)
            if callback_base:
                voice_url = f"{callback_base}/twilio/gather"
                status_url = f"{callback_base}/twilio/status"
                try:
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
                except Exception as exc:
                    print(f" Twilio 전화 연결 실패: {exc}")
            else:
                print(" Twilio 콜백 URL을 찾을 수 없어 로컬 모드로 전환합니다.")
        
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

