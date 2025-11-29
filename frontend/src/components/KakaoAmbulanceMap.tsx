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
const env = (import.meta as any).env || {};
const KAKAO_KEY = env.VITE_KAKAO_JS_KEY || env.VITE_KAKAO_REST_API_KEY || "";
const sdkUrl = `//dapi.kakao.com/v2/maps/sdk.js?appkey=${KAKAO_KEY}&autoload=false`;
// 디버그용: 키 로드 여부를 콘솔에 표시 -> 해결 프론트에 env 넣기 완료
console.log("[KakaoMap] VITE_KAKAO_JS_KEY:", env.VITE_KAKAO_JS_KEY ? "set" : "unset");
console.log("[KakaoMap] VITE_KAKAO_REST_API_KEY:", env.VITE_KAKAO_REST_API_KEY ? "set" : "unset");

console.log("env", import.meta.env.VITE_KAKAO_JS_KEY);

export const KakaoAmbulanceMap: React.FC<Props> = ({ coords, hospitals, routePath = [], tickMs = 800 }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const ambRef = useRef<any>(null);
  const polyRef = useRef<any>(null);
  const [ready, setReady] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const idxRef = useRef(0);

  // SDK 로드
  useEffect(() => {
    if (window.kakao?.maps) {
      setReady(true);
      return;
    }
    const script = document.createElement("script");
    script.src = sdkUrl;
    script.onload = () => window.kakao.maps.load(() => setReady(true));
    script.onerror = () => {
      console.warn("Kakao 지도 스크립트를 불러오지 못했습니다. 키 또는 네트워크를 확인하세요.");
    };
    document.head.appendChild(script);
    return () => {
      script.onload = null;
    };
  }, []);

  // 지도/마커 초기화
  useEffect(() => {
    if (!ready || !coords.lat || !coords.lon || !containerRef.current) return;
    const { kakao } = window;
    const center = new kakao.maps.LatLng(coords.lat, coords.lon);
    if (!mapRef.current) {
      mapRef.current = new kakao.maps.Map(containerRef.current, { center, level: 5 });
      const ambImg = new kakao.maps.MarkerImage("https://t1.daumcdn.net/localimg/localimages/07/mapapidoc/marker_red.png", new kakao.maps.Size(32, 34));
      ambRef.current = new kakao.maps.Marker({ position: center, image: ambImg });
      ambRef.current.setMap(mapRef.current);
    } else {
      mapRef.current.setCenter(center);
      ambRef.current?.setPosition(center);
    }
  }, [ready, coords.lat, coords.lon]);

  // 병원 마커 & polyline
  useEffect(() => {
    if (!ready || !mapRef.current) return;
    const { kakao } = window;
    if (polyRef.current) {
      polyRef.current.setMap(null);
      polyRef.current = null;
    }
    hospitals.forEach((h) => {
      if (!h.wgs84Lat || !h.wgs84Lon) return;
      const m = new kakao.maps.Marker({ position: new kakao.maps.LatLng(h.wgs84Lat, h.wgs84Lon) });
      m.setMap(mapRef.current);
      const iw = new kakao.maps.InfoWindow({ content: `<div style="padding:6px 8px;">${h.dutyName || "병원"}</div>` });
      kakao.maps.event.addListener(m, "click", () => iw.open(mapRef.current, m));
    });
    if (routePath.length > 1) {
      const latLngs = routePath.map(([lon, lat]) => new kakao.maps.LatLng(lat, lon)); // 순서 주의
      polyRef.current = new kakao.maps.Polyline({
        path: latLngs,
        strokeWeight: 5,
        strokeColor: "#2563eb",
        strokeOpacity: 0.85,
      });
      polyRef.current.setMap(mapRef.current);
      mapRef.current.setBounds(new kakao.maps.LatLngBounds(...latLngs));
    }
  }, [ready, hospitals, routePath]);

  // 경로 따라 구급차 애니메이션
  useEffect(() => {
    if (!ready || !mapRef.current || !ambRef.current) return;
    const { kakao } = window;
    if (!routePath.length) {
      if (coords.lat && coords.lon) ambRef.current.setPosition(new kakao.maps.LatLng(coords.lat, coords.lon));
      return;
    }
    if (timerRef.current) clearInterval(timerRef.current);
    idxRef.current = 0;
    timerRef.current = setInterval(() => {
      const [lon, lat] = routePath[idxRef.current] || [];
      if (lat && lon) {
        const pos = new kakao.maps.LatLng(lat, lon);
        ambRef.current.setPosition(pos);
        mapRef.current.setCenter(pos);
      }
      idxRef.current = (idxRef.current + 1) % routePath.length;
    }, Math.max(300, tickMs));
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [ready, routePath, coords.lat, coords.lon, tickMs]);

  return <div ref={containerRef} className="w-full h-[360px] rounded-xl border border-slate-200 shadow-sm" />;
};
