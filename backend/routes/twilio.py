#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Twilio 콜백 관련 라우트"""

from flask import request
from twilio.twiml.voice_response import VoiceResponse
import time
from datetime import datetime
from models import db, RequestAssignment, ChatSession


def register_twilio_routes(app, call_responses, call_metadata, socketio=None):
    """Twilio 콜백 라우트 등록"""
    
    @app.route('/twilio/gather', methods=['POST', 'GET'])
    def twilio_gather_callback():
        """Twilio Gather 콜백 - 다이얼 입력 받기"""
        from flask import Response
        
        try:
            # 모든 요청 파라미터 로그
            print(f"\n{'='*60}")
            print(f" [Twilio Gather Callback]")
            print(f"{'='*60}")
            print(f" 요청 메서드: {request.method}")
            print(f" 요청 헤더 User-Agent: {request.headers.get('User-Agent', 'N/A')}")
            for key, value in request.form.items():
                print(f"   {key}: {value[:200] if value and len(str(value)) > 200 else value}")
            
            call_sid = request.form.get('CallSid', '')
            digits = request.form.get('Digits', '').strip() if request.form.get('Digits') else ''
            call_status = request.form.get('CallStatus', '')
            
            print(f"\n 📞 콜백 정보:")
            print(f"   Call SID: {call_sid}")
            print(f"   Call Status: {call_status}")
            print(f"   Digits: '{digits}' (길이: {len(digits)})")
            
            # 통화 상태 확인
            if call_status in ['failed', 'busy', 'no-answer', 'canceled']:
                print(f"   ⚠️  통화가 이미 종료되었습니다: {call_status}")
                response = VoiceResponse()
                response.say("통화가 종료되었습니다.", language="ko-KR", voice="Polly.Seoyeon")
                twiml = str(response)
                return Response(
                    twiml,
                    mimetype='text/xml',
                    headers={
                        'Content-Type': 'text/xml; charset=utf-8',
                        'X-Content-Type-Options': 'nosniff',
                    }
                )
            
            # patient_info 찾기
            patient_info = None
            if call_sid:
                if call_sid in call_metadata:
                    patient_info = call_metadata[call_sid].get("patient_info")
                if not patient_info and call_sid in call_responses:
                    patient_info = call_responses[call_sid].get("patient_info")
            
            print(f"   patient_info: {'있음' if patient_info else '없음'}")
            if patient_info:
                print(f"   patient_info 길이: {len(patient_info)}")
                print(f"   patient_info 내용: {patient_info[:200]}...")
            
            response = VoiceResponse()
            
            # digits가 "1" 또는 "2"가 아니면 ARS 안내 (첫 호출 또는 재호출)
            if digits not in ['1', '2']:
                print(f" ✅ ARS 안내 시작 (digits가 유효하지 않음: '{digits}')")
                
                # ARS 메시지 준비
                if patient_info and patient_info.strip():
                    ars_message = patient_info.strip()
                    print(f"   ✓ patient_info 사용")
                else:
                    ars_message = "응급환자 수용 요청입니다. 환자 상태 정보를 확인하시고 수용 여부를 선택해 주세요."
                    print(f"   ⚠ 기본 메시지 사용 (patient_info 없음)")
                
                print(f"   ARS 메시지: {ars_message[:150]}...")
                
                # ARS 메시지를 먼저 재생 (gather 외부에서)
                response.say(ars_message, language="ko-KR", voice="Polly.Seoyeon")
                response.pause(length=2)
                response.say("해당 환자 수용이 가능하시면 1번, 수용이 불가능하시면 2번을 눌러주세요.", language="ko-KR", voice="Polly.Seoyeon")
                
                # ARS 메시지 재생 후 Gather로 입력 받기 (메시지 길이에 따라 timeout 동적 계산)
                # 한글 기준 대략 1초에 3-4자 정도 재생, 최소 30초, 최대 90초
                estimated_duration = max(30, min(90, len(ars_message) // 3 + 20))  # 메시지 길이 기반 계산 + 여유 시간
                print(f"   📞 Gather timeout: {estimated_duration}초 (ARS 메시지 길이: {len(ars_message)}자)")
                
                gather = response.gather(
                    numDigits=1,
                    action="/twilio/gather",
                    method="POST",
                    timeout=estimated_duration  # ARS 메시지 길이에 따라 동적 설정
                )
                # Gather 안에서는 짧은 재안내만 (이미 위에서 재생했으므로)
                gather.say("입력을 기다리고 있습니다. 1번 또는 2번을 눌러주세요.", language="ko-KR", voice="Polly.Seoyeon")
                
                # 타임아웃 시 재안내
                response.redirect("/twilio/gather", method="POST")
                
                twiml = str(response)
                print(f" ✅ TwiML 생성 완료 (길이: {len(twiml)})")
                print(f"   TwiML 일부: {twiml[:300]}...")
                
                # ngrok 인터셉터 우회를 위한 헤더 설정
                resp = Response(
                    twiml,
                    mimetype='text/xml',
                    headers={
                        'Content-Type': 'text/xml; charset=utf-8',
                        'X-Content-Type-Options': 'nosniff',
                    }
                )
                return resp
            
            # digits가 "1" 또는 "2"인 경우 - 응답 처리
            print(f" ✅ 유효한 입력: '{digits}'")
            
            # 메모리에 저장
            record = call_responses.setdefault(call_sid, {})
            record.update({
                "digit": digits,
                "timestamp": time.time(),
                "patient_info": patient_info
            })
            
            # DB에 저장
            try:
                assignment = RequestAssignment.query.filter_by(twillio_sid=call_sid).first()
                if assignment:
                    if digits == "1":
                        assignment.response_status = "승인"
                        assignment.responded_at = datetime.now()
                        # ChatSession 생성
                        existing_session = ChatSession.query.filter_by(request_id=assignment.request_id).first()
                        if not existing_session:
                            chat_session = ChatSession(
                                request_id=assignment.request_id,
                                assignment_id=assignment.assignment_id,
                                started_at=datetime.now()
                            )
                            db.session.add(chat_session)
                        print(" ✅ 입실 승인 (DB 저장)")
                        
                        # Socket.IO 알림
                        if socketio:
                            try:
                                socketio.emit('hospital_approved', {
                                    'request_id': assignment.request_id,
                                    'assignment_id': assignment.assignment_id,
                                    'hospital_id': assignment.hospital_id,
                                    'call_sid': call_sid
                                }, namespace='/')
                                print(f" 📡 Socket.IO 승인 알림 전송")
                            except Exception as e:
                                print(f" ⚠️ Socket.IO 알림 실패: {e}")
                                
                        response.say("입실 승인 확인되었습니다. 감사합니다.", language="ko-KR", voice="Polly.Seoyeon")
                        
                    elif digits == "2":
                        assignment.response_status = "거절"
                        assignment.responded_at = datetime.now()
                        print(" ✅ 입실 거절 (DB 저장)")
                        
                        # Socket.IO 알림
                        if socketio:
                            try:
                                socketio.emit('hospital_rejected', {
                                    'request_id': assignment.request_id,
                                    'assignment_id': assignment.assignment_id,
                                    'hospital_id': assignment.hospital_id,
                                    'call_sid': call_sid
                                }, namespace='/')
                                print(f" 📡 Socket.IO 거절 알림 전송")
                            except Exception as e:
                                print(f" ⚠️ Socket.IO 알림 실패: {e}")
                        
                        response.say("입실 불가 확인되었습니다. 다른 병원을 찾겠습니다.", language="ko-KR", voice="Polly.Seoyeon")
                    
                    db.session.commit()
                else:
                    print(f" ⚠️ RequestAssignment를 찾을 수 없음: {call_sid}")
            except Exception as e:
                db.session.rollback()
                import traceback
                print(f" ❌ DB 저장 오류: {traceback.format_exc()}")
            
            twiml = str(response)
            print(f" ✅ TwiML 생성 완료 (길이: {len(twiml)})")
            
            # ngrok 인터셉터 우회를 위한 헤더 설정
            resp = Response(
                twiml,
                mimetype='text/xml',
                headers={
                    'Content-Type': 'text/xml; charset=utf-8',
                    'X-Content-Type-Options': 'nosniff',
                }
            )
            return resp
        except Exception as e:
            import traceback
            print(f"\n ❌ [Twilio Gather Callback 오류]")
            print(f"   오류: {e}")
            print(f"   상세:\n{traceback.format_exc()}")
            
            # 오류 발생 시에도 TwiML 응답 반환 (통화 종료 방지)
            response = VoiceResponse()
            response.say("시스템 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.", language="ko-KR", voice="Polly.Seoyeon")
            twiml = str(response)
            return Response(
                twiml,
                mimetype='text/xml',
                headers={
                    'Content-Type': 'text/xml; charset=utf-8',
                    'X-Content-Type-Options': 'nosniff',
                }
            )

    @app.route('/twilio/status', methods=['POST'])
    def twilio_status_callback():
        """통화 상태 콜백"""
        try:
            call_sid = request.form.get('CallSid', '')
            call_status = request.form.get('CallStatus', '')
            call_duration = request.form.get('CallDuration', '')
            error_code = request.form.get('ErrorCode', '')
            error_message = request.form.get('ErrorMessage', '')
            
            print(f"\n 📞 [통화 상태 콜백]")
            print(f"   Call SID: {call_sid}")
            print(f"   Status: {call_status}")
            if call_duration:
                print(f"   Duration: {call_duration}초")
            if error_code:
                print(f"   ⚠️  오류 코드: {error_code}")
            if error_message:
                print(f"   ⚠️  오류 메시지: {error_message}")
            
            # 메모리에 저장
            record = call_responses.setdefault(call_sid, {})
            record['status'] = call_status or record.get('status')
            if error_code:
                record['error_code'] = error_code
            if error_message:
                record['error_message'] = error_message
            
            # DB에 상태 업데이트
            try:
                assignment = RequestAssignment.query.filter_by(twillio_sid=call_sid).first()
                if assignment:
                    # 상태에 따른 처리
                    if call_status in ['failed', 'busy', 'no-answer', 'canceled']:
                        print(f"   ⚠️  통화 실패 또는 거절: {call_status}")
                    elif call_status == 'completed':
                        print(f"   ✅ 통화 완료")
            except Exception as db_error:
                print(f"   ⚠️  DB 업데이트 오류: {db_error}")
            
            return "", 200
        except Exception as e:
            import traceback
            print(f"   ❌ 상태 콜백 처리 오류: {traceback.format_exc()}")
            return "", 200  # Twilio에 오류 응답을 보내지 않음

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
            time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp)) if timestamp else "N/A"
            
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
