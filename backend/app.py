#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Twilio Callback Flask Server
Twilio의 Gather 콜백을 받기 위한 Flask 서버
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from twilio.twiml.voice_response import VoiceResponse
import time
import os
import requests
import tempfile
import math
from urllib.parse import urlparse
from typing import Optional, Tuple, Dict, Any, List, Iterable
from collections import defaultdict
from xml.etree import ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

# 설정 파일 import
from config import (
    KAKAO_KEY, DATA_GO_KR_KEY, OPENAI_API_KEY,
    ER_BED_URL, EGET_BASE_URL, EGET_LIST_URL, STRM_LIST_URL, KAKAO_DIRECTIONS_URL,
    KAKAO_COORD2REGION_URL, KAKAO_COORD2ADDR_URL, KAKAO_ADDRESS_URL,
    SYMPTOM_RULES, METRO_FALLBACK_PROVINCE, PROVINCE_INCLUDE_METROS,
    FLASK_PORT, CORS_ORIGINS
)

app = Flask(__name__)
# CORS 설정: React 앱에서 접근 가능하도록
CORS(app, origins=CORS_ORIGINS)

# OpenAI API 클라이언트
openai_client = None
try:
    from openai import OpenAI
    if OPENAI_API_KEY:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
except ImportError:
    print("⚠️ OpenAI 패키지가 설치되지 않았습니다. STT 기능을 사용하려면 'pip install openai'를 실행하세요.")


# 전역 변수: 다이얼 입력 저장
call_responses = {}

# 증상별 필수 요구사항은 config.py에서 import

# HTTP GET 헬퍼 함수
def _http_get(url: str, params: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> requests.Response:
    timeout = (5, 15)
    params = dict(params) if params else {}
    if url.startswith("http://apis.data.go.kr/"):
        url = url.replace("http://", "https://", 1)
    netloc = urlparse(url).netloc
    if "apis.data.go.kr" in netloc:
        svc_key = params.pop("serviceKey", DATA_GO_KR_KEY)
        if svc_key:
            if "%" in svc_key:
                join = "&" if ("?" in url) else "?"
                url = f"{url}{join}serviceKey={svc_key}"
            else:
                params["serviceKey"] = svc_key
    resp = requests.get(url, params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp

# 유틸리티 함수
def _safe_int(x):
    try:
        return int(str(x).strip()) if str(x).strip() not in ("", "None", "nan") else 0
    except:
        return 0

def evaluate_requirements(hospital_data: Dict[str, Any], rule: Dict[str, Any]) -> Tuple[float, bool]:
    """필수 요건 충족 비율(0~1)과 완전 충족 여부"""
    bool_requirements = rule.get("bool_any", [])
    min_requirements = rule.get("min_ge1", [])

    bool_total = len(bool_requirements)
    bool_satisfied = 0
    for key, want in bool_requirements:
        if str(hospital_data.get(key, "")).strip().upper() == want:
            bool_satisfied += 1

    min_total = len(min_requirements)
    min_satisfied = 0
    for key, thr in min_requirements:
        if _safe_int(hospital_data.get(key)) >= thr:
            min_satisfied += 1

    parts = []
    if bool_total:
        parts.append(bool_satisfied / bool_total)
    if min_total:
        parts.append(min_satisfied / min_total)
    score = sum(parts) / len(parts) if parts else 0
    fully_met = (bool_total == bool_satisfied if bool_total else True) and (min_total == min_satisfied if min_total else True)
    return score, fully_met

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

def guess_region_from_address(addr: Optional[str]) -> Optional[Tuple[str, str]]:
    if not addr:
        return None
    parts = str(addr).strip().split()
    if len(parts) >= 2:
        return parts[0], parts[1]
    return None

def _fetch_grade_info_for_region(region: str, hpids_to_find: set, url: str, service_key: str) -> Dict[str, Dict[str, Any]]:
    """특정 지역의 등급 정보 조회 (내부 헬퍼 함수) - 스레드 안전"""
    grade_info = {}
    try:
        r = _http_get(url, {"STAGE1": region, "pageNo": 1, "numOfRows": 500, "serviceKey": service_key})
        root = ET.fromstring(r.content)
        for it in root.findall(".//item"):
            hpid_elem = it.find("hpid")
            if hpid_elem is not None and hpid_elem.text in hpids_to_find:
                hpid = hpid_elem.text.strip()
                def g(tag):
                    el = it.find(tag)
                    return el.text.strip() if el is not None and el.text is not None else None
                
                grade_info[hpid] = {
                    "dutyEmcls": g("dutyEmcls"),
                    "dutyEmclsName": g("dutyEmclsName")
                }
    except Exception as e:
        pass
    return grade_info

def fetch_hospital_grade_info(hpids: List[str], service_key: str, target_regions: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
    """병원 등급 정보 조회 (getEgytListInfoInqire + getStrmListInfoInqire) - 병렬 처리로 최적화"""
    if not hpids:
        return {}
    
    grade_info: Dict[str, Dict[str, Any]] = {}
    hpid_set = set(hpids)
    
    # 대상 지역이 지정되지 않으면 주요 지역만 조회 (성능 최적화)
    if target_regions is None:
        target_regions = ["서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시", "대전광역시", "울산광역시", 
                         "경기도", "강원도", "충청북도", "충청남도", "전라북도", "전라남도", "경상북도", "경상남도", "제주특별자치도", "세종특별자치시"]
    
    # 1. getEgytListInfoInqire로 일반 응급의료기관 등급 정보 조회 (병렬 처리)
    remaining_hpids = hpid_set.copy()
    if remaining_hpids:
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(_fetch_grade_info_for_region, region, remaining_hpids, EGET_LIST_URL, service_key)
                for region in target_regions
            ]
            for future in as_completed(futures):
                try:
                    region_grade_info = future.result()
                    for hpid, info in region_grade_info.items():
                        if hpid not in grade_info:
                            grade_info[hpid] = info
                            remaining_hpids.discard(hpid)
                    if not remaining_hpids:
                        break
                except Exception as e:
                    continue
    
    # 2. getStrmListInfoInqire로 권역외상센터 정보 조회 (권역외상센터는 우선 적용, 병렬 처리)
    remaining_hpids = hpid_set - set(grade_info.keys())
    if remaining_hpids:
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(_fetch_grade_info_for_region, region, remaining_hpids, STRM_LIST_URL, service_key)
                for region in target_regions
            ]
            for future in as_completed(futures):
                try:
                    region_grade_info = future.result()
                    for hpid, info in region_grade_info.items():
                        # 권역외상센터 정보가 있으면 우선 적용 (덮어쓰기)
                        grade_info[hpid] = info
                        remaining_hpids.discard(hpid)
                    if not remaining_hpids:
                        break
                except Exception as e:
                    continue
    
    return grade_info

def fetch_baseinfo_by_hpid(hpid: str, service_key: str) -> Optional[Dict[str, Any]]:
    """병원 기본정보 조회"""
    try:
        r = _http_get(EGET_BASE_URL, {"HPID": hpid, "pageNo": 1, "numOfRows": 1, "serviceKey": service_key})
        root = ET.fromstring(r.content)
        it = root.find(".//item")
        if it is None:
            return None
        
        def g(tag):
            el = it.find(tag)
            return el.text.strip() if el is not None and el.text is not None else None
        
        return {
            "hpid": g("hpid"),
            "dutyName": g("dutyName") or g("dutyname"),
            "dutyAddr": g("dutyAddr"),
            "dutytel3": g("dutyTel3"),
            "wgs84Lat": float(g("wgs84Lat")) if g("wgs84Lat") else None,
            "wgs84Lon": float(g("wgs84Lon")) if g("wgs84Lon") else None,
            "dutyDiv": g("dutyDiv"),
            "dutyDivNam": g("dutyDivNam"),
            "dutyEmcls": g("dutyEmcls"),
            "dutyEmclsName": g("dutyEmclsName"),
        }
    except Exception as e:
        print(f"병원 기본정보 조회 오류 ({hpid}): {e}")
        return None

def fetch_emergency_hospitals_in_region(sido: str, sigungu: Optional[str], service_key: str, max_items: int = 120) -> List[Dict[str, Any]]:
    """지역 내 응급 병원 조회 (병렬 처리로 최적화, 최대 120개로 제한)"""
    try:
        params = {"STAGE1": sido, "pageNo": 1, "numOfRows": min(500, max_items * 2), "serviceKey": service_key}  # 필요한 만큼만 요청
        if sigungu:
            params["STAGE2"] = sigungu
        r = _http_get(ER_BED_URL, params)
        root = ET.fromstring(r.content)
        hpids = []
        for it in root.findall(".//item"):
            el = it.find("hpid")
            if el is not None and el.text:
                hpids.append(el.text.strip())
        hpids = list(dict.fromkeys(hpids))[:max_items]  # 최대 개수 제한
        
        # 병렬 처리로 병원 정보 조회 (최대 20개 동시 실행)
        hospitals = []
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_to_hpid = {executor.submit(fetch_baseinfo_by_hpid, hpid, service_key): hpid for hpid in hpids}
            for future in as_completed(future_to_hpid):
                try:
                    info = future.result()
                    if info and info.get("wgs84Lat") and info.get("wgs84Lon"):
                        hospitals.append(info)
                except Exception as e:
                    hpid = future_to_hpid[future]
                    print(f"병원 정보 조회 오류 ({hpid}): {e}")
        
        return hospitals
    except Exception as e:
        print(f"응급 병원 조회 오류: {e}")
        return []

def fetch_er_beds(sido: str, sigungu: Optional[str], service_key: str, rows: int = 500) -> Dict[str, Dict[str, Any]]:
    """실시간 응급 병상/장비 정보 조회"""
    try:
        params = {"STAGE1": sido, "pageNo": 1, "numOfRows": rows, "serviceKey": service_key}
        if sigungu:
            params["STAGE2"] = sigungu
        resp = _http_get(ER_BED_URL, params=params)
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")
        
        beds_dict = {}
        for it in items:
            def g(tag):
                el = it.find(tag)
                return el.text.strip() if el is not None and el.text is not None else None
            
            hpid = g("hpid")
            if not hpid:
                continue
            
            beds_dict[hpid] = {
                "hpid": hpid,
                "dutyName": g("dutyname"),
                "hvidate": g("hvidate"),
                "hvec": g("hvec"),
                "hvoc": g("hvoc"),
                "hvicc": g("hvicc"),
                "hvgc": g("hvgc"),
                "hvcc": g("hvcc"),
                "hvncc": g("hvncc"),
                "hvccc": g("hvccc"),
                "hvctayn": g("hvctayn"),
                "hvmriayn": g("hvmriayn"),
                "hvangioayn": g("hvangioayn"),
                "hvventiayn": g("hvventiayn"),
                "hv1": g("hv1"),
                "hv2": g("hv2"),
                "hv3": g("hv3"),
                "hv4": g("hv4"),
                "hv5": g("hv5"),
                "hv6": g("hv6"),
                "hv7": g("hv7"),
                "hv8": g("hv8"),
                "hv9": g("hv9"),
                "hv10": g("hv10"),
                "hv11": g("hv11"),
                "hv12": g("hv12"),
                "dutytel3": g("dutytel3") or g("hv1"),
                "hvdnm": g("hvdnm"),
            }
        return beds_dict
    except Exception as e:
        print(f"병상 정보 조회 오류: {e}")
        return {}

# METRO_FALLBACK_PROVINCE와 PROVINCE_INCLUDE_METROS는 config.py에서 import

def is_metropolitan(sido: str) -> bool:
    return sido.endswith("광역시") or sido.endswith("특별시") or sido.endswith("특별자치시")

def fetch_trauma_centers_in_region(sido: str, sigungu: Optional[str], service_key: str, max_items: int = 80) -> List[Dict[str, Any]]:
    """지역 내 외상센터 조회 (getStrmListInfoInqire) - 병렬 처리로 최적화, 최대 80개로 제한"""
    try:
        params = {"STAGE1": sido, "pageNo": 1, "numOfRows": min(500, max_items * 2), "serviceKey": service_key}  # 필요한 만큼만 요청
        if sigungu:
            params["STAGE2"] = sigungu
        r = _http_get(STRM_LIST_URL, params)
        root = ET.fromstring(r.content)
        
        # 먼저 모든 item에서 hpid와 등급 정보를 수집
        items_with_grade = []
        for it in root.findall(".//item"):
            hpid_elem = it.find("hpid")
            if hpid_elem is None or not hpid_elem.text:
                continue
            
            hpid = hpid_elem.text.strip()
            def g(tag):
                el = it.find(tag)
                return el.text.strip() if el is not None and el.text is not None else None
            
            items_with_grade.append({
                "hpid": hpid,
                "dutyEmcls": g("dutyEmcls"),
                "dutyEmclsName": g("dutyEmclsName")
            })
            if len(items_with_grade) >= max_items:
                break
        
        # 병렬 처리로 병원 기본정보 조회 (최대 20개 동시 실행)
        hospitals = []
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_to_item = {executor.submit(fetch_baseinfo_by_hpid, item["hpid"], service_key): item for item in items_with_grade}
            for future in as_completed(future_to_item):
                try:
                    info = future.result()
                    item = future_to_item[future]
                    if info and info.get("wgs84Lat") and info.get("wgs84Lon"):
                        # 외상센터 등급 정보 추가
                        info["dutyEmcls"] = item.get("dutyEmcls") or info.get("dutyEmcls")
                        info["dutyEmclsName"] = item.get("dutyEmclsName") or info.get("dutyEmclsName")
                        hospitals.append(info)
                except Exception as e:
                    hpid = future_to_item[future]["hpid"]
                    print(f"외상센터 정보 조회 오류 ({hpid}): {e}")
        
        return hospitals
    except Exception as e:
        print(f"외상센터 조회 오류: {e}")
        return []

def fetch_scope_hospitals(primary_sido: str, extra_sidos: Optional[Iterable[str]] = None, hospital_type: str = "general") -> List[Dict[str, Any]]:
    """지역 내 병원 조회 (일반 응급의료기관, 외상센터, 또는 소아 중증 전용) - 성능 최적화: 최대 150개로 제한"""
    aggregated: Dict[str, Dict[str, Any]] = {}
    targets = [primary_sido]
    if extra_sidos:
        targets.extend(extra_sidos)
    
    # 지역당 최대 조회 개수 제한 (성능 최적화)
    MAX_HOSPITALS_PER_REGION = 150  # 기존 400개에서 대폭 축소
    
    for target in targets:
        if hospital_type == "trauma":
            # 외상센터 우선 조회 (최대 80개)
            hospitals = fetch_trauma_centers_in_region(target, None, DATA_GO_KR_KEY, max_items=80)
            # 외상센터와 함께 일반 응급의료기관도 항상 조회 (최대 70개)
            general_hospitals = fetch_emergency_hospitals_in_region(target, None, DATA_GO_KR_KEY, max_items=70)
            hospitals.extend(general_hospitals)
        elif hospital_type == "pediatric":
            # 소아 중증: 모든 응급의료기관 조회 (최대 120개)
            hospitals = fetch_emergency_hospitals_in_region(target, None, DATA_GO_KR_KEY, max_items=120)
            # 외상센터도 포함 (최대 30개)
            trauma_hospitals = fetch_trauma_centers_in_region(target, None, DATA_GO_KR_KEY, max_items=30)
            hospitals.extend(trauma_hospitals)
        else:
            # 일반 응급의료기관 조회 (최대 120개)
            hospitals = fetch_emergency_hospitals_in_region(target, None, DATA_GO_KR_KEY, max_items=120)
            # 외상센터도 포함하여 통합 검색 (최대 30개)
            trauma_hospitals = fetch_trauma_centers_in_region(target, None, DATA_GO_KR_KEY, max_items=30)
            hospitals.extend(trauma_hospitals)
        
        for hospital in hospitals:
            hpid = hospital.get("hpid")
            if not hpid:
                continue
            if hpid not in aggregated:
                aggregated[hpid] = hospital
        
        # 이미 충분한 병원을 찾았으면 조기 종료 (성능 최적화)
        if len(aggregated) >= MAX_HOSPITALS_PER_REGION * len(targets):
            break
    
    return list(aggregated.values())

def fetch_beds_for_sidos(sidos: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    """병상 정보 조회 - 성능 최적화: 병렬 처리"""
    combined: Dict[str, Dict[str, Any]] = {}
    sidos_list = list(sidos)
    
    # 병렬 처리로 병상 정보 조회
    with ThreadPoolExecutor(max_workers=min(5, len(sidos_list))) as executor:
        future_to_sido = {executor.submit(fetch_er_beds, target, None, DATA_GO_KR_KEY, rows=500): target for target in sidos_list}
        for future in as_completed(future_to_sido):
            try:
                beds_dict = future.result()
                combined.update(beds_dict)
            except Exception as e:
                sido = future_to_sido[future]
                print(f"병상 정보 조회 오류 ({sido}): {e}")
    
    return combined

def prioritize_by_region(records: List[Dict[str, Any]], max_regions: Optional[int] = None) -> List[Dict[str, Any]]:
    if not records:
        return []
    buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for hospital in records:
        region = hospital.get("region_name") or hospital.get("sigunguCd") or "미상"
        buckets[region].append(hospital)
    ordered_regions = sorted(
        buckets.keys(),
        key=lambda region: min(
            buckets[region],
            key=lambda item: item.get("distance_km", float('inf'))
        ).get("distance_km", float('inf'))
    )
    if max_regions is not None:
        ordered_regions = ordered_regions[:max_regions]
    flattened: List[Dict[str, Any]] = []
    for region in ordered_regions:
        region_hospitals = sorted(
            buckets[region],
            key=lambda item: item.get("distance_km", float('inf'))
        )
        flattened.extend(region_hospitals)
    return flattened

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


def serialize_hospital_payload(h: Dict[str, Any]) -> Dict[str, Any]:
    """프론트엔드로 전달할 병원 정보를 정규화"""
    return {
        "hpid": h.get("hpid"),
        "dutyName": h.get("dutyName"),
        "dutyAddr": h.get("dutyAddr"),
        "dutytel3": h.get("dutytel3"),
        "wgs84Lat": h.get("wgs84Lat"),
        "wgs84Lon": h.get("wgs84Lon"),
        "distance_km": h.get("distance_km"),
        "eta_minutes": h.get("eta_minutes"),
        "_meets_conditions": h.get("_meets_conditions", False),
        "dutyDiv": h.get("dutyDiv"),
        "dutyDivNam": h.get("dutyDivNam"),
        "dutyEmcls": h.get("dutyEmcls"),
        "dutyEmclsName": h.get("dutyEmclsName"),
        "hvec": h.get("hvec"),
        "hvoc": h.get("hvoc"),
        "hvicc": h.get("hvicc"),
        "hvgc": h.get("hvgc"),
        "hvcc": h.get("hvcc"),
        "hvncc": h.get("hvncc"),
        "hvccc": h.get("hvccc"),
        "hv1": h.get("hv1"),
        "hv2": h.get("hv2"),
        "hv3": h.get("hv3"),
        "hv4": h.get("hv4"),
        "hv5": h.get("hv5"),
        "hv6": h.get("hv6"),
        "hv7": h.get("hv7"),
        "hv8": h.get("hv8"),
        "hv9": h.get("hv9"),
        "hv10": h.get("hv10"),
        "hv11": h.get("hv11"),
        "hv12": h.get("hv12"),
        "hvdnm": h.get("hvdnm"),
        "hvidate": h.get("hvidate"),
        "hvctayn": h.get("hvctayn"),
        "hvmriayn": h.get("hvmriayn"),
        "hvangioayn": h.get("hvangioayn"),
        "hvventiayn": h.get("hvventiayn"),
        "region_name": h.get("region_name"),
    }

# 카카오 API 함수들
def kakao_coord2region(lon: float, lat: float, kakao_key: str) -> Optional[Tuple[str, str]]:
    """좌표 → 행정구역 변환"""
    if not kakao_key:
        return None
    headers = {"Authorization": f"KakaoAK {kakao_key}"}
    params = {"x": lon, "y": lat}
    try:
        r = _http_get(KAKAO_COORD2REGION_URL, params=params, headers=headers)
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
        r = _http_get(KAKAO_COORD2ADDR_URL, params=params, headers=headers)
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
        r = _http_get(KAKAO_ADDRESS_URL, params=params, headers=headers)
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

# 지오코딩 API 엔드포인트
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

# STT API 엔드포인트
@app.route('/api/stt/transcribe', methods=['POST'])
def api_stt_transcribe():
    """음성을 텍스트로 변환하고 의학용어를 번역하는 API"""
    if not openai_client:
        return jsonify({"error": "OpenAI 클라이언트가 초기화되지 않았습니다. API 키를 확인하세요."}), 500
    
    try:
        # 파일 업로드 확인
        if 'audio' not in request.files:
            return jsonify({"error": "audio 파일이 필요합니다."}), 400
        
        audio_file = request.files['audio']
        if audio_file.filename == '':
            return jsonify({"error": "파일이 선택되지 않았습니다."}), 400
        
        # 임시 파일로 저장
        audio_bytes = audio_file.read()
        if len(audio_bytes) == 0:
            return jsonify({"error": "파일이 비어있습니다."}), 400
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            tmp_file.write(audio_bytes)
            tmp_file_path = tmp_file.name
        
        # Whisper STT
        with open(tmp_file_path, "rb") as audio_file_obj:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file_obj,
                response_format="text",
                language="ko"
            )
        
        # GPT-4-turbo로 의학용어 번역
        medical_keywords = """M/S, mental state, Alert, confusion, drowsy, stupor, semicoma, coma, V/S, vital sign, TPR, temperature, pulse, respiration, HR, heart rate, PR, pulse rate, BP, blood pressure, BT, body temperature, RR, respiratory rate, BST, blood sugar test, SpO2, sat, saturation of percutaneous oxygen, Abdomen, Abdominal pain, Abnormal, Abrasion, Abscess, Acetaminophen, Acidosis, Acute, Acute abdomen, Acute bronchitis, Acute coronary syndrome, Acute myocardial infarction, Acute renal failure, Acute respiratory distress syndrome, Acute stroke, Airway, Airway obstruction, Alcohol intoxication, Allergy, Allergic reaction, Amnesia, Anaphylactic shock, Anaphylaxis, Analgesic, Anemia, Aneurysm, Angina, Angina pectoris, Angiography, Arrhythmia, Arterial bleeding, Asphyxia, Aspiration, Asthma, Cardiac Arrest, Cardiac tamponade, Cardiogenic shock, Cardiopulmonary arrest, Cardiopulmonary resuscitation (CPR), Cerebral hemorrhage, Cerebral infarction, Cerebrovascular accident (CVA), Chest compression, Chest pain, Choking, Chronic obstructive pulmonary disease (COPD), Coma, Concussion, Confusion, Convulsion, Coronary artery disease (CAD), Cough, Cyanosis, Defibrillation, Dehydration, Dementia, Diabetes mellitus, Diabetic ketoacidosis, Diarrhea, Dizziness, Drowning, Drowsy, Dyspnea, ECG (Electrocardiogram), Edema, Electrocution, Embolism, Emphysema, Endotracheal intubation, Epilepsy, Epistaxis, Fever, Fracture, GCS (Glasgow Coma Scale), Headache, Head injury, Heart arrest, Heart failure, Heart rate, Hematoma, Hematuria, Hemoptysis, Hemorrhage, Hyperglycemia, Hypertension, Hyperthermia, Hyperventilation, Hypoglycemia, Hypotension, Hypothermia, Hypovolemic shock, Hypoxia, Intoxication, Intracranial pressure, Ischemia, Laceration, Myocardial infarction, Nausea, Oxygen therapy, Pneumonia, Pneumothorax, Respiratory arrest, Respiratory distress, Respiratory failure, Seizure, Sepsis, Septic shock, Shock, Stroke, Stupor, Syncope, Tachycardia, Trauma, Unconsciousness, Ventilation, Vertigo, Vomiting, Wound"""
        
        prompt = f"""아래는 응급의료 상황 대화의 텍스트입니다.
        전반적으로 한국어로 번역하되, 텍스트에서 등장하는 의학 관련 용어(약어 포함)는 응급의료 문맥에 맞게 올바르게 영어로 번역하세요.
내가 너에게 전달해준 문장을 누락없이 번역해야해.
단, 출력문장은 오직 번역문장만 남겨서 깔끔하게 출력하세요.

참고 키워드: {medical_keywords}

텍스트:
{transcript}
"""
        
        completion = openai_client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "너는 응급의료 현장의 대화를 전문적으로 해석하는 의료용어 번역 전문가이다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        translated_text = completion.choices[0].message.content
        
        # STT 결과 저장 (타임스탬프 포함, 누적 기록)
        import datetime
        save_stt_filepath = "stt_history.txt"
        with open(save_stt_filepath, "a", encoding="utf-8") as fh:
            timestr = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            fh.write(f"[{timestr}] {translated_text}\n")
        
        # 임시 파일 삭제
        os.remove(tmp_file_path)
        
        return jsonify({"text": translated_text}), 200
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"STT 오류: {error_detail}")
        return jsonify({"error": f"음성 인식 오류: {str(e)}"}), 500

# 병원 조회 API
@app.route('/api/hospitals/top3', methods=['POST', 'OPTIONS'])
def api_hospitals_top3():
    """병원 Top3 조회 API"""
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.get_json()
        lat = float(data.get('lat', 0))
        lon = float(data.get('lon', 0))
        sido = data.get('sido', '')
        sigungu = data.get('sigungu', '')
        symptom = data.get('symptom', '')
        stt_text = data.get('stt_text')
        
        # 증상에 따라 자동으로 병원 타입 결정
        # 다발성 외상/중증 외상 → 외상센터 우선
        # 소아 중증 → 소아중환자실 보유 병원 우선 (일반 응급의료기관에서 필터링)
        # 그 외 → 일반 응급의료기관
        if symptom == "다발성 외상/중증 외상":
            hospital_type = "trauma"
        elif symptom == "소아 중증(신생아/영아)":
            hospital_type = "pediatric"  # 소아 중증 전용
        else:
            hospital_type = "general"
        
        if not lat or not lon or not sido or not sigungu:
            return jsonify({"error": "lat, lon, sido, sigungu 파라미터가 필요합니다."}), 400
        
        extra_sidos = PROVINCE_INCLUDE_METROS.get(sido, [])
        scope_targets = [sido] + extra_sidos
        all_hospitals_raw = fetch_scope_hospitals(sido, extra_sidos, hospital_type)
        if not all_hospitals_raw:
            return jsonify({"error": "해당 행정구역의 응급 대상 병원을 찾지 못했습니다."}), 404

        beds_dict = fetch_beds_for_sidos(scope_targets)
        rule = SYMPTOM_RULES.get(symptom, {})
        
        # 모든 병원의 hpid 수집하여 등급 정보 일괄 조회 (대상 지역만 조회하여 성능 최적화)
        all_hpids = [h.get("hpid") for h in all_hospitals_raw if h.get("hpid")]
        target_regions = list(set([sido] + extra_sidos + ([METRO_FALLBACK_PROVINCE.get(sido)] if is_metropolitan(sido) and METRO_FALLBACK_PROVINCE.get(sido) else [])))
        grade_info_dict = fetch_hospital_grade_info(all_hpids, DATA_GO_KR_KEY, target_regions)

        def enrich_records(
            hospitals_raw: List[Dict[str, Any]],
            bed_source: Dict[str, Dict[str, Any]],
            is_local_region: Optional[bool] = None,
        ) -> List[Dict[str, Any]]:
            enriched: List[Dict[str, Any]] = []
            for hospital in hospitals_raw:
                hpid = hospital.get("hpid")
                if not hpid:
                    continue
                merged = dict(hospital)
                if hpid in bed_source:
                    for key, value in bed_source[hpid].items():
                        if key in ("dutyName", "dutytel3"):
                            continue
                        if value is not None:
                            merged[key] = value
                # 등급 정보 병합 (우선순위: grade_info_dict > 기존 정보)
                if hpid in grade_info_dict:
                    grade_info = grade_info_dict[hpid]
                    if grade_info.get("dutyEmcls"):
                        merged["dutyEmcls"] = grade_info["dutyEmcls"]
                    if grade_info.get("dutyEmclsName"):
                        merged["dutyEmclsName"] = grade_info["dutyEmclsName"]
                guess = guess_region_from_address(merged.get("dutyAddr"))
                region_name = guess[1] if guess and len(guess) > 1 else (guess[0] if guess else None)
                merged["region_name"] = region_name or sigungu or merged.get("region_name")
                
                # 거리 계산을 먼저 수행 (조기 필터링을 위해)
                if merged.get("wgs84Lat") and merged.get("wgs84Lon"):
                    merged["distance_km"] = calculate_distance(lat, lon, merged["wgs84Lat"], merged["wgs84Lon"])
                    # 조기 필터링: 150km 이상 떨어진 병원은 제외 (성능 최적화)
                    if merged["distance_km"] > 150.0:
                        continue
                else:
                    merged["distance_km"] = float('inf')
                    # 좌표가 없으면 제외
                    continue
                
                # 지역 내 병원 판단: region_name이 sigungu와 정확히 일치하면 local
                # 단, extra_sidos(광역시)에 포함된 병원은 neighbor로 분류하되, 거리 필터링은 별도로 적용
                if is_local_region is None:
                    # region_name이 sigungu와 일치하면 local
                    is_local = (not sigungu) or (merged["region_name"] == sigungu)
                    merged["_is_local_region"] = is_local
                else:
                    merged["_is_local_region"] = is_local_region
                
                score, fully_met = evaluate_requirements(merged, rule)
                merged["_requirement_score"] = score
                merged["_meets_conditions"] = fully_met
                
                # 소아 중증 환자의 경우: 소아중환자실(hvncc) 보유 병원에 가산점
                if hospital_type == "pediatric" and symptom == "소아 중증(신생아/영아)":
                    hvncc = _safe_int(merged.get("hvncc", 0))
                    if hvncc >= 1:
                        merged["_requirement_score"] = score + 10.0  # 소아중환자실 보유 시 가산점
                enriched.append(merged)
            return enriched

        merged_hospitals = enrich_records(all_hospitals_raw, beds_dict)
        local_hospitals = [h for h in merged_hospitals if h.get("_is_local_region")]
        if not local_hospitals:
            local_hospitals = merged_hospitals.copy()
        neighbor_same_scope = [h for h in merged_hospitals if not h.get("_is_local_region")]

        def get_priority_score(hospital: Dict[str, Any]) -> float:
            """등급 우선순위 점수 (높을수록 우선) - 외부에서도 사용 가능하도록 함수로 분리"""
            # 권역외상센터 > 권역응급의료센터 > 3차 상급종합병원 > 2차 응급의료기관
            duty_emcls_name = str(hospital.get("dutyEmclsName", ""))
            duty_div_name = str(hospital.get("dutyDivNam", ""))
            
            # 권역외상센터 (최우선)
            if "권역외상센터" in duty_emcls_name:
                return 4.0
            # 권역응급의료센터 (조선대학교병원 등)
            if "권역응급의료센터" in duty_emcls_name or "권역응급의료센터" in duty_div_name:
                return 3.5
            # 3차 상급종합병원
            if "3차" in duty_div_name or "상급종합" in duty_div_name:
                return 2.0
            # 2차 응급의료기관
            if "2차" in duty_div_name:
                return 1.0
            return 0.0
        
        def sort_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            """병원 정렬: 요구사항 점수 > 등급 우선순위 > 거리"""
            return sorted(
                records,
                key=lambda x: (
                    -x.get("_requirement_score", 0.0),  # 요구사항 점수 (높을수록 우선)
                    -get_priority_score(x),  # 등급 우선순위 (높을수록 우선)
                    x.get("distance_km", float('inf'))  # 거리 (가까울수록 우선)
                )
            )

        # 지역 내 병원도 거리 제한 적용: 100km 이내만 (너무 먼 지역 내 병원 제외)
        local_hospitals_filtered = [h for h in local_hospitals if h.get("distance_km", float('inf')) <= 100.0]
        primary_sorted = sort_records(local_hospitals_filtered if local_hospitals_filtered else local_hospitals)
        secondary_sorted = sort_records(neighbor_same_scope)
        
        # 거리 기반 필터링: 100km 이내 병원만 고려 (광주광역시 같은 인접 광역시 포함)
        nearby_secondary = [h for h in secondary_sorted if h.get("distance_km", float('inf')) <= 100.0]
        far_secondary = [h for h in secondary_sorted if h.get("distance_km", float('inf')) > 100.0]
        
        # 가까운 병원들을 행정구역별로 정렬 (최대 3개 구역)
        # 단, 각 구역 내에서도 거리 순으로 정렬되어야 함
        nearby_prioritized = prioritize_by_region(nearby_secondary, max_regions=3)
        
        # combined_candidates: 지역 내 병원 + 가까운 인접 지역 병원 (100km 이내, 광주광역시 포함)
        combined_candidates = primary_sorted + nearby_prioritized
        
        # 100km 이내 병원이 부족하면 더 먼 병원도 추가하되, 거리 순으로 정렬하여 추가
        # (하지만 이미 nearby_secondary에 100km 이내가 모두 포함되어 있으므로 이 부분은 거의 실행되지 않음)
        if len(combined_candidates) < 3:
            # 먼 병원들도 거리 순으로 추가 (하지만 100km 이내만)
            far_filtered = [h for h in far_secondary if h.get("distance_km", float('inf')) <= 100.0]
            combined_candidates.extend(sort_records(far_filtered)[:10])
        
        if not combined_candidates:
            # merged_hospitals에서도 100km 이내만 사용
            combined_candidates = [h for h in sort_records(merged_hospitals) if h.get("distance_km", float('inf')) <= 100.0]

        # 최종 정렬: 요구사항 점수 > 거리 순으로 다시 정렬
        combined_candidates = sort_records(combined_candidates)
        
        # combined_candidates에서 100km 초과 병원 제거 (128km 같은 병원 제외)
        combined_candidates = [h for h in combined_candidates if h.get("distance_km", float('inf')) <= 100.0]
        
        # top3는 거리 제한 적용: 50km 이내 우선, 부족하면 최대 100km까지 확장
        # 128km 같은 먼 병원은 절대 포함하지 않음
        top3_filtered_50km = [h for h in combined_candidates if h.get("distance_km", float('inf')) <= 50.0]
        if len(top3_filtered_50km) >= 3:
            top3 = top3_filtered_50km[:3]
        else:
            # 50km 이내가 3개 미만이면 50-100km 범위에서만 추가 (거리 순으로)
            mid_range = [h for h in combined_candidates if 50.0 < h.get("distance_km", float('inf')) <= 100.0]
            top3 = top3_filtered_50km + sort_records(mid_range)[:3 - len(top3_filtered_50km)]
            # 여전히 3개 미만이면 지역 내 병원만 사용하되, 100km 이내만 (절대 100km 초과 병원은 제외)
            if len(top3) < 3:
                remaining = [h for h in combined_candidates if h.get("distance_km", float('inf')) <= 100.0 and h not in top3]
                top3.extend(sort_records(remaining)[:3 - len(top3)])
        
        # 최종 검증: top3에 100km 초과 병원이 있으면 제거
        top3 = [h for h in top3 if h.get("distance_km", float('inf')) <= 100.0]
        
        backup_candidates = [h for h in combined_candidates[3:13] if h.get("distance_km", float('inf')) <= 100.0]

        # neighbor_candidates: 100km 이내 인접 지역 병원 우선 (최대 5개 구역, 최대 10개, 광주광역시 포함)
        nearby_neighbor = prioritize_by_region(nearby_secondary, max_regions=5)[:10]
        neighbor_candidates = nearby_neighbor

        fallback_sido = METRO_FALLBACK_PROVINCE.get(sido) if is_metropolitan(sido) else None
        fallback_hospitals: List[Dict[str, Any]] = []
        if fallback_sido:
            fallback_extra = PROVINCE_INCLUDE_METROS.get(fallback_sido, [])
            fallback_raw = fetch_scope_hospitals(fallback_sido, fallback_extra, hospital_type)
            fallback_beds = fetch_beds_for_sidos([fallback_sido] + fallback_extra)
            fallback_profiles = enrich_records(fallback_raw, fallback_beds, is_local_region=False)
            fallback_hospitals.extend(prioritize_by_region(fallback_profiles, max_regions=3))

        used_hpids = {h.get("hpid") for h in top3}
        neighbor_augmented = []
        seen_ids = set()
        
        # neighbor_candidates와 fallback_hospitals를 거리 순으로 정렬하여 추가
        all_neighbor_sources = neighbor_candidates + fallback_hospitals
        all_neighbor_sorted = sort_records(all_neighbor_sources)
        
        for hospital in all_neighbor_sorted:
            hpid = hospital.get("hpid")
            if not hpid or hpid in used_hpids or hpid in seen_ids:
                continue
            # 거리 제한: 100km 이내 병원만 추가
            if hospital.get("distance_km", float('inf')) <= 100.0:
                neighbor_augmented.append(hospital)
                seen_ids.add(hpid)
                if len(neighbor_augmented) >= 9:
                    break

        neighbor_candidates = neighbor_augmented

        # top3가 3개 미만이면 neighbor_candidates에서 추가 (거리 순으로, 100km 이내만)
        if len(top3) < 3 and neighbor_candidates:
            needed = 3 - len(top3)
            # 100km 이내 병원만 추가
            nearby_neighbors = [h for h in neighbor_candidates if h.get("distance_km", float('inf')) <= 100.0]
            top3.extend(nearby_neighbors[:needed])
            neighbor_candidates = neighbor_candidates[needed:]

        # 경로 정보 조회 (카카오 API) - 병렬 처리로 최적화
        route_paths = {}
        top3_valid = []
        top3_to_backup = []
        
        # 경로 정보 조회를 병렬로 수행
        hospitals_with_coords = [
            (h, h.get("wgs84Lat"), h.get("wgs84Lon")) 
            for h in top3 
            if h.get("wgs84Lat") and h.get("wgs84Lon")
        ]
        
        if hospitals_with_coords:
            with ThreadPoolExecutor(max_workers=min(5, len(hospitals_with_coords))) as executor:
                future_to_hospital = {
                    executor.submit(get_driving_info_kakao, lat, lon, h_lat, h_lon, KAKAO_KEY): (hospital, h_lat, h_lon)
                    for hospital, h_lat, h_lon in hospitals_with_coords
                }
                
                for future in as_completed(future_to_hospital):
                    hospital, h_lat, h_lon = future_to_hospital[future]
                    try:
                        real_dist, real_eta, path_coords = future.result()
                        
                        if real_dist and real_eta:
                            hospital["distance_km"] = real_dist
                            hospital["eta_minutes"] = real_eta
                            if path_coords:
                                route_paths[hospital.get("hpid", "")] = path_coords
                        else:
                            # API 실패 시 추정값
                            if isinstance(hospital.get("distance_km"), (int, float)):
                                dist = hospital["distance_km"]
                                hospital["eta_minutes"] = int((dist * 1.3 / 40) * 60)
                    except Exception as e:
                        print(f"경로 정보 조회 오류 ({hospital.get('hpid', 'unknown')}): {e}")
                        # API 실패 시 추정값
                        if isinstance(hospital.get("distance_km"), (int, float)):
                            dist = hospital["distance_km"]
                            hospital["eta_minutes"] = int((dist * 1.3 / 40) * 60)
        
        # 거리 검증 및 분류
        for hospital in top3:
            if hospital.get("distance_km", float('inf')) <= 100.0:
                top3_valid.append(hospital)
            else:
                # 100km 초과면 backup으로 이동
                top3_to_backup.append(hospital)
        
        # backup_candidates에 100km 초과 병원 추가
        backup_candidates.extend(top3_to_backup)
        
        # top3 업데이트: 100km 이내 병원만 포함
        top3 = top3_valid
        
        # top3가 3개 미만이 되면 backup에서 가까운 병원으로 보충 (100km 이내만)
        if len(top3) < 3:
            backup_sorted = sort_records([h for h in backup_candidates if h.get("distance_km", float('inf')) <= 100.0])
            needed = 3 - len(top3)
            top3.extend(backup_sorted[:needed])
            backup_candidates = backup_sorted[needed:]
        
        # 응답 형식 변환
        result_hospitals = [serialize_hospital_payload(h) for h in top3]
        backup_payload = [serialize_hospital_payload(h) for h in backup_candidates]
        
        return jsonify({
            "hospitals": result_hospitals,
            "route_paths": route_paths,
            "backup_hospitals": backup_payload,
            "neighbor_hospitals": [serialize_hospital_payload(h) for h in neighbor_candidates]
        }), 200
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"병원 조회 오류: {error_detail}")
        return jsonify({"error": f"병원 조회 중 오류가 발생했습니다: {str(e)}"}), 500

@app.route('/')
def index():
    """서버 상태 확인"""
    return """
    <html>
    <head><title>Twilio Flask Server</title></head>
    <body style="font-family: Arial; padding: 2rem;">
        <h1>✅ Twilio Flask Server 실행 중</h1>
        <p><b>포트:</b> 5001 (macOS AirPlay가 5000 사용)</p>
        <p><b>엔드포인트:</b></p>
        <ul>
            <li><code>/twilio/gather</code> - 다이얼 입력 콜백</li>
            <li><code>/twilio/status</code> - 통화 상태 콜백</li>
            <li><code>/responses</code> - 저장된 응답 확인 (HTML)</li>
            <li><code>/api/responses</code> - 모든 응답 (JSON)</li>
            <li><code>/api/response/&lt;call_sid&gt;</code> - 특정 응답 (JSON)</li>
            <li><code>/api/geo/coord2address</code> - 좌표 → 주소 변환</li>
            <li><code>/api/geo/coord2region</code> - 좌표 → 행정구역 변환</li>
            <li><code>/api/geo/address2coord</code> - 주소 → 좌표 변환</li>
            <li><code>/api/stt/transcribe</code> - 음성 → 텍스트 변환 (STT)</li>
            <li><code>/api/hospitals/top3</code> - 병원 Top3 조회</li>
        </ul>
        <hr>
        <p>🔗 <b>ngrok 사용법:</b></p>
        <ol>
            <li>새 터미널 열기</li>
            <li><code>ngrok http 5001</code> 실행</li>
            <li>ngrok URL을 Streamlit 앱에 입력</li>
        </ol>
    </body>
    </html>
    """

@app.route('/twilio/gather', methods=['POST'])
def twilio_gather_callback():
    """Twilio Gather 콜백 - 다이얼 입력 받기"""
    digits = request.form.get('Digits', '')
    call_sid = request.form.get('CallSid', '')
    
    print(f"\n📞 [Twilio Callback] Call SID: {call_sid}")
    print(f"🔢 입력된 다이얼: {digits}")
    
    # 입력값 저장
    call_responses[call_sid] = {
        "digit": digits,
        "timestamp": time.time()
    }
    
    # 응답 TwiML 생성
    response = VoiceResponse()
    
    if digits == "1":
        response.say("입실 승인 확인되었습니다. 감사합니다.", language="ko-KR", voice="Polly.Seoyeon")
        print("✅ 1번 입력 - 입실 승인")
    elif digits == "2":
        response.say("입실 불가 확인되었습니다. 다른 병원을 찾겠습니다.", language="ko-KR", voice="Polly.Seoyeon")
        print("❌ 2번 입력 - 입실 거절")
    else:
        response.say("잘못된 입력입니다.", language="ko-KR", voice="Polly.Seoyeon")
        print(f"⚠️ 잘못된 입력: {digits}")
    
    return str(response), 200, {'Content-Type': 'text/xml'}

@app.route('/twilio/status', methods=['POST'])
def twilio_status_callback():
    """통화 상태 콜백"""
    call_sid = request.form.get('CallSid', '')
    call_status = request.form.get('CallStatus', '')
    
    print(f"\n📡 [통화 상태] Call SID: {call_sid}, Status: {call_status}")
    
    return "", 200

@app.route('/responses', methods=['GET'])
def get_responses():
    """저장된 응답 확인 (디버깅용)"""
    if not call_responses:
        return "<h2>저장된 응답이 없습니다.</h2>"
    
    html = "<html><head><title>저장된 응답</title></head><body style='font-family: Arial; padding: 2rem;'>"
    html += "<h1>📋 저장된 다이얼 응답</h1><hr>"
    
    for call_sid, data in call_responses.items():
        digit = data.get('digit')
        timestamp = data.get('timestamp')
        time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
        
        status = "✅ 승인" if digit == "1" else "❌ 거절" if digit == "2" else "⚠️ 기타"
        
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
    """저장된 응답을 JSON으로 반환 (Streamlit 앱용)"""
    return call_responses, 200

@app.route('/api/response/<call_sid>', methods=['GET'])
def get_response_by_sid(call_sid):
    """특정 Call SID의 응답 확인"""
    if call_sid in call_responses:
        return call_responses[call_sid], 200
    else:
        return {"error": "Not found"}, 404

@app.route('/clear', methods=['GET', 'POST'])
def clear_responses():
    """저장된 응답 초기화"""
    call_responses.clear()
    return "<h2>✅ 모든 응답이 초기화되었습니다.</h2><br><a href='/'>홈으로</a>"

if __name__ == '__main__':
    PORT = FLASK_PORT  # config.py에서 가져옴
    
    print("=" * 60)
    print("🚀 Twilio Flask Server 시작")
    print("=" * 60)
    print(f"📍 URL: http://localhost:{PORT}")
    print(f"📍 Gather Callback: http://localhost:{PORT}/twilio/gather")
    print(f"📍 Status Callback: http://localhost:{PORT}/twilio/status")
    print("=" * 60)
    print("\n🔗 다음 단계:")
    print(f"1. 새 터미널을 열어서 'ngrok http {PORT}' 실행")
    print("2. ngrok URL (예: https://xxxx.ngrok.io)을 복사")
    print("3. Streamlit 앱의 'Twilio 다이얼 입력 설정'에 URL 입력\n")
    print("=" * 60)
    print("서버 실행 중... (Ctrl+C로 종료)\n")
    
    # Flask 서버 실행
    app.run(
        host='0.0.0.0',
        port=PORT,
        debug=False,
        use_reloader=False
    )

