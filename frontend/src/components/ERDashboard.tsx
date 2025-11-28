import React, { useState, useEffect, useRef } from "react";
import type { ChatMessage, Hospital } from "../types";
import { getChatSessions, getChatMessages, sendChatMessage, getChatSession } from "../services/api";
import { MapDisplay } from "./MapDisplay";

interface ChatSession {
  session_id: number;
  request_id: number;
  assignment_id: number;
  started_at: string;
  ended_at?: string;
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
}

interface ERDashboardProps {
  hospitalId?: string;
  hospitalName?: string;
}

const HOSPITAL_ID = "A1500002"; // 전남대학교병원 (실제로는 설정에서 가져올 수 있음)

export const ERDashboard: React.FC<ERDashboardProps> = ({
  hospitalId: propHospitalId, // hospitalId가 없으면 모든 세션 조회
  hospitalName = "전남대학교병원",
}) => {
  // URL 파라미터에서 hospital_id 가져오기
  const [hospitalId, setHospitalId] = useState<string | undefined>(() => {
    const urlParams = new URLSearchParams(window.location.search);
    return propHospitalId || urlParams.get("hospital_id") || undefined;
  });
  
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [selectedSession, setSelectedSession] = useState<ChatSession | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draftText, setDraftText] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 세션 목록 로드
  const loadSessions = async () => {
    try {
      console.log("ERDashboard: 세션 목록 로드 시작, hospitalId:", hospitalId);
      const data = await getChatSessions(hospitalId);
      console.log("ERDashboard: 세션 목록 로드 완료, 세션 수:", data.length, data);
      setSessions(data);
      if (data.length > 0 && !selectedSession) {
        setSelectedSession(data[0]);
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
      const formattedMessages: ChatMessage[] = dbMessages.map((msg) => ({
        id: `msg-${msg.message_id}`,
        role: msg.sender_type === "EMS" ? "PARAMEDIC" : "ER",
        content: msg.content,
        imageUrl: msg.image_url,
        sentAt: new Date(msg.sent_at).toLocaleTimeString("ko-KR", {
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
        }),
      }));
      setMessages(formattedMessages);
    } catch (error) {
      console.error("메시지 로드 실패:", error);
    }
  };

  // 초기 로드
  useEffect(() => {
    console.log("ERDashboard: 초기 로드, hospitalId:", hospitalId);
    loadSessions();
    // 주기적 새로고침 (10초마다 - 더 빠른 업데이트)
    const interval = setInterval(() => {
      setRefreshing(true);
      loadSessions();
    }, 10000);
    return () => clearInterval(interval);
  }, [hospitalId]);

  // 선택된 세션 변경 시 메시지 로드
  useEffect(() => {
    if (selectedSession && selectedSession.session_id) {
      loadMessages(selectedSession.session_id);
      // 메시지 자동 새로고침 (3초마다 - 더 빠른 업데이트)
      const interval = setInterval(() => {
        if (selectedSession && selectedSession.session_id) {
          loadMessages(selectedSession.session_id);
        }
      }, 3000);
      return () => clearInterval(interval);
    } else {
      setMessages([]);
    }
  }, [selectedSession]);

  // 메시지 전송
  const handleSendMessage = async () => {
    const text = draftText.trim();
    if (!text) return;
    
    if (!selectedSession) {
      console.error("선택된 세션이 없습니다.");
      return;
    }
    
    if (!selectedSession.session_id) {
      console.error("세션 ID가 없습니다:", selectedSession);
      return;
    }

    const newMessage: ChatMessage = {
      id: `local-${Date.now()}`,
      role: "ER",
      content: text,
      sentAt: new Date().toLocaleTimeString("ko-KR", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }),
    };

    // 로컬 상태에 먼저 추가
    setMessages((prev) => [...prev, newMessage]);
    setDraftText("");

    // DB에 저장
    try {
      console.log("응급실 메시지 전송 시도:", {
        session_id: selectedSession.session_id,
        sender_type: "HOSPITAL",
        sender_ref_id: hospitalId,
        content: text,
      });
      
      const savedMessage = await sendChatMessage(
        selectedSession.session_id,
        "HOSPITAL",
        hospitalId || "A1500002", // 기본값
        text
      );
      
      console.log("응급실 메시지 저장 성공:", savedMessage);
      
      // DB에서 저장된 메시지로 업데이트
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === newMessage.id
            ? {
                ...msg,
                id: `msg-${savedMessage.message_id}`,
                sentAt: new Date(savedMessage.sent_at).toLocaleTimeString("ko-KR", {
                  hour: "2-digit",
                  minute: "2-digit",
                  hour12: false,
                }),
              }
            : msg
        )
      );
    } catch (error) {
      console.error("메시지 저장 실패:", error);
      // 실패해도 로컬 메시지는 유지
    }
  };

  // 메시지 스크롤
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const getStatusLabel = (session: ChatSession) => {
    return session.ended_at ? "인계 완료" : "인계 진행 중";
  };

  const getSexLabel = (sex: string | null) => {
    if (sex === "M") return "남";
    if (sex === "F") return "여";
    return "-";
  };

  const formatTime = (timeStr: string | null) => {
    if (!timeStr) return "";
    const date = new Date(timeStr);
    return date.toLocaleTimeString("ko-KR", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  };

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
    <div className="min-h-screen bg-slate-50 flex">
      {/* 왼쪽: 인계 채팅 목록 */}
      <aside className="w-80 bg-white border-r border-slate-200 flex flex-col">
        <div className="px-4 py-3 border-b border-slate-200 bg-slate-50">
          <h1 className="text-sm font-bold text-slate-900">SAFE BRIDGE 응급실 인계 채팅 대시보드</h1>
          <p className="text-xs text-slate-600 mt-1">구급대원별 세션 단위</p>
          {hospitalId && (
            <p className="text-xs text-slate-500 mt-1">병원 ID: {hospitalId}</p>
          )}
          <div className="mt-2 flex items-center justify-between">
            <span className="text-xs text-slate-500">총 {sessions.length}건</span>
            <button
              onClick={() => {
                setRefreshing(true);
                loadSessions();
              }}
              className="text-xs text-emerald-600 hover:text-emerald-700"
              disabled={refreshing}
            >
              {refreshing ? "새로고침 중..." : "새로고침"}
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
          {sessions.length === 0 ? (
            <div className="p-4 text-center text-sm text-slate-500">
              진행 중인 인계 채팅이 없습니다.
            </div>
          ) : (
            sessions.map((session) => (
              <button
                key={session.session_id}
                onClick={() => setSelectedSession(session)}
                className={`w-full text-left px-4 py-3 border-b border-slate-100 hover:bg-slate-50 transition-colors ${
                  selectedSession?.session_id === session.session_id ? "bg-emerald-50 border-l-4 border-l-emerald-600" : ""
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-semibold text-slate-900">
                    {session.ems_id || "알 수 없음"}
                  </span>
                  <span className="text-xs text-slate-500">{formatTime(session.started_at)}</span>
                </div>
                <div className="text-xs text-slate-600 mb-1">
                  {session.patient_age ? `${session.patient_age}세` : ""} {getSexLabel(session.patient_sex)}
                </div>
                {session.rag_summary && (
                  <div className="text-xs text-slate-700 mb-1 truncate">{session.rag_summary}</div>
                )}
                <div className="flex items-center justify-between">
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full ${
                      session.ended_at
                        ? "bg-slate-100 text-slate-600"
                        : "bg-emerald-100 text-emerald-700"
                    }`}
                  >
                    {getStatusLabel(session)}
                  </span>
                  {session.latest_message && (
                    <span className="text-xs text-slate-400 truncate max-w-[120px]">
                      {session.latest_message.content?.substring(0, 20)}...
                    </span>
                  )}
                </div>
              </button>
            ))
          )}
        </div>
      </aside>

      {/* 중간: 채팅 영역 */}
      <main className="flex-1 flex flex-col min-w-0">
        {selectedSession ? (
          <>
            {/* 채팅 헤더 */}
            <div className="px-4 py-3 border-b border-slate-200 bg-white">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-semibold text-slate-900">
                    구급대원 {selectedSession.ems_id || "알 수 없음"}와의 인계 채팅
                  </h2>
                  <div className="text-xs text-slate-500 mt-1">
                    {selectedSession.patient_age ? `${selectedSession.patient_age}세` : ""}{" "}
                    {getSexLabel(selectedSession.patient_sex)} · Pre-KTAS{" "}
                    {selectedSession.pre_ktas_class || "-"}점
                  </div>
                </div>
                <span
                  className={`text-xs px-2 py-1 rounded-full ${
                    selectedSession.ended_at
                      ? "bg-slate-100 text-slate-600"
                      : "bg-emerald-100 text-emerald-700"
                  }`}
                >
                  {getStatusLabel(selectedSession)}
                </span>
              </div>
            </div>

            {/* 메시지 영역 */}
            <div className="flex-1 overflow-y-auto px-4 py-3 bg-slate-50">
              {messages.map((msg) => (
                <ERMessageBubble key={msg.id} message={msg} />
              ))}
              <div ref={messagesEndRef} />
            </div>

            {/* 메시지 입력 */}
            <div className="border-t border-slate-200 bg-white px-4 py-3">
              <div className="flex items-center gap-2">
                <div className="flex-1">
                  <textarea
                    rows={1}
                    className="w-full bg-transparent text-sm leading-snug text-slate-900 placeholder:text-slate-400 focus:outline-none resize-none border border-emerald-500 rounded-xl px-3 py-2"
                    placeholder="구급대원에게 전달할 지시사항이나 질문을 입력하세요. (사진 전송은 구급대원 단말에서만 가능)"
                    value={draftText}
                    onChange={(e) => setDraftText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleSendMessage();
                      }
                    }}
                  />
                </div>
                <button
                  type="button"
                  onClick={handleSendMessage}
                  disabled={!draftText.trim()}
                  className="h-10 px-4 rounded-xl text-sm font-semibold shadow-sm border border-slate-300 bg-emerald-600 text-white disabled:opacity-40 disabled:cursor-not-allowed hover:bg-emerald-700"
                >
                  전송
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-slate-500">
            채팅 세션을 선택해주세요.
          </div>
        )}
      </main>

      {/* 오른쪽: 구급대원 위치/도착 예상 */}
      <aside className="w-96 bg-white border-l border-slate-200 flex flex-col">
        {selectedSession ? (
          <>
            <div className="px-3 py-2 border-b border-slate-200 bg-slate-50">
              <div className="text-xs font-semibold text-slate-700 mb-1">구급대원 위치/도착 예상</div>
              <span
                className={`text-xs px-2 py-1 rounded-full inline-block ${
                  selectedSession.ended_at
                    ? "bg-slate-100 text-slate-600"
                    : "bg-emerald-100 text-emerald-700"
                }`}
              >
                {getStatusLabel(selectedSession)}
              </span>
            </div>
            <div className="flex-1 overflow-y-auto p-3">
              {/* 지도 영역 (간단한 플레이스홀더) */}
              <div className="rounded-xl border border-slate-200 bg-slate-100 h-64 mb-3 flex items-center justify-center text-xs text-slate-500">
                지도 표시 영역
                <br />
                (구급대원 위치 및 경로)
              </div>

              {/* 도착 예상 시간 */}
              <div className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs text-slate-800 mb-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold">예상 도착 시간</span>
                  <span className="text-xs text-slate-500">{formatTime(new Date().toISOString())}</span>
                </div>
                <div className="text-2xl font-semibold text-slate-900 mb-1">-</div>
                <div className="text-xs text-slate-600">남은 거리 약 - km</div>
              </div>

              {/* 인계 체크포인트 */}
              <div className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs text-slate-700">
                <div className="font-semibold mb-2">인계 체크포인트</div>
                <ul className="list-disc list-inside space-y-1 text-xs">
                  <li>Pre-KTAS/KTAS 등급 확인</li>
                  <li>혈압/맥박/호흡/산소포화도 최신 수치 반영 여부</li>
                  <li>필요 시 도착 전 추가 검사 또는 처치 지시</li>
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
            ? "bg-emerald-600 text-white rounded-br-sm"
            : "bg-white text-slate-900 border border-slate-200 rounded-bl-sm"
        }`}
      >
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-semibold opacity-80">{senderLabel}</span>
          <span className="text-[10px] opacity-60">{message.sentAt}</span>
        </div>
        {message.content && <p className="whitespace-pre-wrap leading-snug">{message.content}</p>}
        {message.imageUrl && (
          <div className="mt-2">
            <img
              src={message.imageUrl}
              alt="전송 이미지"
              className="rounded-xl border border-slate-200 w-full max-h-64 object-cover"
            />
          </div>
        )}
      </div>
    </div>
  );
};

