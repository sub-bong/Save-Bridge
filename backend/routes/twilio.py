#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Twilio 콜백 관련 라우트"""

from flask import request
from twilio.twiml.voice_response import VoiceResponse
import time
from datetime import datetime
from models import db, RequestAssignment, ChatSession


def register_twilio_routes(app, call_responses, call_metadata):
    """Twilio 콜백 라우트 등록"""
    
    @app.route('/twilio/gather', methods=['POST'])
    def twilio_gather_callback():
        """Twilio Gather 콜백 - 다이얼 입력 받기"""
        digits = request.form.get('Digits', '')
        call_sid = request.form.get('CallSid', '')
        patient_info = call_metadata.get(call_sid, {}).get("patient_info") or call_responses.get(call_sid, {}).get("patient_info")
        
        print(f"\n [Twilio Callback] Call SID: {call_sid}")
        print(f" 입력된 다이얼: {digits}")
        
        # 응답 TwiML 생성
        response = VoiceResponse()
        
        if not digits:
            message = patient_info or "응급환자 상태 정보가 전달되지 않았습니다."
            gather = response.gather(
                numDigits=1,
                action="/twilio/gather",
                method="POST",
                timeout=8
            )
            gather.say(message, language="ko-KR", voice="Polly.Seoyeon")
            gather.pause(length=1)
            gather.say("해당 환자 수용이 가능하시면 1번, 수용이 불가능하시면 2번을 눌러주세요.", language="ko-KR", voice="Polly.Seoyeon")
            return str(response), 200, {'Content-Type': 'text/xml'}
        
        # 입력값 저장 (메모리 - 하위 호환성)
        record = call_responses.setdefault(call_sid, {})
        record.update({
            "digit": digits,
            "timestamp": time.time(),
            "patient_info": patient_info
        })
        
        # DB에 저장: RequestAssignment 업데이트
        try:
            assignment = RequestAssignment.query.filter_by(twillio_sid=call_sid).first()
            if assignment:
                if digits == "1":
                    assignment.response_status = "승인"
                    assignment.responded_at = datetime.now()
                    # 승인된 경우 ChatSession 생성
                    existing_session = ChatSession.query.filter_by(request_id=assignment.request_id).first()
                    if not existing_session:
                        chat_session = ChatSession(
                            request_id=assignment.request_id,
                            assignment_id=assignment.assignment_id,
                            started_at=datetime.now()
                        )
                        db.session.add(chat_session)
                    print(" 1번 입력 - 입실 승인 (DB 저장됨)")
                elif digits == "2":
                    assignment.response_status = "거절"
                    assignment.responded_at = datetime.now()
                    print(" 2번 입력 - 입실 거절 (DB 저장됨)")
                else:
                    print(f" 잘못된 입력: {digits}")
                
                db.session.commit()
            else:
                print(f" Warning: Call SID {call_sid}에 해당하는 RequestAssignment를 찾을 수 없습니다.")
        except Exception as e:
            db.session.rollback()
            import traceback
            print(f" DB 저장 오류: {traceback.format_exc()}")
        
        if digits == "1":
            response.say("입실 승인 확인되었습니다. 감사합니다.", language="ko-KR", voice="Polly.Seoyeon")
        elif digits == "2":
            response.say("입실 불가 확인되었습니다. 다른 병원을 찾겠습니다.", language="ko-KR", voice="Polly.Seoyeon")
        else:
            response.say("잘못된 입력입니다.", language="ko-KR", voice="Polly.Seoyeon")
        
        return str(response), 200, {'Content-Type': 'text/xml'}

    @app.route('/twilio/status', methods=['POST'])
    def twilio_status_callback():
        """통화 상태 콜백"""
        call_sid = request.form.get('CallSid', '')
        call_status = request.form.get('CallStatus', '')
        
        print(f"\n [통화 상태] Call SID: {call_sid}, Status: {call_status}")
        
        # 메모리에 저장 (하위 호환성)
        record = call_responses.setdefault(call_sid, {})
        record['status'] = call_status or record.get('status')
        
        return "", 200

    @app.route('/responses', methods=['GET'])
    def get_responses():
        """저장된 응답 확인 (디버깅용)"""
        if not call_responses:
            return "<h2>저장된 응답이 없습니다.</h2>"
        
        html = "<html><head><title>저장된 응답</title></head><body style='font-family: Arial; padding: 2rem;'>"
        html += "<h1>저장된 다이얼 응답</h1><hr>"
        
        for call_sid, data in call_responses.items():
            digit = data.get('digit')
            timestamp = data.get('timestamp')
            time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
            
            status = "승인" if digit == "1" else "거절" if digit == "2" else "기타"
            
            html += f"""
            <div style='border: 1px solid #ddd; padding: 1rem; margin: 1rem 0; border-radius: 8px;'>
                <b>Call SID:</b> {call_sid}<br>
                <b>입력:</b> {digit} ({status})<br>
                <b>시간:</b> {time_str}
            </div>
            """
        
        html += "</body></html>"
        return html

    @app.route('/api/responses', methods=['GET'])
    def get_responses_json():
        """저장된 응답을 JSON으로 반환 (DB에서 조회)"""
        from flask import jsonify
        try:
            # DB에서 모든 RequestAssignment 조회
            assignments = RequestAssignment.query.filter(
                RequestAssignment.twillio_sid.isnot(None)
            ).all()
            
            result = {}
            for assignment in assignments:
                if assignment.twillio_sid:
                    result[assignment.twillio_sid] = {
                        "assignment_id": assignment.assignment_id,
                        "request_id": assignment.request_id,
                        "hospital_id": assignment.hospital_id,
                        "response_status": assignment.response_status,
                        "digit": "1" if assignment.response_status == "승인" else "2" if assignment.response_status == "거절" else None,
                        "responded_at": assignment.responded_at.isoformat() if assignment.responded_at else None,
                        "called_at": assignment.called_at.isoformat() if assignment.called_at else None,
                        "distance_km": assignment.distance_km,
                        "eta_min": assignment.eta_min
                    }
            
            # 메모리 데이터도 병합 (하위 호환성)
            for call_sid, data in call_responses.items():
                if call_sid not in result:
                    result[call_sid] = data
            
            return jsonify(result), 200
        except Exception as e:
            import traceback
            print(f"응답 조회 오류: {traceback.format_exc()}")
            # 오류 시 메모리 데이터 반환 (하위 호환성)
            return jsonify(call_responses), 200

    @app.route('/api/response/<call_sid>', methods=['GET'])
    def get_response_by_sid(call_sid):
        """특정 Call SID의 응답 확인 (DB에서 조회)"""
        from flask import jsonify
        try:
            # DB에서 조회
            assignment = RequestAssignment.query.filter_by(twillio_sid=call_sid).first()
            if assignment:
                return jsonify({
                    "assignment_id": assignment.assignment_id,
                    "request_id": assignment.request_id,
                    "hospital_id": assignment.hospital_id,
                    "response_status": assignment.response_status,
                    "digit": "1" if assignment.response_status == "승인" else "2" if assignment.response_status == "거절" else None,
                    "responded_at": assignment.responded_at.isoformat() if assignment.responded_at else None,
                    "called_at": assignment.called_at.isoformat() if assignment.called_at else None,
                    "distance_km": assignment.distance_km,
                    "eta_min": assignment.eta_min
                }), 200
            
            # 메모리에서 조회 (하위 호환성)
            if call_sid in call_responses:
                return jsonify(call_responses[call_sid]), 200
            
            return jsonify({"error": "Not found"}), 404
        except Exception as e:
            import traceback
            print(f"응답 조회 오류: {traceback.format_exc()}")
            # 오류 시 메모리 데이터 반환 (하위 호환성)
            if call_sid in call_responses:
                return jsonify(call_responses[call_sid]), 200
            return jsonify({"error": "Not found"}), 404

    @app.route('/clear', methods=['GET', 'POST'])
    def clear_responses():
        """저장된 응답 초기화"""
        call_responses.clear()
        return "<h2>모든 응답이 초기화되었습니다.</h2><br><a href='/'>홈으로</a>"

