import React, { useState, useEffect, useRef, useMemo, useCallback } from "react";
import type { ChatMessage, Hospital, Coords } from "../types";
import { getChatSessions, getChatMessages, sendChatMessage, getChatSession, deleteChatSession, hospitalLogin, getCurrentUser, logout, getImageUrl, getRoute } from "../services/api";
import { extractPatientAgeDisplay } from "../utils/hospitalUtils";
import { KakaoAmbulanceMap } from "./KakaoAmbulanceMap";
import { getSocket, disconnectSocket } from "../services/socket";
import type { Socket } from "socket.io-client";

interface ChatSession {
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
  stt_full_text?: string | null;  // STT 원문 (optional)
  current_lat?: number | null;  // 구급대원 현재 위치 (위도)
  current_lon?: number | null;  // 구급대원 현재 위치 (경도)
  hospital_id?: string | null;  // 병원 ID
  hospital_lat?: number | null;  // 병원 위도
  hospital_lon?: number | null;  // 병원 경도
  latest_message: {
    content: string | null;
    sent_at: string | null;
    sender_type: string | null;
  } | null;
}

interface ERDashboardProps {
  hospitalId?: string;
  hospitalName?: string;
}

export const ERDashboard: React.FC<ERDashboardProps> = ({
  hospitalId: propHospitalId,
  hospitalName: propHospitalName,
}) => {
  // 로그인 상태
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [hospitalId, setHospitalId] = useState<string | undefined>(propHospitalId);
  const [hospitalName, setHospitalName] = useState<string>(propHospitalName || "");
  const [loginHospitalId, setLoginHospitalId] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginError, setLoginError] = useState<string | null>(null);
  const [checkingAuth, setCheckingAuth] = useState(true);
  
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [selectedSession, setSelectedSession] = useState<ChatSession | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draftText, setDraftText] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [deletingSessionId, setDeletingSessionId] = useState<number | null>(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [sessionToDelete, setSessionToDelete] = useState<number | null>(null);
  const [isSendingMessage, setIsSendingMessage] = useState(false); // 메시지 전송 중 플래그
  const [showLogoutModal, setShowLogoutModal] = useState(false); // 로그아웃 모달 표시 여부
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [routePaths, setRoutePaths] = useState<Record<string, number[][]>>({}); // 경로 정보
  const [distanceKm, setDistanceKm] = useState<number | undefined>(undefined); // 거리 (km)
  const [etaMinutes, setEtaMinutes] = useState<number | undefined>(undefined); // 예상 도착 시간 (분)
  // IME(한글) 입력 후 Enter 전송 시 마지막 글자가 남는 문제를 막기 위한 플래그
  const ignoreNextChangeRef = useRef(false);
  
  // 구급대원 위치와 병원 위치 기반으로 지도 표시용 데이터 생성
  const mapData = useMemo(() => {
    if (!selectedSession || !selectedSession.current_lat || !selectedSession.current_lon) {
      return null;
    }
    
    const ambulanceCoords: Coords = {
      lat: selectedSession.current_lat,
      lon: selectedSession.current_lon,
    };
    
    const hospital: Hospital | null = selectedSession.hospital_lat && selectedSession.hospital_lon ? {
      hpid: selectedSession.hospital_id || undefined,
      dutyName: selectedSession.hospital_name || undefined,
      wgs84Lat: selectedSession.hospital_lat,
      wgs84Lon: selectedSession.hospital_lon,
    } : null;
    
    return { ambulanceCoords, hospital };
  }, [selectedSession]);
  
  // 경로 정보 가져오기
  useEffect(() => {
    if (!mapData || !mapData.hospital || !mapData.ambulanceCoords.lat || !mapData.ambulanceCoords.lon) {
      setRoutePaths({});
      setDistanceKm(undefined);
      setEtaMinutes(undefined);
      return;
    }
    
    const fetchRoute = async () => {
      try {
        const result = await getRoute(
          mapData.ambulanceCoords.lat!,
          mapData.ambulanceCoords.lon!,
          mapData.hospital.wgs84Lat!,
          mapData.hospital.wgs84Lon!
        );
        
        if (result?.path_coords && mapData.hospital.hpid) {
          setRoutePaths({ [mapData.hospital.hpid]: result.path_coords });
        }
        
        // 거리와 ETA 정보 저장
        if (result?.distance_km !== undefined) {
          setDistanceKm(result.distance_km);
        }
        if (result?.eta_minutes !== undefined) {
          setEtaMinutes(result.eta_minutes);
        }
      } catch (error) {
        console.error("경로 정보 가져오기 실패:", error);
        setRoutePaths({});
        setDistanceKm(undefined);
        setEtaMinutes(undefined);
      }
    };
    
    fetchRoute();
  }, [mapData]);
  
  // 로그인 확인
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const user = await getCurrentUser();
        if (user && user.user_type === "HOSPITAL" && user.hospital_id) {
          setHospitalId(user.hospital_id);
          setHospitalName(user.hospital_name || "");
          setIsLoggedIn(true);
        } else {
          setIsLoggedIn(false);
        }
      } catch (error) {
        console.error("인증 확인 실패:", error);
        setIsLoggedIn(false);
      } finally {
        setCheckingAuth(false);
      }
    };
    checkAuth();
  }, []);

  // 로그인 처리
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError(null);
    
    if (!loginHospitalId || !loginPassword) {
      setLoginError("병원 ID와 비밀번호를 입력해주세요.");
      return;
    }

    try {
      const result = await hospitalLogin(loginHospitalId, loginPassword);
      console.log("ERDashboard: 로그인 성공, hospital_id:", result.hospital_id);
      setHospitalId(result.hospital_id);
      setHospitalName(result.hospital_name);
      setIsLoggedIn(true);
      setLoginPassword(""); // 보안을 위해 비밀번호 초기화
      // 로그인 후 세션 목록 자동 로드
      setTimeout(() => {
        loadSessions();
      }, 100);
    } catch (error: any) {
      setLoginError(error.message || "로그인에 실패했습니다.");
    }
  };

  // 세션 목록 로드
  const loadSessions = async () => {
    if (!hospitalId) {
      // 초기 로딩 중이거나 로그인 전 상태일 수 있으므로 경고를 info로 변경
      console.log("ERDashboard: hospitalId가 아직 설정되지 않았습니다. 로그인 대기 중...");
      setLoading(false);
      setRefreshing(false);
      return;
    }
    
    try {
      console.log("ERDashboard: 세션 목록 로드 시작, hospitalId:", hospitalId);
      const data = await getChatSessions(hospitalId);
      console.log("ERDashboard: 세션 목록 로드 완료, 세션 수:", data.length, data);
      setSessions(data);
      
      // 사용자가 수동으로 선택한 세션이 있으면 그 세션을 유지하고 정보만 업데이트
      if (selectedSession) {
        const updatedSession = data.find(s => s.session_id === selectedSession.session_id);
        if (updatedSession) {
          // 선택된 세션이 목록에 있으면 정보만 업데이트 (포커스 유지)
          setSelectedSession(updatedSession);
          return;
        }
        // 선택된 세션이 목록에서 사라졌으면 선택 해제
        setSelectedSession(null);
      }
      
      // 선택된 세션이 없을 때만 자동으로 가장 최신 진행 중인 세션 선택
      if (!selectedSession && data.length > 0) {
        const ongoingSessions = data.filter(s => !s.is_completed);
        if (ongoingSessions.length > 0) {
          // 가장 최신 진행 중인 세션 선택 (백엔드에서 최신순으로 정렬됨)
          setSelectedSession(ongoingSessions[0]);
        } else if (data.length > 0) {
          // 진행 중인 세션이 없으면 가장 최신 세션 선택
          setSelectedSession(data[0]);
        }
      }
    } catch (error) {
      console.error("세션 목록 로드 실패:", error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  // 메시지 로드
  const loadMessages = async (sessionId: number) => {
    try {
      const dbMessages = await getChatMessages(sessionId);
      
      // 중복 제거: message_id 기준으로 중복 제거
      const uniqueMessages = new Map<number, typeof dbMessages[0]>();
      for (const msg of dbMessages) {
        if (!uniqueMessages.has(msg.message_id)) {
          uniqueMessages.set(msg.message_id, msg);
        }
      }
      const deduplicatedMessages = Array.from(uniqueMessages.values());
      
      const formattedMessages: ChatMessage[] = deduplicatedMessages.map((msg) => {
        // ISO 형식 문자열을 Date 객체로 변환
        // 백엔드에서 KST 시간대 정보가 포함된 ISO 문자열을 보냄
        let date: Date;
        try {
          // ISO 문자열 파싱 (예: "2024-11-29T23:44:00+09:00")
          date = new Date(msg.sent_at);
          
          // 유효하지 않은 날짜인 경우 현재 시간 사용
          if (isNaN(date.getTime())) {
            console.warn("Invalid date:", msg.sent_at);
            date = new Date();
          }
          
        } catch (e) {
          console.warn("Date parsing error:", msg.sent_at, e);
          date = new Date();
        }
        
        // 한국 시간대로 표시
        // ISO 문자열에 시간대 정보가 포함되어 있으므로, toLocaleTimeString에서 timeZone을 명시적으로 지정
        const timeString = date.toLocaleTimeString("ko-KR", {
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
          timeZone: "Asia/Seoul",
        });
        
        return {
          id: `msg-${msg.message_id}`,
          role: msg.sender_type === "EMS" ? "PARAMEDIC" : "ER",
          content: msg.content,
          imageUrl: getImageUrl(msg.image_url), // 전체 URL로 변환
          sentAt: timeString,
        };
      });
      
      // message_id 기준으로 정렬 (오래된 것부터)
      formattedMessages.sort((a, b) => {
        const aId = parseInt(a.id.replace('msg-', ''));
        const bId = parseInt(b.id.replace('msg-', ''));
        return aId - bId;
      });
      
      setMessages(formattedMessages);
    } catch (error) {
      console.error("메시지 로드 실패:", error);
    }
  };

  // 초기 로드 (로그인 후에만)
  useEffect(() => {
    if (!isLoggedIn || !hospitalId) return;
    
    console.log("ERDashboard: 초기 로드 또는 선택 세션 변경, hospitalId:", hospitalId);
    loadSessions();
    // 주기적 새로고침 (5초마다 - 인계 완료 상태 빠른 반영)
    const interval = setInterval(() => {
      setRefreshing(true);
      loadSessions();
    }, 5000);
    return () => clearInterval(interval);
  }, [hospitalId, isLoggedIn, selectedSession?.session_id]);

  // 선택된 세션 변경 시 메시지 로드 및 WebSocket 연결
  useEffect(() => {
    if (!selectedSession?.session_id) {
      setMessages([]);
      return;
    }
    
    const sessionId = selectedSession.session_id;
    const socket = getSocket();
    
    // 초기 메시지 로드
    loadMessages(sessionId).catch(console.error);
    
    // WebSocket으로 세션 참여
    socket.emit('join_session', { session_id: sessionId });
    console.log(`✅ ERDashboard: 세션 ${sessionId}에 참여했습니다.`);
    
    // 새 메시지 수신 이벤트 리스너
    const handleNewMessage = (messageData: any) => {
      console.log('📨 ERDashboard: 새 메시지 수신:', messageData);
      if (messageData.session_id === sessionId) {
        // 메시지 목록 다시 로드
        loadMessages(sessionId).catch(console.error);
      }
    };
    
    socket.on('new_message', handleNewMessage);
    
    return () => {
      // 세션에서 나가기
      socket.emit('leave_session', { session_id: sessionId });
      socket.off('new_message', handleNewMessage);
      console.log(`👋 ERDashboard: 세션 ${sessionId}에서 나갔습니다.`);
    };
  }, [selectedSession?.session_id]);

  // 메시지 전송
  const handleSendMessage = async (textOverride?: string) => {
    // 이미 전송 중이면 중복 전송 방지 (가장 먼저 체크)
    if (isSendingMessage) {
      console.warn("⚠️ 메시지 전송 중입니다. 중복 전송을 방지합니다.");
      return;
    }
    
    const text = textOverride || draftText.trim();
    if (!text) return;
    
    if (!selectedSession) {
      console.error("선택된 세션이 없습니다.");
      return;
    }
    
    if (!selectedSession.session_id) {
      console.error("세션 ID가 없습니다:", selectedSession);
      return;
    }

    // 전송 시작 플래그 설정 (다른 호출 방지)
    setIsSendingMessage(true);
    
    // 입력 필드 초기화 (항상 초기화하여 마지막 단어 남는 문제 해결)
    const messageToSend = text;
    // textOverride가 있으면 이미 onKeyDown에서 초기화했지만, 확실히 하기 위해 다시 초기화
    setDraftText(""); // 항상 초기화

    // DB에 저장
    try {
      console.log("응급실 메시지 전송 시도:", {
        session_id: selectedSession.session_id,
        sender_type: "HOSPITAL",
        sender_ref_id: hospitalId,
        content: messageToSend,
      });
      
      await sendChatMessage(
        selectedSession.session_id,
        "HOSPITAL",
        hospitalId || "A1500002", // 기본값
        messageToSend
      );
      
      console.log("응급실 메시지 저장 성공");
      
      // 짧은 지연 후 DB에서 최신 메시지 목록을 다시 로드하여 중복 방지 및 정확한 시간 표시
      // DB 커밋이 완료될 시간을 주기 위해 약간의 지연 추가
      setTimeout(async () => {
        await loadMessages(selectedSession.session_id);
        setIsSendingMessage(false); // 전송 완료
      }, 200);
    } catch (error) {
      console.error("메시지 저장 실패:", error);
      // 실패 시에도 입력 필드는 비워둠 (사용자가 다시 입력할 수 있도록)
      // setDraftText(""); // 이미 초기화되어 있으므로 다시 초기화할 필요 없음
      setIsSendingMessage(false); // 전송 실패
      alert("메시지 전송에 실패했습니다. 다시 시도해주세요.");
    }
  };

  // 메시지 스크롤
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // 세션 삭제 모달 열기
  const handleDeleteClick = (sessionId: number, e: React.MouseEvent) => {
    e.stopPropagation(); // 버튼 클릭 시 세션 선택 방지
    setSessionToDelete(sessionId);
    setShowDeleteModal(true);
  };

  // 세션 삭제 확인
  const handleDeleteConfirm = async () => {
    if (!sessionToDelete) return;

    setDeletingSessionId(sessionToDelete);
    try {
      console.log("🗑️  세션 삭제 시도:", sessionToDelete);
      await deleteChatSession(sessionToDelete);
      console.log("✅ 세션 삭제 성공");
      
      // 삭제된 세션이 선택된 세션이면 선택 해제
      if (selectedSession?.session_id === sessionToDelete) {
        setSelectedSession(null);
        setMessages([]);
      }
      // 세션 목록 새로고침
      await loadSessions();
      setShowDeleteModal(false);
      setSessionToDelete(null);
    } catch (error: any) {
      console.error("❌ 세션 삭제 실패:", error);
      console.error("❌ 에러 상세:", {
        message: error.message,
        response: error.response?.data,
        status: error.response?.status,
      });
      const errorMessage = error.response?.data?.error || error.message || "알 수 없는 오류";
      alert(`세션 삭제 실패: ${errorMessage}`);
    } finally {
      setDeletingSessionId(null);
    }
  };

  // 삭제 모달 닫기
  const handleDeleteCancel = () => {
    setShowDeleteModal(false);
    setSessionToDelete(null);
  };

  // 로그아웃 모달 열기
  const handleLogoutClick = () => {
    setShowLogoutModal(true);
  };

  // 로그아웃 확인
  const handleLogoutConfirm = async () => {
    try {
      await logout();
      setIsLoggedIn(false);
      setHospitalId(undefined);
      setHospitalName("");
      setShowLogoutModal(false);
      // 페이지 새로고침하여 로그인 페이지로 이동
      window.location.reload();
    } catch (error) {
      console.error("로그아웃 실패:", error);
      alert("로그아웃에 실패했습니다. 다시 시도해주세요.");
    }
  };

  // 로그아웃 취소
  const handleLogoutCancel = () => {
    setShowLogoutModal(false);
  };

  const getStatusLabel = (session: ChatSession) => {
    // EmergencyRequest.is_completed가 true면 인계 완료
    if (session.is_completed === true) {
      return "인계 완료";
    }
    return "인계 진행 중";
  };

  const getSexLabel = (sex: string | null) => {
    if (sex === "M") return "남";
    if (sex === "F") return "여";
    return "-";
  };

  // 환자 정보를 "구급대원 식별번호 / 성별 / 나이" 형식으로 반환
  const getPatientInfoLabel = (session: ChatSession): string => {
    const emsId = session.ems_id || "알 수 없음";
    // 🔹 연령 정보는 STT 원문 또는 요약(rag_summary)에서만 추출
    //    (DB 기본값 30세 등에 영향받지 않도록 함)
    const ageSourceText = (session.stt_full_text || session.rag_summary || "") as string;
    const age = extractPatientAgeDisplay(ageSourceText);
    const sex = getSexLabel(session.patient_sex);
    
    const parts: string[] = [emsId];
    if (sex !== "-") {
      parts.push(sex);
    }
    if (age) {
      parts.push(age);
    }
    
    return parts.join(" / ");
  };

  const formatTime = (timeStr: string | null) => {
    if (!timeStr) return "";
    const date = new Date(timeStr);
    // 한국 시간대로 변환하여 표시
    return date.toLocaleTimeString("ko-KR", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone: "Asia/Seoul",
    });
  };

  // 인증 확인 중
  if (checkingAuth) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-emerald-600"></div>
          <p className="mt-4 text-slate-600">로딩 중...</p>
        </div>
      </div>
    );
  }

  // 로그인하지 않은 경우 로그인 화면 표시
  if (!isLoggedIn) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="w-full max-w-md bg-white rounded-xl shadow-lg p-8">
          <div className="text-center mb-8">
            <h1 className="text-2xl font-bold text-slate-900 mb-2">SAFE BRIDGE</h1>
            <p className="text-sm text-slate-600">응급실 인계 채팅 대시보드</p>
          </div>
          
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label htmlFor="hospital_id" className="block text-sm font-medium text-slate-700 mb-1">
                병원 ID
              </label>
              <input
                id="hospital_id"
                type="text"
                value={loginHospitalId}
                onChange={(e) => setLoginHospitalId(e.target.value)}
                className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                placeholder="병원 ID를 입력하세요"
                required
              />
            </div>
            
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-slate-700 mb-1">
                비밀번호
              </label>
              <input
                id="password"
                type="password"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                placeholder="비밀번호를 입력하세요"
                required
              />
            </div>
            
            {loginError && (
              <div className="text-sm text-red-600 bg-red-50 px-4 py-2 rounded-lg">
                {loginError}
              </div>
            )}
            
            <button
              type="submit"
              className="w-full py-2 px-4 bg-emerald-600 text-white rounded-lg font-semibold hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 transition-colors"
            >
              로그인
            </button>
          </form>
        </div>
      </div>
    );
  }

  // 로딩 중
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-emerald-600"></div>
          <p className="mt-4 text-slate-600">로딩 중...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen w-full bg-slate-100 flex">
      <div className="flex flex-col flex-1 w-full bg-white overflow-hidden">
        {/* 상단 헤더 */}
        <header className="h-12 flex items-center justify-between px-4 border-b border-slate-200 bg-slate-50">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold tracking-wide text-sky-700 uppercase">
              SAFE BRIDGE
            </span>
            <span className="w-px h-4 bg-slate-300" />
            <span className="text-sm font-semibold text-slate-900">
              응급실 인계 채팅 대시보드
            </span>
          </div>
          <div className="flex items-center gap-3">
            {hospitalName && (
              <span className="text-[11px] text-slate-600">{hospitalName}</span>
            )}
            {hospitalId && (
              <span className="text-[11px] text-slate-500">ID: {hospitalId}</span>
            )}
            <button
              onClick={handleLogoutClick}
              className="text-[11px] text-slate-500 hover:text-slate-700 px-2 py-1 rounded hover:bg-slate-100"
            >
              로그아웃
            </button>
            <div className="text-[11px] text-slate-500">
              현재 화면은 응급실 의료진 전용 · 사진 업로드는 구급대원 단말에서만 가능
            </div>
          </div>
        </header>

        <div className="flex flex-1 min-h-0 divide-x divide-slate-200">
          {/* 왼쪽: 인계 채팅 목록 - 고정 폭 (너비 줄이기) */}
          <aside className="w-56 flex-shrink-0 flex flex-col bg-slate-50 min-h-0">
            <div className="px-3 py-2 border-b border-slate-200 flex-shrink-0">
              <div className="text-xs font-semibold text-slate-700 mb-1">
                인계 채팅 목록
              </div>
              <div className="flex items-center justify-between text-[11px] text-slate-500">
                <span>구급대원별 세션 단위</span>
                <div className="flex items-center gap-2">
                  <span>총 {sessions.length}건</span>
                  <button
                    onClick={() => {
                      setRefreshing(true);
                      loadSessions();
                    }}
                    className="text-emerald-600 hover:text-emerald-700 disabled:opacity-50"
                    disabled={refreshing}
                  >
                    {refreshing ? "새로고침 중..." : "새로고침"}
                  </button>
                </div>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto min-h-0">
              {sessions.length === 0 ? (
                <div className="p-4 text-center text-[11px] text-slate-500">
                  진행 중인 인계 채팅이 없습니다.
                </div>
              ) : (
                sessions.map((session) => {
                  const isSelected = selectedSession?.session_id === session.session_id;
                  const statusLabel = getStatusLabel(session);
                  const chiefComplaint = session.rag_summary || "증상 정보 없음";
                  
                  return (
                    <button
                      key={session.session_id}
                      type="button"
                      onClick={() => setSelectedSession(session)}
                      className={`relative w-full text-left px-3 py-2 border-b border-slate-100 hover:bg-sky-50 focus:outline-none transition ${
                        isSelected ? "bg-sky-50" : "bg-transparent"
                      }`}
                    >
                      {/* 상단: 구급대원/환자 정보 + 상태 배지 */}
                      <div className="flex items-center justify-between mb-0.5 pr-8">
                        <div className="text-xs font-semibold text-slate-900 flex-1 min-w-0">
                          {getPatientInfoLabel(session)}
                        </div>
                        <span
                          className={`rounded-full px-2 py-0.5 text-[10px] border flex-shrink-0 ${
                            session.is_completed === true
                              ? "border-slate-300 text-slate-600 bg-slate-50"
                              : "border-amber-400 text-amber-700 bg-amber-50"
                          }`}
                        >
                          {statusLabel}
                        </span>
                      </div>
                      {/* 중간: 주증상 */}
                      <div className="text-[11px] text-slate-600 truncate">
                        주증상: {chiefComplaint}
                      </div>
                      {/* 하단: 마지막 메시지 프리뷰 + 시간 */}
                      <div className="mt-0.5 flex items-center justify-between">
                        <span className="text-[10px] text-slate-500 truncate max-w-[70%]">
                          {session.latest_message?.content?.substring(0, 30) || "메시지 없음"}
                        </span>
                        <span className="text-[10px] text-slate-500">{formatTime(session.started_at)}</span>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </aside>

          {/* 중간: 채팅 패널 (비율 2) */}
          <section className="flex-[2] flex flex-col min-w-[420px]">
            {selectedSession ? (
              <>
                <div className="px-4 py-2 border-b border-slate-200 bg-white">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs font-semibold text-slate-900">
                        {getPatientInfoLabel(selectedSession)}
                      </div>
                      <div className="mt-0.5 text-[11px] text-slate-500">
                        주증상: {selectedSession.rag_summary || "정보 없음"}
                      </div>
                    </div>
                    <button
                      onClick={(e) => handleDeleteClick(selectedSession.session_id, e)}
                      disabled={deletingSessionId === selectedSession.session_id}
                      className="text-slate-400 hover:text-red-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      title="세션 삭제"
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                  <div className="mt-1 text-[11px] text-slate-500">
                    상태: {getStatusLabel(selectedSession)}
                  </div>
                </div>

                <div className="flex-1 overflow-y-auto px-4 py-3 bg-slate-50">
                  {messages.map((msg) => (
                    <ERMessageBubble key={msg.id} message={msg} />
                  ))}
                  <div ref={messagesEndRef} />
                </div>

                {selectedSession.is_completed === true ? (
                  <div className="border-t border-slate-200 bg-slate-50 px-4 py-2 text-[11px] text-slate-500 text-center">
                    해당 환자는 인계가 완료된 세션입니다. 추가 채팅 입력은 불가능합니다.
                  </div>
                ) : (
                  <div className="border-t border-slate-200 bg-white px-4 py-2">
                    <div className="flex items-end gap-2">
                      <textarea
                        rows={2}
                        className="flex-1 resize-none rounded-xl border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500"
                        placeholder="구급대원에게 전달할 지시사항이나 질문을 입력하세요. (사진 전송은 구급대원 단말에서만 가능)"
                        value={draftText}
                        onChange={(e) => {
                          // 직전에 Enter로 전송하면서 입력을 비운 경우,
                          // IME(compositionend)에서 들어오는 마지막 글자 변경 이벤트는 무시
                          if (ignoreNextChangeRef.current) {
                            ignoreNextChangeRef.current = false;
                            setDraftText("");
                            // DOM value도 비워서 한 글자 남는 현상 완전히 제거
                            e.target.value = "";
                            return;
                          }

                          // Enter 키로 인한 줄바꿈 제거 (Shift+Enter는 허용하지만, 일반 Enter는 제거)
                          let value = e.target.value;
                          if (value.includes("\n") && value.endsWith("\n")) {
                            value = value.slice(0, -1);
                          }
                          setDraftText(value);
                        }}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" && !e.shiftKey) {
                            e.preventDefault();
                            e.stopPropagation();
                            
                            // 이미 전송 중이면 무시
                            if (isSendingMessage) {
                              console.warn("⚠️ 메시지 전송 중입니다. Enter 키 무시");
                              return;
                            }
                            
                            // ✅ 실제 textarea 요소의 현재 값을 직접 가져옴 (상태가 아닌 실제 값 사용)
                            const textarea = e.currentTarget as HTMLTextAreaElement;
                            const textToSend = textarea.value.trim();
                            
                            // 전송할 내용이 없으면 무시
                            if (!textToSend) {
                              return;
                            }
                            
                            // 입력 필드를 즉시 초기화 (DOM + state 동기화)
                            textarea.value = "";
                            setDraftText("");
                            // 다음 onChange(IME compositionend 등)에서 들어오는 값은 무시
                            ignoreNextChangeRef.current = true;
                            
                            // 즉시 전송 (textOverride로 전달하여 중복 방지)
                            handleSendMessage(textToSend);
                          }
                        }}
                      />
                      <button
                        type="button"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          // 버튼 클릭 시에도 textarea 내용을 직접 읽어서 전송 후 완전히 비움
                          const container = (e.currentTarget.closest("div") as HTMLDivElement) || null;
                          const textarea = container?.querySelector("textarea") as HTMLTextAreaElement | null;
                          const value = textarea ? textarea.value.trim() : draftText.trim();
                          if (!value || isSendingMessage) return;
                          if (textarea) {
                            textarea.value = "";
                          }
                          setDraftText("");
                          handleSendMessage(value);
                        }}
                        disabled={isSendingMessage}
                        className="px-4 py-2 rounded-full text-sm font-semibold shadow-sm border border-slate-300 bg-slate-900 text-white disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-800"
                      >
                        {isSendingMessage ? "전송 중..." : "전송"}
                      </button>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center text-slate-500">
                채팅 세션을 선택해주세요.
              </div>
            )}
          </section>

          {/* 오른쪽: 환자 / 이송 정보 요약 (비율 1) */}
          <aside className="flex-[1] min-w-[320px] flex flex-col bg-slate-50">
            {selectedSession ? (
              <>
                <div className="px-3 py-2 border-b border-slate-200 bg-slate-50">
                  <div className="text-xs font-semibold text-slate-700 mb-1">환자 / 이송 정보 요약</div>
                  <div className="text-xs text-slate-500">병원 기준 · {selectedSession.hospital_name || hospitalName}</div>
                </div>
                <div className="p-3 flex-1 flex flex-col gap-3 overflow-y-auto">
                  {/* 1. 현재 위치 / 경로 */}
                  <div className="rounded-xl border border-slate-200 bg-white overflow-hidden flex flex-col flex-1 min-h-0">
                    <div className="px-3 py-2 border-b border-slate-200 flex items-center justify-between flex-shrink-0">
                      <span className="text-xs font-semibold text-slate-800">현재 위치 / 경로</span>
                      <span className="text-[10px] text-slate-500">구급차 기준</span>
                    </div>
                    <div className="flex-1 min-h-0">
                      {mapData && mapData.hospital && mapData.ambulanceCoords.lat && mapData.ambulanceCoords.lon ? (
                        <div className="w-full h-full">
                          <KakaoAmbulanceMap
                            coords={mapData.ambulanceCoords}
                            hospitals={[mapData.hospital]}
                            routePath={
                              mapData.hospital.hpid ? routePaths[mapData.hospital.hpid] || [] : []
                            }
                          />
                        </div>
                      ) : (
                        <div className="h-full bg-slate-100 flex flex-col items-center justify-center text-xs text-slate-500 gap-1 p-4">
                          <div>표시할 병원 정보가 없습니다.</div>
                          {selectedSession &&
                            (!selectedSession.current_lat || !selectedSession.current_lon) && (
                              <div className="text-[10px] mt-2">구급대원 위치 정보가 없습니다.</div>
                            )}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* 2. 예상 도착 시간 */}
                  <div className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs text-slate-800">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-semibold">예상 도착 시간</span>
                      <span className="text-xs text-slate-500">
                        {new Date().toLocaleTimeString("ko-KR", {
                          hour: "2-digit",
                          minute: "2-digit",
                          hour12: false,
                          timeZone: "Asia/Seoul",
                        })}
                      </span>
                    </div>
                    <div className="flex items-baseline gap-2">
                      <span className="text-2xl font-semibold text-slate-900">{etaMinutes !== undefined ? etaMinutes : "-"}</span>
                      <span className="text-xs text-slate-600">분 후 도착 예상</span>
                    </div>
                    <div className="mt-1 text-xs text-slate-600">남은 거리 약 {distanceKm !== undefined ? distanceKm.toFixed(1) : "-"} km</div>
                    <div className="mt-2 text-xs text-slate-600">이 화면에서는 이송 중 환자의 남은 거리와 예상 도착 시간을 한눈에 볼 수 있도록 간단한 요약 정보만 표시합니다.</div>
                  </div>

                  {/* 3. 환자 정보 / 인계 체크 포인트 */}
                  <div className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs text-slate-700">
                    <div className="font-semibold mb-2">환자 정보 / 인계 체크 포인트</div>
                    <div className="mb-2 text-slate-700">
                      {selectedSession.patient_age && selectedSession.patient_sex ? (
                        <>
                          현재 이송 중인 환자: {selectedSession.patient_age}세 {getSexLabel(selectedSession.patient_sex)} · Pre-KTAS {selectedSession.pre_ktas_class || "-"}점.
                        </>
                      ) : (
                        "환자 정보가 입력되지 않았습니다."
                      )}
                    </div>
                    {selectedSession.rag_summary && (
                      <div className="mb-2 text-slate-700">
                        <span className="font-semibold">주요 증상:</span> {selectedSession.rag_summary}
                      </div>
                    )}
                    {selectedSession.stt_full_text && (
                      <div className="mb-2 text-slate-700">
                        <span className="font-semibold">생체 징후:</span> {selectedSession.stt_full_text}
                      </div>
                    )}
                    <ul className="list-disc list-inside space-y-1 text-xs">
                      <li>환자 기본 정보(이름, 나이, 성별, 등록번호) 최종 확인</li>
                      <li>Pre-KTAS 또는 KTAS 등급과 분류 사유 재확인</li>
                      <li>증상 시작 시각과 최근 악화 시점이 기록되어 있는지 확인</li>
                      <li>투여한 약물과 시행한 처치, 알레르기 및 항응고제 복용 여부 공유 여부 확인</li>
                    </ul>
                  </div>
                </div>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
                세션을 선택하면 상세 정보가 표시됩니다.
              </div>
            )}
          </aside>
        </div>
      </div>

      {/* 삭제 확인 모달 */}
      {showDeleteModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold text-slate-900 mb-2">채팅 세션 삭제</h3>
            <p className="text-sm text-slate-600 mb-6">
              정말 이 채팅 세션을 삭제하시겠습니까?<br />
              삭제된 세션은 목록에서만 숨겨지며, 데이터는 보관됩니다.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={handleDeleteCancel}
                className="px-4 py-2 text-sm font-medium text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors"
              >
                취소
              </button>
              <button
                onClick={handleDeleteConfirm}
                disabled={deletingSessionId !== null}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {deletingSessionId !== null ? "삭제 중..." : "삭제"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 로그아웃 확인 모달 */}
      {showLogoutModal && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={handleLogoutCancel}
        >
          <div 
            className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              로그아웃
            </h3>
            <p className="text-gray-600 mb-6">
              로그아웃하시겠습니까?
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={handleLogoutCancel}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition"
              >
                취소
              </button>
              <button
                onClick={handleLogoutConfirm}
                className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition"
              >
                확인
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// 메시지 버블 컴포넌트
interface ERMessageBubbleProps {
  message: ChatMessage;
}

const ERMessageBubble: React.FC<ERMessageBubbleProps> = ({ message }) => {
  const isER = message.role === "ER";
  const senderLabel = isER ? "응급실" : "구급대원";

  return (
    <div className={`mb-3 flex ${isER ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[70%] rounded-2xl px-3 py-2 text-sm shadow-sm ${
          isER
            ? "bg-sky-600 text-white rounded-br-sm"
            : "bg-white text-slate-900 border border-slate-200 rounded-bl-sm"
        }`}
      >
        <div className="flex items-center justify-between mb-1">
          <span className="text-[11px] font-semibold opacity-80">{senderLabel}</span>
          <span className="text-[10px] opacity-60">{message.sentAt}</span>
        </div>
        {message.content && (
          <p className="whitespace-pre-wrap leading-snug">{message.content}</p>
        )}
        {message.imageUrl && (
          <div className="mt-2">
            <img
              src={message.imageUrl}
              alt="구급대원 전송 이미지"
              className="rounded-xl border border-slate-200 w-full max-h-64 object-cover"
              onError={(e) => {
                console.error("이미지 로드 실패:", message.imageUrl);
                const target = e.target as HTMLImageElement;
                target.style.display = 'none';
                const errorDiv = document.createElement('div');
                errorDiv.className = 'text-xs text-red-500 p-2 bg-red-50 rounded';
                errorDiv.textContent = '이미지를 불러올 수 없습니다.';
                target.parentElement?.appendChild(errorDiv);
              }}
            />
            <p className="mt-1 text-[10px] opacity-70">
              실제 서비스에서는 의료정보 보호를 위해 암호화와 접근 권한 제어가 필요합니다.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

