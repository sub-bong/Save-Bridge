#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""인증 관련 라우트"""

from flask import request, jsonify, session
from models import db, EMSTeam
from utils.password import verify_password


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

    @app.route('/api/auth/me', methods=['GET'])
    def api_get_current_user():
        """현재 로그인한 사용자 정보 조회"""
        if not session.get('logged_in'):
            return jsonify({"error": "로그인이 필요합니다."}), 401
        
        team_id = session.get('team_id')
        if not team_id:
            return jsonify({"error": "세션 정보가 없습니다."}), 401
        
        team = EMSTeam.query.get(team_id)
        if not team:
            session.clear()
            return jsonify({"error": "사용자를 찾을 수 없습니다."}), 404
        
        return jsonify({
            "team_id": team.team_id,
            "ems_id": team.ems_id,
            "region": team.region
        }), 200

