#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""채팅 관련 라우트"""

from flask import request, jsonify
from pathlib import Path
from models import db, ChatSession, ChatMessage, RequestAssignment, EmergencyRequest, EMSTeam, Hospital


def register_chat_routes(app):
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
        """ChatSession 목록 조회 (hospital_id로 필터링 가능)"""
        try:
            hospital_id = request.args.get('hospital_id')
            
            # hospital_id가 있으면 해당 병원의 ChatSession만 조회
            if hospital_id:
                # RequestAssignment를 통해 hospital_id로 필터링
                assignments = RequestAssignment.query.filter_by(
                    hospital_id=hospital_id,
                    response_status='승인'
                ).all()
                assignment_ids = [a.assignment_id for a in assignments]
                
                if not assignment_ids:
                    return jsonify({"sessions": []}), 200
                
                sessions = ChatSession.query.filter(
                    ChatSession.assignment_id.in_(assignment_ids)
                ).order_by(ChatSession.started_at.desc()).all()
            else:
                # 모든 ChatSession 조회
                sessions = ChatSession.query.order_by(ChatSession.started_at.desc()).limit(100).all()
            
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
                    "started_at": session.started_at.isoformat() if session.started_at else None,
                    "ended_at": session.ended_at.isoformat() if session.ended_at else None,
                    "ems_id": ems_team.ems_id if ems_team else None,
                    "hospital_name": hospital.name if hospital else None,
                    "patient_age": emergency_request.patient_age if emergency_request else None,
                    "patient_sex": emergency_request.patient_sex if emergency_request else None,
                    "pre_ktas_class": emergency_request.pre_ktas_class if emergency_request else None,
                    "rag_summary": emergency_request.rag_summary if emergency_request else None,
                    "latest_message": {
                        "content": latest_message.content if latest_message else None,
                        "sent_at": latest_message.sent_at.isoformat() if latest_message and latest_message.sent_at else None,
                        "sender_type": latest_message.sender_type if latest_message else None
                    } if latest_message else None
                })
            
            return jsonify({"sessions": result}), 200
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"ChatSession 목록 조회 오류: {error_detail}")
            return jsonify({"error": f"ChatSession 목록 조회 중 오류가 발생했습니다: {str(e)}"}), 500

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
                        "sent_at": msg.sent_at.isoformat() if msg.sent_at else None
                    } for msg in messages]
                }), 200
            
            else:  # POST
                # 메시지 생성
                data = request.get_json()
                session_id = data.get('session_id')
                sender_type = data.get('sender_type')  # 'EMS' or 'HOSPITAL'
                sender_ref_id = data.get('sender_ref_id')
                content = data.get('content', '')
                image_path = data.get('image_path')  # 이미 업로드된 이미지 경로
                
                if not session_id or not sender_type or not sender_ref_id:
                    return jsonify({"error": "session_id, sender_type, sender_ref_id가 필요합니다."}), 400
                
                # 세션 존재 확인
                session = ChatSession.query.get(session_id)
                if not session:
                    return jsonify({"error": "채팅 세션을 찾을 수 없습니다."}), 404
                
                # 메시지 생성
                new_message = ChatMessage(
                    session_id=session_id,
                    sender_type=sender_type,
                    sender_ref_id=str(sender_ref_id),
                    content=content,
                    image_path=image_path
                )
                
                db.session.add(new_message)
                db.session.commit()
                
                return jsonify({
                    "message_id": new_message.message_id,
                    "session_id": new_message.session_id,
                    "sender_type": new_message.sender_type,
                    "sender_ref_id": new_message.sender_ref_id,
                    "content": new_message.content,
                    "image_path": new_message.image_path,
                    "image_url": f"/uploads/images/{Path(new_message.image_path).name}" if new_message.image_path else None,
                    "sent_at": new_message.sent_at.isoformat() if new_message.sent_at else None
                }), 201
                
        except Exception as e:
            db.session.rollback()
            import traceback
            error_detail = traceback.format_exc()
            print(f"채팅 메시지 오류: {error_detail}")
            return jsonify({"error": f"채팅 메시지 처리 중 오류가 발생했습니다: {str(e)}"}), 500

