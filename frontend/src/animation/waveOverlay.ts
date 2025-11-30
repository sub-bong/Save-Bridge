declare global {
  interface Window {
    kakao: any;
  }
}

export interface WaveOverlayOptions {
  position: { lat: number; lon: number };
  color?: string; // 파동 색상 (기본 rgba(37,99,235,0.2))
  diameter?: number; // 지름 px (기본 60)
  durationMs?: number; // 애니메이션 주기 (기본 2.5초)
}

/**
 * Kakao CustomOverlay로 원형 파동을 만들어 반환
 * caller가 setMap/map, setPosition을 관리
 */
export const createWaveOverlay = (opts: WaveOverlayOptions) => {
  const { kakao } = window;
  if (!kakao) return null;

  const color = opts.color ?? "rgba(235, 99, 33, 0.6)";
  const diameter = opts.diameter ?? 48;
  const radius = diameter / 2;
  const durationMs = opts.durationMs ?? 2500;

  // style 태그 1회 삽입
  if (!document.getElementById("kakao-ambulance-wave-style")) {
    const style = document.createElement("style");
    style.id = "kakao-ambulance-wave-style";
    style.innerHTML = `
    @keyframes kakao-ambulance-wave {
      0%   { transform: scale(0.2); opacity: 0.8; }
      70%  { transform: scale(1.3); opacity: 0; }
      100% { transform: scale(1.3); opacity: 0; }
    }`;
    document.head.appendChild(style);
  }

  // 파동 엘리먼트
  const el = document.createElement("div");
  el.style.width = `${diameter}px`;
  el.style.height = `${diameter}px`;
  el.style.marginLeft = `-${radius}px`;
  el.style.marginTop = `-${radius}px`;
  el.style.position = "absolute";
  el.style.borderRadius = "50%";
  el.style.background = color;
  el.style.animation = `kakao-ambulance-wave ${durationMs}ms ease-out infinite`;
  el.style.pointerEvents = "none";

  const pos = new kakao.maps.LatLng(opts.position.lat, opts.position.lon);
  return new kakao.maps.CustomOverlay({
    position: pos,
    content: el,
    yAnchor: 0.5,
  });
};
