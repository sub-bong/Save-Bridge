import React, { useEffect, useRef, useState } from "react";
import type { Coords, Hospital } from "../types";
declare global {
  interface Window {
    kakao: any;
  }
}

interface Props {
  coords: Coords; // 실시간 구급차 좌표 (watchPosition)
  hospitals: Hospital[]; // 보통 approved 1개
  routePath?: number[][]; // backend route_paths[hpid] (lon, lat 순서!)
  tickMs?: number; // 애니메이션 주기
}
const env = import.meta.env || {};
const KAKAO_KEY = env.VITE_KAKAO_JS_KEY || env.VITE_KAKAO_REST_API_KEY || "";
const sdkUrl = KAKAO_KEY 
  ? `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${KAKAO_KEY}&autoload=false`
  : "";

export const KakaoAmbulanceMap: React.FC<Props> = ({ coords, hospitals, routePath = [], tickMs = 800 }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const ambRef = useRef<any>(null);
  const polyRef = useRef<any>(null);
  const hospitalMarkersRef = useRef<Map<string, any>>(new Map());
  const [ready, setReady] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const idxRef = useRef(0);

  // SDK 로드
  useEffect(() => {
    // API 키가 없으면 지도 사용 불가
    if (!KAKAO_KEY) {
      console.error("❌ Kakao 지도 API 키가 설정되지 않았습니다. .env 파일에 VITE_KAKAO_JS_KEY 또는 VITE_KAKAO_REST_API_KEY를 설정해주세요.");
      return;
    }
    
    if (window.kakao?.maps) {
      setReady(true);
      return;
    }
    
    // 이미 스크립트가 로드 중이면 중복 로드 방지
    const existingScript = document.querySelector(`script[src*="dapi.kakao.com/v2/maps/sdk.js"]`);
    if (existingScript) {
      // 스크립트가 이미 있으면 로드 완료를 기다림
      const checkKakao = setInterval(() => {
        if (window.kakao?.maps) {
          window.kakao.maps.load(() => setReady(true));
          clearInterval(checkKakao);
        }
      }, 100);
      return () => clearInterval(checkKakao);
    }
    
    if (!sdkUrl) {
      console.error("❌ Kakao 지도 SDK URL을 생성할 수 없습니다.");
      return;
    }
    
    const script = document.createElement("script");
    script.src = sdkUrl;
    script.async = true;
    script.onload = () => {
      if (window.kakao?.maps) {
        window.kakao.maps.load(() => {
          console.log("✅ Kakao 지도 SDK 로드 완료");
          setReady(true);
        });
      }
    };
    script.onerror = (error) => {
      console.error("❌ Kakao 지도 스크립트를 불러오지 못했습니다:", error);
      console.error("   - API 키가 올바른지 확인하세요: VITE_KAKAO_JS_KEY 또는 VITE_KAKAO_REST_API_KEY");
      console.error("   - 네트워크 연결을 확인하세요");
    };
    document.head.appendChild(script);
    return () => {
      script.onload = null;
      script.onerror = null;
    };
  }, []);

  // 지도/마커 초기화
  useEffect(() => {
    if (!ready || !containerRef.current) return;
    
    // coords가 없으면 기본 좌표 사용 (서울시청)
    const defaultLat = 37.5665;
    const defaultLon = 126.9780;
    const lat = coords?.lat || defaultLat;
    const lon = coords?.lon || defaultLon;
    
    if (!lat || !lon) {
      console.warn("KakaoAmbulanceMap: 좌표가 없어 기본 좌표를 사용합니다.");
      return;
    }
    
    const { kakao } = window;
    const center = new kakao.maps.LatLng(lat, lon);
    if (!mapRef.current) {
      mapRef.current = new kakao.maps.Map(containerRef.current, { center, level: 5 });
      // 구급차 마커 이미지 추가 필요
      const ambImg = new kakao.maps.MarkerImage("https://t1.daumcdn.net/localimg/localimages/07/mapapidoc/marker_red.png", new kakao.maps.Size(32, 34));
      ambRef.current = new kakao.maps.Marker({ position: center, image: ambImg });
      ambRef.current.setMap(mapRef.current);
    } else {
      mapRef.current.setCenter(center);
      ambRef.current?.setPosition(center);
    }
  }, [ready, coords?.lat, coords?.lon]);

  // 병원 마커 & polyline
  useEffect(() => {
    if (!ready || !mapRef.current) return;
    const { kakao } = window;
    
    // 기존 병원 마커 제거
    hospitalMarkersRef.current.forEach((marker) => {
      marker.setMap(null);
    });
    hospitalMarkersRef.current.clear();
    
    // 기존 polyline 제거
    if (polyRef.current) {
      polyRef.current.setMap(null);
      polyRef.current = null;
    }
    
    // 새로운 병원 마커 추가
    hospitals.forEach((h) => {
      if (!h.wgs84Lat || !h.wgs84Lon || !h.hpid) return;
      const marker = new kakao.maps.Marker({ 
        position: new kakao.maps.LatLng(h.wgs84Lat, h.wgs84Lon) 
      });
      marker.setMap(mapRef.current);
      hospitalMarkersRef.current.set(h.hpid, marker);
      
      const iw = new kakao.maps.InfoWindow({ 
        content: `<div style="padding:6px 8px;">${h.dutyName || "병원"}</div>` 
      });
      kakao.maps.event.addListener(marker, "click", () => {
        iw.open(mapRef.current, marker);
      });
    });
    
    // 경로 표시
    if (routePath && routePath.length > 1) {
      const latLngs = routePath.map(([lon, lat]) => new kakao.maps.LatLng(lat, lon)); // 순서 주의
      polyRef.current = new kakao.maps.Polyline({
        path: latLngs,
        strokeWeight: 5,
        strokeColor: "#2563eb",
        strokeOpacity: 0.85,
      });
      polyRef.current.setMap(mapRef.current);
      try {
        const bounds = new kakao.maps.LatLngBounds();
        latLngs.forEach((latLng) => bounds.extend(latLng));
        mapRef.current.setBounds(bounds);
      } catch (e) {
        console.warn("지도 bounds 설정 실패:", e);
      }
    }
  }, [ready, hospitals, routePath]);

  // 구급차 기준 실시간성 갱신
  useEffect(() => {
    if (!ready || !mapRef.current || !ambRef.current) return;
    if (!coords?.lat || !coords?.lon) return;
    const { kakao } = window;
    const pos = new kakao.maps.LatLng(coords.lat, coords.lon);
    ambRef.current.setPosition(pos);
    // 필요하면 아래 줄로 센터도 GPS에 맞춰 이동
    mapRef.current.setCenter(pos);
  }, [ready, coords?.lat, coords?.lon]);

  // API 키가 없으면 안내 메시지 표시
  if (!KAKAO_KEY) {
    return (
      <div className="w-full h-[360px] rounded-xl border border-slate-200 shadow-sm flex items-center justify-center bg-slate-50">
        <div className="text-center text-sm text-slate-600">
          <p className="font-semibold mb-1">지도를 불러올 수 없습니다</p>
          <p className="text-xs">Kakao 지도 API 키가 설정되지 않았습니다.</p>
          <p className="text-xs mt-1">.env 파일에 VITE_KAKAO_JS_KEY를 설정해주세요.</p>
        </div>
      </div>
    );
  }
  
  return <div ref={containerRef} className="w-full h-[360px] rounded-xl border border-slate-200 shadow-sm" />;
};
