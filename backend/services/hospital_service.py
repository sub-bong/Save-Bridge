#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""병원 관련 비즈니스 로직 서비스"""

from typing import Optional, Tuple, Dict, Any, List, Iterable
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from xml.etree import ElementTree as ET

from config import (
    DATA_GO_KR_KEY, ER_BED_URL, EGET_BASE_URL, EGET_LIST_URL, STRM_LIST_URL,
    METRO_FALLBACK_PROVINCE, PROVINCE_INCLUDE_METROS, SYMPTOM_RULES
)
from models import db, Hospital
from utils.http import http_get, safe_int
from utils.geo import calculate_distance, guess_region_from_address


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
        if safe_int(hospital_data.get(key)) >= thr:
            min_satisfied += 1

    parts = []
    if bool_total:
        parts.append(bool_satisfied / bool_total)
    if min_total:
        parts.append(min_satisfied / min_total)
    score = sum(parts) / len(parts) if parts else 0
    fully_met = (bool_total == bool_satisfied if bool_total else True) and (min_total == min_satisfied if min_total else True)
    return score, fully_met


def _fetch_grade_info_for_region(region: str, hpids_to_find: set, url: str, service_key: str) -> Dict[str, Dict[str, Any]]:
    """특정 지역의 등급 정보 조회 (내부 헬퍼 함수) - 스레드 안전"""
    grade_info = {}
    try:
        r = http_get(url, {"STAGE1": region, "pageNo": 1, "numOfRows": 500, "serviceKey": service_key})
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
    
    # 1. getEgytListInfoInqire로 일반 응급의료기관 등급 정보 조회 (병렬 처리, API 제한 고려)
    remaining_hpids = hpid_set.copy()
    if remaining_hpids:
        with ThreadPoolExecutor(max_workers=5) as executor:
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
    
    # 2. getStrmListInfoInqire로 권역외상센터 정보 조회 (권역외상센터는 우선 적용, 병렬 처리, API 제한 고려)
    remaining_hpids = hpid_set - set(grade_info.keys())
    if remaining_hpids:
        with ThreadPoolExecutor(max_workers=5) as executor:
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
    """병원 기본정보 조회 (DB 캐싱 우선, 없으면 API 호출)"""
    # DB에서 먼저 확인 (API 호출 제한 방지)
    try:
        from flask import has_app_context, current_app
        # Flask app context가 있는 경우에만 DB 조회
        if has_app_context():
            hospital = Hospital.query.filter_by(hospital_id=hpid).first()
            if hospital and hospital.latitude and hospital.longitude:
                # DB에 좌표 정보가 있으면 DB 데이터 사용 (API 호출 건너뜀)
                return {
                    "hpid": hospital.hospital_id,
                    "dutyName": hospital.name,
                    "dutyAddr": hospital.address,
                    "dutytel3": hospital.phone_number,
                    "wgs84Lat": float(hospital.latitude),
                    "wgs84Lon": float(hospital.longitude),
                    "dutyDiv": None,
                    "dutyDivNam": None,
                    "dutyEmcls": None,
                    "dutyEmclsName": hospital.hospital_grade,
                }
    except Exception as db_error:
        # DB 조회 실패 시 API 호출로 진행
        pass
    
    # DB에 없거나 좌표 정보가 없으면 API 호출
    try:
        r = http_get(EGET_BASE_URL, {"HPID": hpid, "pageNo": 1, "numOfRows": 1, "serviceKey": service_key})
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
        # 429 에러 등 API 제한 에러는 조용히 처리
        if "429" in str(e) or "too many" in str(e).lower():
            print(f"⚠️  병원 기본정보 조회 제한 ({hpid}): API 호출 제한 도달")
        else:
            print(f"병원 기본정보 조회 오류 ({hpid}): {e}")
        return None


def save_or_update_hospital(hospital_data: Dict[str, Any]) -> Optional[Hospital]:
    """
    병원 정보를 DB에 저장하거나 업데이트
    API에서 가져온 병원 정보를 DB에 저장하여 웹소켓 연동에 사용
    
    Args:
        hospital_data: API에서 가져온 병원 정보 딕셔너리
        
    Returns:
        Hospital 객체 또는 None
    """
    if not hospital_data or not hospital_data.get("hpid"):
        return None
    
    hpid = hospital_data["hpid"]
    
    # 기존 병원 조회
    hospital = Hospital.query.filter_by(hospital_id=hpid).first()
    
    # 필수 필드 확인
    if not hospital_data.get("wgs84Lat") or not hospital_data.get("wgs84Lon"):
        print(f"⚠️  병원 {hpid}의 좌표 정보가 없어 저장하지 않습니다.")
        return None
    
    if hospital:
        # 업데이트
        hospital.name = hospital_data.get("dutyName") or hospital.name
        hospital.address = hospital_data.get("dutyAddr") or hospital.address
        hospital.latitude = hospital_data.get("wgs84Lat")
        hospital.longitude = hospital_data.get("wgs84Lon")
        hospital.hospital_grade = hospital_data.get("dutyEmclsName") or hospital_data.get("dutyDivNam") or hospital.hospital_grade
        hospital.phone_number = hospital_data.get("dutytel3") or hospital.phone_number
    else:
        # 새로 생성
        hospital = Hospital(
            hospital_id=hpid,
            name=hospital_data.get("dutyName", ""),
            address=hospital_data.get("dutyAddr", ""),
            latitude=hospital_data.get("wgs84Lat"),
            longitude=hospital_data.get("wgs84Lon"),
            hospital_grade=hospital_data.get("dutyEmclsName") or hospital_data.get("dutyDivNam"),
            phone_number=hospital_data.get("dutytel3")
        )
        db.session.add(hospital)
    
    try:
        db.session.commit()
        return hospital
    except Exception as e:
        db.session.rollback()
        print(f"병원 정보 저장 오류 ({hpid}): {e}")
        return None


def fetch_emergency_hospitals_in_region(sido: str, sigungu: Optional[str], service_key: str, max_items: int = 120) -> List[Dict[str, Any]]:
    """지역 내 응급 병원 조회 (DB 캐싱 우선, 최대 120개로 제한)"""
    try:
        params = {"STAGE1": sido, "pageNo": 1, "numOfRows": min(500, max_items * 2), "serviceKey": service_key}
        if sigungu:
            params["STAGE2"] = sigungu
        r = http_get(ER_BED_URL, params)
        root = ET.fromstring(r.content)
        hpids = []
        for it in root.findall(".//item"):
            el = it.find("hpid")
            if el is not None and el.text:
                hpids.append(el.text.strip())
        hpids = list(dict.fromkeys(hpids))[:max_items]  # 최대 개수 제한
        
        if not hpids:
            return []
        
        hospitals = []
        missing_hpids = []
        
        # DB에서 일괄 조회 (API 호출 최소화)
        try:
            from flask import has_app_context
            if has_app_context():
                db_hospitals = Hospital.query.filter(Hospital.hospital_id.in_(hpids)).filter(
                    Hospital.latitude.isnot(None),
                    Hospital.longitude.isnot(None)
                ).all()
                
                # DB에 있는 병원들을 딕셔너리로 변환
                db_hospital_dict = {h.hospital_id: h for h in db_hospitals}
                
                # DB에 있는 병원들은 DB 데이터 사용
                for hpid in hpids:
                    if hpid in db_hospital_dict:
                        hospital = db_hospital_dict[hpid]
                        hospitals.append({
                            "hpid": hospital.hospital_id,
                            "dutyName": hospital.name,
                            "dutyAddr": hospital.address,
                            "dutytel3": hospital.phone_number,
                            "wgs84Lat": float(hospital.latitude),
                            "wgs84Lon": float(hospital.longitude),
                            "dutyDiv": None,
                            "dutyDivNam": None,
                            "dutyEmcls": None,
                            "dutyEmclsName": hospital.hospital_grade,
                        })
                    else:
                        missing_hpids.append(hpid)
            else:
                # app context가 없으면 모든 병원을 API로 조회
                missing_hpids = hpids
        except Exception as db_error:
            # DB 조회 실패 시 모든 병원을 API로 조회
            missing_hpids = hpids
        
        # DB에 없는 병원들만 API 호출 (병렬 처리, 최대 5개 동시 실행 - API 제한 고려)
        if missing_hpids:
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_hpid = {executor.submit(fetch_baseinfo_by_hpid, hpid, service_key): hpid for hpid in missing_hpids}
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
        resp = http_get(ER_BED_URL, params=params)
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


def is_metropolitan(sido: str) -> bool:
    """광역시/특별시 여부 확인"""
    return sido.endswith("광역시") or sido.endswith("특별시") or sido.endswith("특별자치시")


def fetch_trauma_centers_in_region(sido: str, sigungu: Optional[str], service_key: str, max_items: int = 80) -> List[Dict[str, Any]]:
    """지역 내 외상센터 조회 (getStrmListInfoInqire) - 병렬 처리로 최적화, 최대 80개로 제한"""
    try:
        params = {"STAGE1": sido, "pageNo": 1, "numOfRows": min(500, max_items * 2), "serviceKey": service_key}
        if sigungu:
            params["STAGE2"] = sigungu
        r = http_get(STRM_LIST_URL, params)
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
        
        if not items_with_grade:
            return []
        
        hospitals = []
        missing_items = []
        
        # DB에서 일괄 조회 (API 호출 최소화)
        try:
            from flask import has_app_context
            if has_app_context():
                hpids = [item["hpid"] for item in items_with_grade]
                db_hospitals = Hospital.query.filter(Hospital.hospital_id.in_(hpids)).filter(
                    Hospital.latitude.isnot(None),
                    Hospital.longitude.isnot(None)
                ).all()
                
                # DB에 있는 병원들을 딕셔너리로 변환
                db_hospital_dict = {h.hospital_id: h for h in db_hospitals}
                
                # DB에 있는 병원들은 DB 데이터 사용
                for item in items_with_grade:
                    hpid = item["hpid"]
                    if hpid in db_hospital_dict:
                        hospital = db_hospital_dict[hpid]
                        hospital_info = {
                            "hpid": hospital.hospital_id,
                            "dutyName": hospital.name,
                            "dutyAddr": hospital.address,
                            "dutytel3": hospital.phone_number,
                            "wgs84Lat": float(hospital.latitude),
                            "wgs84Lon": float(hospital.longitude),
                            "dutyDiv": None,
                            "dutyDivNam": None,
                            "dutyEmcls": item.get("dutyEmcls"),
                            "dutyEmclsName": item.get("dutyEmclsName") or hospital.hospital_grade,
                        }
                        hospitals.append(hospital_info)
                    else:
                        missing_items.append(item)
            else:
                # app context가 없으면 모든 병원을 API로 조회
                missing_items = items_with_grade
        except Exception as db_error:
            # DB 조회 실패 시 모든 병원을 API로 조회
            missing_items = items_with_grade
        
        # DB에 없는 병원들만 API 호출 (병렬 처리, 최대 5개 동시 실행 - API 제한 고려)
        if missing_items:
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_item = {executor.submit(fetch_baseinfo_by_hpid, item["hpid"], service_key): item for item in missing_items}
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
    MAX_HOSPITALS_PER_REGION = 150
    
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
    """행정구역별로 병원 정렬"""
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

