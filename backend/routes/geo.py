#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""지오코딩 관련 라우트"""

from flask import request, jsonify
from config import KAKAO_KEY
from utils.geo import (
    kakao_coord2address, kakao_coord2region, kakao_address2coord,
    get_driving_info_kakao
)


def register_geo_routes(app):
    """지오코딩 라우트 등록"""
    
    @app.route('/api/geo/coord2address', methods=['GET'])
    def api_coord2address():
        """좌표 → 주소 변환 API"""
        try:
            lat = float(request.args.get('lat', 0))
            lon = float(request.args.get('lon', 0))
            
            if not lat or not lon:
                return jsonify({"error": "lat와 lon 파라미터가 필요합니다."}), 400
            
            address = kakao_coord2address(lon, lat, KAKAO_KEY)
            if address:
                return jsonify({"address": address}), 200
            else:
                return jsonify({"error": "주소를 찾을 수 없습니다."}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/geo/coord2region', methods=['GET'])
    def api_coord2region():
        """좌표 → 행정구역 변환 API"""
        try:
            lat = float(request.args.get('lat', 0))
            lon = float(request.args.get('lon', 0))
            
            if not lat or not lon:
                return jsonify({"error": "lat와 lon 파라미터가 필요합니다."}), 400
            
            result = kakao_coord2region(lon, lat, KAKAO_KEY)
            if result:
                sido, sigungu = result
                return jsonify({"sido": sido, "sigungu": sigungu}), 200
            else:
                return jsonify({"error": "행정구역을 찾을 수 없습니다."}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/geo/route', methods=['GET'])
    def api_geo_route():
        """경로 조회 API (카카오 길찾기)"""
        try:
            origin_lat = request.args.get('origin_lat', type=float)
            origin_lon = request.args.get('origin_lon', type=float)
            dest_lat = request.args.get('dest_lat', type=float)
            dest_lon = request.args.get('dest_lon', type=float)
            
            if not all([origin_lat, origin_lon, dest_lat, dest_lon]):
                return jsonify({"error": "origin_lat, origin_lon, dest_lat, dest_lon 파라미터가 필요합니다."}), 400
            
            # 카카오 길찾기 API 호출
            real_dist, real_eta, path_coords = get_driving_info_kakao(origin_lat, origin_lon, dest_lat, dest_lon, KAKAO_KEY)
            
            if path_coords:
                return jsonify({
                    "path_coords": path_coords,
                    "distance_km": real_dist,
                    "eta_minutes": real_eta
                })
            else:
                return jsonify({
                    "path_coords": None,
                    "distance_km": real_dist,
                    "eta_minutes": real_eta
                })
        except Exception as e:
            print(f"경로 조회 오류: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/geo/address2coord', methods=['GET'])
    def api_address2coord():
        """주소 → 좌표 변환 API"""
        try:
            # 여러 파라미터 이름 지원
            address = request.args.get('q') or request.args.get('query') or request.args.get('address')
            
            if not address:
                return jsonify({"error": "주소 파라미터(q, query, 또는 address)가 필요합니다."}), 400
            
            result = kakao_address2coord(address, KAKAO_KEY)
            if result:
                lat, lon, sido, sigungu = result
                response = {
                    "lat": lat,
                    "lon": lon
                }
                if sido:
                    response["sido"] = sido
                if sigungu:
                    response["sigungu"] = sigungu
                return jsonify(response), 200
            else:
                return jsonify({"error": "주소를 찾을 수 없습니다."}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500

