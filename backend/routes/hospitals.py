#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""병원 조회 관련 라우트"""

from flask import request, jsonify
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import (
    KAKAO_KEY, DATA_GO_KR_KEY, SYMPTOM_RULES, METRO_FALLBACK_PROVINCE,
    PROVINCE_INCLUDE_METROS
)
from services.hospital_service import (
    fetch_scope_hospitals, fetch_beds_for_sidos, fetch_hospital_grade_info,
    evaluate_requirements, prioritize_by_region, save_or_update_hospital,
    serialize_hospital_payload, is_metropolitan
)
from utils.geo import calculate_distance, get_driving_info_kakao, guess_region_from_address
from utils.http import safe_int


def register_hospitals_routes(app):
    """병원 조회 라우트 등록"""
    
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
            if symptom == "다발성 외상/중증 외상":
                hospital_type = "trauma"
            elif symptom == "소아 중증(신생아/영아)":
                hospital_type = "pediatric"
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
            
            # 모든 병원의 hpid 수집하여 등급 정보 일괄 조회
            all_hpids = [h.get("hpid") for h in all_hospitals_raw if h.get("hpid")]
            target_regions = list(set([sido] + extra_sidos + ([METRO_FALLBACK_PROVINCE.get(sido)] if is_metropolitan(sido) and METRO_FALLBACK_PROVINCE.get(sido) else [])))
            grade_info_dict = fetch_hospital_grade_info(all_hpids, DATA_GO_KR_KEY, target_regions)

            def enrich_records(
                hospitals_raw, bed_source, is_local_region=None
            ):
                enriched = []
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
                    # 등급 정보 병합
                    if hpid in grade_info_dict:
                        grade_info = grade_info_dict[hpid]
                        if grade_info.get("dutyEmcls"):
                            merged["dutyEmcls"] = grade_info["dutyEmcls"]
                        if grade_info.get("dutyEmclsName"):
                            merged["dutyEmclsName"] = grade_info["dutyEmclsName"]
                    guess = guess_region_from_address(merged.get("dutyAddr"))
                    region_name = guess[1] if guess and len(guess) > 1 else (guess[0] if guess else None)
                    merged["region_name"] = region_name or sigungu or merged.get("region_name")
                    
                    # 거리 계산
                    if merged.get("wgs84Lat") and merged.get("wgs84Lon"):
                        merged["distance_km"] = calculate_distance(lat, lon, merged["wgs84Lat"], merged["wgs84Lon"])
                        if merged["distance_km"] > 150.0:
                            continue
                    else:
                        merged["distance_km"] = float('inf')
                        continue
                    
                    # 지역 내 병원 판단
                    if is_local_region is None:
                        is_local = (not sigungu) or (merged["region_name"] == sigungu)
                        merged["_is_local_region"] = is_local
                    else:
                        merged["_is_local_region"] = is_local_region
                    
                    score, fully_met = evaluate_requirements(merged, rule)
                    merged["_requirement_score"] = score
                    merged["_meets_conditions"] = fully_met
                    
                    # 소아 중증 환자의 경우: 소아중환자실(hvncc) 보유 병원에 가산점
                    if hospital_type == "pediatric" and symptom == "소아 중증(신생아/영아)":
                        hvncc = safe_int(merged.get("hvncc", 0))
                        if hvncc >= 1:
                            merged["_requirement_score"] = score + 10.0
                    enriched.append(merged)
                return enriched

            merged_hospitals = enrich_records(all_hospitals_raw, beds_dict)
            local_hospitals = [h for h in merged_hospitals if h.get("_is_local_region")]
            if not local_hospitals:
                local_hospitals = merged_hospitals.copy()
            neighbor_same_scope = [h for h in merged_hospitals if not h.get("_is_local_region")]

            def get_priority_score(hospital):
                """등급 우선순위 점수"""
                duty_emcls_name = str(hospital.get("dutyEmclsName", ""))
                duty_div_name = str(hospital.get("dutyDivNam", ""))
                
                if "권역외상센터" in duty_emcls_name:
                    return 4.0
                if "권역응급의료센터" in duty_emcls_name or "권역응급의료센터" in duty_div_name:
                    return 3.5
                if "3차" in duty_div_name or "상급종합" in duty_div_name:
                    return 2.0
                if "2차" in duty_div_name:
                    return 1.0
                return 0.0
            
            def sort_records(records):
                """병원 정렬: 요구사항 점수 > 등급 우선순위 > 거리"""
                return sorted(
                    records,
                    key=lambda x: (
                        -x.get("_requirement_score", 0.0),
                        -get_priority_score(x),
                        x.get("distance_km", float('inf'))
                    )
                )

            # 지역 내 병원도 거리 제한 적용: 100km 이내만
            local_hospitals_filtered = [h for h in local_hospitals if h.get("distance_km", float('inf')) <= 100.0]
            primary_sorted = sort_records(local_hospitals_filtered if local_hospitals_filtered else local_hospitals)
            secondary_sorted = sort_records(neighbor_same_scope)
            
            nearby_secondary = [h for h in secondary_sorted if h.get("distance_km", float('inf')) <= 100.0]
            far_secondary = [h for h in secondary_sorted if h.get("distance_km", float('inf')) > 100.0]
            
            nearby_prioritized = prioritize_by_region(nearby_secondary, max_regions=3)
            
            combined_candidates = primary_sorted + nearby_prioritized
            
            if len(combined_candidates) < 3:
                far_filtered = [h for h in far_secondary if h.get("distance_km", float('inf')) <= 100.0]
                combined_candidates.extend(sort_records(far_filtered)[:10])
            
            if not combined_candidates:
                combined_candidates = [h for h in sort_records(merged_hospitals) if h.get("distance_km", float('inf')) <= 100.0]

            combined_candidates = sort_records(combined_candidates)
            combined_candidates = [h for h in combined_candidates if h.get("distance_km", float('inf')) <= 100.0]
            
            # top3는 거리 제한 적용: 50km 이내 우선, 부족하면 최대 100km까지 확장
            top3_filtered_50km = [h for h in combined_candidates if h.get("distance_km", float('inf')) <= 50.0]
            if len(top3_filtered_50km) >= 3:
                top3 = top3_filtered_50km[:3]
            else:
                mid_range = [h for h in combined_candidates if 50.0 < h.get("distance_km", float('inf')) <= 100.0]
                top3 = top3_filtered_50km + sort_records(mid_range)[:3 - len(top3_filtered_50km)]
                if len(top3) < 3:
                    remaining = [h for h in combined_candidates if h.get("distance_km", float('inf')) <= 100.0 and h not in top3]
                    top3.extend(sort_records(remaining)[:3 - len(top3)])
            
            top3 = [h for h in top3 if h.get("distance_km", float('inf')) <= 100.0]
            
            backup_candidates = [h for h in combined_candidates[3:13] if h.get("distance_km", float('inf')) <= 100.0]

            nearby_neighbor = prioritize_by_region(nearby_secondary, max_regions=5)[:10]
            neighbor_candidates = nearby_neighbor

            fallback_sido = METRO_FALLBACK_PROVINCE.get(sido) if is_metropolitan(sido) else None
            fallback_hospitals = []
            if fallback_sido:
                fallback_extra = PROVINCE_INCLUDE_METROS.get(fallback_sido, [])
                fallback_raw = fetch_scope_hospitals(fallback_sido, fallback_extra, hospital_type)
                fallback_beds = fetch_beds_for_sidos([fallback_sido] + fallback_extra)
                fallback_profiles = enrich_records(fallback_raw, fallback_beds, is_local_region=False)
                fallback_hospitals.extend(prioritize_by_region(fallback_profiles, max_regions=3))

            used_hpids = {h.get("hpid") for h in top3}
            neighbor_augmented = []
            seen_ids = set()
            
            all_neighbor_sources = neighbor_candidates + fallback_hospitals
            all_neighbor_sorted = sort_records(all_neighbor_sources)
            
            for hospital in all_neighbor_sorted:
                hpid = hospital.get("hpid")
                if not hpid or hpid in used_hpids or hpid in seen_ids:
                    continue
                if hospital.get("distance_km", float('inf')) <= 100.0:
                    neighbor_augmented.append(hospital)
                    seen_ids.add(hpid)
                    if len(neighbor_augmented) >= 9:
                        break

            neighbor_candidates = neighbor_augmented

            if len(top3) < 3 and neighbor_candidates:
                needed = 3 - len(top3)
                nearby_neighbors = [h for h in neighbor_candidates if h.get("distance_km", float('inf')) <= 100.0]
                top3.extend(nearby_neighbors[:needed])
                neighbor_candidates = neighbor_candidates[needed:]

            # 경로 정보 조회 (카카오 API) - 병렬 처리로 최적화
            route_paths = {}
            top3_valid = []
            top3_to_backup = []
            
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
                                if isinstance(hospital.get("distance_km"), (int, float)):
                                    dist = hospital["distance_km"]
                                    hospital["eta_minutes"] = int((dist * 1.3 / 40) * 60)
                        except Exception as e:
                            print(f"경로 정보 조회 오류 ({hospital.get('hpid', 'unknown')}): {e}")
                            if isinstance(hospital.get("distance_km"), (int, float)):
                                dist = hospital["distance_km"]
                                hospital["eta_minutes"] = int((dist * 1.3 / 40) * 60)
            
            for hospital in top3:
                if hospital.get("distance_km", float('inf')) <= 100.0:
                    top3_valid.append(hospital)
                else:
                    top3_to_backup.append(hospital)
            
            backup_candidates.extend(top3_to_backup)
            top3 = top3_valid
            
            if len(top3) < 3:
                backup_sorted = sort_records([h for h in backup_candidates if h.get("distance_km", float('inf')) <= 100.0])
                needed = 3 - len(top3)
                top3.extend(backup_sorted[:needed])
                backup_candidates = backup_sorted[needed:]
            
            # 병원 정보를 DB에 저장
            with app.app_context():
                for hospital in top3 + backup_candidates + neighbor_candidates:
                    hpid = hospital.get("hpid")
                    if hpid:
                        save_or_update_hospital(hospital)
            
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

