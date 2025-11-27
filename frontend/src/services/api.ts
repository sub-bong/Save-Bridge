import axios from "axios";
import type { Coords, Region, Hospital } from "../types";

// API 기본 URL (환경 변수 또는 기본값)
const getApiBaseUrl = (): string => {
  try {
    // Vite 환경 변수 접근
    const env = (import.meta as { env?: { VITE_API_BASE_URL?: string } }).env;
    return env?.VITE_API_BASE_URL || "http://localhost:5001";
  } catch {
    return "http://localhost:5001";
  }
};

const API_BASE_URL = getApiBaseUrl();

// axios 기본 설정 (쿠키 포함)
axios.defaults.withCredentials = true;

// 주소 → 좌표 변환
export const addressToCoord = async (address: string): Promise<{ lat: number; lon: number; sido?: string; sigungu?: string } | null> => {
  if (!address.trim()) {
    throw new Error("주소를 입력해주세요.");
  }

  // 여러 파라미터 이름 시도 (백엔드 구현에 따라 다를 수 있음)
  const paramNames = ['q', 'query', 'address'];
  
  for (const paramName of paramNames) {
    try {
      const res = await axios.get(`${API_BASE_URL}/api/geo/address2coord`, {
        params: { [paramName]: address },
        timeout: 5000,
      });
      
      // 응답이 배열인 경우 (여러 결과)
      let data = res.data;
      if (Array.isArray(data) && data.length > 0) {
        data = data[0]; // 첫 번째 결과 사용
      }
      
      if (data?.lat && data?.lon) {
        return {
          lat: data.lat,
          lon: data.lon,
          sido: data.sido,
          sigungu: data.sigungu,
        };
      }
      
      // lat, lon이 없으면 다음 파라미터 시도
      if (data && !data.lat) {
        continue;
      }
    } catch (error: any) {
      // 404나 다른 에러면 다음 파라미터 시도
      if (error.response?.status === 404 || error.code === 'ECONNABORTED') {
        continue;
      }
      
      // 마지막 파라미터 시도 실패 시 에러 던지기
      if (paramName === paramNames[paramNames.length - 1]) {
        console.error("주소 → 좌표 변환 실패:", error);
        const errorMessage = error.response?.data?.message || 
                            error.response?.data?.error ||
                            error.message ||
                            "주소를 찾을 수 없습니다.";
        throw new Error(errorMessage);
      }
    }
  }
  
  throw new Error("주소를 찾을 수 없습니다. 더 구체적인 주소를 입력해주세요. (예: '광주광역시 광산구 신가동' 또는 '광주광역시 광산구 신가동 123')");
};

// 좌표 → 주소 변환
export const coordToAddress = async (lat: number, lon: number): Promise<string | null> => {
  try {
    const res = await axios.get(`${API_BASE_URL}/api/geo/coord2address`, {
      params: { lat, lon },
      timeout: 5000,
    });
    return res.data?.address || null;
  } catch (error: any) {
    console.error("좌표 → 주소 변환 실패:", error);
    // 네트워크 오류나 서버 오류 시 null 반환 (에러를 던지지 않음)
    if (error.code === 'ECONNREFUSED' || error.code === 'ERR_NETWORK') {
      console.warn("백엔드 서버에 연결할 수 없습니다. API 서버가 실행 중인지 확인해주세요.");
    }
    return null;
  }
};

// 좌표 → 행정구역 변환
export const coordToRegion = async (lat: number, lon: number): Promise<Region | null> => {
  try {
    const res = await axios.get(`${API_BASE_URL}/api/geo/coord2region`, {
      params: { lat, lon },
      timeout: 5000,
    });
    if (res.data?.sido && res.data?.sigungu) {
      return {
        sido: res.data.sido,
        sigungu: res.data.sigungu,
      };
    }
    return null;
  } catch (error: any) {
    console.error("좌표 → 행정구역 변환 실패:", error);
    // 네트워크 오류나 서버 오류 시 null 반환 (에러를 던지지 않음)
    if (error.code === 'ECONNREFUSED' || error.code === 'ERR_NETWORK') {
      console.warn("백엔드 서버에 연결할 수 없습니다. API 서버가 실행 중인지 확인해주세요.");
    }
    return null;
  }
};

// 병원 조회
export const searchHospitals = async (
  lat: number,
  lon: number,
  sido: string,
  sigungu: string,
  symptom: string,
  sttText?: string | null
): Promise<{
  hospitals: Hospital[];
  route_paths?: Record<string, number[][]>;
  backup_hospitals?: Hospital[];
  neighbor_hospitals?: Hospital[];
}> => {
  try {
    const res = await axios.post(`${API_BASE_URL}/api/hospitals/top3`, {
      lat,
      lon,
      sido,
      sigungu,
      symptom,
      stt_text: sttText || null,
      // hospital_type은 백엔드에서 증상에 따라 자동 결정
    });
    return {
      hospitals: res.data.hospitals || [],
      route_paths: res.data.route_paths,
      backup_hospitals: res.data.backup_hospitals,
      neighbor_hospitals: res.data.neighbor_hospitals,
    };
  } catch (error: any) {
    console.error("병원 조회 실패:", error);
    throw new Error(
      error.response?.data?.message ||
      error.response?.data?.error ||
      "병원 조회 중 오류가 발생했습니다."
    );
  }
};

// STT 음성 인식
export const transcribeAudio = async (audioFile: File): Promise<string> => {
  try {
    const formData = new FormData();
    formData.append("audio", audioFile);
    const res = await axios.post(`${API_BASE_URL}/api/stt/transcribe`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return res.data?.text || "";
  } catch (error: any) {
    console.error("음성 인식 실패:", error);
    throw new Error(error.response?.data?.message || "음성 인식 중 오류가 발생했습니다.");
  }
};

// Twilio 전화 걸기
export const makeCall = async (
  hospitalTel: string,
  hospitalName: string,
  patientInfo: string | null,
  callbackUrl?: string | null
): Promise<{ call_sid: string }> => {
  try {
    const res = await axios.post(`${API_BASE_URL}/api/telephony/call`, {
      hospital_tel: hospitalTel,
      hospital_name: hospitalName,
      patient_info: patientInfo,
      callback_url: callbackUrl || null,
    });
    return { call_sid: res.data.call_sid };
  } catch (error: any) {
    console.error("전화 연결 실패:", error);
    throw new Error(error.response?.data?.message || "전화 연결 중 오류가 발생했습니다.");
  }
};

// 전화 응답 확인
export const getCallResponse = async (callSid: string): Promise<{ digit?: string; status?: string } | null> => {
  try {
    const res = await axios.get(`${API_BASE_URL}/api/telephony/response/${callSid}`);
    return res.data || null;
  } catch (error: any) {
    console.error("전화 응답 확인 실패:", error);
    return null;
  }
};

// 경로 조회
export const getRoute = async (
  originLat: number,
  originLon: number,
  destLat: number,
  destLon: number
): Promise<{ path_coords?: number[][] } | null> => {
  try {
    const res = await axios.get(`${API_BASE_URL}/api/geo/route`, {
      params: {
        origin_lat: originLat,
        origin_lon: originLon,
        dest_lat: destLat,
        dest_lon: destLon,
      },
    });
    return res.data || null;
  } catch (error: any) {
    console.error("경로 조회 실패:", error);
    return null;
  }
};

// 인증 API
export const login = async (emsId: string, password: string): Promise<{ team_id: number; ems_id: string; region: string | null }> => {
  try {
    const res = await axios.post(`${API_BASE_URL}/api/auth/login`, {
      ems_id: emsId,
      password: password,
    }, {
      withCredentials: true, // 쿠키 포함
    });
    return res.data;
  } catch (error: any) {
    console.error("로그인 실패:", error);
    throw new Error(error.response?.data?.error || "로그인 중 오류가 발생했습니다.");
  }
};

export const logout = async (): Promise<void> => {
  try {
    await axios.post(`${API_BASE_URL}/api/auth/logout`, {}, {
      withCredentials: true,
    });
  } catch (error: any) {
    console.error("로그아웃 실패:", error);
  }
};

export const getCurrentUser = async (): Promise<{ team_id: number; ems_id: string; region: string | null } | null> => {
  try {
    const res = await axios.get(`${API_BASE_URL}/api/auth/me`, {
      withCredentials: true,
    });
    return res.data;
  } catch (error: any) {
    if (error.response?.status === 401) {
      return null; // 로그인되지 않음
    }
    console.error("사용자 정보 조회 실패:", error);
    return null;
  }
};

