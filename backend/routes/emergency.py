#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""응급 요청 관련 라우트"""

from flask import request, jsonify
from datetime import datetime
from models import db, EmergencyRequest, RequestAssignment, ChatSession, Hospital
from services.hospital_service import fetch_baseinfo_by_hpid, save_or_update_hospital
from config import DATA_GO_KR_KEY


def register_emergency_routes(app):
    """응급 요청 라우트 등록"""
    
    @app.route('/api/emergency/request', methods=['POST', 'OPTIONS'])
    def api_create_emergency_request():
        """응급실 입실 요청 생성"""
        if request.method == 'OPTIONS':
            return '', 200
        
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "요청 데이터가 없습니다."}), 400
            
            team_id = data.get('team_id')
            patient_sex = data.get('patient_sex')
            patient_age = data.get('patient_age')
            pre_ktas_class = data.get('pre_ktas_class')
            stt_full_text = data.get('stt_full_text')
            rag_summary = data.get('rag_summary')
            current_lat = data.get('current_lat')
            current_lon = data.get('current_lon')
            
            # 타입 변환
            if team_id is not None:
                team_id = int(team_id)
            if patient_age is not None:
                patient_age = int(patient_age)
            if current_lat is not None:
                current_lat = float(current_lat)
            if current_lon is not None:
                current_lon = float(current_lon)
            
            if not all([team_id, patient_sex, patient_age, pre_ktas_class, current_lat, current_lon]):
                return jsonify({"error": "필수 파라미터가 누락되었습니다."}), 400
            
            # EmergencyRequest 생성
            emergency_request = EmergencyRequest(
                team_id=team_id,
                patient_sex=patient_sex,
                patient_age=patient_age,
                pre_ktas_class=pre_ktas_class,
                stt_full_text=stt_full_text,
                rag_summary=rag_summary,
                current_lat=current_lat,
                current_lon=current_lon,
                is_completed=False
            )
            
            db.session.add(emergency_request)
            db.session.commit()
            
            return jsonify({
                "request_id": emergency_request.request_id,
                "team_id": emergency_request.team_id,
                "requested_at": emergency_request.requested_at.isoformat() if emergency_request.requested_at else None
            }), 201
            
        except Exception as e:
            db.session.rollback()
            import traceback
            error_detail = traceback.format_exc()
            print(f"응급 요청 생성 오류: {error_detail}")
            return jsonify({"error": f"응급 요청 생성 중 오류가 발생했습니다: {str(e)}"}), 500

    @app.route('/api/emergency/call-hospital', methods=['POST', 'OPTIONS'])
    def api_call_hospital():
        """병원에 전화를 걸고 RequestAssignment 생성"""
        if request.method == 'OPTIONS':
            return '', 200
        
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "요청 데이터가 없습니다."}), 400
            
            request_id = data.get('request_id')
            hospital_id = data.get('hospital_id')  # hpid
            distance_km = data.get('distance_km')
            eta_min = data.get('eta_minutes')
            twilio_sid = data.get('twilio_sid')  # Twilio Call SID (선택)
            
            # 타입 변환
            if request_id is not None:
                request_id = int(request_id)
            if distance_km is not None:
                distance_km = float(distance_km)
            if eta_min is not None:
                eta_min = int(eta_min)
            
            if not all([request_id, hospital_id]):
                return jsonify({"error": "request_id와 hospital_id가 필요합니다."}), 400
            
            # EmergencyRequest 존재 확인
            emergency_request = EmergencyRequest.query.get(request_id)
            if not emergency_request:
                return jsonify({"error": "응급 요청을 찾을 수 없습니다."}), 404
            
            # Hospital 존재 확인 (없으면 API에서 가져와서 저장)
            hospital = Hospital.query.filter_by(hospital_id=hospital_id).first()
            if not hospital:
                # API에서 병원 정보 가져오기
                hospital_data = fetch_baseinfo_by_hpid(hospital_id, DATA_GO_KR_KEY)
                if hospital_data:
                    hospital = save_or_update_hospital(hospital_data)
                if not hospital:
                    return jsonify({"error": "병원 정보를 찾을 수 없습니다."}), 404
            
            # 이미 같은 요청-병원 조합이 있는지 확인
            existing_assignment = RequestAssignment.query.filter_by(
                request_id=request_id,
                hospital_id=hospital_id
            ).first()
            
            if existing_assignment:
                # 기존 assignment 업데이트
                if twilio_sid:
                    existing_assignment.twillio_sid = twilio_sid
                if distance_km is not None:
                    existing_assignment.distance_km = distance_km
                if eta_min is not None:
                    existing_assignment.eta_min = eta_min
                existing_assignment.called_at = datetime.now()
                assignment = existing_assignment
            else:
                # 새 RequestAssignment 생성
                assignment = RequestAssignment(
                    request_id=request_id,
                    hospital_id=hospital_id,
                    twillio_sid=twilio_sid,
                    response_status='대기중',
                    distance_km=distance_km,
                    eta_min=eta_min,
                    called_at=datetime.now()
                )
                db.session.add(assignment)
            
            db.session.commit()
            
            return jsonify({
                "assignment_id": assignment.assignment_id,
                "request_id": assignment.request_id,
                "hospital_id": assignment.hospital_id,
                "response_status": assignment.response_status,
                "called_at": assignment.called_at.isoformat() if assignment.called_at else None
            }), 201
            
        except Exception as e:
            db.session.rollback()
            import traceback
            error_detail = traceback.format_exc()
            print(f"병원 전화 걸기 오류: {error_detail}")
            return jsonify({"error": f"병원 전화 걸기 중 오류가 발생했습니다: {str(e)}"}), 500

    @app.route('/api/emergency/update-response', methods=['POST', 'OPTIONS'])
    def api_update_response():
        """RequestAssignment의 응답 상태 업데이트 (승인/거절)"""
        if request.method == 'OPTIONS':
            return '', 200
        
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "요청 데이터가 없습니다."}), 400
            
            assignment_id = data.get('assignment_id')
            response_status = data.get('response_status')  # '승인' 또는 '거절'
            twilio_sid = data.get('twilio_sid')  # 선택
            
            # 타입 변환
            if assignment_id is not None:
                assignment_id = int(assignment_id)
            
            if not assignment_id or not response_status:
                return jsonify({"error": "assignment_id와 response_status가 필요합니다."}), 400
            
            if response_status not in ['승인', '거절', '대기중']:
                return jsonify({"error": "response_status는 '승인', '거절', '대기중' 중 하나여야 합니다."}), 400
            
            assignment = RequestAssignment.query.get(assignment_id)
            if not assignment:
                return jsonify({"error": "RequestAssignment를 찾을 수 없습니다."}), 404
            
            assignment.response_status = response_status
            if twilio_sid:
                assignment.twillio_sid = twilio_sid
            
            assignment.responded_at = datetime.now()
            
            # 승인된 경우 ChatSession 생성
            chat_session = None
            if response_status == '승인':
                # 기존 세션이 있는지 확인
                existing_session = ChatSession.query.filter_by(request_id=assignment.request_id).first()
                if existing_session:
                    chat_session = existing_session
                else:
                    chat_session = ChatSession(
                        request_id=assignment.request_id,
                        assignment_id=assignment_id,
                        started_at=datetime.now()
                    )
                    db.session.add(chat_session)
            
            db.session.commit()
            
            # ChatSession이 생성되었으면 session_id도 반환
            response_data = {
                "assignment_id": assignment.assignment_id,
                "response_status": assignment.response_status,
                "responded_at": assignment.responded_at.isoformat() if assignment.responded_at else None
            }
            
            if chat_session:
                response_data["session_id"] = chat_session.session_id
                response_data["request_id"] = chat_session.request_id
                response_data["assignment_id"] = chat_session.assignment_id
            
            return jsonify(response_data), 200
            
        except Exception as e:
            db.session.rollback()
            import traceback
            error_detail = traceback.format_exc()
            print(f"응답 상태 업데이트 오류: {error_detail}")
            return jsonify({"error": f"응답 상태 업데이트 중 오류가 발생했습니다: {str(e)}"}), 500

    @app.route('/api/emergency/requests', methods=['GET'])
    def api_get_emergency_requests():
        """응급 요청 목록 조회"""
        try:
            team_id = request.args.get('team_id', type=int)
            request_id = request.args.get('request_id', type=int)
            
            if request_id:
                # 특정 요청 조회
                emergency_request = EmergencyRequest.query.get(request_id)
                if not emergency_request:
                    return jsonify({"error": "응급 요청을 찾을 수 없습니다."}), 404
                
                return jsonify({
                    "request_id": emergency_request.request_id,
                    "team_id": emergency_request.team_id,
                    "patient_sex": emergency_request.patient_sex,
                    "patient_age": emergency_request.patient_age,
                    "pre_ktas_class": emergency_request.pre_ktas_class,
                    "stt_full_text": emergency_request.stt_full_text,
                    "rag_summary": emergency_request.rag_summary,
                    "current_lat": emergency_request.current_lat,
                    "current_lon": emergency_request.current_lon,
                    "requested_at": emergency_request.requested_at.isoformat() if emergency_request.requested_at else None,
                    "is_completed": emergency_request.is_completed
                }), 200
            else:
                # 목록 조회
                query = EmergencyRequest.query
                if team_id:
                    query = query.filter_by(team_id=team_id)
                
                requests = query.order_by(EmergencyRequest.requested_at.desc()).limit(100).all()
                
                return jsonify({
                    "requests": [{
                        "request_id": req.request_id,
                        "team_id": req.team_id,
                        "patient_sex": req.patient_sex,
                        "patient_age": req.patient_age,
                        "pre_ktas_class": req.pre_ktas_class,
                        "requested_at": req.requested_at.isoformat() if req.requested_at else None,
                        "is_completed": req.is_completed
                    } for req in requests]
                }), 200
                
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"응급 요청 조회 오류: {error_detail}")
            return jsonify({"error": f"응급 요청 조회 중 오류가 발생했습니다: {str(e)}"}), 500

    @app.route('/api/emergency/assignments', methods=['GET'])
    def api_get_assignments():
        """RequestAssignment 목록 조회"""
        try:
            request_id = request.args.get('request_id', type=int)
            assignment_id = request.args.get('assignment_id', type=int)
            
            if assignment_id:
                # 특정 assignment 조회
                assignment = RequestAssignment.query.get(assignment_id)
                if not assignment:
                    return jsonify({"error": "RequestAssignment를 찾을 수 없습니다."}), 404
                
                return jsonify({
                    "assignment_id": assignment.assignment_id,
                    "request_id": assignment.request_id,
                    "hospital_id": assignment.hospital_id,
                    "twillio_sid": assignment.twillio_sid,
                    "response_status": assignment.response_status,
                    "distance_km": assignment.distance_km,
                    "eta_min": assignment.eta_min,
                    "called_at": assignment.called_at.isoformat() if assignment.called_at else None,
                    "responded_at": assignment.responded_at.isoformat() if assignment.responded_at else None
                }), 200
            else:
                # 목록 조회
                query = RequestAssignment.query
                if request_id:
                    query = query.filter_by(request_id=request_id)
                
                assignments = query.order_by(RequestAssignment.called_at.desc()).limit(100).all()
                
                return jsonify({
                    "assignments": [{
                        "assignment_id": a.assignment_id,
                        "request_id": a.request_id,
                        "hospital_id": a.hospital_id,
                        "response_status": a.response_status,
                        "called_at": a.called_at.isoformat() if a.called_at else None,
                        "responded_at": a.responded_at.isoformat() if a.responded_at else None
                    } for a in assignments]
                }), 200
                
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"RequestAssignment 조회 오류: {error_detail}")
            return jsonify({"error": f"RequestAssignment 조회 중 오류가 발생했습니다: {str(e)}"}), 500

