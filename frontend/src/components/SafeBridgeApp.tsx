import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import type { Coords, Region, Hospital, ApprovalStatus, HospitalHandoverSummary, PatientTransportMeta } from "../types";
import { symptomOptions } from "../constants";
import {
  addressToCoord,
  coordToAddress,
  coordToRegion,
  searchHospitals,
  transcribeAudio,
  makeCall,
  getCallResponse,
  getRoute,
  logout,
  getCurrentUser,
  getChatSession,
  createEmergencyRequest,
  callHospital,
  updateResponseStatus,
  getPendingChatSessionForEms,
  convertTextToSBAR,
} from "../services/api";
import { detectPatientAgeGroup, extractPatientAge, extractPatientSex, extractPreKtasLevel, parsePatientInfoFromText } from "../utils/hospitalUtils";
import { LocationInput } from "./LocationInput";
import { PatientStatusInput, CRITICAL_PRESETS } from "./PatientStatusInput";
import { HospitalSearchButtons } from "./SymptomSelector";
import { HospitalPrioritySelector } from "./HospitalPrioritySelector";
import type { PriorityMode } from "./HospitalPrioritySelector";
import { HospitalCard } from "./HospitalCard";
import { MapDisplay } from "./MapDisplay";
import { ApprovedHospitalInfo } from "./ApprovedHospitalInfo";
import { ParamedicChatSlideOver } from "./ParamedicChatSlideOver";
import { KakaoAmbulanceMap } from "./KakaoAmbulanceMap";
import { getSocket } from "../services/socket";

export const SafeBridgeApp: React.FC = () => {
  const [address, setAddress] = useState<string>("");
  const [coords, setCoords] = useState<Coords>({ lat: null, lon: null });
  const [region, setRegion] = useState<Region | null>(null);
  const [loadingGps, setLoadingGps] = useState<boolean>(false);
  const [symptom, setSymptom] = useState<string>("뇌졸중 의심(FAST+)");
  const [sttText, setSttText] = useState<string>("");
  const [sbarText, setSbarText] = useState<string>("");
  const [arsSource, setArsSource] = useState<"stt" | "sbar" | null>(null);
  const [inputMode, setInputMode] = useState<"stt" | "critical">("stt");
  const [priorityModes, setPriorityModes] = useState<PriorityMode[]>(["distance"]);
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [loadingHospitals, setLoadingHospitals] = useState<boolean>(false);
  const [voiceMode, setVoiceMode] = useState<boolean>(false);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [hospitalApprovalStatus, setHospitalApprovalStatus] = useState<Record<string, ApprovalStatus>>({});
  const [rejectedHospitals, setRejectedHospitals] = useState<Set<string>>(new Set());
  const [approvedHospital, setApprovedHospital] = useState<Hospital | null>(null);
  const [rerollCount, setRerollCount] = useState<number>(0);
  const [twilioAutoCalling, setTwilioAutoCalling] = useState<boolean>(false);
  const [currentHospitalIndex, setCurrentHospitalIndex] = useState<number>(0);
  const [showHospitalPanel, setShowHospitalPanel] = useState<boolean>(false);
  const [activeCalls, setActiveCalls] = useState<Record<string, { call_sid: string; start_time: number }>>({});
  const [routePaths, setRoutePaths] = useState<Record<string, number[][]>>({});
  const [backupHospitals, setBackupHospitals] = useState<Hospital[]>([]);
  const [neighborHospitals, setNeighborHospitals] = useState<Hospital[]>([]);
  const [hasExhaustedHospitals, setHasExhaustedHospitals] = useState<boolean>(false);
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [recordingError, setRecordingError] = useState<string>("");
  const [micLevel, setMicLevel] = useState<number>(0);
  const [isChatOpen, setIsChatOpen] = useState<boolean>(false);
  const [chatSession, setChatSession] = useState<HospitalHandoverSummary | null>(null);
  const [patientSex, setPatientSex] = useState<"male" | "female" | null>(null);
  const [patientAgeBand, setPatientAgeBand] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<{ 
    user_type: "EMS" | "HOSPITAL";
    team_id?: number;
    ems_id?: string;
    region?: string | null;
    hospital_id?: string;
    hospital_name?: string;
  } | null>(null);
  const [currentRequestId, setCurrentRequestId] = useState<number>(0);
  const [showLogoutModal, setShowLogoutModal] = useState<boolean>(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const levelAnimationRef = useRef<number | null>(null);
  const callTimeoutsRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const colorMapRef = useRef<Record<string, string>>({});
  const [liveCoords, setLiveCoords] = useState<Coords>({ lat: null, lon: null }); // 11/29 추가: 실시간 좌표 상태 관리

  // EMS 계정 기준, 인계 완료되지 않은 마지막 채팅 세션
  const [pendingChatSession, setPendingChatSession] = useState<{
    session_id: number;
    request_id: number;
    assignment_id: number;
    hospital: Hospital | null;
    patient_age?: number | null;
    patient_sex?: "M" | "F" | null;
    pre_ktas_class?: number | string | null;
    rag_summary?: string | null;
    stt_full_text?: string | null;
  } | null>(null);

  // 사용자 정보 로드
  useEffect(() => {
    const loadUser = async () => {
      try {
        const user = await getCurrentUser();
        setCurrentUser(user);

        // EMS 계정인 경우, 미완료 채팅 세션 조회
        if (user && user.user_type === "EMS" && user.ems_id) {
          try {
            const pending = await getPendingChatSessionForEms(user.ems_id);
            if (pending && !pending.is_completed) {
              const hospital: Hospital | null = pending.hospital_id
                ? {
                    hpid: pending.hospital_id || undefined,
                    dutyName: pending.hospital_name || undefined,
                    wgs84Lat: pending.hospital_lat || undefined,
                    wgs84Lon: pending.hospital_lon || undefined,
                  }
                : null;
              setPendingChatSession({
                session_id: pending.session_id,
                request_id: pending.request_id,
                assignment_id: pending.assignment_id,
                hospital,
                patient_age: pending.patient_age ?? null,
                patient_sex: (pending.patient_sex === "M" || pending.patient_sex === "F"
                  ? pending.patient_sex
                  : null),
                pre_ktas_class: pending.pre_ktas_class ?? null,
                rag_summary: pending.rag_summary ?? null,
                stt_full_text: pending.stt_full_text ?? null,
              });
            } else {
              setPendingChatSession(null);
            }
          } catch (e) {
            console.error("미완료 채팅 세션 조회 중 오류:", e);
            setPendingChatSession(null);
          }
        } else {
          setPendingChatSession(null);
        }
      } catch (error) {
        console.error("사용자 정보 로드 실패:", error);
        // 에러가 발생해도 컴포넌트는 계속 렌더링되도록 함
        setCurrentUser(null);
        setPendingChatSession(null);
      }
    };
    loadUser();
  }, []);

  // 중증탭에서 선택한 정보를 STT 텍스트로 자동 생성하고 SBAR로 변환
  useEffect(() => {
    if (inputMode !== "critical") return;
    
    // 중증탭에서 선택한 정보로 STT 텍스트 생성
    const parts: string[] = [];
    
    // Pre-KTAS 점수 (증상에서 추출)
    let preKtasLevel: number | undefined;
    const presetMatch = CRITICAL_PRESETS.find(p => p.label === symptom)?.preKtasLevel?.match(/\d+/);
    if (presetMatch) {
      preKtasLevel = parseInt(presetMatch[0]);
    }
    if (preKtasLevel) {
      parts.push(`프리케이타스 ${preKtasLevel}점`);
    }
    
    // 나이대
    if (patientAgeBand) {
      parts.push(patientAgeBand);
    }
    
    // 성별
    if (patientSex === "male") {
      parts.push("남성");
    } else if (patientSex === "female") {
      parts.push("여성");
    }
    
    // 증상
    if (symptom) {
      parts.push(symptom);
    }
    
    if (parts.length > 0) {
      const generatedSttText = parts.join(" ");
      setSttText(generatedSttText);
      
      // SBAR로 변환
      convertTextToSBAR(generatedSttText)
        .then((result) => {
          if (result.sbarSummary) {
            setSbarText(result.sbarSummary);
          }
        })
        .catch((error) => {
          console.error("SBAR 변환 실패:", error);
          // 실패해도 계속 진행
        });
    }
  }, [inputMode, patientSex, patientAgeBand, symptom]);

  // 로그아웃 모달 열기
  const handleLogoutClick = () => {
    setShowLogoutModal(true);
  };

  // 로그아웃 확인
  const handleLogoutConfirm = async () => {
    await logout();
    window.location.reload(); // 페이지 새로고침하여 로그인 페이지로 이동
  };

  // 로그아웃 취소
  const handleLogoutCancel = () => {
    setShowLogoutModal(false);
  };
  const hospitalColorPalette = useMemo(
    () => ["#ef4444", "#f97316", "#f59e0b", "#14b8a6", "#0ea5e9", "#6366f1", "#a855f7", "#ec4899", "#22c55e", "#e11d48", "#10b981", "#94a3b8"],
    []
  );

  // STT 텍스트에서 환자 연령 그룹 감지
  const patientAgeGroup = useMemo(() => {
    return detectPatientAgeGroup(sttText);
  }, [sttText]);

  // 연령 그룹에 따라 필터링된 증상 카테고리 목록
  const filteredSymptomOptions = useMemo(() => {
    // 공통 증상 (성인/소아 모두 가능)
    const commonSymptoms = [
      "뇌졸중 의심(FAST+)",
      "심근경색 의심(STEMI)",
      "다발성 외상/중증 외상",
      "심정지/심폐정지",
      "정형외과 중증(대형골절/절단)",
      "신경외과 응급(의식저하/외상성출혈)",
    ];
    
    // 성인 전용 증상
    const adultOnlySymptoms = ["성인 호흡곤란", "성인 경련"];
    
    // 소아 전용 증상
    const pediatricOnlySymptoms = ["소아 호흡곤란", "소아 경련", "소아 중증(신생아/영아)"];
    
    if (patientAgeGroup === "adult") {
      // 성인인 경우: 공통 증상 + 성인 전용 증상
      return [...commonSymptoms, ...adultOnlySymptoms];
    } else if (patientAgeGroup === "pediatric") {
      // 소아인 경우: 공통 증상 + 소아 전용 증상
      return [...commonSymptoms, ...pediatricOnlySymptoms];
    }
    // 판단 불가능한 경우 모든 증상 카테고리 표시
    return symptomOptions;
  }, [patientAgeGroup]);

  // 필터링된 목록에 현재 선택된 증상이 없으면 첫 번째 증상으로 자동 변경
  useEffect(() => {
    if (filteredSymptomOptions.length > 0 && !filteredSymptomOptions.includes(symptom)) {
      setSymptom(filteredSymptomOptions[0]);
    }
  }, [filteredSymptomOptions, symptom]);

  const displayedMapHospitals = useMemo(() => {
    if (approvedHospital && approvedHospital.wgs84Lat && approvedHospital.wgs84Lon) {
      return [approvedHospital];
    }
    if (hasExhaustedHospitals) {
      return hospitals.filter((h) => h.wgs84Lat && h.wgs84Lon);
    }
    return [];
  }, [approvedHospital, hasExhaustedHospitals, hospitals]);
  const hasCallableHospital = useMemo(() => {
    if (hospitals.some((h) => !rejectedHospitals.has(h.hpid || ""))) {
      return true;
    }
    const existingIds = new Set(hospitals.map((h) => h.hpid || ""));
    const hasBackupCandidate = backupHospitals.some((candidate) => {
      const id = candidate.hpid || "";
      return id && !existingIds.has(id) && !rejectedHospitals.has(id);
    });
    if (hasBackupCandidate) {
      return true;
    }
    return neighborHospitals.some((candidate) => {
      const id = candidate.hpid || "";
      return id && !existingIds.has(id) && !rejectedHospitals.has(id);
    });
  }, [hospitals, rejectedHospitals, backupHospitals, neighborHospitals]);

  const resolveHospitalColor = useCallback(
    (hospital: Hospital, fallbackIndex: number) => {
      const key = hospital.hpid || `${hospital.wgs84Lat}-${hospital.wgs84Lon}-${fallbackIndex}`;
      if (!key) {
        return hospitalColorPalette[fallbackIndex % hospitalColorPalette.length];
      }

      if (approvedHospital && hospital.hpid === approvedHospital.hpid) {
        colorMapRef.current[key] = "#16a34a";
        return "#16a34a";
      }

      if (!colorMapRef.current[key]) {
        const usedColors = Object.values(colorMapRef.current);
        const paletteIndex = usedColors.length % hospitalColorPalette.length;
        colorMapRef.current[key] = hospitalColorPalette[paletteIndex];
      }

      return colorMapRef.current[key];
    },
    [approvedHospital, hospitalColorPalette]
  );

  useEffect(() => {
    colorMapRef.current = {};
  }, [rerollCount]);

  const handleGpsClick = async () => {
    if (!navigator.geolocation) {
      alert("브라우저가 위치 정보를 지원하지 않습니다.");
      return;
    }
    
    setLoadingGps(true);
    
    try {
      const position = await fetchCoordsWithFallback(); // 11/29 수정: fetchCoordsWithFallback(coords, liveCoords 상태 동시 관리) 헬퍼 함수로 관리
      const { latitude, longitude } = position.coords;
      console.log("GPS 좌표 획득:", latitude, longitude);
      const next = { lat: latitude, lon: longitude };
      setCoords(next);
      setLiveCoords(next);
      
      // 주소 및 행정구역 역변환 (병렬 처리)
      try {
        const [addressResult, regionResult] = await Promise.allSettled([coordToAddress(latitude, longitude), coordToRegion(latitude, longitude)]);
        
        // 주소 설정
        if (addressResult.status === "fulfilled" && addressResult.value) {
          console.log("주소 변환 성공:", addressResult.value);
          setAddress(addressResult.value);
        } else {
          // rejected가 아니고 value가 null인 경우는 정상 (카카오 API가 주소를 찾지 못한 경우)
          if (addressResult.status === "rejected") {
            const error = addressResult.reason;
          const errorMsg = error?.message || (error ? String(error) : "결과 없음");
          console.warn("주소 변환 실패:", errorMsg);
          
            // 실제 네트워크 오류나 서버 연결 실패 시에만 경고
            if (error && (error?.code === 'ERR_NETWORK' || error?.message?.includes('CORS') || error?.code === 'ECONNREFUSED' || error?.response?.status === 404)) {
            console.warn("백엔드 API 서버에 연결할 수 없습니다. 백엔드 서버가 실행 중인지 확인해주세요.");
          }
          }
          // fulfilled이지만 value가 null인 경우는 조용히 처리 (카카오 API가 주소를 찾지 못한 정상적인 경우)
        }
        
        // 행정구역 설정
        if (regionResult.status === "fulfilled" && regionResult.value) {
          console.log("행정구역 변환 성공:", regionResult.value);
          setRegion(regionResult.value);
        } else {
          // rejected가 아니고 value가 null인 경우는 정상 (카카오 API가 행정구역을 찾지 못한 경우)
          if (regionResult.status === "rejected") {
            const error = regionResult.reason;
          const errorMsg = error?.message || (error ? String(error) : "결과 없음");
          console.warn("행정구역 변환 실패:", errorMsg);
          
            // 실제 네트워크 오류나 서버 연결 실패 시에만 경고
            if (error && (error?.code === 'ERR_NETWORK' || error?.message?.includes('CORS') || error?.code === 'ECONNREFUSED' || error?.response?.status === 404)) {
            console.warn("백엔드 API 서버에 연결할 수 없습니다. 백엔드 서버가 실행 중인지 확인해주세요.");
            }
          }
          // fulfilled이지만 value가 null인 경우는 조용히 처리
          
          // 행정구역이 없으면 좌표로부터 기본 행정구역 추정 시도
          const regionValue = regionResult.status === "fulfilled" ? regionResult.value : null;
          if (!regionValue && latitude && longitude) {
            // 한국의 주요 도시 좌표 범위로 기본 행정구역 설정
            // 광주광역시: 35.15~35.20, 126.85~126.95
            if (latitude >= 35.1 && latitude <= 35.3 && longitude >= 126.8 && longitude <= 127.0) {
              setRegion({ sido: "광주광역시", sigungu: "광산구" });
              console.log("기본 행정구역 설정: 광주광역시 광산구");
            }
            // 서울특별시: 37.4~37.7, 126.9~127.2
            else if (latitude >= 37.4 && latitude <= 37.7 && longitude >= 126.9 && longitude <= 127.2) {
              setRegion({ sido: "서울특별시", sigungu: "종로구" });
              console.log("기본 행정구역 설정: 서울특별시 종로구");
            }
            // 기타 지역은 좌표 기반으로 추정 (필요시 확장)
          }
        }
      } catch (error: any) {
        console.error("주소/행정구역 변환 중 오류:", error);
        // 좌표는 이미 설정되었으므로 사용자에게 알림만 표시
        if (error?.code === "ECONNREFUSED" || error?.response?.status === 404) {
          console.warn("백엔드 API 서버가 실행되지 않았습니다. 좌표만 설정되었습니다.");
        }
      }
    } catch (err: any) {
      console.error("GPS 위치 정보 오류:", err);
      
      // HTTP 환경 체크
      const hostname = window.location.hostname;
      const protocol = window.location.protocol;
      const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1';
      const isLocalDomain = hostname.endsWith('.local'); // mDNS/Bonjour 도메인 지원
      const isHttpNotLocalhost = protocol === 'http:' && !isLocalhost && !isLocalDomain;
      
      if (err.code === 1) {
        // 위치 권한 거부
        if (isHttpNotLocalhost) {
          alert(
            "HTTP 환경에서는 위치 권한을 사용할 수 없습니다.\n\n" +
            "Safari 브라우저는 보안상의 이유로 HTTP 사이트에서 위치 정보 접근을 허용하지 않습니다.\n\n" +
            "해결 방법:\n" +
            "1. HTTPS 환경(ngrok URL)을 사용하거나\n" +
            "2. 주소 입력란에 직접 주소를 입력해주세요."
          );
        } else {
        alert("위치 권한이 거부되었습니다. 브라우저 설정에서 위치 권한을 허용해주세요.");
        }
      } else if (err.code === 2) {
        alert("위치를 확인할 수 없습니다. GPS 신호를 확인해주세요.");
      } else if (err.code === 3) {
        alert("위치 정보 요청 시간이 초과되었습니다. 다시 시도해주세요.");
      } else {
        alert(`위치 정보를 불러오지 못했습니다: ${err.message || "알 수 없는 오류"}`);
      }
    } finally {
      setLoadingGps(false);
    }
  };

  const handleSearchAddress = async () => {
    if (!address.trim()) {
      alert("주소를 입력해주세요.");
      return;
    }
    
    // 주소 검색 중 표시를 위한 상태 (선택사항)
    const originalAddress = address;
    
    try {
      const result = await addressToCoord(address);
      if (result) {
        setCoords({ lat: result.lat, lon: result.lon });
        if (result.sido && result.sigungu) {
          setRegion({ sido: result.sido, sigungu: result.sigungu });
        } else {
          // 행정구역이 없으면 좌표로 다시 조회 시도
          const regionResult = await coordToRegion(result.lat, result.lon);
          if (regionResult) {
            setRegion(regionResult);
          } else {
            console.warn("행정구역을 확인할 수 없습니다.");
            // 좌표는 설정되었으므로 경고만 표시
          }
        }
      } else {
        alert("주소를 찾을 수 없습니다. 주소를 확인해주세요.\n\n예시:\n- 광주광역시 광산구 신가동\n- 서울특별시 종로구 종로1길 50");
      }
    } catch (error: any) {
      console.error("주소 검색 오류:", error);
      const errorMsg = error.message || "주소 → 좌표 변환에 실패했습니다.";
      
      // 더 친절한 에러 메시지
      if (errorMsg.includes("찾을 수 없습니다")) {
        alert(
          `${errorMsg}\n\n팁:\n- 더 구체적인 주소를 입력해보세요 (예: "광주광역시 광산구 신가동")\n- 도로명 주소를 사용해보세요 (예: "광주광역시 광산구 첨단중앙로 123")\n- 백엔드 서버가 실행 중인지 확인해주세요`
        );
      } else {
        alert(`${errorMsg}\n\n백엔드 서버가 실행 중인지 확인해주세요.`);
      }
    }
  };

  // 인계완료 후 화면 초기화 함수
  const handleResetAfterHandover = useCallback(() => {
    console.log("🔄 인계완료 - 메인화면 초기화 중...");
    
    // 채팅 관련 상태 초기화
    setIsChatOpen(false);
    setChatSession(null);
    
    // 환자 정보 초기화
    setSttText("");
    setSbarText("");
    setArsSource(null);
    setPatientSex(null);
    setPatientAgeBand(null);
    setAudioFile(null);
    setVoiceMode(false);
    setInputMode("stt");
    
    // 병원 관련 상태 초기화
    setHospitals([]);
    setBackupHospitals([]);
    setNeighborHospitals([]);
    setApprovedHospital(null);
    setHospitalApprovalStatus({});
    setRejectedHospitals(new Set());
    setCurrentHospitalIndex(0);
    setShowHospitalPanel(false);
    setHasExhaustedHospitals(false);
    setTwilioAutoCalling(false);
    setActiveCalls({});
    setRoutePaths({});
    setRerollCount(0);
    setCurrentRequestId(0);
    
    // 증상 및 우선순위 초기화
    setSymptom("뇌졸중 의심(FAST+)");
    setPriorityModes(["distance"]);
    
    // 녹음 관련 초기화
    setIsRecording(false);
    setRecordingError("");
    setMicLevel(0);
    
    // 색상 맵 초기화
    colorMapRef.current = {};
    
    // 진행 중인 전화 타임아웃 정리
    Object.values(callTimeoutsRef.current).forEach((timeout) => {
      if (timeout) clearTimeout(timeout);
    });
    callTimeoutsRef.current = {};
    
    console.log("✅ 메인화면 초기화 완료 - 다음 환자 인계 준비됨");
  }, []);

  const handleSearchHospitals = async () => {
    if (!coords.lat || !coords.lon) {
      alert("위치를 먼저 설정해주세요.");
      return;
    }
    
    if (!region) {
      alert("행정구역을 확인할 수 없습니다. GPS 버튼을 다시 눌러주거나 주소를 검색해주세요.");
      return;
    }
    
    try {
      setShowHospitalPanel(true);
      setLoadingHospitals(true);
      setRerollCount((prev) => prev + 1);
      setHospitalApprovalStatus({});
      setRejectedHospitals(new Set());
      // 채팅이 열려있지 않을 때만 approvedHospital 초기화 (채팅 중이면 유지)
      if (!isChatOpen) {
      setApprovedHospital(null);
      }
      setRoutePaths({});
      setBackupHospitals([]);
      setNeighborHospitals([]);
      setHasExhaustedHospitals(false);
      setTwilioAutoCalling(false);
      setCurrentHospitalIndex(0);
      setActiveCalls({});
      colorMapRef.current = {};
      
      // 중증탭 모드이고 SBAR 변환이 완료되지 않았으면 변환 완료까지 대기
      if (inputMode === "critical" && sttText && !sbarText) {
        try {
          console.log("⏳ SBAR 변환 대기 중...");
          const sbarResult = await convertTextToSBAR(sttText);
          if (sbarResult.sbarSummary) {
            setSbarText(sbarResult.sbarSummary);
            console.log("✅ SBAR 변환 완료");
          }
        } catch (error) {
          console.error("SBAR 변환 실패 (병원 찾기 시작 시점):", error);
          // 실패해도 계속 진행 (STT 텍스트 사용)
        }
      }

      // 증상에 따라 자동으로 병원 타입 결정
      // 다발성 외상/중증 외상 → 외상센터 우선, 그 외 → 일반 (백엔드에서 자동 처리)
      const result = await searchHospitals(coords.lat, coords.lon, region.sido, region.sigungu, symptom, sttText || null);
      const fetchedHospitals = result.hospitals || [];
      const fetchedBackup = (result.backup_hospitals || []).filter(Boolean);
      const fetchedNeighbor = (result.neighbor_hospitals || []).filter(Boolean);

      // 중복 제거: hpid 기준으로 중복된 병원 제거
      const uniqueHospitals = fetchedHospitals.filter((h, idx, self) => {
        const firstIndex = self.findIndex((item) => item.hpid === h.hpid);
        return firstIndex === idx;
      });
      const uniqueBackup = fetchedBackup.filter((h, idx, self) => {
        const firstIndex = self.findIndex((item) => item.hpid === h.hpid);
        return firstIndex === idx;
      });
      const uniqueNeighbor = fetchedNeighbor.filter((h, idx, self) => {
        const firstIndex = self.findIndex((item) => item.hpid === h.hpid);
        return firstIndex === idx;
      });
      
      setHospitals(uniqueHospitals);
      setBackupHospitals(uniqueBackup);
      setNeighborHospitals(uniqueNeighbor);
      if (!fetchedHospitals.length) {
        setHasExhaustedHospitals(true);
      }
      
      if (result.route_paths) {
        setRoutePaths(result.route_paths);
      }
      // top3 병원 경로 정보 조회 및 업데이트
      await fetchRoutePaths(uniqueHospitals, { updateDistances: true });
      // 백업 병원 경로 정보 조회 및 업데이트
      if (uniqueBackup.length > 0) {
        await fetchRoutePaths(uniqueBackup, { append: true, updateBackup: true });
      }
      // 인접 병원 경로 정보 조회 및 업데이트
      if (uniqueNeighbor.length > 0) {
        await fetchRoutePaths(uniqueNeighbor, { append: true, updateNeighbor: true });
      }

      // EmergencyRequest 생성 (DB에 저장)
      if (currentUser && uniqueHospitals.length > 0) {
        try {
          // STT 텍스트에서 환자 정보 통합 파싱 (개선된 버전)
          const parsedInfo = parsePatientInfoFromText(sttText);
          
          // 통합 파싱 결과 우선 사용, 실패 시 개별 함수로 재시도
          let patientAgeFromStt = parsedInfo.age;
          let patientSexFromStt = parsedInfo.sex;
          let preKtasLevel = parsedInfo.preKtas;
          
          // 통합 파싱에서 실패한 항목만 개별 함수로 재시도
          if (!patientAgeFromStt) {
            patientAgeFromStt = extractPatientAge(sttText);
          }
          if (!patientSexFromStt) {
            patientSexFromStt = extractPatientSex(sttText);
          }
          if (!preKtasLevel) {
            preKtasLevel = extractPreKtasLevel(sttText);
          }
          
          // STT에서 추출 실패 시 사용자 선택값 사용, 그래도 없으면 기본값
          const patientAge = patientAgeFromStt || extractPatientAge(patientAgeBand) || 30;
          const patientSexValue = patientSexFromStt || (patientSex === "male" ? "M" : patientSex === "female" ? "F" : "M");
          
          const emergencyRequest = await createEmergencyRequest({
            team_id: currentUser.team_id!,
            patient_sex: patientSexValue,
            patient_age: patientAge,
            pre_ktas_class: preKtasLevel || 3,
            stt_full_text: sttText,
            rag_summary: sbarText,
            current_lat: coords.lat!,
            current_lon: coords.lon!,
          });
          setCurrentRequestId(emergencyRequest.request_id);
          console.log("EmergencyRequest 생성됨:", emergencyRequest.request_id);
        } catch (error) {
          console.error("EmergencyRequest 생성 실패:", error);
          // 실패해도 계속 진행
        }
      }

      // 병원 조회 후 자동 전화 시작
      if (uniqueHospitals.length > 0) {
        setTwilioAutoCalling(true); // Start auto-calling
      } else {
        setTwilioAutoCalling(false);
      }
    } catch (error: any) {
      console.error("병원 조회 오류:", error);
      alert(error.message || "병원 조회 중 오류가 발생했습니다. 백엔드 서버가 실행 중인지 확인해주세요.");
    } finally {
      setLoadingHospitals(false);
    }
  };

  const fetchRoutePaths = useCallback(
    async (
      targetHospitals: Hospital[],
      options?: {
        append?: boolean;
        updateDistances?: boolean;
        updateBackup?: boolean;
        updateNeighbor?: boolean;
        updateApproved?: boolean;
      }
    ) => {
      if (!coords.lat || !coords.lon || !targetHospitals?.length) return;
      
      const paths: Record<string, number[][]> = {};
      const meta: Record<string, { distance_km?: number; eta_minutes?: number }> = {};
      for (const hospital of targetHospitals) {
        if (hospital.wgs84Lat && hospital.wgs84Lon) {
          try {
            const result = await getRoute(coords.lat!, coords.lon!, hospital.wgs84Lat, hospital.wgs84Lon);
            if (result?.path_coords) {
              paths[hospital.hpid || ""] = result.path_coords;
            }
            if (result) {
              meta[hospital.hpid || ""] = {
                distance_km: result.distance_km,
                eta_minutes: result.eta_minutes,
              };
            }
          } catch (e) {
            console.error("경로 조회 실패:", e);
          }
        }
      }
      setRoutePaths((prev) => (options?.append ? { ...prev, ...paths } : paths));
      if (options?.updateDistances && Object.keys(meta).length > 0) {
        setHospitals((prev) =>
          prev.map((h) => {
            const key = h.hpid || "";
            if (meta[key]) {
              return {
                ...h,
                distance_km: meta[key].distance_km ?? h.distance_km,
                eta_minutes: meta[key].eta_minutes ?? h.eta_minutes,
              };
            }
            return h;
          })
        );
      }
      if (options?.updateBackup && Object.keys(meta).length > 0) {
        setBackupHospitals((prev) =>
          prev.map((h) => {
            const key = h.hpid || "";
            if (meta[key]) {
              return {
                ...h,
                distance_km: meta[key].distance_km ?? h.distance_km,
                eta_minutes: meta[key].eta_minutes ?? h.eta_minutes,
              };
            }
            return h;
          })
        );
      }
      if (options?.updateNeighbor && Object.keys(meta).length > 0) {
        setNeighborHospitals((prev) =>
          prev.map((h) => {
            const key = h.hpid || "";
            if (meta[key]) {
              return {
                ...h,
                distance_km: meta[key].distance_km ?? h.distance_km,
                eta_minutes: meta[key].eta_minutes ?? h.eta_minutes,
              };
            }
            return h;
          })
        );
      }
      if (options?.updateApproved && Object.keys(meta).length > 0) {
        setApprovedHospital((prev) => {
          if (!prev || !prev.hpid) return prev;
          const key = prev.hpid;
          if (!meta[key]) return prev;
          return {
            ...prev,
            distance_km: meta[key].distance_km ?? prev.distance_km,
            eta_minutes: meta[key].eta_minutes ?? prev.eta_minutes,
          };
        });
      }
    },
    [coords.lat, coords.lon]
  );

  useEffect(() => {
    if (!approvedHospital || !approvedHospital.hpid) return;
    if (routePaths[approvedHospital.hpid]) return;
    fetchRoutePaths([approvedHospital], {
      append: true,
      updateDistances: true,
      updateApproved: true,
    });
  }, [approvedHospital, routePaths, fetchRoutePaths]);

  const handleAudioFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setAudioFile(file);
    }
  };

  const handleUploadAudio = async () => {
    if (!audioFile) return;
    try {
      const result = await transcribeAudio(audioFile);
      if (result && result.text) {
        setSttText(String(result.text)); // 문자열로 확실히 변환
        if (result.sbarSummary) {
          setSbarText(result.sbarSummary);
        }
        setVoiceMode(false);
        setAudioFile(null);
      } else {
        alert("음성 인식 결과가 없습니다.");
      }
    } catch (error: any) {
      console.error("음성 인식 오류:", error);
      alert(error.message || "음성 인식 중 오류가 발생했습니다.");
    }
  };

  const cleanupAudioVisualization = useCallback(() => {
    if (levelAnimationRef.current) {
      cancelAnimationFrame(levelAnimationRef.current);
      levelAnimationRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    analyserRef.current = null;
    setMicLevel(0);
  }, []);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/wav" });
        const audioFile = new File([audioBlob], "recording.wav", { type: "audio/wav" });
        
        // 녹음된 파일을 업로드
        try {
          const result = await transcribeAudio(audioFile);
          if (result && result.text) {
            setSttText(String(result.text)); // 문자열로 확실히 변환
            if (result.sbarSummary) {
              setSbarText(result.sbarSummary);
            }
            setVoiceMode(false);
          } else {
            alert("음성 인식 결과가 없습니다.");
          }
        } catch (error: any) {
          console.error("음성 인식 오류:", error);
          alert(error.message || "음성 인식 중 오류가 발생했습니다.");
        }
        
        // 스트림 정리
        stream.getTracks().forEach((track) => track.stop());
        cleanupAudioVisualization();
      };

      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      if (AudioContextClass) {
        const audioContext: AudioContext = new AudioContextClass();
        audioContextRef.current = audioContext;
        const source = audioContext.createMediaStreamSource(stream);
        const analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;
        analyserRef.current = analyser;
        source.connect(analyser);
        const dataArray = new Uint8Array(analyser.frequencyBinCount);

        const updateLevel = () => {
          if (!analyserRef.current) {
            return;
          }
          analyserRef.current.getByteTimeDomainData(dataArray);
          let sum = 0;
          for (let i = 0; i < dataArray.length; i += 1) {
            sum += Math.abs(dataArray[i] - 128);
          }
          const average = sum / dataArray.length;
          const normalized = Math.min(average / 50, 1);
          setMicLevel(normalized);
          levelAnimationRef.current = requestAnimationFrame(updateLevel);
        };

        levelAnimationRef.current = requestAnimationFrame(updateLevel);
      } else {
        setMicLevel(0);
      }

      mediaRecorder.start();
      setIsRecording(true);
      setRecordingError("");
    } catch (error: any) {
      console.error("마이크 접근 오류:", error);
      setRecordingError("마이크 권한이 필요합니다. 브라우저 설정에서 마이크 권한을 허용해주세요.");
      setIsRecording(false);
      cleanupAudioVisualization();
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      cleanupAudioVisualization();
      setIsRecording(false);
    }
  };

  const handleToggleRecording = () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
        mediaRecorderRef.current.stop();
      }
      cleanupAudioVisualization();
    };
  }, [cleanupAudioVisualization]);

  const handleApproveHospital = async (hospital: Hospital) => {
    const approvedId = hospital.hpid || "";

    // 프론트엔드 상태 업데이트
    setHospitalApprovalStatus(() => {
      const nextStatuses: Record<string, ApprovalStatus> = {};
      hospitals.forEach((h) => {
        const id = h.hpid || "";
        if (!id) return;
        nextStatuses[id] = id === approvedId ? "approved" : "rejected";
      });
      return nextStatuses;
    });
    setRejectedHospitals(new Set(hospitals.filter((h) => (h.hpid || "") !== approvedId).map((h) => h.hpid || "")));
    setApprovedHospital(hospital);
    setTwilioAutoCalling(false);
    setActiveCalls({});

    // DB에 RequestAssignment 생성 및 승인 상태 업데이트
    if (!hospital.hpid) {
      console.warn("hospital.hpid가 없어 병원 승인을 처리할 수 없습니다.");
    handleOpenChat(hospital);
      return;
    }

    try {
      let requestId = currentRequestId;

      // EmergencyRequest가 없으면 먼저 생성
      if (!requestId && currentUser) {
        console.log("EmergencyRequest가 없어서 먼저 생성합니다...");
        try {
          // STT 텍스트에서 환자 정보 통합 파싱 (개선된 버전)
          const parsedInfo = parsePatientInfoFromText(sttText);
          
          // 통합 파싱 결과 우선 사용, 실패 시 개별 함수로 재시도
          let patientAgeFromStt = parsedInfo.age;
          let patientSexFromStt = parsedInfo.sex;
          let preKtasLevel = parsedInfo.preKtas;
          
          // 통합 파싱에서 실패한 항목만 개별 함수로 재시도
          if (!patientAgeFromStt) {
            patientAgeFromStt = extractPatientAge(sttText);
          }
          if (!patientSexFromStt) {
            patientSexFromStt = extractPatientSex(sttText);
          }
          if (!preKtasLevel) {
            preKtasLevel = extractPreKtasLevel(sttText);
          }
          
          // STT에서 추출 실패 시 사용자 선택값 사용, 그래도 없으면 기본값
          const patientAge = patientAgeFromStt || extractPatientAge(patientAgeBand) || 30;
          const patientSexValue = patientSexFromStt || (patientSex === "male" ? "M" : patientSex === "female" ? "F" : "M");
          
          if (!coords.lat || !coords.lon) {
            throw new Error("좌표 정보가 없습니다.");
          }

          const emergencyRequest = await createEmergencyRequest({
            team_id: currentUser.team_id!,
            patient_sex: patientSexValue,
            patient_age: patientAge,
            pre_ktas_class: preKtasLevel || 3,
            stt_full_text: sttText,
            rag_summary: sbarText,
            current_lat: coords.lat,
            current_lon: coords.lon,
          });
          requestId = emergencyRequest.request_id;
          setCurrentRequestId(requestId);
          console.log("EmergencyRequest 생성됨:", requestId);
        } catch (error) {
          console.error("EmergencyRequest 생성 실패:", error);
          // EmergencyRequest 생성 실패해도 채팅 패널은 열기 (로컬 모드)
          handleOpenChat(hospital);
          return;
        }
      }

      if (!requestId) {
        console.warn("EmergencyRequest를 생성할 수 없어 로컬 모드로 진행합니다.");
        handleOpenChat(hospital);
        return;
      }

      console.log("병원 승인 시작:", {
        request_id: requestId,
        hospital_id: hospital.hpid,
        hospital_name: hospital.dutyName,
      });

      // RequestAssignment 생성
      const assignment = await callHospital({
        request_id: requestId,
        hospital_id: hospital.hpid,
        distance_km: typeof hospital.distance_km === "number" ? hospital.distance_km : typeof hospital.distance_km === "string" ? parseFloat(hospital.distance_km) : undefined,
        eta_minutes: hospital.eta_minutes,
      });

      console.log("RequestAssignment 생성됨:", assignment.assignment_id, assignment);

      // 승인 상태 업데이트 (ChatSession 자동 생성됨)
      const updated = await updateResponseStatus({
        assignment_id: assignment.assignment_id,
        response_status: "승인",
      });

      console.log("병원 승인 완료, 응답 상태:", updated);

      // 응답에 session_id가 포함되어 있으면 바로 사용
      if (updated.session_id) {
        console.log("ChatSession이 응답에 포함됨:", updated.session_id);
        // 채팅 패널 열기 (실제 DB sessionId 포함)
        handleOpenChat(hospital, updated.session_id, updated.request_id || requestId, updated.assignment_id || assignment.assignment_id);
      } else {
        // session_id가 없으면 조회 시도 (여러 번 시도)
        console.log("응답에 session_id가 없어서 조회 시도...");
        let dbSession = null;
        for (let i = 0; i < 5; i++) {
          dbSession = await getChatSession(requestId, assignment.assignment_id);
          if (dbSession) {
            console.log("ChatSession 조회 성공:", dbSession);
            break;
          }
          console.log(`ChatSession 조회 시도 ${i + 1}/5 실패, 1초 후 재시도...`);
          await new Promise((resolve) => setTimeout(resolve, 1000));
        }

        if (dbSession) {
          // 채팅 패널 열기 (실제 DB sessionId 포함)
          handleOpenChat(hospital, dbSession.session_id, requestId, assignment.assignment_id);
        } else {
          console.warn("ChatSession을 찾을 수 없지만 채팅 패널은 열기");
          // ChatSession이 없어도 채팅 패널은 열기
          handleOpenChat(hospital, undefined, requestId, assignment.assignment_id);
        }
      }
    } catch (error) {
      console.error("병원 승인 처리 실패:", error);
      // 실패해도 채팅 패널은 열기
      handleOpenChat(hospital);
    }
  };

  const handleOpenChat = async (hospital: Hospital, dbSessionId?: number, requestId?: number, assignmentId?: number) => {
    // 채팅 슬라이드 패널 열기
    if (hospital.hpid && hospital.dutyName) {
      const sessionId = `session-${hospital.hpid}-${Date.now()}`;
      const regionLabel = hospital.dutyEmclsName || hospital.dutyDivNam || "응급의료기관";

      // 실제 DB의 ChatSession 조회 시도
      let finalSessionId: number | undefined = dbSessionId;
      const finalRequestId = requestId || currentRequestId;
      const finalAssignmentId = assignmentId;

      // sessionId가 없고 requestId나 assignmentId가 있으면 조회 시도
      if (!finalSessionId && (finalRequestId || finalAssignmentId)) {
        console.log("ChatSession 조회 시도:", { finalRequestId, finalAssignmentId });
        try {
          // 여러 번 시도 (최대 5번)
          for (let i = 0; i < 5; i++) {
            const dbSession = await getChatSession(finalRequestId, finalAssignmentId);
            if (dbSession) {
              finalSessionId = dbSession.session_id;
              console.log("ChatSession 조회 성공:", finalSessionId);
              break;
            }
            if (i < 4) {
              console.log(`ChatSession 조회 시도 ${i + 1}/5 실패, 1초 후 재시도...`);
              await new Promise((resolve) => setTimeout(resolve, 1000));
            }
          }
          if (!finalSessionId) {
            console.warn("ChatSession을 찾을 수 없습니다. 로컬 모드로 진행합니다.");
          }
        } catch (error) {
          console.error("ChatSession 조회 실패:", error);
        }
      }

      console.log("채팅 패널 열기:", {
        sessionId: finalSessionId,
        requestId: finalRequestId,
        assignmentId: finalAssignmentId,
      });

      // 재접속한 경우에도 지도 경로/ETA가 보이도록 승인 병원 및 경로 정보 갱신
      if (hospital.wgs84Lat && hospital.wgs84Lon) {
        setApprovedHospital(hospital);
        try {
          // 현재 위치와 병원 좌표를 기반으로 경로/ETA 재계산
          fetchRoutePaths([hospital], {
            append: true,
            updateDistances: true,
            updateApproved: true,
          });
        } catch (e) {
          console.warn("재접속 세션 경로 계산 중 오류:", e);
        }
      }

      setChatSession({
        id: sessionId,
        hospitalName: hospital.dutyName,
        regionLabel: regionLabel,
        status: "ONGOING",
        sessionId: finalSessionId,
        requestId: finalRequestId || undefined,
        assignmentId: finalAssignmentId || undefined,
      });
      setIsChatOpen(true);
    }
  };

  const handleRejectHospital = (hospital: Hospital) => {
    setHospitalApprovalStatus((prev) => ({ ...prev, [hospital.hpid || ""]: "rejected" }));
    setRejectedHospitals((prev) => new Set([...prev, hospital.hpid || ""]));
    setActiveCalls((prev) => {
      const updated = { ...prev };
      delete updated[hospital.hpid || ""];
      return updated;
    });
    setCurrentHospitalIndex((prev) => prev + 1);
  };

  // Socket.IO 이벤트 리스너: 병원 승인/거절 실시간 알림
  useEffect(() => {
    const socket = getSocket();
    
    const handleHospitalApproved = async (data: {
      request_id: number;
      assignment_id: number;
      hospital_id: string;
      call_sid: string;
    }) => {
      console.log("📞 Socket.IO: 병원 승인 알림 수신:", data);
      
      // 해당 병원 찾기
      const approvedHospital = hospitals.find((h) => h.hpid === data.hospital_id);
      if (!approvedHospital) {
        console.warn("승인된 병원을 목록에서 찾을 수 없습니다:", data.hospital_id);
        return;
      }
      
      // 자동 전화 즉시 중단
      setTwilioAutoCalling(false);
      setActiveCalls({});
      
      // 병원 승인 처리
      await handleApproveHospital(approvedHospital);
    };
    
    const handleHospitalRejected = (data: {
      request_id: number;
      assignment_id: number;
      hospital_id: string;
      call_sid: string;
    }) => {
      console.log("📞 Socket.IO: 병원 거절 알림 수신:", data);
      
      // 해당 병원 찾아서 거절 처리
      const rejectedHospital = hospitals.find((h) => h.hpid === data.hospital_id);
      if (rejectedHospital) {
        handleRejectHospital(rejectedHospital);
      }
    };
    
    socket.on("hospital_approved", handleHospitalApproved);
    socket.on("hospital_rejected", handleHospitalRejected);
    
    return () => {
      socket.off("hospital_approved", handleHospitalApproved);
      socket.off("hospital_rejected", handleHospitalRejected);
    };
  }, [hospitals]);

  const FALLBACK_TWILIO_NUMBER = "010-4787-1547";
  // ARS용 환자 정보: 사용자가 선택한 STT 원문 또는 SBAR 텍스트를 우선 사용
  // - STT/SBAR가 없으면 중증 탭에서 선택한 정보(Pre-KTAS, 성별, 나이대, 증상)를 기반으로 ARS 메시지 생성
  // - Pre-KTAS 표기는 음성에서 자연스럽게 읽히도록 "프리케이타스"로 변환
  // - "프리케이타스"와 "Pre-KTAS" 중복 제거, "프리케이타스 X점" 형태로만 표시
  const buildPatientInfo = () => {
    const normalizePreKtas = (text: string) => {
      // "프리케이타스"로 시작하는 부분을 찾아서 숫자만 추출하고 "프리케이타스 X점" 형태로 교체
      // 예: "프리케이타스 Pre-KTAS 1단계·긴급점" → "프리케이타스 1점"
      const preKtasMatch = text.match(/프리케이타스[^\d]*(\d+)/);
      if (preKtasMatch) {
        const level = preKtasMatch[1];
        // "프리케이타스"로 시작해서 쉼표, 공백, 또는 문장 끝까지의 모든 텍스트를 "프리케이타스 X점"으로 교체
        // 더 포괄적인 패턴: "프리케이타스" 뒤에 오는 모든 문자(공백 포함)를 매칭하되, 쉼표나 문장 끝에서 멈춤
        text = text.replace(/프리케이타스[^,]*?(\d+)[^,]*/g, `프리케이타스 ${level}점`);
      }
      
      // 모든 Pre-KTAS 변형을 제거 (혹시 남아있을 수 있는 영문 표기 완전 제거)
      text = text.replace(/Pre[-\s]?KTAS/gi, "");
      // "프리케이타스 프리케이타스" 같은 중복 제거
      text = text.replace(/프리케이타스\s+프리케이타스/g, "프리케이타스");
      // 연속된 공백 정리
      text = text.replace(/\s+/g, " ").trim();
      return text;
    };

    const stt = sttText?.trim() || "";
    const sbar = sbarText?.trim() || "";

    // 중증탭 모드: SBAR가 있으면 SBAR 앞에 프리케이타스 붙여서 사용, 없으면 STT 사용
    if (inputMode === "critical") {
      if (sbar) {
        // Pre-KTAS 점수 추출
        let preKtasLevel: number | undefined = extractPreKtasLevel(sttText);
        if (!preKtasLevel) {
          const presetMatch = CRITICAL_PRESETS.find(p => p.label === symptom)?.preKtasLevel?.match(/\d+/);
          if (presetMatch) {
            preKtasLevel = parseInt(presetMatch[0]);
          }
        }
        
        // SBAR 앞에 프리케이타스 붙이기
        const normalizedSbar = normalizePreKtas(sbar);
        if (preKtasLevel) {
          // SBAR에 이미 프리케이타스가 포함되어 있지 않으면 앞에 붙이기
          if (!normalizedSbar.includes("프리케이타스")) {
            return `프리케이타스 ${preKtasLevel}점 ${normalizedSbar}`;
          }
        }
        return normalizedSbar;
      } else if (stt) {
        // SBAR 변환이 완료되지 않았으면 STT 텍스트 사용
        return normalizePreKtas(stt);
      }
    }

    // STT/SBAR 텍스트가 있으면 우선 사용
    if (arsSource === "sbar" && sbar) {
      return normalizePreKtas(sbar);
    }
    if (arsSource === "stt" && stt) {
      return normalizePreKtas(stt);
    }
    if (stt) {
      return normalizePreKtas(stt);
    }

    // STT/SBAR 텍스트가 없으면 중증 탭에서 선택한 정보를 기반으로 ARS 메시지 생성
    // 형식: "현재 {프리케이타스 1~5단계} {나이대} {성별} {중증 종류}"
    const parts: string[] = ["현재"];
    
    // 1. Pre-KTAS 점수
    let preKtasLevel: number | undefined = extractPreKtasLevel(sttText);
    if (!preKtasLevel) {
      const presetMatch = CRITICAL_PRESETS.find(p => p.label === symptom)?.preKtasLevel?.match(/\d+/);
      if (presetMatch) {
        preKtasLevel = parseInt(presetMatch[0]);
      }
    }
    if (preKtasLevel) {
      parts.push(`프리케이타스 ${preKtasLevel}점`);
    }
    
    // 2. 나이대
    if (patientAgeBand) {
      parts.push(patientAgeBand);
    }
    
    // 3. 성별
    if (patientSex === "male") {
      parts.push("남성");
    } else if (patientSex === "female") {
      parts.push("여성");
    }
    
    // 4. 중증 종류 (증상)
    if (symptom) {
      parts.push(symptom);
    }
    
    if (parts.length > 1) { // "현재" 외에 다른 정보가 있으면
      return parts.join(" ");
    }
    
    // 모든 정보가 없으면 빈 문자열 반환 (백엔드에서 기본 멘트 처리)
    return "";
  };

  // [실제 Twilio 전화 기능 - 필요시 주석 해제하여 사용]
  // 실제 Twilio 전화 기능은 테스트 완료. 테스트 환경에서는 수동 버튼 사용.
  const handleStartTwilioCall = async (hospital: Hospital) => {
    // 모든 자동 전화는 지정된 안전 테스트 번호로 우회
    try {
      setHospitalApprovalStatus((prev) => ({ ...prev, [hospital.hpid || ""]: "calling" }));
      const result = await makeCall(
        FALLBACK_TWILIO_NUMBER, // 모든 전화는 테스트 번호로만 전송
        hospital.dutyName || "",
        buildPatientInfo() || sttText || null,
        undefined // ngrok URL은 선택사항
      );

      // 11/29 추가: callHospital 호출 -> DB에 매칭 저장/갱신
      /*  
        승인된 병원 카드에서 getChatSession으로 session_id를 받아 ParamedicChatSlideOver에 넘기면 ER 대시보드와 같은 세션을 공유
      */
      await callHospital({
        request_id: currentRequestId,
        hospital_id: hospital.hpid!, // ! -> hpid 필수값으로 명시
        distance_km: typeof hospital.distance_km === "number" ? hospital.distance_km : undefined,
        eta_minutes: hospital.eta_minutes,
        twilio_sid: result.call_sid,
      });

      if (result.call_sid) {
        setActiveCalls((prev) => ({
          ...prev,
          [hospital.hpid || ""]: {
            call_sid: result.call_sid,
            start_time: Date.now(),
          },
        }));
        const timeoutKey = hospital.hpid || "";
        if (callTimeoutsRef.current[timeoutKey]) {
          clearTimeout(callTimeoutsRef.current[timeoutKey]);
        }
        // 전화 타임아웃: ARS 메시지 길이에 따라 동적으로 설정 (최소 90초, 최대 180초)
        // ARS 메시지가 길 경우를 대비해 충분한 시간 제공
        // 한글 기준 대략 1초에 3-4자 재생, ARS 재생 시간 + 사용자 입력 대기 시간 고려
        const patientInfoText = buildPatientInfo() || sttText || "";
        const estimatedArsSeconds = Math.max(30, Math.min(90, Math.ceil(patientInfoText.length / 3))); // ARS 재생 예상 시간 (초)
        const totalTimeoutSeconds = Math.max(90, Math.min(180, estimatedArsSeconds + 60)); // ARS 재생 + 입력 대기 (최소 90초, 최대 180초)
        const totalTimeoutMs = totalTimeoutSeconds * 1000;
        console.log(`⏱️ 전화 타임아웃 설정: ${totalTimeoutSeconds}초 (ARS 메시지 길이: ${patientInfoText.length}자, 예상 재생: ${estimatedArsSeconds}초)`);
        callTimeoutsRef.current[timeoutKey] = setTimeout(() => {
          console.log(`⏱️ 전화 타임아웃: ${hospital.dutyName} (${timeoutKey})`);
          completeCallAndMoveNext(hospital, "rejected");
        }, totalTimeoutMs);
      }
    } catch (error: any) {
      console.error("전화 연결 오류:", error);
      alert(error.message || "전화 연결 중 오류가 발생했습니다.");
      setHospitalApprovalStatus((prev) => ({ ...prev, [hospital.hpid || ""]: "pending" }));
    }
  };

  const completeCallAndMoveNext = (hospital: Hospital, decision: "approved" | "rejected") => {
    const timeoutKey = hospital.hpid || "";
    const existingTimer = callTimeoutsRef.current[timeoutKey];
    if (existingTimer) {
      clearTimeout(existingTimer);
      delete callTimeoutsRef.current[timeoutKey];
    }
    if (decision === "approved") {
      handleApproveHospital(hospital);
    } else {
      handleRejectHospital(hospital);
    }
    setActiveCalls((prev) => {
      const newCalls = { ...prev };
      delete newCalls[hospital.hpid || ""];
      return newCalls;
    });
  };

  const checkCallResponse = async (hospital: Hospital) => {
    const callInfo = activeCalls[hospital.hpid || ""];
    if (!callInfo) return;
    try {
      const result = await getCallResponse(callInfo.call_sid);
      const decision = result?.digit === "1" ? "approved" : result?.digit === "2" ? "rejected" : null;
      const status = result?.status;

      // 승인/거절 응답이 있으면 처리
      if (decision) {
        completeCallAndMoveNext(hospital, decision);
        return;
      }

      // 전화 상태가 실제 실패 상태일 때만 거절 처리
      // "completed"는 통화 완료 상태일 뿐 거절이 아니므로 제외
      // "ringing", "in-progress"는 통화 진행 중이므로 기다림
      if (status && ["busy", "failed", "no-answer", "canceled"].includes(status)) {
        completeCallAndMoveNext(hospital, "rejected");
      }
      // "completed" 상태는 다이얼 입력(digit) 확인 후 처리하므로 여기서는 무시
    } catch (e) {
      console.error("전화 응답 확인 실패:", e);
    }
  };

  useEffect(() => {
    // 활성 통화가 있으면 주기적으로 응답 확인
    const interval = setInterval(() => {
      hospitals.forEach((h) => {
        if (activeCalls[h.hpid || ""] && hospitalApprovalStatus[h.hpid || ""] === "calling") {
          checkCallResponse(h);
        }
      });
    }, 2000);
    return () => clearInterval(interval);
  }, [hospitals, activeCalls, hospitalApprovalStatus]);

  // 자동 전화 기능: 병원 승인 시 자동으로 다음 병원으로 전화
  useEffect(() => {
    if (!twilioAutoCalling || approvedHospital || currentHospitalIndex >= hospitals.length) {
      return;
    }

    const currentHospital = hospitals[currentHospitalIndex];
    if (!currentHospital) return;

    // 이미 거절된 병원이면 스킵
    if (rejectedHospitals.has(currentHospital.hpid || "")) {
      return;
    }

    // 이미 전화 중이면 스킵
    if (activeCalls[currentHospital.hpid || ""]) {
      return;
    }

    let timer: ReturnType<typeof setTimeout> | null = null;
    // 첫 번째 병원은 바로 발신, 이후 병원들은 약간의 간격(10초) 후 자동 발신
    const delayMs = currentHospitalIndex === 0 ? 0 : 10000;
    if (delayMs === 0) {
      void handleStartTwilioCall(currentHospital);
    } else {
      timer = setTimeout(() => {
        handleStartTwilioCall(currentHospital);
      }, delayMs);
    }
    
    return () => {
      if (timer) clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [twilioAutoCalling, currentHospitalIndex, hospitals.length, approvedHospital, activeCalls, rejectedHospitals]);

  useEffect(() => {
    if (twilioAutoCalling && !hasCallableHospital) {
      setTwilioAutoCalling(false);
      setActiveCalls({});
    }
  }, [twilioAutoCalling, hasCallableHospital]);

  // 거절 시 백업 병원 자동 추가 및 파이프라인 유지
  useEffect(() => {
    if (!hospitals.length) {
      return;
    }

    const firstAvailableIdx = hospitals.findIndex((hospital) => !rejectedHospitals.has(hospital.hpid || ""));

    if (firstAvailableIdx >= 0) {
      if (currentHospitalIndex !== firstAvailableIdx) {
        setCurrentHospitalIndex(firstAvailableIdx);
      }
      setHasExhaustedHospitals(false);
      return;
    }

    let cancelled = false;

    const hydrateNextHospital = async () => {
      const existingIds = new Set(hospitals.map((h) => h.hpid));
      const collectNew = (source: Hospital[]) =>
        source.filter((candidate) => {
          const id = candidate.hpid || "";
          return id && !existingIds.has(id) && !rejectedHospitals.has(id);
        });

      const backupOptions = collectNew(backupHospitals);
      if (backupOptions.length > 0) {
        const nextCandidate = backupOptions[0];
        setHospitals((prev) => {
          // 중복 체크: 이미 존재하는 hpid면 추가하지 않음
          const exists = prev.some((h) => h.hpid === nextCandidate.hpid);
          return exists ? prev : [...prev, nextCandidate];
        });
        await fetchRoutePaths([nextCandidate], { append: true, updateDistances: true });
        if (!cancelled) {
          setHasExhaustedHospitals(false);
        }
        return;
      }

      const neighborOptions = collectNew(neighborHospitals);
      if (neighborOptions.length > 0) {
        setHospitals((prev) => {
          // 중복 체크: 이미 존재하는 hpid는 제외
          const existingIds = new Set(prev.map((h) => h.hpid));
          const newOptions = neighborOptions.filter((h) => !existingIds.has(h.hpid));
          return [...prev, ...newOptions];
        });
        await fetchRoutePaths(neighborOptions, { append: true, updateDistances: true });
        if (!cancelled) {
          setHasExhaustedHospitals(false);
        }
        return;
      }

      if (!cancelled) {
        setHasExhaustedHospitals(true);
      }
    };

    hydrateNextHospital();

    return () => {
      cancelled = true;
    };
  }, [hospitals, rejectedHospitals, backupHospitals, neighborHospitals, fetchRoutePaths, currentHospitalIndex]);

  useEffect(() => {
    if (hasExhaustedHospitals) {
      setTwilioAutoCalling(false);
      setActiveCalls({});
    }
  }, [hasExhaustedHospitals]);

  // 11/29 추가: 자동으로 현재 좌표 잡는 것과 수동으로 좌표 잡는거 상태관리 변수 함께 업데이트 하기위한 헬퍼 함수
  const getPosition = (opts: PositionOptions) =>
    new Promise<GeolocationPosition>((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(resolve, reject, opts);
    });

  const fetchCoordsWithFallback = async () => {
    const highAccuracy: PositionOptions = { enableHighAccuracy: true, timeout: 20000, maximumAge: 5000 };
    const fallback: PositionOptions = { enableHighAccuracy: false, timeout: 15000, maximumAge: 20000 };
    try {
      try {
        return await getPosition(highAccuracy);
      } catch (err) {
        console.warn("고정 실패, 저정확도 재시도:", err);
        return await getPosition(fallback);
      }
    } catch (err) {
      throw err;
    }
  };

  /* 
    (첫 렌더링 이후)
    liveCoords와 Coords 상태관리 변수 마운트하고 데이터 상태 업데이트
  */

  const applyRegionFromCoords = async (lat: number, lon: number) => {
    const res = await coordToRegion(lat, lon);
    if (res) setRegion(res);
  };

  useEffect(() => {
    // ✅ HTTP 환경에서는 자동 위치 추적 비활성화 (위치 권한 팝업 반복 방지)
    const hostname = window.location.hostname;
    const protocol = window.location.protocol;
    const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1';
    const isLocalDomain = hostname.endsWith('.local'); // mDNS/Bonjour 도메인 지원
    const isSecure = protocol === 'https:';
    
    // HTTPS, localhost, 또는 .local 도메인이 아니면 자동 실행하지 않음
    // (예: http://10.50.1.62:5173 같은 로컬 IP 접속은 자동 실행 안 함)
    // .local 도메인은 Safari에서 일부 secure context로 인식될 수 있음
    if (!isSecure && !isLocalhost && !isLocalDomain) {
      console.log("HTTP 환경에서는 자동 위치 추적이 비활성화됩니다. GPS 버튼을 클릭하여 위치를 가져오세요.");
      return;
    }
    
    if (!navigator.geolocation) return;
    
    const id = navigator.geolocation.watchPosition(
      async (pos) => {
        const next = { lat: pos.coords.latitude, lon: pos.coords.longitude };
        setLiveCoords(next);
        setCoords(next); // 버튼/검색에서 쓰는 coords도 같이 업데이트
        if (!region) await applyRegionFromCoords(next.lat!, next.lon!);
      },
      (error) => {
        // 권한 거부 시 자동 실행 중단하여 팝업 반복 방지
        if (error.code === 1) {
          console.warn("위치 권한이 거부되었습니다. 자동 위치 추적을 중단합니다.");
          navigator.geolocation.clearWatch(id);
        }
      },
      { enableHighAccuracy: true, maximumAge: 5000 }
    );
    return () => navigator.geolocation.clearWatch(id);
  }, [region]);

  const currentPos = liveCoords.lat ? liveCoords : coords;

  return (
    <div className="relative min-h-screen bg-slate-100 text-slate-900">
      <header className="border-b border-slate-200 bg-white px-4 md:px-5 py-3 shadow-sm">
        <div className="max-w-6xl mx-auto flex items-center justify-between gap-4">
          <div>
            <h1 className="text-lg md:text-xl font-semibold tracking-tight text-slate-900">SAFE BRIDGE · 응급 이송 지원</h1>
            <p className="text-[11px] md:text-xs text-slate-500 mt-1">
              Pre-KTAS 기반 환자 상태 요약과 인근 응급의료기관 추천을 위한 태블릿 전용 화면입니다.
            </p>
          </div>
          <div className="flex items-center gap-3">
            {pendingChatSession && pendingChatSession.hospital && (
              <button
                type="button"
                onClick={() =>
                  handleOpenChat(
                    pendingChatSession.hospital as Hospital,
                    pendingChatSession.session_id,
                    pendingChatSession.request_id,
                    pendingChatSession.assignment_id
                  )
                }
                className="px-3 py-1 rounded-full bg-amber-100 text-[11px] text-amber-800 border border-amber-300 hover:bg-amber-200 whitespace-nowrap"
              >
                현재 환자인계가 정상적으로 종료되지 않은 채팅방이 존재합니다.{" "}
                <span className="underline font-semibold">바로가기</span>
              </button>
            )}
            {currentUser && (
              <div className="text-right text-[10px] md:text-[11px] text-slate-600">
                <div className="font-semibold">{currentUser.ems_id}</div>
                {currentUser.region && <div className="text-slate-400">{currentUser.region}</div>}
              </div>
            )}
            <button
              onClick={handleLogoutClick}
              className="px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition"
              title="로그아웃"
            >
              로그아웃
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 flex flex-col gap-6">
        <LocationInput
          address={address}
          setAddress={setAddress}
          coords={coords}
          region={region}
          loadingGps={loadingGps}
          onSearchAddress={handleSearchAddress}
          onGpsClick={handleGpsClick}
        />

        <PatientStatusInput
          sttText={sttText}
          setSttText={setSttText}
          sbarText={sbarText}
          setSbarText={setSbarText}
          symptom={symptom}
          setSymptom={setSymptom}
          arsSource={arsSource}
          setArsSource={setArsSource}
          inputMode={inputMode}
          setInputMode={setInputMode}
          isRecording={isRecording}
          onToggleRecording={handleToggleRecording}
          micLevel={micLevel}
          recordingError={recordingError}
          patientSex={patientSex}
          setPatientSex={setPatientSex}
          patientAgeBand={patientAgeBand}
          setPatientAgeBand={setPatientAgeBand}
        />

        <HospitalPrioritySelector
          priorityModes={priorityModes}
          onTogglePriority={(mode) => {
            setPriorityModes((prev) => (prev.includes(mode) ? prev.filter((m) => m !== mode) : [...prev, mode]));
          }}
        />

        <div className="bg-white rounded-2xl shadow-lg p-4 md:p-6 border border-slate-200">
          <div className="flex flex-col md:flex-row items-center gap-4">
            <div className="flex-1 text-center md:text-left">
              <p className="text-xs uppercase tracking-[0.2em] text-emerald-500 font-semibold mb-1">Emergency Dispatch</p>
              <h3 className="text-lg md:text-xl font-bold text-slate-900">응급환자 수용 가능 병원 탐색</h3>
              <p className="text-sm md:text-base text-slate-600 mt-1">버튼을 누르면 병원 조회와 동시에 Twilio ARS(010-4787-1547) 자동 통화가 연속으로 진행됩니다.</p>
            </div>
            <button
              className="w-full md:w-auto inline-flex items-center justify-center gap-3 rounded-2xl bg-gradient-to-r from-emerald-500 via-emerald-600 to-green-600 text-white px-6 md:px-10 py-5 text-base md:text-xl font-bold shadow-xl hover:from-emerald-600 hover:to-green-700 active:scale-[0.99] transition disabled:opacity-40 disabled:cursor-not-allowed"
              onClick={handleSearchHospitals}
              disabled={loadingHospitals || !coords.lat || !coords.lon || !region}
            >
              {loadingHospitals ? (
                <>
                  <span className="h-4 w-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
                  <span>병원 탐색 중...</span>
                </>
              ) : (
                <>
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 19V5M12 5l-4 4M12 5l4 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    <path d="M5 12a7 7 0 0 1 14 0v2a7 7 0 1 1-14 0v-2z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  <div className="text-left leading-tight">
                    <div>응급환자 수용 가능</div>
                    <div className="text-xs font-semibold text-emerald-100">검색 후 자동 ARS 연결</div>
                  </div>
                </>
              )}
            </button>
          </div>
        </div>

        {/* 우측: 근처 응급의료기관 리스트 */}
        {showHospitalPanel && (
        <section className="bg-white rounded-xl shadow-sm p-3 md:p-4 border border-slate-200 flex flex-col">
          <div className="flex items-center justify-between mb-2 md:mb-3">
            <div>
              <h2 className="text-sm md:text-base font-semibold">근처 응급의료기관 현황</h2>
                <p className="text-[10px] md:text-[11px] text-slate-500 mt-0.5">실제 서비스에서는 실시간 수용 가능 여부와 거리, 장비 여건 등을 함께 반영합니다.</p>
            </div>
            <div className="flex flex-col items-end gap-1">
              <span className="inline-flex items-center rounded-full border border-slate-300 bg-slate-50 px-2.5 py-1 text-[10px] md:text-[11px] text-slate-700">
                  우선조건: {priorityModes.map((m) => (m === "distance" ? "거리 우선" : m === "beds" ? "병상 여유 우선" : "장비·전담팀 우선")).join(" + ") || "거리 우선"}
              </span>
              <span className="text-[10px] md:text-[11px] text-slate-400">(목업 화면으로, 실제 알고리즘 연동 전 단계입니다.)</span>
            </div>
          </div>
            {!hospitals.length && <p className="text-xs md:text-sm text-slate-500">표시할 병원 정보가 없습니다.</p>}
          {!!hospitals.length && (
            <div className="mt-1 md:mt-3 overflow-hidden">
              <div className="flex overflow-x-auto snap-x snap-mandatory gap-5 pb-4 pr-4">
                {hospitals.map((h, idx) => (
                    <div key={h.hpid || idx} className="snap-center shrink-0 w-[calc(100vw-3rem)] md:w-[580px]">
                    <HospitalCard
                      hospital={h}
                      index={idx}
                      region={region}
                      approvalStatus={hospitalApprovalStatus[h.hpid || ""] || "pending"}
                      isRejected={rejectedHospitals.has(h.hpid || "")}
                      isActiveCandidate={!approvedHospital && idx === currentHospitalIndex}
                      canInteract={!approvedHospital}
                      onApprove={handleApproveHospital}
                      onReject={handleRejectHospital}
                      onStartCall={handleStartTwilioCall}
                      onOpenChat={handleOpenChat}
                    />
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
        )}
        
        {approvedHospital && <ApprovedHospitalInfo approvedHospital={approvedHospital} />}
        
        {!approvedHospital && coords.lat && coords.lon && displayedMapHospitals.length > 0 && (
          <MapDisplay coords={coords} hospitals={displayedMapHospitals} routePaths={routePaths} approvedHospital={approvedHospital} resolveHospitalColor={resolveHospitalColor} />
        )}
      </main>

      {/* 채팅 슬라이드 패널 */}
      {/* 채팅이 열려있으면 approvedHospital이 없어도 유지 (응급실과의 채팅이 계속 진행 중일 수 있음) */}
      {isChatOpen && chatSession && (
        <ParamedicChatSlideOver
          isOpen={isChatOpen}
          session={chatSession}
          hospital={
            approvedHospital ||
            (chatSession.hospitalName
              ? ({
                  hpid: chatSession.requestId?.toString() || "",
                  dutyName: chatSession.hospitalName || "병원",
                  dutyEmclsName: chatSession.regionLabel || "응급의료기관",
                  dutyDivNam: chatSession.regionLabel || "응급의료기관",
                  wgs84Lat: undefined,
                  wgs84Lon: undefined,
                } as Hospital)
              : null!)
          }
          patientMeta={{
            sessionId: chatSession.id,
            patientAge:
              extractPatientAge(sttText) ??
              (pendingChatSession &&
              pendingChatSession.session_id === chatSession.sessionId
                ? pendingChatSession.patient_age ?? undefined
                : undefined),
            patientSex:
              extractPatientSex(sttText) ??
              (pendingChatSession &&
              pendingChatSession.session_id === chatSession.sessionId
                ? (pendingChatSession.patient_sex as "M" | "F" | null) ?? undefined
                : undefined),
            preKtasLevel:
              extractPreKtasLevel(sttText) ??
              (pendingChatSession &&
              pendingChatSession.session_id === chatSession.sessionId
                ? (typeof pendingChatSession.pre_ktas_class === "string"
                    ? parseInt(pendingChatSession.pre_ktas_class, 10)
                    : pendingChatSession.pre_ktas_class ?? undefined)
                : undefined),
            chiefComplaint:
              symptom ||
              (pendingChatSession &&
              pendingChatSession.session_id === chatSession.sessionId
                ? pendingChatSession.rag_summary ?? undefined
                : undefined),
            vitalsSummary:
              sttText && sttText.trim()
                ? sttText.substring(0, 200)
                : pendingChatSession &&
                  pendingChatSession.session_id === chatSession.sessionId &&
                  pendingChatSession.stt_full_text
                ? pendingChatSession.stt_full_text.substring(0, 200)
                : undefined,
            etaMinutes: (() => {
              if (!approvedHospital) return undefined;
              const matched =
                hospitals.find((h) => h.hpid === approvedHospital.hpid) || approvedHospital;
              return matched?.eta_minutes;
            })(),
            distanceKm: (() => {
              if (!approvedHospital) return undefined;
              const matched =
                hospitals.find((h) => h.hpid === approvedHospital.hpid) || approvedHospital;
              if (typeof matched?.distance_km === "number") return matched.distance_km;
              if (typeof matched?.distance_km === "string")
                return parseFloat(matched.distance_km);
              return undefined;
            })(),
            lastUpdated: new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: false }),
          }}
          sttText={sttText}
          emsId={currentUser?.ems_id} // 로그인한 구급대원의 ems_id 전달
          mapCoords={currentPos}
          mapRoutePaths={routePaths}
          // resolveHospitalColor={resolveHospitalColor}
          onClose={() => setIsChatOpen(false)}
          onHandoverComplete={(sessionId) => {
            if (chatSession && chatSession.id === sessionId) {
              // 인계완료 후 화면 초기화
              handleResetAfterHandover();
            }
          }}
        />
      )}

      {/* 로그아웃 확인 모달 */}
      {showLogoutModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={handleLogoutCancel}>
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md mx-4" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-gray-900 mb-4">로그아웃</h3>
            <p className="text-gray-600 mb-6">로그아웃하시겠습니까?</p>
            <div className="flex justify-end gap-3">
              <button onClick={handleLogoutCancel} className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition">
                취소
              </button>
              <button onClick={handleLogoutConfirm} className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition">
                확인
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 감사 인사 푸터 - 작고 절제된 디자인 */}
      <footer className="border-t border-slate-200 bg-white mt-auto">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <p className="text-center text-[11px] text-slate-500 leading-relaxed">
            오늘도 생명의 불씨가 꺼지지 않게 노력하는 당신의 노고에 감사합니다.
          </p>
        </div>
      </footer>
    </div>
  );
};
