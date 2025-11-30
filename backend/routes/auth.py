#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""인증 관련 라우트"""

from flask import request, jsonify, session
from models import db, EMSTeam, Hospital
from utils.password import verify_password, hash_password


def register_auth_routes(app):
    """인증 라우트 등록"""
    
    @app.route('/api/auth/login', methods=['POST', 'OPTIONS'])
    def api_login():
        """EMS 팀 로그인"""
        if request.method == 'OPTIONS':
            return '', 200
        
        try:
            data = request.get_json()
            ems_id = data.get('ems_id')
            password = data.get('password')
            
            if not ems_id or not password:
                return jsonify({"error": "ems_id와 password가 필요합니다."}), 400
            
            # DB에서 EMS 팀 조회
            team = EMSTeam.query.filter_by(ems_id=ems_id).first()
            if not team:
                return jsonify({"error": "존재하지 않는 EMS ID입니다."}), 401
            
            # 비밀번호 검증
            if not verify_password(password, team.password):
                return jsonify({"error": "비밀번호가 일치하지 않습니다."}), 401
            
            # 세션에 로그인 정보 저장
            session['team_id'] = team.team_id
            session['ems_id'] = team.ems_id
            session['logged_in'] = True
            
            return jsonify({
                "team_id": team.team_id,
                "ems_id": team.ems_id,
                "region": team.region,
                "message": "로그인 성공"
            }), 200
            
        except Exception as e:
            db.session.rollback()
            import traceback
            error_detail = traceback.format_exc()
            print(f"로그인 오류: {error_detail}")
            return jsonify({"error": f"로그인 중 오류가 발생했습니다: {str(e)}"}), 500

    @app.route('/api/auth/logout', methods=['POST', 'OPTIONS'])
    def api_logout():
        """로그아웃"""
        if request.method == 'OPTIONS':
            return '', 200
        
        session.clear()
        return jsonify({"message": "로그아웃되었습니다."}), 200

    @app.route('/api/auth/hospital-login', methods=['POST', 'OPTIONS'])
    def api_hospital_login():
        """병원 로그인"""
        if request.method == 'OPTIONS':
            return '', 200
        
        try:
            data = request.get_json()
            hospital_id = data.get('hospital_id')
            password = data.get('password')
            
            if not hospital_id or not password:
                return jsonify({"error": "hospital_id와 password가 필요합니다."}), 400
            
            # DB에서 병원 조회
            hospital = Hospital.query.filter_by(hospital_id=hospital_id).first()
            if not hospital:
                return jsonify({"error": "존재하지 않는 병원 ID입니다."}), 401
            
            # 비밀번호 검증 (password가 None이면 검증하지 않음 - 기존 데이터 호환성)
            if hospital.password:
                if not verify_password(password, hospital.password):
                    return jsonify({"error": "비밀번호가 일치하지 않습니다."}), 401
            else:
                # password가 설정되지 않은 경우, 기본 비밀번호로 설정하거나 에러 반환
                return jsonify({"error": "비밀번호가 설정되지 않은 병원입니다. 관리자에게 문의하세요."}), 401
            
            # 세션에 로그인 정보 저장
            session['hospital_id'] = hospital.hospital_id
            session['hospital_name'] = hospital.name
            session['hospital_logged_in'] = True
            
            return jsonify({
                "hospital_id": hospital.hospital_id,
                "hospital_name": hospital.name,
                "message": "로그인 성공"
            }), 200
            
        except Exception as e:
            db.session.rollback()
            import traceback
            error_detail = traceback.format_exc()
            print(f"병원 로그인 오류: {error_detail}")
            return jsonify({"error": f"로그인 중 오류가 발생했습니다: {str(e)}"}), 500

    @app.route('/api/auth/set-hospital-password', methods=['POST', 'OPTIONS'])
    def api_set_hospital_password():
        """병원 비밀번호 설정 (관리자용 또는 초기 설정용)"""
        if request.method == 'OPTIONS':
            return '', 200
        
        try:
            data = request.get_json()
            hospital_id = data.get('hospital_id')
            password = data.get('password')
            
            if not hospital_id or not password:
                return jsonify({"error": "hospital_id와 password가 필요합니다."}), 400
            
            # DB에서 병원 조회
            hospital = Hospital.query.filter_by(hospital_id=hospital_id).first()
            if not hospital:
                return jsonify({"error": "존재하지 않는 병원 ID입니다."}), 404
            
            # 비밀번호 해시하여 저장
            hospital.password = hash_password(password)
            db.session.commit()
            
            return jsonify({
                "hospital_id": hospital.hospital_id,
                "hospital_name": hospital.name,
                "message": "비밀번호가 설정되었습니다."
            }), 200
            
        except Exception as e:
            db.session.rollback()
            import traceback
            error_detail = traceback.format_exc()
            print(f"병원 비밀번호 설정 오류: {error_detail}")
            return jsonify({"error": f"비밀번호 설정 중 오류가 발생했습니다: {str(e)}"}), 500

    @app.route('/api/auth/me', methods=['GET'])
    def api_get_current_user():
        """현재 로그인한 사용자 정보 조회 (EMS 또는 Hospital)"""
        # EMS 로그인 확인
        if session.get('logged_in'):
            team_id = session.get('team_id')
            if team_id:
                team = EMSTeam.query.get(team_id)
                if team:
                    return jsonify({
                        "user_type": "EMS",
                        "team_id": team.team_id,
                        "ems_id": team.ems_id,
                        "region": team.region
                    }), 200
        
        # Hospital 로그인 확인
        if session.get('hospital_logged_in'):
            hospital_id = session.get('hospital_id')
            if hospital_id:
                # hospital_id는 문자열이므로 filter_by 사용
                hospital = Hospital.query.filter_by(hospital_id=hospital_id).first()
                if hospital:
                    return jsonify({
                        "user_type": "HOSPITAL",
                        "hospital_id": hospital.hospital_id,
                        "hospital_name": hospital.name
                    }), 200
        
        # 로그인되지 않은 경우에도 200을 반환하되, user 정보는 null
        # 프론트엔드에서 401 에러를 처리하지 않도록 함
        return jsonify({
            "user_type": None,
            "error": "로그인이 필요합니다."
        }), 200

