import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import type { Coords, Region, Hospital, ApprovalStatus, HospitalHandoverSummary, PatientTransportMeta } from "../types";
import { symptomOptions } from "../constants";
import { addressToCoord, coordToAddress, coordToRegion, searchHospitals, transcribeAudio, makeCall, getCallResponse, getRoute } from "../services/api";
import { detectPatientAgeGroup, extractPatientAge, extractPatientSex, extractPreKtasLevel } from "../utils/hospitalUtils";
import { LocationInput } from "./LocationInput";
import { PatientStatusInput } from "./PatientStatusInput";
import { HospitalSearchButtons } from "./SymptomSelector";
import { HospitalPrioritySelector } from "./HospitalPrioritySelector";
import type { PriorityMode } from "./HospitalPrioritySelector";
import { HospitalCard } from "./HospitalCard";
import { MapDisplay } from "./MapDisplay";
import { ApprovedHospitalInfo } from "./ApprovedHospitalInfo";
import { ParamedicChatSlideOver } from "./ParamedicChatSlideOver";

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
  const [activeCalls, setActiveCalls] = useState<Record<string, { call_sid: string; start_time: number }>>({});
  const [routePaths, setRoutePaths] = useState<Record<string, number[][]>>({});
  const [backupHospitals, setBackupHospitals] = useState<Hospital[]>([]);
  const [neighborHospitals, setNeighborHospitals] = useState<Hospital[]>([]);
  const [hasExhaustedHospitals, setHasExhaustedHospitals] = useState<boolean>(false);
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [recordingError, setRecordingError] = useState<string>("");
  const [isChatOpen, setIsChatOpen] = useState<boolean>(false);
  const [chatSession, setChatSession] = useState<HospitalHandoverSummary | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const colorMapRef = useRef<Record<string, string>>({});
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
      "정형외과 중증(대형골절/절단)",
      "신경외과 응급(의식저하/외상성출혈)",
    ];
    
    // 성인 전용 증상
    const adultOnlySymptoms = [
      "성인 호흡곤란",
      "성인 경련",
    ];
    
    // 소아 전용 증상
    const pediatricOnlySymptoms = [
      "소아 호흡곤란",
      "소아 경련",
      "소아 중증(신생아/영아)",
    ];
    
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
      const position = await new Promise<GeolocationPosition>((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, { 
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 0
        });
      });
      
      const { latitude, longitude } = position.coords;
      console.log("GPS 좌표 획득:", latitude, longitude);
      setCoords({ lat: latitude, lon: longitude });
      
      // 주소 및 행정구역 역변환 (병렬 처리)
      try {
        const [addressResult, regionResult] = await Promise.allSettled([
          coordToAddress(latitude, longitude),
          coordToRegion(latitude, longitude),
        ]);
        
        // 주소 설정
        if (addressResult.status === "fulfilled" && addressResult.value) {
          console.log("주소 변환 성공:", addressResult.value);
          setAddress(addressResult.value);
        } else {
          const error = addressResult.status === "rejected" ? addressResult.reason : null;
          const errorMsg = error?.message || (error ? String(error) : "결과 없음");
          console.warn("주소 변환 실패:", errorMsg);
          
          // CORS 오류나 서버 연결 실패 시 사용자에게 알림
          if (error && (error?.code === 'ERR_NETWORK' || error?.message?.includes('CORS') || error?.code === 'ECONNREFUSED')) {
            console.warn("백엔드 API 서버에 연결할 수 없습니다. 백엔드 서버가 실행 중인지 확인해주세요.");
            // 좌표는 설정되었지만 주소는 없음
          }
        }
        
        // 행정구역 설정
        if (regionResult.status === "fulfilled" && regionResult.value) {
          console.log("행정구역 변환 성공:", regionResult.value);
          setRegion(regionResult.value);
        } else {
          const error = regionResult.status === "rejected" ? regionResult.reason : null;
          const errorMsg = error?.message || (error ? String(error) : "결과 없음");
          console.warn("행정구역 변환 실패:", errorMsg);
          
          // CORS 오류나 서버 연결 실패 시 사용자에게 알림
          if (error && (error?.code === 'ERR_NETWORK' || error?.message?.includes('CORS') || error?.code === 'ECONNREFUSED')) {
            console.warn("백엔드 API 서버에 연결할 수 없습니다. 백엔드 서버가 실행 중인지 확인해주세요.");
            // 좌표는 설정되었지만 행정구역은 없음
          }
        }
        
        // 좌표는 설정되었지만 주소나 행정구역이 없을 때 사용자에게 알림
        const hasAddress = addressResult.status === "fulfilled" && addressResult.value;
        const hasRegion = regionResult.status === "fulfilled" && regionResult.value;
        
        if (!hasAddress || !hasRegion) {
          const missingItems = [];
          if (!hasAddress) missingItems.push("주소");
          if (!hasRegion) missingItems.push("행정구역");
          
          console.warn(`좌표는 설정되었지만 ${missingItems.join(", ")}를 가져올 수 없습니다. 백엔드 API 서버가 실행 중인지 확인해주세요.`);
        }
      } catch (error: any) {
        console.error("주소/행정구역 변환 중 오류:", error);
        // 좌표는 이미 설정되었으므로 사용자에게 알림만 표시
        if (error?.code === 'ECONNREFUSED' || error?.response?.status === 404) {
          console.warn("백엔드 API 서버가 실행되지 않았습니다. 좌표만 설정되었습니다.");
        }
      }
    } catch (err: any) {
      console.error("GPS 위치 정보 오류:", err);
      if (err.code === 1) {
        alert("위치 권한이 거부되었습니다. 브라우저 설정에서 위치 권한을 허용해주세요.");
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
        alert(`${errorMsg}\n\n팁:\n- 더 구체적인 주소를 입력해보세요 (예: "광주광역시 광산구 신가동")\n- 도로명 주소를 사용해보세요 (예: "광주광역시 광산구 첨단중앙로 123")\n- 백엔드 서버가 실행 중인지 확인해주세요`);
      } else {
        alert(`${errorMsg}\n\n백엔드 서버가 실행 중인지 확인해주세요.`);
      }
    }
  };

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
      setLoadingHospitals(true);
      setRerollCount((prev) => prev + 1);
      setHospitalApprovalStatus({});
      setRejectedHospitals(new Set());
      setApprovedHospital(null);
      setRoutePaths({});
      setBackupHospitals([]);
      setNeighborHospitals([]);
      setHasExhaustedHospitals(false);
      setTwilioAutoCalling(false);
      setCurrentHospitalIndex(0);
      setActiveCalls({});
      colorMapRef.current = {};
      
      // 증상에 따라 자동으로 병원 타입 결정
      // 다발성 외상/중증 외상 → 외상센터 우선, 그 외 → 일반 (백엔드에서 자동 처리)
      const result = await searchHospitals(
        coords.lat,
        coords.lon,
        region.sido,
        region.sigungu,
        symptom,
        sttText || null
      );
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
      } else {
        await fetchRoutePaths(fetchedHospitals);
      }
    } catch (error: any) {
      console.error("병원 조회 오류:", error);
      alert(error.message || "병원 조회 중 오류가 발생했습니다. 백엔드 서버가 실행 중인지 확인해주세요.");
    } finally {
      setLoadingHospitals(false);
    }
  };

  const fetchRoutePaths = useCallback(
    async (targetHospitals: Hospital[], options?: { append?: boolean }) => {
      if (!coords.lat || !coords.lon || !targetHospitals?.length) return;
      
      const paths: Record<string, number[][]> = {};
      for (const hospital of targetHospitals) {
        if (hospital.wgs84Lat && hospital.wgs84Lon) {
          try {
            const result = await getRoute(
              coords.lat!,
              coords.lon!,
              hospital.wgs84Lat,
              hospital.wgs84Lon
            );
            if (result?.path_coords) {
              paths[hospital.hpid || ""] = result.path_coords;
            }
          } catch (e) {
            console.error("경로 조회 실패:", e);
          }
        }
      }
      setRoutePaths((prev) => (options?.append ? { ...prev, ...paths } : paths));
    },
    [coords.lat, coords.lon]
  );

  useEffect(() => {
    if (!approvedHospital || !approvedHospital.hpid) return;
    if (routePaths[approvedHospital.hpid]) return;
    fetchRoutePaths([approvedHospital], { append: true });
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
      const text = await transcribeAudio(audioFile);
      if (text) {
        setSttText(text);
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
          const text = await transcribeAudio(audioFile);
          if (text) {
            setSttText(text);
            setVoiceMode(false);
          } else {
            alert("음성 인식 결과가 없습니다.");
          }
        } catch (error: any) {
          console.error("음성 인식 오류:", error);
          alert(error.message || "음성 인식 중 오류가 발생했습니다.");
        }
        
        // 스트림 정리
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
      setRecordingError("");
    } catch (error: any) {
      console.error("마이크 접근 오류:", error);
      setRecordingError("마이크 권한이 필요합니다. 브라우저 설정에서 마이크 권한을 허용해주세요.");
      setIsRecording(false);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
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

  const handleApproveHospital = (hospital: Hospital) => {
    setHospitalApprovalStatus((prev) => ({ ...prev, [hospital.hpid || ""]: "approved" }));
    setApprovedHospital(hospital);
    setTwilioAutoCalling(false);
    setActiveCalls({});
    // 승인 후 채팅 패널 자동으로 열기
    handleOpenChat(hospital);
  };

  const handleOpenChat = (hospital: Hospital) => {
    // 채팅 슬라이드 패널 열기
    if (hospital.hpid && hospital.dutyName) {
      const sessionId = `session-${hospital.hpid}-${Date.now()}`;
      const regionLabel = hospital.dutyEmclsName || hospital.dutyDivNam || "응급의료기관";
      setChatSession({
        id: sessionId,
        hospitalName: hospital.dutyName,
        regionLabel: regionLabel,
        status: "ONGOING",
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

  const handleStartTwilioCall = async (hospital: Hospital) => {
    // ngrok URL은 선택사항이므로 제거
    try {
      setHospitalApprovalStatus((prev) => ({ ...prev, [hospital.hpid || ""]: "calling" }));
      const result = await makeCall(
        hospital.dutytel3 || "",
        hospital.dutyName || "",
        sttText || null,
        undefined  // ngrok URL은 선택사항
      );
      if (result.call_sid) {
        setActiveCalls((prev) => ({
          ...prev,
          [hospital.hpid || ""]: {
            call_sid: result.call_sid,
            start_time: Date.now(),
          },
        }));
      }
    } catch (error: any) {
      console.error("전화 연결 오류:", error);
      alert(error.message || "전화 연결 중 오류가 발생했습니다.");
      setHospitalApprovalStatus((prev) => ({ ...prev, [hospital.hpid || ""]: "pending" }));
    }
  };

  const checkCallResponse = async (hospital: Hospital) => {
    const callInfo = activeCalls[hospital.hpid || ""];
    if (!callInfo) return;
    try {
      const result = await getCallResponse(callInfo.call_sid);
      if (result?.digit) {
        if (result.digit === "1") {
          handleApproveHospital(hospital);
        } else if (result.digit === "2") {
          handleRejectHospital(hospital);
        }
        setActiveCalls((prev) => {
          const newCalls = { ...prev };
          delete newCalls[hospital.hpid || ""];
          return newCalls;
        });
      }
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


  // Twilio 자동 전화 로직
  useEffect(() => {
    if (!twilioAutoCalling || approvedHospital || currentHospitalIndex >= hospitals.length) {
      return;
    }

    const currentHospital = hospitals[currentHospitalIndex];
    if (!currentHospital) return;

    // 아직 전화를 걸지 않았다면
    if (!activeCalls[currentHospital.hpid || ""]) {
      handleStartTwilioCall(currentHospital);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [twilioAutoCalling, currentHospitalIndex, hospitals.length, approvedHospital]);

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

    const firstAvailableIdx = hospitals.findIndex(
      (hospital) => !rejectedHospitals.has(hospital.hpid || "")
    );

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
        await fetchRoutePaths([nextCandidate], { append: true });
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
        await fetchRoutePaths(neighborOptions, { append: true });
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


  return (
    <div className="relative min-h-screen bg-slate-100 text-slate-900">
      <header className="border-b border-slate-200 bg-white px-4 md:px-5 py-3 shadow-sm">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-lg md:text-xl font-semibold tracking-tight text-slate-900">
              SAFE BRIDGE · 응급 이송 지원
            </h1>
            <p className="text-[11px] md:text-xs text-slate-500 mt-1">
              Pre-KTAS 기반 환자 상태 요약과 인근 응급의료기관 추천을 위한 태블릿 전용 화면입니다.
            </p>
          </div>
          <div className="text-right text-[10px] md:text-[11px] text-slate-400 leading-snug">
            <div>Mock UI · 실제 환자 이송에 사용 금지</div>
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
        />

        <HospitalPrioritySelector
          priorityModes={priorityModes}
          onTogglePriority={(mode) => {
            setPriorityModes((prev) =>
              prev.includes(mode) ? prev.filter((m) => m !== mode) : [...prev, mode]
            );
          }}
        />

        <div className="bg-white rounded-xl shadow-sm p-3 md:p-4 border border-slate-200">
          <div className="flex justify-center">
            <button
              className="inline-flex items-center rounded-lg bg-emerald-600 text-white px-6 py-3 text-sm md:text-base font-semibold shadow-sm hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed"
              onClick={handleSearchHospitals}
              disabled={loadingHospitals || !coords.lat || !coords.lon || !region}
            >
              {loadingHospitals ? "병원 탐색 중..." : "응급환자 수용 가능 병원 찾기"}
            </button>
          </div>
        </div>

        {/* 우측: 근처 응급의료기관 리스트 */}
        <section className="bg-white rounded-xl shadow-sm p-3 md:p-4 border border-slate-200 flex flex-col h-[420px] md:h-[460px]">
          <div className="flex items-center justify-between mb-2 md:mb-3">
            <div>
              <h2 className="text-sm md:text-base font-semibold">근처 응급의료기관 수용 가능 확인중</h2>
              <p className="text-[10px] md:text-[11px] text-slate-500 mt-0.5">
                실제 서비스에서는 실시간 수용 가능 여부와 거리, 장비 여건 등을 함께 반영합니다.
              </p>
            </div>
            <div className="flex flex-col items-end gap-1">
              <span className="inline-flex items-center rounded-full border border-slate-300 bg-slate-50 px-2.5 py-1 text-[10px] md:text-[11px] text-slate-700">
                우선조건: {priorityModes.map(m => m === "distance" ? "거리 우선" : m === "beds" ? "병상 여유 우선" : "장비·전담팀 우선").join(" + ") || "거리 우선"}
              </span>
              <span className="text-[10px] md:text-[11px] text-slate-400">(목업 화면으로, 실제 알고리즘 연동 전 단계입니다.)</span>
            </div>
          </div>
          {!hospitals.length && (
            <p className="text-xs md:text-sm text-slate-500">표시할 병원 정보가 없습니다.</p>
          )}
          <div className="mt-1 md:mt-2 flex-1 overflow-y-auto pr-1 space-y-3">
            {hospitals.map((h, idx) => {
              const approvalStatus = hospitalApprovalStatus[h.hpid || ""] || "pending";
              const isRejected = rejectedHospitals.has(h.hpid || "");
              const isAccepted = approvalStatus === "approved";
              
              return (
                <div key={h.hpid || idx} className="rounded-lg border border-slate-200 p-3 md:p-3.5 bg-slate-50 flex flex-col gap-1.5">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-sm md:text-base font-semibold truncate">
                        {h.dutyName || "병원 명칭 미상"}
                        <span className="ml-1 text-[11px] md:text-xs font-normal text-slate-600">
                          ({h.dutyEmclsName || h.dutyDivNam || "응급의료기관"})
                        </span>
                      </div>
                      <div className="text-[11px] md:text-xs text-slate-600 truncate">{h.dutyAddr || "주소 정보 없음"}</div>
                    </div>
                    <div className="text-right text-[11px] md:text-xs text-slate-600 space-y-0.5 flex-shrink-0">
                      <div>약 {typeof h.distance_km === "number" ? h.distance_km.toFixed(1) : h.distance_km || "-"} km</div>
                      <div>예상 {h.eta_minutes || "-"}분</div>
                    </div>
                  </div>
                  <div className="mt-1 flex items-center justify-between text-[11px] md:text-xs text-slate-600">
                    <div className="flex items-center gap-2">
                      <span className="text-slate-500">대표번호</span>
                      <span className="font-medium text-slate-800">{h.dutytel3 || "-"}</span>
                    </div>
                  </div>
                  <div className="mt-1.5 flex items-center justify-between text-[11px] md:text-xs text-slate-600">
                    <div className="max-w-[65%] truncate" title={h._meets_conditions ? "증상 맞춤 병원" : "기본 병원"}>
                      기준: {h._meets_conditions ? "증상 맞춤 병원" : "거리 및 가용성 기준"}
                    </div>
                    <div className="flex-shrink-0 flex items-center gap-2">
                      {isAccepted ? (
                        <button
                          type="button"
                          onClick={() => handleOpenChat(h)}
                          className="inline-flex items-center rounded-full bg-emerald-600 text-white px-3 py-1 text-[10px] md:text-[11px] font-semibold shadow-sm hover:bg-emerald-700"
                        >
                          수용 가능
                        </button>
                      ) : isRejected ? (
                        <span className="inline-flex items-center rounded-full bg-red-50 text-red-700 border border-red-200 px-2 py-0.5 text-[10px] md:text-[11px]">
                          수용 거절
                        </span>
                      ) : (
                        <>
                          <button
                            type="button"
                            onClick={() => handleApproveHospital(h)}
                            className="inline-flex items-center rounded-full bg-green-600 text-white px-3 py-1 text-[10px] md:text-[11px] font-semibold shadow-sm hover:bg-green-700"
                          >
                            승낙
                          </button>
                          <button
                            type="button"
                            onClick={() => handleRejectHospital(h)}
                            className="inline-flex items-center rounded-full bg-red-600 text-white px-3 py-1 text-[10px] md:text-[11px] font-semibold shadow-sm hover:bg-red-700"
                          >
                            거절
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
        
        {approvedHospital && <ApprovedHospitalInfo approvedHospital={approvedHospital} />}
        
        {coords.lat && coords.lon && displayedMapHospitals.length > 0 && (
          <MapDisplay
            coords={coords}
            hospitals={displayedMapHospitals}
            routePaths={routePaths}
            approvedHospital={approvedHospital}
            resolveHospitalColor={resolveHospitalColor}
          />
        )}
      </main>

      {/* 채팅 슬라이드 패널 */}
      {isChatOpen && chatSession && approvedHospital && (
        <ParamedicChatSlideOver
          isOpen={isChatOpen}
          session={chatSession}
          hospital={approvedHospital}
          patientMeta={{
            sessionId: chatSession.id,
            patientAge: extractPatientAge(sttText),
            patientSex: extractPatientSex(sttText),
            preKtasLevel: extractPreKtasLevel(sttText),
            chiefComplaint: symptom,
            vitalsSummary: sttText ? sttText.substring(0, 200) : undefined,
            etaMinutes: approvedHospital.eta_minutes,
            distanceKm: typeof approvedHospital.distance_km === "number" 
              ? approvedHospital.distance_km 
              : typeof approvedHospital.distance_km === "string" 
              ? parseFloat(approvedHospital.distance_km) 
              : undefined,
            lastUpdated: new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: false }),
          }}
          sttText={sttText}
          onClose={() => setIsChatOpen(false)}
          onHandoverComplete={(sessionId) => {
            if (chatSession && chatSession.id === sessionId) {
              setChatSession((prev) => prev ? { ...prev, status: "COMPLETED" } : null);
            }
          }}
        />
      )}
    </div>
  );
};

