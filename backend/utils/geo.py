#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""지오코딩 유틸리티 함수"""

import math
from typing import Optional, Tuple, List
from pathlib import Path

from config import (
    KAKAO_KEY, KAKAO_COORD2REGION_URL, KAKAO_COORD2ADDR_URL, 
    KAKAO_ADDRESS_URL, KAKAO_DIRECTIONS_URL
)
from utils.http import http_get
import requests


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 좌표 간 거리 계산 (km)"""
    try:
        from geopy.distance import geodesic
        return geodesic((lat1, lon1), (lat2, lon2)).km
    except ImportError:
        # geopy가 없으면 간단한 계산
        R = 6371  # 지구 반지름 (km)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        return R * c


def kakao_coord2region(lon: float, lat: float, kakao_key: str) -> Optional[Tuple[str, str]]:
    """좌표 → 행정구역 변환"""
    if not kakao_key:
        return None
    headers = {"Authorization": f"KakaoAK {kakao_key}"}
    params = {"x": lon, "y": lat}
    try:
        r = http_get(KAKAO_COORD2REGION_URL, params=params, headers=headers)
        data = r.json()
        docs = data.get("documents", [])
        target = next((d for d in docs if d.get("region_type") == "B"), docs[0] if docs else None)
        if not target:
            return None
        return target.get("region_1depth_name"), target.get("region_2depth_name")
    except Exception as e:
        print(f"카카오 coord2region 오류: {e}")
        return None


def kakao_coord2address(lon: float, lat: float, kakao_key: str) -> Optional[str]:
    """좌표 → 주소 변환"""
    if not kakao_key:
        return None
    headers = {"Authorization": f"KakaoAK {kakao_key}"}
    params = {"x": lon, "y": lat}
    try:
        r = http_get(KAKAO_COORD2ADDR_URL, params=params, headers=headers)
        data = r.json()
        docs = data.get("documents", [])
        if not docs:
            return None
        d0 = docs[0]
        if d0.get("road_address") and d0["road_address"].get("address_name"):
            return d0["road_address"]["address_name"]
        if d0.get("address") and d0["address"].get("address_name"):
            return d0["address"]["address_name"]
        return None
    except Exception as e:
        print(f"카카오 coord2address 오류: {e}")
        return None


def kakao_address2coord(address: str, kakao_key: str) -> Optional[Tuple[float, float, Optional[str], Optional[str]]]:
    """주소 → 좌표 변환"""
    if not kakao_key:
        return None
    headers = {"Authorization": f"KakaoAK {kakao_key}"}
    params = {"query": address}
    try:
        r = http_get(KAKAO_ADDRESS_URL, params=params, headers=headers)
        data = r.json()
        docs = data.get("documents", [])
        if not docs:
            return None
        first = docs[0]
        lon = float(first["x"])
        lat = float(first["y"])
        
        # 행정구역 정보 추출 (주소에서)
        sido = None
        sigungu = None
        if first.get("road_address"):
            sido = first["road_address"].get("region_1depth_name")
            sigungu = first["road_address"].get("region_2depth_name")
        elif first.get("address"):
            sido = first["address"].get("region_1depth_name")
            sigungu = first["address"].get("region_2depth_name")
        
        return (lat, lon, sido, sigungu)
    except Exception as e:
        print(f"카카오 address2coord 오류: {e}")
        return None


def get_driving_info_kakao(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float, kakao_key: str) -> Tuple[Optional[float], Optional[int], Optional[List[List[float]]]]:
    """카카오 길찾기 API - 경로 및 소요 시간"""
    if not kakao_key:
        return None, None, None
    
    url = KAKAO_DIRECTIONS_URL
    headers = {"Authorization": f"KakaoAK {kakao_key}"}
    params = {
        "origin": f"{origin_lon},{origin_lat}",
        "destination": f"{dest_lon},{dest_lat}",
        "priority": "RECOMMEND",
    }
    
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            routes = data.get("routes", [])
            if routes:
                route = routes[0]
                summary = route.get("summary", {})
                distance_m = summary.get("distance", 0)
                duration_sec = summary.get("duration", 0)
                
                distance_km = distance_m / 1000
                duration_min = int(duration_sec / 60)
                
                # 경로 좌표 추출
                path_coords = []
                sections = route.get("sections", [])
                for section in sections:
                    guides = section.get("guides", [])
                    for guide in guides:
                        x = guide.get("x")
                        y = guide.get("y")
                        if x and y:
                            path_coords.append([x, y])
                
                return distance_km, duration_min, path_coords
    except Exception as e:
        print(f"카카오 길찾기 API 오류: {e}")
    
    return None, None, None


def guess_region_from_address(addr: Optional[str]) -> Optional[Tuple[str, str]]:
    """주소에서 행정구역 추측"""
    if not addr:
        return None
    parts = str(addr).strip().split()
    if len(parts) >= 2:
        return parts[0], parts[1]
    return None

