import React, { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Coords, Hospital } from "../types";

interface MapDisplayProps {
  coords: Coords;
  hospitals: Hospital[];
  routePaths: Record<string, number[][]>;
  approvedHospital: Hospital | null;
  resolveHospitalColor: (hospital: Hospital, index: number) => string;
  compact?: boolean;
  compactHeightClass?: string;
}

export const MapDisplay: React.FC<MapDisplayProps> = ({
  coords,
  hospitals,
  routePaths,
  approvedHospital,
  resolveHospitalColor,
  compact = false,
  compactHeightClass,
}) => {
  const mapRef = useRef<L.Map | null>(null);
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const markersRef = useRef<L.Marker[]>([]);
  const polylinesRef = useRef<L.Polyline[]>([]);
  const hospitalMarkersRef = useRef<Map<string, L.Marker>>(new Map()); // hpid -> Marker 매핑

  useEffect(() => {
    if (!mapContainerRef.current || !coords.lat || !coords.lon) return;

    // 지도 초기화
    if (!mapRef.current) {
      mapRef.current = L.map(mapContainerRef.current).setView([coords.lat!, coords.lon!], 13);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(mapRef.current);
    }

    const map = mapRef.current;

    // 기존 마커와 경로 제거
    markersRef.current.forEach((marker) => marker.remove());
    polylinesRef.current.forEach((polyline) => polyline.remove());
    markersRef.current = [];
    polylinesRef.current = [];
    hospitalMarkersRef.current.clear();

    // 구급대원 위치 마커 (사람 아이콘)
    const personIcon = L.divIcon({
      className: "custom-person-icon",
      html: '<div style="width: 30px; height: 30px; background-color: #1e293b; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-size: 18px; font-weight: bold; border: 3px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);">P</div>',
      iconSize: [30, 30],
      iconAnchor: [15, 15],
    });

    const userMarker = L.marker([coords.lat!, coords.lon!], { icon: personIcon }).addTo(map);
    markersRef.current.push(userMarker);

    // 병원 마커 및 경로 추가
    const bounds = L.latLngBounds([[coords.lat!, coords.lon!]]);

    hospitals.forEach((hospital, idx) => {
      if (!hospital.wgs84Lat || !hospital.wgs84Lon) return;

      const color = resolveHospitalColor(hospital, idx);
      const hospitalIcon = L.divIcon({
        className: "custom-hospital-icon",
        html: `<div style="width: 20px; height: 20px; background-color: ${color}; border-radius: 50%; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>`,
        iconSize: [20, 20],
        iconAnchor: [10, 10],
      });

      const hospitalMarker = L.marker([hospital.wgs84Lat, hospital.wgs84Lon], { icon: hospitalIcon }).addTo(map);
      hospitalMarker.bindPopup(`<b>${hospital.dutyName || "병원"}</b><br/>${hospital.dutyAddr || ""}`);
      markersRef.current.push(hospitalMarker);
      
      // hpid로 마커 매핑 저장 (범례 클릭 시 사용)
      const hpid = hospital.hpid || `${hospital.dutyName}-${idx}`;
      hospitalMarkersRef.current.set(hpid, hospitalMarker);
      
      bounds.extend([hospital.wgs84Lat, hospital.wgs84Lon]);

      // 경로 표시
      const routeHpid = hospital.hpid || "";
      if (routePaths[routeHpid] && routePaths[routeHpid].length > 0) {
        const path = routePaths[routeHpid].map(([lat, lon]) => [lat, lon] as [number, number]);
        const polyline = L.polyline(path, {
          color: color,
          weight: 4,
          opacity: 0.7,
        }).addTo(map);
        polylinesRef.current.push(polyline);
      }
    });

    // 지도 범위 조정
    map.fitBounds(bounds, { padding: [50, 50] });

    return () => {
      // cleanup은 하지 않음 (지도는 유지)
    };
  }, [coords, hospitals, routePaths, approvedHospital, resolveHospitalColor]);

  if (!coords.lat || !coords.lon || hospitals.length === 0) {
    return null;
  }

  if (compact) {
    return (
      <div className="w-full h-full">
        <div
          ref={mapContainerRef}
          className={`w-full ${compactHeightClass || "h-[260px]"} rounded-lg overflow-hidden border border-gray-200`}
          style={{ zIndex: 0 }}
        />
      </div>
    );
  }

  return (
    <section className="bg-white rounded-lg shadow-md p-6 border border-gray-200">
      <h2 className="text-lg font-bold mb-4 text-gray-900 border-b-2 border-gray-300 pb-2">
        지도
        <span className="ml-3 text-sm font-normal text-gray-600">(OpenStreetMap)</span>
      </h2>
      <div
        ref={mapContainerRef}
        className="w-full h-[600px] rounded-lg overflow-hidden border-2 border-gray-300"
        style={{ zIndex: 0 }}
      />

      <div className="mt-4 flex flex-wrap gap-4 text-sm text-gray-700">
        <span className="flex items-center gap-2">
          <span className="inline-block w-5 h-5 rounded-full bg-blue-700 text-white text-xs font-bold flex items-center justify-center shadow">
            P
          </span>
          <span>구급대원 현위치</span>
        </span>
        {hospitals.map((hospital, idx) => {
          const color = resolveHospitalColor(hospital, idx);
          const hpid = hospital.hpid || `${hospital.dutyName}-${idx}`;
          
          const handleLegendClick = () => {
            if (!mapRef.current || !hospital.wgs84Lat || !hospital.wgs84Lon) return;
            
            const map = mapRef.current;
            const marker = hospitalMarkersRef.current.get(hpid);
            
            // 지도 중심 이동 및 확대 (zoom level 15)
            map.setView([hospital.wgs84Lat, hospital.wgs84Lon], 15, {
              animate: true,
              duration: 0.5,
            });
            
            // 마커 팝업 자동 표시
            if (marker) {
              setTimeout(() => {
                marker.openPopup();
              }, 300); // 애니메이션 완료 후 팝업 표시
            }
          };
          
          return (
            <span
              key={hpid}
              className="flex items-center gap-2 cursor-pointer hover:bg-gray-100 px-2 py-1 rounded transition"
              onClick={handleLegendClick}
              title="클릭하여 해당 병원으로 지도 이동"
            >
              <span
                className="inline-block w-4 h-4 rounded-full border border-white shadow"
                style={{ backgroundColor: color }}
              />
              <span className="flex flex-col">
                <span className="font-semibold text-gray-900">{hospital.dutyName || `병원 ${idx + 1}`}</span>
                <span className="text-xs text-gray-500">
                  {approvedHospital ? "환자 수용 확정 경로" : "환자 수용 거절 이력"}
                </span>
              </span>
            </span>
          );
        })}
      </div>
    </section>
  );
};

