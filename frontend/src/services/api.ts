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

// 이미지 URL을 전체 URL로 변환하는 헬퍼 함수
export const getImageUrl = (imagePathOrUrl: string | null | undefined): string | undefined => {
  if (!imagePathOrUrl) return undefined;
  
  // 이미 전체 URL인 경우 그대로 반환
  if (imagePathOrUrl.startsWith('http://') || imagePathOrUrl.startsWith('https://') || imagePathOrUrl.startsWith('blob:') || imagePathOrUrl.startsWith('data:')) {
    return imagePathOrUrl;
  }
  
  // 상대 경로인 경우 전체 URL로 변환
  const baseUrl = API_BASE_URL.replace(/\/$/, ''); // 끝의 슬래시 제거
  const imagePath = imagePathOrUrl.startsWith('/') ? imagePathOrUrl : `/${imagePathOrUrl}`;
  return `${baseUrl}${imagePath}`;
};

// 주소 → 좌표 변환
export const addressToCoord = async (address: string): Promise<{ lat: number; lon: number; sido?: string; sigungu?: string } | null> => {
  if (!address.trim()) {
    throw new Error("주소를 입력해주세요.");
  }

  // 여러 파라미터 이름 시도 (백엔드 구현에 따라 다를 수 있음)
  const paramNames = ["q", "query", "address"];

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
      if (error.response?.status === 404 || error.code === "ECONNABORTED") {
        continue;
      }

      // 마지막 파라미터 시도 실패 시 에러 던지기
      if (paramName === paramNames[paramNames.length - 1]) {
        console.error("주소 → 좌표 변환 실패:", error);
        const errorMessage = error.response?.data?.message || error.response?.data?.error || error.message || "주소를 찾을 수 없습니다.";
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
      timeout: 15000, // 타임아웃 시간 증가 (5초 → 15초)
    });
    return res.data?.address || null;
  } catch (error: any) {
    console.error("좌표 → 주소 변환 실패:", error);
    // 타임아웃이나 네트워크 오류 시 null 반환 (에러를 던지지 않음)
    if (error.code === 'ECONNREFUSED' || error.code === 'ERR_NETWORK' || error.code === 'ECONNABORTED') {
      console.warn("백엔드 서버에 연결할 수 없거나 응답이 지연되고 있습니다. API 서버가 실행 중인지 확인해주세요.");
    }
    return null;
  }
};

// 좌표 → 행정구역 변환
export const coordToRegion = async (lat: number, lon: number): Promise<Region | null> => {
  try {
    const res = await axios.get(`${API_BASE_URL}/api/geo/coord2region`, {
      params: { lat, lon },
      timeout: 15000, // 타임아웃 시간 증가 (5초 → 15초)
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
    // 타임아웃이나 네트워크 오류 시 null 반환 (에러를 던지지 않음)
    if (error.code === 'ECONNREFUSED' || error.code === 'ERR_NETWORK' || error.code === 'ECONNABORTED') {
      console.warn("백엔드 서버에 연결할 수 없거나 응답이 지연되고 있습니다. API 서버가 실행 중인지 확인해주세요.");
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
    throw new Error(error.response?.data?.message || error.response?.data?.error || "병원 조회 중 오류가 발생했습니다.");
  }
};

// STT 음성 인식
export const transcribeAudio = async (audioFile: File): Promise<{ text: string; sbarSummary?: string; arsNarrative?: string }> => {
  try {
    const formData = new FormData();
    formData.append("audio", audioFile);
    // Content-Type을 명시하지 않으면 axios가 자동으로 multipart/form-data와 boundary를 설정합니다
    const res = await axios.post(`${API_BASE_URL}/api/stt/transcribe`, formData, {
      withCredentials: true,
      headers: {
        // Content-Type을 명시하지 않아야 axios가 boundary를 자동으로 설정합니다
      },
    });
    return {
      text: res.data?.text || "",
      sbarSummary: res.data?.sbar_summary || undefined,
      arsNarrative: res.data?.ars_narrative || undefined  // ARS 서비스용 자연스러운 문장
    };
  } catch (error: any) {
    console.error("음성 인식 실패:", error);

    // 더 자세한 에러 메시지 추출
    let errorMessage = "음성 인식 중 오류가 발생했습니다.";

    if (error.response) {
      // 서버 응답이 있는 경우
      errorMessage = error.response.data?.error || error.response.data?.message || errorMessage;
    } else if (error.request) {
      // 요청은 보냈지만 응답을 받지 못한 경우 (서버가 실행되지 않았을 수 있음)
      errorMessage = "서버에 연결할 수 없습니다. 백엔드 서버가 실행 중인지 확인해주세요.";
    } else {
      // 요청 설정 중 오류
      errorMessage = error.message || errorMessage;
    }

    throw new Error(errorMessage);
  }
};

// 텍스트를 SBAR 형식으로 변환
export const convertTextToSBAR = async (text: string): Promise<{ text: string; sbarSummary?: string; arsNarrative?: string }> => {
  try {
    const res = await axios.post(`${API_BASE_URL}/api/stt/convert-to-sbar`, {
      text: text,
    });
    return {
      text: res.data?.text || "",
      sbarSummary: res.data?.sbar_summary || undefined,
      arsNarrative: res.data?.ars_narrative || undefined  // ARS 서비스용 자연스러운 문장
    };
  } catch (error: any) {
    console.error("텍스트→SBAR 변환 실패:", error);
    throw new Error(error.response?.data?.message || "텍스트 변환 중 오류가 발생했습니다.");
  }
};

// Twilio 전화 걸기
export const makeCall = async (hospitalTel: string, hospitalName: string, patientInfo: string | null, callbackUrl?: string | null): Promise<{ call_sid: string }> => {
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
): Promise<{ path_coords?: number[][]; distance_km?: number; eta_minutes?: number } | null> => {
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
    const res = await axios.post(
      `${API_BASE_URL}/api/auth/login`,
      {
        ems_id: emsId,
        password: password,
      },
      {
        withCredentials: true, // 쿠키 포함
      }
    );
    return res.data;
  } catch (error: any) {
    console.error("로그인 실패:", error);
    throw new Error(error.response?.data?.error || "로그인 중 오류가 발생했습니다.");
  }
};

export const logout = async (): Promise<void> => {
  try {
    await axios.post(
      `${API_BASE_URL}/api/auth/logout`,
      {},
      {
        withCredentials: true,
      }
    );
  } catch (error: any) {
    console.error("로그아웃 실패:", error);
  }
};

export const hospitalLogin = async (hospitalId: string, password: string): Promise<{ hospital_id: string; hospital_name: string }> => {
  try {
    const res = await axios.post(`${API_BASE_URL}/api/auth/hospital-login`, {
      hospital_id: hospitalId,
      password: password,
    }, {
      withCredentials: true, // 쿠키 포함
    });
    return res.data;
  } catch (error: any) {
    console.error("병원 로그인 실패:", error);
    throw new Error(error.response?.data?.error || "로그인 중 오류가 발생했습니다.");
  }
};

export const getCurrentUser = async (): Promise<{ 
  user_type: "EMS" | "HOSPITAL";
  team_id?: number;
  ems_id?: string;
  region?: string | null;
  hospital_id?: string;
  hospital_name?: string;
} | null> => {
  try {
    const res = await axios.get(`${API_BASE_URL}/api/auth/me`, {
      withCredentials: true,
    });
    // user_type이 null이거나 없으면 로그인되지 않은 것으로 간주
    if (!res.data || !res.data.user_type) {
      return null;
    }
    return res.data;
  } catch (error: any) {
    // 401 에러는 더 이상 발생하지 않지만, 다른 에러는 처리
    console.error("사용자 정보 조회 실패:", error);
    return null;
  }
};

// 채팅 메시지 API
export const getChatMessages = async (
  sessionId: number
): Promise<
  Array<{
    message_id: number;
    session_id: number;
    sender_type: string;
    sender_ref_id: string;
    content: string;
    image_path?: string;
    image_url?: string;
    sent_at: string;
  }>
> => {
  try {
    const res = await axios.get(`${API_BASE_URL}/api/chat/messages`, {
      params: { session_id: sessionId },
      withCredentials: true,
    });
    return res.data.messages || [];
  } catch (error: any) {
    console.error("채팅 메시지 조회 실패:", error);
    throw new Error(error.response?.data?.error || "채팅 메시지 조회 중 오류가 발생했습니다.");
  }
};

// 이미지 업로드
export const uploadImage = async (imageFile: File): Promise<{ image_path: string; image_url: string }> => {
  try {
    const formData = new FormData();
    formData.append("image", imageFile);
    
    const res = await axios.post(`${API_BASE_URL}/api/chat/upload-image`, formData, {
      withCredentials: true,
      headers: {
        // Content-Type을 명시하지 않아야 axios가 boundary를 자동으로 설정합니다
      },
    });
    return res.data;
  } catch (error: any) {
    console.error("이미지 업로드 실패:", error);
    throw new Error(error.response?.data?.error || "이미지 업로드 중 오류가 발생했습니다.");
  }
};

export const sendChatMessage = async (
  sessionId: number,
  senderType: "EMS" | "HOSPITAL",
  senderRefId: string,
  content: string,
  imagePath?: string
): Promise<{
  message_id: number;
  session_id: number;
  sender_type: string;
  sender_ref_id: string;
  content: string;
  image_path?: string;
  image_url?: string;
  sent_at: string;
}> => {
  try {
    const res = await axios.post(
      `${API_BASE_URL}/api/chat/messages`,
      {
        session_id: sessionId,
        sender_type: senderType,
        sender_ref_id: senderRefId,
        content: content,
        image_path: imagePath || null,
      },
      {
        withCredentials: true,
      }
    );
    return res.data;
  } catch (error: any) {
    console.error("채팅 메시지 전송 실패:", error);
    throw new Error(error.response?.data?.error || "채팅 메시지 전송 중 오류가 발생했습니다.");
  }
};

// ChatSession 조회 API
export const getChatSession = async (
  requestId?: number,
  assignmentId?: number
): Promise<{
  session_id: number;
  request_id: number;
  assignment_id: number;
  started_at: string;
  ended_at?: string;
} | null> => {
  try {
    const params: any = {};
    if (requestId) params.request_id = requestId;
    if (assignmentId) params.assignment_id = assignmentId;

    const res = await axios.get(`${API_BASE_URL}/api/chat/session`, {
      params,
      withCredentials: true,
    });
    return res.data;
  } catch (error: any) {
    if (error.response?.status === 404) {
      return null; // 세션이 없음
    }
    console.error("ChatSession 조회 실패:", error);
    return null;
  }
};

// ChatSession 인계 완료 API
export const completeChatSession = async (sessionId: number, emsId: string): Promise<{
  session_id: number;
  ended_at: string;
}> => {
  try {
    const res = await axios.post(
      `${API_BASE_URL}/api/chat/session/${sessionId}/complete`,
      { ems_id: emsId },
      { withCredentials: true }
    );
    return res.data;
  } catch (error: any) {
    console.error("ChatSession 인계 완료 실패:", error);
    throw new Error(error.response?.data?.error || "인계 완료 처리 중 오류가 발생했습니다.");
  }
};

// ChatSession 삭제 API
export const deleteChatSession = async (sessionId: number): Promise<void> => {
  try {
    await axios.delete(`${API_BASE_URL}/api/chat/session/${sessionId}`, {
      withCredentials: true,
    });
  } catch (error: any) {
    console.error("ChatSession 삭제 실패:", error);
    throw new Error(error.response?.data?.error || "채팅 세션 삭제 중 오류가 발생했습니다.");
  }
};

// ChatSession 목록 조회 API (응급실 대시보드용)
export const getChatSessions = async (
  hospitalId?: string
): Promise<Array<{
  session_id: number;
  request_id: number;
  assignment_id: number;
  started_at: string;
  ended_at?: string;
  is_completed?: boolean;  // EmergencyRequest.is_completed
  ems_id: string | null;
  hospital_name: string | null;
  patient_age: number | null;
  patient_sex: string | null;
  pre_ktas_class: string | null;
  rag_summary: string | null;
  latest_message: {
    content: string | null;
    sent_at: string | null;
    sender_type: string | null;
  } | null;
}>> => {
  try {
    const params: any = {};
    if (hospitalId) params.hospital_id = hospitalId;

    const res = await axios.get(`${API_BASE_URL}/api/chat/sessions`, {
      params,
      withCredentials: true,
    });
    return res.data.sessions || [];
  } catch (error: any) {
    console.error("ChatSession 목록 조회 실패:", error);
    throw new Error(error.response?.data?.error || "ChatSession 목록 조회 중 오류가 발생했습니다.");
  }
};

// EmergencyRequest 생성 API
export const createEmergencyRequest = async (data: {
  team_id: number;
  patient_sex: string;
  patient_age: number;
  pre_ktas_class: number;
  stt_full_text?: string;
  rag_summary?: string;
  current_lat: number;
  current_lon: number;
}): Promise<{
  request_id: number;
  team_id: number;
  requested_at: string;
}> => {
  try {
    const res = await axios.post(`${API_BASE_URL}/api/emergency/request`, data, {
      withCredentials: true,
    });
    return res.data;
  } catch (error: any) {
    console.error("EmergencyRequest 생성 실패:", error);
    throw new Error(error.response?.data?.error || "EmergencyRequest 생성 중 오류가 발생했습니다.");
  }
};

// RequestAssignment 생성 및 병원에 전화 걸기 API
export const callHospital = async (data: {
  request_id: number;
  hospital_id: string;
  distance_km?: number;
  eta_minutes?: number;
  twilio_sid?: string;
}): Promise<{
  assignment_id: number;
  request_id: number;
  hospital_id: string;
  response_status: string;
  called_at: string;
}> => {
  try {
    const res = await axios.post(`${API_BASE_URL}/api/emergency/call-hospital`, data, {
      withCredentials: true,
    });
    return res.data;
  } catch (error: any) {
    console.error("병원 전화 걸기 실패:", error);
    throw new Error(error.response?.data?.error || "병원 전화 걸기 중 오류가 발생했습니다.");
  }
};

// RequestAssignment 응답 상태 업데이트 API (병원 승인/거절)
export const updateResponseStatus = async (data: {
  assignment_id: number;
  response_status: "승인" | "거절" | "대기중";
  twilio_sid?: string;
}): Promise<{
  assignment_id: number;
  response_status: string;
  responded_at: string;
  session_id?: number;
  request_id?: number;
}> => {
  try {
    const res = await axios.post(`${API_BASE_URL}/api/emergency/update-response`, data, {
      withCredentials: true,
    });
    return res.data;
  } catch (error: any) {
    console.error("응답 상태 업데이트 실패:", error);
    throw new Error(error.response?.data?.error || "응답 상태 업데이트 중 오류가 발생했습니다.");
  }
};
