import React, { useEffect, useRef, useState } from "react";
import type { Coords, Hospital } from "../types";
import { ambulanceSvg } from "../svg/ambulanceSvg";
import { hospitalSvg } from "../svg/hospitalsSvg";
import { createWaveOverlay } from "../animation/waveOverlay";
declare global {
  interface Window {
    kakao: any;
  }
}

interface Props {
  coords: Coords;
  hospitals: Hospital[];
  routePath?: number[][]; // [lon, lat]
}

const env = (import.meta as any).env || {};
const KAKAO_KEY = env.VITE_KAKAO_JS_KEY || env.VITE_KAKAO_REST_API_KEY || "";
const sdkUrl = `//dapi.kakao.com/v2/maps/sdk.js?appkey=${KAKAO_KEY}&autoload=false`;

export const KakaoAmbulanceMap: React.FC<Props> = ({ coords, hospitals, routePath = [] }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const ambRef = useRef<any>(null);
  const polyRef = useRef<any>(null);
  const [ready, setReady] = useState(false);
  const [followAmbulance, setFollowAmbulance] = useState(true);
  const recenterTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const boundsFittedRef = useRef(false);
  const initialLevelRef = useRef<number>(5);

  const overlay = createWaveOverlay({ position: { lat: coords.lat!, lon: coords.lon! } });

  // SDK 로드
  useEffect(() => {
    if (!KAKAO_KEY) {
      console.warn("Kakao JS 키가 비어 있습니다. VITE_KAKAO_JS_KEY를 확인하세요.");
      return;
    }
    if (window.kakao?.maps) {
      setReady(true);
      return;
    }
    const script = document.createElement("script");
    script.src = sdkUrl;
    script.onload = () => window.kakao.maps.load(() => setReady(true));
    script.onerror = () => console.warn("Kakao 지도 스크립트를 불러오지 못했습니다. 키/도메인을 확인하세요.");
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
      initialLevelRef.current = mapRef.current.getLevel();
      const ambImg = new kakao.maps.MarkerImage(ambulanceSvg, new kakao.maps.Size(36, 36), { offset: new window.kakao.maps.Point(18, 18) });
      ambRef.current = new kakao.maps.Marker({ position: center, image: ambImg });
      ambRef.current.setMap(mapRef.current);
      overlay?.setMap(mapRef.current);

      // 사용자 조작 시 추적 중단, 10초 후 재추적
      const markManual = () => {
        setFollowAmbulance(false);
        if (recenterTimerRef.current) clearTimeout(recenterTimerRef.current);
        recenterTimerRef.current = setTimeout(() => {
          setFollowAmbulance(true);
          if (mapRef.current && coords.lat && coords.lon) {
            mapRef.current.setLevel(initialLevelRef.current);
            mapRef.current.setCenter(new kakao.maps.LatLng(coords.lat, coords.lon));
          }
        }, 10000);
      };
      kakao.maps.event.addListener(mapRef.current, "dragstart", markManual);
      kakao.maps.event.addListener(mapRef.current, "zoom_changed", markManual);
    } else {
      // 중심/줌은 유지, 마커만 이동
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
      const hospitalImg = new kakao.maps.MarkerImage(hospitalSvg, new kakao.maps.Size(25, 52), { offset: new window.kakao.maps.Point(18, 18) });
      const m = new kakao.maps.Marker({ position: new kakao.maps.LatLng(h.wgs84Lat, h.wgs84Lon), image: hospitalImg });
      m.setMap(mapRef.current);
      const iw = new kakao.maps.InfoWindow({ content: `<div style="padding:6px 8px;">${h.dutyName || "병원"}</div>` });
      kakao.maps.event.addListener(m, "click", () => iw.open(mapRef.current, m));
    });
    if (routePath.length > 1) {
      const latLngs = routePath.map(([lon, lat]) => new kakao.maps.LatLng(lat, lon));
      polyRef.current = new kakao.maps.Polyline({
        path: latLngs,
        strokeWeight: 5,
        strokeColor: "#2563eb",
        strokeOpacity: 0.85,
      });
      polyRef.current.setMap(mapRef.current);
      // 사용자가 조작하지 않았다면 초기 1회만 경로에 맞춰 줌/센터 적용
      if (followAmbulance && !boundsFittedRef.current) {
        mapRef.current.setBounds(new kakao.maps.LatLngBounds(...latLngs));
        boundsFittedRef.current = true;
      }
    }
  }, [ready, hospitals, routePath, followAmbulance]);

  // 실시간 좌표 반영: 마커만 이동, 추적 모드일 때만 센터 이동
  useEffect(() => {
    if (!ready || !mapRef.current || !ambRef.current) return;
    if (!coords.lat || !coords.lon) return;
    const pos = new window.kakao.maps.LatLng(coords.lat, coords.lon);
    const wave = new window.kakao.maps.LatLng(coords.lat!, coords.lon!);
    ambRef.current.setPosition(pos);
    overlay?.setPosition(wave);

    if (followAmbulance) {
      mapRef.current.setCenter(pos);
    }
  }, [ready, coords.lat, coords.lon, followAmbulance]);

  return <div ref={containerRef} className="w-full h-[360px] rounded-xl border border-slate-200 shadow-sm" />;
};
