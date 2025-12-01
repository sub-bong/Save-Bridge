#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""채팅 관련 라우트"""

from flask import request, jsonify, send_from_directory
from flask_socketio import emit
from pathlib import Path
from datetime import timezone, timedelta, datetime
from werkzeug.utils import secure_filename
import os
from models import db, ChatSession, ChatMessage, RequestAssignment, EmergencyRequest, EMSTeam, Hospital

# 한국 시간대 (UTC+9)
KST = timezone(timedelta(hours=9))

def format_datetime_with_tz(dt):
    """datetime을 한국 시간대 정보를 포함한 ISO 형식으로 변환"""
    if dt is None:
        return None
    # naive datetime을 한국 시간대로 가정하고 timezone 정보 추가
    # SQLite는 timezone을 저장하지 않으므로, DB에서 읽은 naive datetime은 KST로 가정
    if dt.tzinfo is None:
        # naive datetime을 KST로 가정
        dt = dt.replace(tzinfo=KST)
    # 이미 timezone이 있으면 그대로 사용
    return dt.isoformat()


def register_chat_routes(app, socketio=None):
    """채팅 라우트 등록"""
    
    @app.route('/api/chat/session', methods=['GET'])
    def api_get_chat_session():
        """ChatSession 조회 (request_id 또는 assignment_id로)"""
        try:
            request_id = request.args.get('request_id', type=int)
            assignment_id = request.args.get('assignment_id', type=int)
            
            if not request_id and not assignment_id:
                return jsonify({"error": "request_id 또는 assignment_id 파라미터가 필요합니다."}), 400
            
            session = None
            if request_id:
                session = ChatSession.query.filter_by(request_id=request_id).first()
            elif assignment_id:
                session = ChatSession.query.filter_by(assignment_id=assignment_id).first()
            
            if not session:
                return jsonify({"error": "채팅 세션을 찾을 수 없습니다."}), 404
            
            return jsonify({
                "session_id": session.session_id,
                "request_id": session.request_id,
                "assignment_id": session.assignment_id,
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "ended_at": session.ended_at.isoformat() if session.ended_at else None
            }), 200
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"ChatSession 조회 오류: {error_detail}")
            return jsonify({"error": f"ChatSession 조회 중 오류가 발생했습니다: {str(e)}"}), 500

    @app.route('/api/chat/sessions', methods=['GET'])
    def api_get_chat_sessions():
        """ChatSession 목록 조회 (hospital_id로 필터링 가능, 삭제되지 않은 것만)"""
        try:
            hospital_id = request.args.get('hospital_id')
            print(f"📋 ChatSession 목록 조회 요청: hospital_id={hospital_id}")
            
            # hospital_id가 있으면 해당 병원의 ChatSession만 조회
            if hospital_id:
                # RequestAssignment를 통해 hospital_id로 필터링
                assignments = RequestAssignment.query.filter_by(
                    hospital_id=hospital_id,
                    response_status='승인'
                ).all()
                assignment_ids = [a.assignment_id for a in assignments]
                print(f"📋 승인된 RequestAssignment 수: {len(assignments)}, assignment_ids: {assignment_ids}")
                
                # 각 assignment의 상세 정보 출력
                for a in assignments:
                    print(f"  - assignment_id={a.assignment_id}, request_id={a.request_id}, hospital_id={a.hospital_id}, response_status={a.response_status}")
                
                if not assignment_ids:
                    print("⚠️  승인된 RequestAssignment가 없습니다.")
                    return jsonify({"sessions": []}), 200
                
                # 모든 세션 조회 (인계 완료된 것도 포함, is_deleted만 제외)
                all_sessions_raw = ChatSession.query.filter(
                    ChatSession.assignment_id.in_(assignment_ids)
                ).order_by(ChatSession.started_at.desc()).all()
                print(f"📋 DB에서 조회된 세션 수 (assignment_id 필터만): {len(all_sessions_raw)}")
                
                # Python 레벨에서 필터링 (is_deleted만 체크, is_completed는 정렬에만 사용)
                sessions = []
                for s in all_sessions_raw:
                    # is_deleted 체크 (삭제된 것만 제외)
                    if getattr(s, 'is_deleted', False):
                        print(f"  ⏭️  세션 {s.session_id} 건너뜀 (is_deleted=True)")
                        continue
                    
                    # EmergencyRequest 조회하여 is_completed 정보 포함
                    emergency_request = EmergencyRequest.query.get(s.request_id)
                    if not emergency_request:
                        print(f"  ⚠️  세션 {s.session_id}의 EmergencyRequest를 찾을 수 없음 (request_id={s.request_id})")
                        continue
                    
                    print(f"  ✅ 세션 {s.session_id} 포함 (is_completed={emergency_request.is_completed}, request_id={s.request_id})")
                    sessions.append(s)
                
                # 정렬: 진행 중인 것 먼저, 인계 완료된 것은 나중에
                # 각 상태별로 최신순(started_at 내림차순)으로 정렬
                from collections import defaultdict
                by_status = defaultdict(list)
                for s in sessions:
                    er = EmergencyRequest.query.get(s.request_id)
                    is_completed = er.is_completed == True if er else False
                    by_status[is_completed].append(s)
                
                # 각 상태별로 최신순 정렬 (started_at 내림차순)
                for status in by_status:
                    by_status[status].sort(key=lambda s: s.started_at if s.started_at else datetime(1970, 1, 1, tzinfo=KST), reverse=True)
                
                # 진행중(False) 먼저, 완료(True) 나중에
                sessions = by_status[False] + by_status[True]
                
                # 15건 이상일 때 인계 완료된 것부터 제거
                if len(sessions) > 15:
                    completed_sessions = [s for s in sessions if EmergencyRequest.query.get(s.request_id) and EmergencyRequest.query.get(s.request_id).is_completed == True]
                    if len(completed_sessions) > 0:
                        # 맨 아래 인계 완료된 것부터 제거
                        sessions_to_remove = completed_sessions[:len(sessions) - 15]
                        for s in sessions_to_remove:
                            print(f"  🗑️  세션 {s.session_id} 제거 (15건 초과, 인계 완료됨)")
                            sessions.remove(s)
                
                print(f"📋 최종 필터링된 세션 수: {len(sessions)}")
            else:
                # 모든 ChatSession 조회 (인계 완료된 것도 포함, is_deleted만 제외)
                all_sessions_raw = ChatSession.query.order_by(ChatSession.started_at.desc()).limit(100).all()
                print(f"📋 DB에서 조회된 세션 수 (hospital_id 없음): {len(all_sessions_raw)}")
                
                # Python 레벨에서 필터링 (is_deleted만 체크)
                sessions = []
                for s in all_sessions_raw:
                    # is_deleted 체크
                    if getattr(s, 'is_deleted', False):
                        print(f"  ⏭️  세션 {s.session_id} 건너뜀 (is_deleted=True)")
                        continue
                    
                    # EmergencyRequest 조회
                    emergency_request = EmergencyRequest.query.get(s.request_id)
                    if not emergency_request:
                        print(f"  ⚠️  세션 {s.session_id}의 EmergencyRequest를 찾을 수 없음 (request_id={s.request_id})")
                        continue
                    
                    sessions.append(s)
                
                # 정렬: 진행 중인 것 먼저, 인계 완료된 것은 나중에
                # 각 상태별로 최신순(started_at 내림차순)으로 정렬
                from collections import defaultdict
                by_status = defaultdict(list)
                for s in sessions:
                    er = EmergencyRequest.query.get(s.request_id)
                    is_completed = er.is_completed == True if er else False
                    by_status[is_completed].append(s)
                
                # 각 상태별로 최신순 정렬 (started_at 내림차순)
                for status in by_status:
                    by_status[status].sort(key=lambda s: s.started_at if s.started_at else datetime(1970, 1, 1, tzinfo=KST), reverse=True)
                
                # 진행중(False) 먼저, 완료(True) 나중에
                sessions = by_status[False] + by_status[True]
                
                # 15건 이상일 때 인계 완료된 것부터 제거
                if len(sessions) > 15:
                    completed_sessions = [s for s in sessions if EmergencyRequest.query.get(s.request_id) and EmergencyRequest.query.get(s.request_id).is_completed == True]
                    if len(completed_sessions) > 0:
                        sessions_to_remove = completed_sessions[:len(sessions) - 15]
                        for s in sessions_to_remove:
                            print(f"  🗑️  세션 {s.session_id} 제거 (15건 초과, 인계 완료됨)")
                            sessions.remove(s)
                
                print(f"📋 최종 필터링된 세션 수: {len(sessions)}")
            
            result = []
            for session in sessions:
                # 관련 정보 조회
                assignment = RequestAssignment.query.get(session.assignment_id)
                emergency_request = EmergencyRequest.query.get(session.request_id)
                ems_team = None
                hospital = None
                
                if emergency_request:
                    ems_team = EMSTeam.query.get(emergency_request.team_id)
                if assignment:
                    hospital = Hospital.query.filter_by(hospital_id=assignment.hospital_id).first()
                
                # 최신 메시지 조회
                latest_message = ChatMessage.query.filter_by(
                    session_id=session.session_id
                ).order_by(ChatMessage.sent_at.desc()).first()
                
                result.append({
                    "session_id": session.session_id,
                    "request_id": session.request_id,
                    "assignment_id": session.assignment_id,
                    "started_at": format_datetime_with_tz(session.started_at),
                    "ended_at": format_datetime_with_tz(session.ended_at),
                    "is_completed": emergency_request.is_completed if emergency_request else False,  # EmergencyRequest.is_completed 추가
                    "ems_id": ems_team.ems_id if ems_team else None,
                    "hospital_name": hospital.name if hospital else None,
                    "hospital_id": hospital.hospital_id if hospital else None,  # 병원 ID 추가
                    "hospital_lat": hospital.latitude if hospital else None,  # 병원 위도 추가
                    "hospital_lon": hospital.longitude if hospital else None,  # 병원 경도 추가
                    "patient_age": emergency_request.patient_age if emergency_request else None,
                    "patient_sex": emergency_request.patient_sex if emergency_request else None,
                    "pre_ktas_class": emergency_request.pre_ktas_class if emergency_request else None,
                    "rag_summary": emergency_request.rag_summary if emergency_request else None,
                    "stt_full_text": emergency_request.stt_full_text if emergency_request else None,  # STT 원문 추가
                    "current_lat": emergency_request.current_lat if emergency_request else None,  # 구급대원 현재 위치 (위도)
                    "current_lon": emergency_request.current_lon if emergency_request else None,  # 구급대원 현재 위치 (경도)
                    "latest_message": {
                        "content": latest_message.content if latest_message else None,
                        "sent_at": format_datetime_with_tz(latest_message.sent_at) if latest_message else None,
                        "sender_type": latest_message.sender_type if latest_message else None
                    } if latest_message else None
                })
            
            return jsonify({"sessions": result}), 200
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"ChatSession 목록 조회 오류: {error_detail}")
            return jsonify({"error": f"ChatSession 목록 조회 중 오류가 발생했습니다: {str(e)}"}), 500

    @app.route('/api/chat/pending-session', methods=['GET'])
    def api_get_pending_session_for_ems():
        """특정 EMS 계정에 대해, 아직 인계 완료되지 않은 최신 ChatSession 조회"""
        try:
            ems_id = request.args.get('ems_id')
            if not ems_id:
                return jsonify({"error": "ems_id가 필요합니다."}), 400

            # EMS 팀 조회
            ems_team = EMSTeam.query.filter_by(ems_id=ems_id).first()
            if not ems_team:
                return jsonify({"session": None}), 200

            # team_id 기준으로, 인계가 완료되지 않은(EmergencyRequest.is_completed != True) 세션 중
            # 삭제되지 않은(ChatSession.is_deleted=False) 최신 세션 하나 조회
            pending_session = (
                ChatSession.query
                .join(EmergencyRequest, ChatSession.request_id == EmergencyRequest.request_id)
                .filter(
                    EmergencyRequest.team_id == ems_team.team_id,
                    (EmergencyRequest.is_completed.is_(False)) | (EmergencyRequest.is_completed.is_(None)),
                    ChatSession.is_deleted.is_(False)
                )
                .order_by(ChatSession.started_at.desc())
                .first()
            )

            if not pending_session:
                return jsonify({"session": None}), 200

            emergency_request = EmergencyRequest.query.get(pending_session.request_id)
            assignment = RequestAssignment.query.get(pending_session.assignment_id)
            hospital = None
            if assignment and assignment.hospital_id:
                hospital = Hospital.query.filter_by(hospital_id=assignment.hospital_id).first()

            # 최신 메시지
            latest_message = ChatMessage.query.filter_by(
                session_id=pending_session.session_id
            ).order_by(ChatMessage.sent_at.desc()).first()

            session_payload = {
                "session_id": pending_session.session_id,
                "request_id": pending_session.request_id,
                "assignment_id": pending_session.assignment_id,
                "started_at": format_datetime_with_tz(pending_session.started_at),
                "ended_at": format_datetime_with_tz(pending_session.ended_at),
                "is_completed": emergency_request.is_completed if emergency_request else False,
                "ems_id": ems_team.ems_id if ems_team else None,
                "hospital_id": assignment.hospital_id if assignment else None,
                "hospital_name": hospital.name if hospital else None,
                "hospital_lat": hospital.latitude if hospital else None,
                "hospital_lon": hospital.longitude if hospital else None,
                "patient_age": emergency_request.patient_age if emergency_request else None,
                "patient_sex": emergency_request.patient_sex if emergency_request else None,
                "pre_ktas_class": emergency_request.pre_ktas_class if emergency_request else None,
                "rag_summary": emergency_request.rag_summary if emergency_request else None,
                "stt_full_text": emergency_request.stt_full_text if emergency_request else None,
                "current_lat": emergency_request.current_lat if emergency_request else None,
                "current_lon": emergency_request.current_lon if emergency_request else None,
                "latest_message": {
                    "content": latest_message.content if latest_message else None,
                    "sent_at": format_datetime_with_tz(latest_message.sent_at) if latest_message else None,
                    "sender_type": latest_message.sender_type if latest_message else None,
                } if latest_message else None,
            }

            return jsonify({"session": session_payload}), 200
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"EMS 미완료 세션 조회 오류: {error_detail}")
            return jsonify({"error": f"미완료 세션 조회 중 오류가 발생했습니다: {str(e)}"}), 500

    @app.route('/api/chat/session/<int:session_id>/complete', methods=['POST', 'OPTIONS'])
    def api_complete_chat_session(session_id):
        """ChatSession 인계 완료 처리 (ended_at 설정)"""
        if request.method == 'OPTIONS':
            return '', 200
        
        try:
            data = request.get_json() or {}
            ems_id = data.get('ems_id')
            
            if not ems_id:
                return jsonify({"error": "ems_id가 필요합니다."}), 400
            
            session = ChatSession.query.get(session_id)
            if not session:
                return jsonify({"error": "채팅 세션을 찾을 수 없습니다."}), 404
            
            # EMS 팀 확인
            emergency_request = EmergencyRequest.query.get(session.request_id)
            if not emergency_request:
                return jsonify({"error": "응급 요청을 찾을 수 없습니다."}), 404
            
            ems_team = EMSTeam.query.get(emergency_request.team_id)
            if not ems_team or ems_team.ems_id != ems_id:
                return jsonify({"error": "ems_id가 일치하지 않습니다."}), 403
            
            # 인계 완료 처리 (ended_at 설정 + EmergencyRequest.is_completed = True)
            from datetime import datetime
            session.ended_at = datetime.utcnow()
            emergency_request.is_completed = True  # EmergencyRequest도 완료 처리
            db.session.commit()
            
            print(f"✅ 인계 완료 처리: session_id={session_id}, request_id={emergency_request.request_id}, is_completed={emergency_request.is_completed}")
            
            return jsonify({
                "message": "인계 완료 처리되었습니다.",
                "session_id": session_id,
                "request_id": emergency_request.request_id,
                "ended_at": session.ended_at.isoformat() if session.ended_at else None,
                "is_completed": emergency_request.is_completed
            }), 200
            
        except Exception as e:
            db.session.rollback()
            import traceback
            error_detail = traceback.format_exc()
            print(f"ChatSession 인계 완료 오류: {error_detail}")
            return jsonify({"error": f"인계 완료 처리 중 오류가 발생했습니다: {str(e)}"}), 500

    @app.route('/api/chat/session/<int:session_id>', methods=['DELETE', 'OPTIONS'])
    def api_delete_chat_session(session_id):
        """ChatSession 소프트 삭제 (DB에는 남고 프론트엔드에서만 숨김)"""
        if request.method == 'OPTIONS':
            # withCredentials를 사용하는 요청에서는 명시적인 origin을 반환해야 함
            origin = request.headers.get('Origin')
            allowed_origins = ['http://localhost:5173', 'http://localhost:3000']
            
            response = jsonify({})
            if origin in allowed_origins:
                response.headers.add('Access-Control-Allow-Origin', origin)
            else:
                response.headers.add('Access-Control-Allow-Origin', allowed_origins[0])  # 기본값
            response.headers.add('Access-Control-Allow-Credentials', 'true')
            response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
            response.headers.add('Access-Control-Allow-Methods', 'DELETE,OPTIONS')
            return response, 200
        
        try:
            session = ChatSession.query.get(session_id)
            if not session:
                # CORS 헤더 추가 (404 응답에도 필요)
                origin = request.headers.get('Origin')
                allowed_origins = ['http://localhost:5173', 'http://localhost:3000']
                
                response = jsonify({"error": "채팅 세션을 찾을 수 없습니다."})
                if origin in allowed_origins:
                    response.headers.add('Access-Control-Allow-Origin', origin)
                else:
                    response.headers.add('Access-Control-Allow-Origin', allowed_origins[0])
                response.headers.add('Access-Control-Allow-Credentials', 'true')
                
                return response, 404
            
            print(f"🗑️  ChatSession 삭제 요청: session_id={session_id}")
            
            # 소프트 삭제 (is_deleted 플래그만 True로 설정)
            # hasattr로 간단하게 체크
            if hasattr(session, 'is_deleted'):
                session.is_deleted = True
                print(f"✅ is_deleted 컬럼 사용하여 소프트 삭제")
            else:
                # 컬럼이 없으면 ended_at을 설정하여 숨김 처리 (임시)
                from datetime import datetime
                session.ended_at = datetime.utcnow()
                print(f"⚠️  is_deleted 컬럼이 없어 ended_at 설정으로 숨김 처리")
            
            try:
                db.session.commit()
                print(f"✅ ChatSession {session_id} 삭제 완료")
            except Exception as commit_error:
                db.session.rollback()
                print(f"❌ DB 커밋 실패: {commit_error}")
                import traceback
                print(traceback.format_exc())
                return jsonify({"error": f"데이터베이스 저장 중 오류가 발생했습니다: {str(commit_error)}"}), 500
            
            # CORS 헤더 추가 (withCredentials를 사용하는 요청을 위해)
            origin = request.headers.get('Origin')
            allowed_origins = ['http://localhost:5173', 'http://localhost:3000']
            
            response = jsonify({
                "message": "채팅 세션이 삭제되었습니다.",
                "session_id": session_id
            })
            
            if origin in allowed_origins:
                response.headers.add('Access-Control-Allow-Origin', origin)
            else:
                response.headers.add('Access-Control-Allow-Origin', allowed_origins[0])
            response.headers.add('Access-Control-Allow-Credentials', 'true')
            
            return response, 200
            
        except Exception as e:
            db.session.rollback()
            import traceback
            error_detail = traceback.format_exc()
            print(f"ChatSession 삭제 오류: {error_detail}")
            
            # CORS 헤더 추가 (에러 응답에도 필요)
            origin = request.headers.get('Origin')
            allowed_origins = ['http://localhost:5173', 'http://localhost:3000']
            
            response = jsonify({"error": f"채팅 세션 삭제 중 오류가 발생했습니다: {str(e)}"})
            if origin in allowed_origins:
                response.headers.add('Access-Control-Allow-Origin', origin)
            else:
                response.headers.add('Access-Control-Allow-Origin', allowed_origins[0])
            response.headers.add('Access-Control-Allow-Credentials', 'true')
            
            return response, 500

    @app.route('/api/chat/messages', methods=['GET', 'POST'])
    def api_chat_messages():
        """채팅 메시지 조회(GET) 또는 생성(POST)"""
        try:
            if request.method == 'GET':
                # 메시지 조회
                session_id = request.args.get('session_id', type=int)
                if not session_id:
                    return jsonify({"error": "session_id 파라미터가 필요합니다."}), 400
                
                messages = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.sent_at).all()
                
                return jsonify({
                    "messages": [{
                        "message_id": msg.message_id,
                        "session_id": msg.session_id,
                        "sender_type": msg.sender_type,
                        "sender_ref_id": msg.sender_ref_id,
                        "content": msg.content,
                        "image_path": msg.image_path,
                        "image_url": f"/uploads/images/{Path(msg.image_path).name}" if msg.image_path else None,
                        "sent_at": format_datetime_with_tz(msg.sent_at)
                    } for msg in messages]
                }), 200
            
            else:  # POST
                # 메시지 생성
                data = request.get_json()
                if not data:
                    print("❌ POST /api/chat/messages: 요청 데이터가 없습니다.")
                    return jsonify({"error": "요청 데이터가 없습니다."}), 400
                
                session_id = data.get('session_id')
                sender_type = data.get('sender_type')  # 'EMS' or 'HOSPITAL'
                sender_ref_id = data.get('sender_ref_id')
                content = data.get('content', '')
                image_path = data.get('image_path')  # 이미 업로드된 이미지 경로
                
                print(f"📨 메시지 저장 요청: session_id={session_id}, sender_type={sender_type}, sender_ref_id={sender_ref_id}, content={content[:50]}...")
                
                if not session_id or not sender_type or not sender_ref_id:
                    print(f"❌ 필수 파라미터 누락: session_id={session_id}, sender_type={sender_type}, sender_ref_id={sender_ref_id}")
                    return jsonify({"error": "session_id, sender_type, sender_ref_id가 필요합니다."}), 400
                
                # 세션 존재 확인
                session = ChatSession.query.get(session_id)
                if not session:
                    print(f"❌ ChatSession을 찾을 수 없음: session_id={session_id}")
                    return jsonify({"error": "채팅 세션을 찾을 수 없습니다."}), 404
                
                print(f"✅ ChatSession 확인됨: session_id={session_id}")
                
                # 메시지 생성 (KST 시간대 사용)
                now_kst = datetime.now(KST)
                new_message = ChatMessage(
                    session_id=session_id,
                    sender_type=sender_type,
                    sender_ref_id=str(sender_ref_id),
                    content=content,
                    image_path=image_path,
                    sent_at=now_kst  # 명시적으로 KST 시간 설정
                )
                
                db.session.add(new_message)
                print(f"💾 메시지 DB에 추가: content={content[:50]}...")
                
                try:
                    db.session.commit()
                    print(f"✅ 메시지 저장 성공: message_id={new_message.message_id}")
                except Exception as commit_error:
                    print(f"❌ DB 커밋 실패: {commit_error}")
                    db.session.rollback()
                    raise
                
                # WebSocket으로 새 메시지 브로드캐스트
                if socketio:
                    message_data = {
                        "message_id": new_message.message_id,
                        "session_id": new_message.session_id,
                        "sender_type": new_message.sender_type,
                        "sender_ref_id": new_message.sender_ref_id,
                        "content": new_message.content,
                        "image_path": new_message.image_path,
                        "image_url": f"/uploads/images/{Path(new_message.image_path).name}" if new_message.image_path else None,
                        "sent_at": format_datetime_with_tz(new_message.sent_at)
                    }
                    # 해당 세션의 모든 클라이언트에게 메시지 전송
                    socketio.emit('new_message', message_data, room=f'session_{session_id}')
                    print(f"📡 WebSocket으로 메시지 브로드캐스트: session_id={session_id}")
                
                return jsonify({
                    "message_id": new_message.message_id,
                    "session_id": new_message.session_id,
                    "sender_type": new_message.sender_type,
                    "sender_ref_id": new_message.sender_ref_id,
                    "content": new_message.content,
                    "image_path": new_message.image_path,
                    "image_url": f"/uploads/images/{Path(new_message.image_path).name}" if new_message.image_path else None,
                    "sent_at": format_datetime_with_tz(new_message.sent_at)
                }), 201
                
        except Exception as e:
            db.session.rollback()
            import traceback
            error_detail = traceback.format_exc()
            print(f"채팅 메시지 오류: {error_detail}")
            return jsonify({"error": f"채팅 메시지 처리 중 오류가 발생했습니다: {str(e)}"}), 500
    
    # WebSocket 이벤트 핸들러
    if socketio:
        @socketio.on('connect')
        def handle_connect():
            """클라이언트 연결"""
            print(f"✅ 클라이언트 연결됨: {request.sid}")
        
        @socketio.on('disconnect')
        def handle_disconnect():
            """클라이언트 연결 해제"""
            print(f"👋 클라이언트 연결 해제됨: {request.sid}")
        
        @socketio.on('join_session')
        def handle_join_session(data):
            """클라이언트가 특정 세션에 참여"""
            try:
                session_id = data.get('session_id')
                if session_id:
                    from flask_socketio import join_room
                    join_room(f'session_{session_id}')
                    print(f"✅ 클라이언트 {request.sid}가 세션 {session_id}에 참여했습니다.")
                    emit('joined', {'session_id': session_id})
                else:
                    print(f"⚠️ join_session: session_id가 없습니다. data={data}")
            except Exception as e:
                print(f"❌ join_session 오류: {e}")
                import traceback
                traceback.print_exc()
        
        @socketio.on('leave_session')
        def handle_leave_session(data):
            """클라이언트가 특정 세션에서 나감"""
            try:
                session_id = data.get('session_id')
                if session_id:
                    from flask_socketio import leave_room
                    leave_room(f'session_{session_id}')
                    print(f"👋 클라이언트 {request.sid}가 세션 {session_id}에서 나갔습니다.")
                    emit('left', {'session_id': session_id})
                else:
                    print(f"⚠️ leave_session: session_id가 없습니다. data={data}")
            except Exception as e:
                print(f"❌ leave_session 오류: {e}")
                import traceback
                traceback.print_exc()
    
    # 이미지 업로드 엔드포인트
    @app.route('/api/chat/upload-image', methods=['POST'])
    def api_upload_image():
        """이미지 업로드 API"""
        try:
            if 'image' not in request.files:
                return jsonify({"error": "이미지 파일이 없습니다."}), 400
            
            file = request.files['image']
            if file.filename == '':
                return jsonify({"error": "파일명이 없습니다."}), 400
            
            # 파일명 보안 처리
            filename = secure_filename(file.filename)
            # 타임스탬프 추가하여 중복 방지
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            name, ext = os.path.splitext(filename)
            filename = f"{timestamp}_{name}{ext}"
            
            # 업로드 디렉토리 경로
            upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads/images')
            os.makedirs(upload_folder, exist_ok=True)
            
            filepath = os.path.join(upload_folder, filename)
            file.save(filepath)
            
            # 상대 경로 반환 (DB에 저장할 경로)
            relative_path = f"uploads/images/{filename}"
            
            print(f"✅ 이미지 업로드 성공: {relative_path}")
            return jsonify({
                "image_path": relative_path,
                "image_url": f"/uploads/images/{filename}"
            }), 200
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({"error": f"이미지 업로드 실패: {str(e)}"}), 500
    
    # 이미지 서빙 엔드포인트
    @app.route('/uploads/images/<filename>')
    def serve_image(filename):
        """업로드된 이미지 파일 서빙"""
        try:
            upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads/images')
            return send_from_directory(upload_folder, filename)
        except Exception as e:
            return jsonify({"error": f"이미지 로드 실패: {str(e)}"}), 404

