import React, { useState, useEffect, useRef, ChangeEvent, useCallback } from "react";
import type { HospitalHandoverSummary, ChatMessage, PatientTransportMeta, Hospital, Coords } from "../types";
import { MapDisplay } from "./MapDisplay";
import { getChatMessages, sendChatMessage, completeChatSession, uploadImage } from "../services/api";
import { getSocket } from "../services/socket";

interface ParamedicChatSlideOverProps {
  isOpen: boolean;
  session: HospitalHandoverSummary;
  hospital: Hospital;
  patientMeta: PatientTransportMeta;
  sttText?: string;
  emsId?: string; // 구급대원 식별코드 (로그인한 사용자의 ems_id)
  onClose: () => void;
  onHandoverComplete: (sessionId: string) => void;
  mapCoords: Coords;
  mapRoutePaths: Record<string, number[][]>;
  resolveHospitalColor: (hospital: Hospital, index: number) => string;
}

export const ParamedicChatSlideOver: React.FC<ParamedicChatSlideOverProps> = ({
  isOpen,
  session,
  hospital,
  patientMeta,
  sttText = "",
  emsId = "A100", // 기본값 (하위 호환성)
  onClose,
  onHandoverComplete,
  mapCoords,
  mapRoutePaths,
  resolveHospitalColor,
}) => {
  // 로그인한 구급대원의 ems_id 사용
  const PARAMEDIC_ID = emsId;
  const [localSession, setLocalSession] = useState<HospitalHandoverSummary>(session);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draftText, setDraftText] = useState("");
  const [draftImage, setDraftImage] = useState<string | undefined>();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const [confirmCode, setConfirmCode] = useState("");
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [isSendingMessage, setIsSendingMessage] = useState(false); // 메시지 전송 중 플래그
  const initialMessageSentRef = useRef<boolean>(false);

  useEffect(() => {
    setLocalSession(session);
  }, [session]);

  // 메시지 포맷팅 헬퍼 함수
  const formatMessages = useCallback((dbMessages: any[]): ChatMessage[] => {
    return dbMessages.map((msg) => ({
      id: `msg-${msg.message_id}`,
      role: msg.sender_type === "EMS" ? "PARAMEDIC" : "ER",
      content: msg.content,
      imageUrl: msg.image_url,
      sentAt: new Date(msg.sent_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: false }),
    }));
  }, []);

  // 초기 메시지 생성 헬퍼 함수
  const createInitialMessage = useCallback((text: string): ChatMessage => {
    return {
      id: "s1-m1",
      role: "PARAMEDIC",
      content: `119 구급대원 ${PARAMEDIC_ID}입니다. 현재 원문: ${text}`,
      sentAt: new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: false }),
    };
  }, []);

  // DB에서 메시지 로드
  useEffect(() => {
    if (!isOpen || !localSession.sessionId) {
      // sessionId가 없는 경우: 로컬 초기 메시지 표시 (한 번만)
      if (!isOpen) {
        setMessages([]);
        return;
      }
      if (!localSession.sessionId && sttText) {
        // 로컬 메시지만 표시 (DB 저장 안 함)
        const localMsg = createInitialMessage(sttText);
        setMessages([localMsg]);
      } else {
        setMessages([]);
      }
      return;
    }

    // sessionId가 있는 경우: DB에서 메시지 로드
    const loadMessages = async () => {
      try {
        const dbMessages = await getChatMessages(localSession.sessionId!);
        setMessages(formatMessages(dbMessages));
      } catch (error) {
        console.error("메시지 로드 실패:", error);
      }
    };

    // 초기 로드
    loadMessages();
    
    // WebSocket 연결 및 이벤트 리스너 설정
    if (localSession.sessionId) {
      const socket = getSocket();
      const sessionId = localSession.sessionId;
      
      // WebSocket으로 세션 참여
      socket.emit('join_session', { session_id: sessionId });
      console.log(`✅ ParamedicChat: 세션 ${sessionId}에 참여했습니다.`);
      
      // 새 메시지 수신 이벤트 리스너
      const handleNewMessage = (messageData: any) => {
        console.log('📨 ParamedicChat: 새 메시지 수신:', messageData);
        if (messageData.session_id === sessionId) {
          // 메시지 목록 다시 로드
          loadMessages();
        }
      };
      
      socket.on('new_message', handleNewMessage);
      
      return () => {
        // 세션에서 나가기
        socket.emit('leave_session', { session_id: sessionId });
        socket.off('new_message', handleNewMessage);
        console.log(`👋 ParamedicChat: 세션 ${sessionId}에서 나갔습니다.`);
      };
    }
  }, [isOpen, localSession.sessionId, formatMessages, createInitialMessage, sttText]);

  // sttText 변경 시 자동으로 메시지 전송 (중증 버튼 클릭 시 등)
  // 이전 sttText 값을 추적하여 실제로 변경되었을 때만 전송
  const prevSttTextRef = useRef<string>("");
  const sttTextSentRef = useRef<Set<string>>(new Set()); // 이미 전송한 sttText 추적
  
  // sttText를 채팅에 전송하는 함수
  const sendSttMessageToChat = useCallback(async (textToSend: string) => {
    if (!localSession.sessionId || !textToSend) {
      return;
    }
    
    // 이미 전송한 sttText인지 확인
    if (sttTextSentRef.current.has(textToSend)) {
      console.log("✅ 이미 전송한 sttText입니다:", textToSend);
      return;
    }
    
    try {
      // 기존 메시지 확인 (중복 체크)
      const dbMessages = await getChatMessages(localSession.sessionId!);
      const messageContent = `119 구급대원 ${PARAMEDIC_ID}입니다. 현재 원문: ${textToSend}`;
      
      // 이미 같은 내용의 메시지가 있는지 확인 (최근 메시지 10개만 체크)
      const recentMessages = dbMessages.slice(-10);
      const hasSameMessage = recentMessages.some(msg => 
        msg.content && msg.content.trim() === messageContent.trim()
      );
      
      if (hasSameMessage) {
        console.log("✅ 같은 내용의 메시지가 이미 있어 전송 건너뜀");
        // 이미 전송된 것으로 표시
        sttTextSentRef.current.add(textToSend);
        // 기존 메시지로 UI 업데이트
        setMessages(formatMessages(dbMessages));
        return;
      }

      console.log("📤 중증 버튼으로 생성된 메시지 전송:", messageContent);
      
      // 메시지 전송
      await sendChatMessage(
        localSession.sessionId!,
        "EMS",
        PARAMEDIC_ID,
        messageContent
      );
      
      // 전송 완료 표시
      sttTextSentRef.current.add(textToSend);
      console.log("✅ sttText 메시지 저장 성공");
      // 메시지 목록 다시 로드
      const updatedMessages = await getChatMessages(localSession.sessionId!);
      setMessages(formatMessages(updatedMessages));
    } catch (error) {
      console.error("❌ 메시지 저장 실패:", error);
      // 실패 시 전송 표시 제거하여 재시도 가능하게
      sttTextSentRef.current.delete(textToSend);
    }
  }, [localSession.sessionId, formatMessages, PARAMEDIC_ID]);
  
  // sttText 변경 시 자동으로 메시지 전송 (채팅이 열려있을 때만)
  useEffect(() => {
    if (!isOpen || !localSession.sessionId || !sttText) {
      return;
    }
    
    // 이미 전송한 sttText인지 확인 (먼저 체크하여 중복 방지)
    if (sttTextSentRef.current.has(sttText)) {
      console.log("✅ 이미 전송한 sttText입니다 (건너뜀):", sttText);
      prevSttTextRef.current = sttText; // 이전 값도 업데이트
      return;
    }
    
    // sttText가 실제로 변경되었는지 확인
    if (prevSttTextRef.current === sttText) {
      return;
    }
    
    // 이전 값 업데이트 (전송 전에 업데이트하여 중복 방지)
    prevSttTextRef.current = sttText;
    
    console.log("📤 sttText 변경 감지, 메시지 전송 예정:", sttText);
    
    // 약간의 지연을 두어 메시지 로드가 먼저 완료되도록
    const timeoutId = setTimeout(() => {
      sendSttMessageToChat(sttText);
    }, 500);
    
    return () => clearTimeout(timeoutId);
  }, [isOpen, localSession.sessionId, sttText, sendSttMessageToChat]);
  
  // 세션이 변경되면 초기 메시지 전송 플래그 리셋
  useEffect(() => {
    if (localSession.sessionId) {
      initialMessageSentRef.current = false;
      prevSttTextRef.current = ""; // sttText 추적 리셋
      sttTextSentRef.current.clear(); // 전송 기록 리셋
      console.log("🔄 세션 변경으로 초기 메시지 전송 플래그 리셋:", localSession.sessionId);
    }
  }, [localSession.sessionId]);

  const handleChangeFile = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    // 파일 타입 확인
    if (!file.type.startsWith('image/')) {
      alert('이미지 파일만 업로드할 수 있습니다.');
      return;
    }
    
    // 파일 크기 확인 (10MB 제한)
    if (file.size > 10 * 1024 * 1024) {
      alert('이미지 크기는 10MB 이하여야 합니다.');
      return;
    }
    
    // 미리보기용 URL 생성
    const url = URL.createObjectURL(file);
    setDraftImage(url);
    
    // 파일 객체 저장 (업로드 시 사용)
    if (fileInputRef.current) {
      (fileInputRef.current as any).uploadFile = file;
    }
  };

  const handleClickAttach = () => {
    fileInputRef.current?.click();
  };

  const handleClearImage = () => {
    if (draftImage) URL.revokeObjectURL(draftImage);
    setDraftImage(undefined);
  };

  const handleSendFromParamedic = async (textOverride?: string, imageOverride?: string) => {
    // 이미 전송 중이면 중복 전송 방지 (가장 먼저 체크)
    if (isSendingMessage) {
      console.warn("⚠️ 메시지 전송 중입니다. 중복 전송을 방지합니다.");
      return;
    }
    
    const text = textOverride || draftText.trim();
    const image = imageOverride || draftImage;
    if (!text && !image) return;
    
    // 전송 시작 플래그 설정 (다른 호출 방지)
    setIsSendingMessage(true);
    
    // 입력 필드 초기화 (textOverride가 있으면 이미 onKeyDown에서 초기화했지만, 확실히 하기 위해 다시 초기화)
    const messageToSend = text;
    const imageToSend = image;
    
    // 항상 입력 필드 초기화 (Enter 키로 인한 마지막 단어 남는 문제 해결)
    // textOverride가 있으면 이미 onKeyDown에서 초기화했지만, 확실히 하기 위해 다시 초기화
    setDraftText(""); // 항상 초기화
    if (draftImage) {
      handleClearImage(); // 항상 초기화
    }

    // DB에 저장 (sessionId가 있을 때만)
    if (localSession.sessionId) {
      try {
        let imagePath: string | undefined = undefined;
        
        // 이미지가 있으면 먼저 업로드
        if (imageToSend && fileInputRef.current && (fileInputRef.current as any).uploadFile) {
          const file = (fileInputRef.current as any).uploadFile;
          console.log("📤 이미지 업로드 시도:", file.name);
          try {
            const uploadResult = await uploadImage(file);
            imagePath = uploadResult.image_path;
            console.log("✅ 이미지 업로드 성공:", uploadResult);
          } catch (uploadError: any) {
            console.error("❌ 이미지 업로드 실패:", uploadError);
            alert(`이미지 업로드 실패: ${uploadError.message || "알 수 없는 오류"}`);
            setIsSendingMessage(false);
            // 실패 시 입력 필드 복원
            setDraftText(messageToSend);
            setDraftImage(imageToSend);
            return;
          }
        }
        
        console.log("📤 메시지 전송 시도:", {
          sessionId: localSession.sessionId,
          senderType: "EMS",
          senderRefId: PARAMEDIC_ID,
          content: messageToSend,
          imagePath: imagePath,
        });
        const savedMessage = await sendChatMessage(
          localSession.sessionId,
          "EMS",
          PARAMEDIC_ID,
          messageToSend,
          imagePath
        );
        console.log("✅ 메시지 저장 성공:", savedMessage);
        
        // DB에서 저장된 메시지를 로컬 상태에 추가
        const newMessage: ChatMessage = {
          id: `msg-${savedMessage.message_id}`,
          role: "PARAMEDIC",
          content: savedMessage.content,
          imageUrl: savedMessage.image_url || imageToSend,
          sentAt: new Date(savedMessage.sent_at).toLocaleTimeString("ko-KR", {
            hour: "2-digit",
            minute: "2-digit",
            hour12: false,
            timeZone: "Asia/Seoul",
          }),
        };
        setMessages((prev) => [...prev, newMessage]);
        
        // 파일 입력 초기화
        if (fileInputRef.current) {
          (fileInputRef.current as any).uploadFile = null;
          fileInputRef.current.value = '';
        }
        
        setIsSendingMessage(false); // 전송 완료
      } catch (error: any) {
        console.error("❌ 메시지 저장 실패:", error);
        console.error("❌ 에러 상세:", {
          message: error.message,
          response: error.response?.data,
          status: error.response?.status,
        });
        // 실패 시 입력 필드 복원
        setDraftText(messageToSend);
        if (imageToSend) setDraftImage(imageToSend);
        setIsSendingMessage(false); // 전송 실패
        alert(`메시지 저장 실패: ${error.response?.data?.error || error.message || "알 수 없는 오류"}`);
      }
    } else {
      console.warn("⚠️ sessionId가 없어 메시지를 DB에 저장할 수 없습니다. localSession:", localSession);
      setIsSendingMessage(false); // 전송 실패
    }
  };

  const handleOpenConfirmModal = () => {
    if (localSession.status === "COMPLETED") return;
    setConfirmCode("");
    setConfirmError(null);
    setIsConfirmOpen(true);
  };

  const handleCloseConfirmModal = () => {
    setIsConfirmOpen(false);
    setConfirmCode("");
    setConfirmError(null);
  };

  const handleConfirmHandoverComplete = async () => {
    const trimmed = confirmCode.trim();
    if (!trimmed) {
      setConfirmError("식별코드를 입력해 주세요.");
      return;
    }
    if (trimmed !== PARAMEDIC_ID) {
      setConfirmError("식별코드가 일치하지 않습니다. 다시 확인해 주세요.");
      return;
    }

    // DB에 인계 완료 처리
    if (localSession.sessionId) {
      try {
        await completeChatSession(localSession.sessionId, PARAMEDIC_ID);
        console.log("✅ 인계 완료 처리 성공");
      } catch (error: any) {
        console.error("❌ 인계 완료 처리 실패:", error);
        setConfirmError(error.message || "인계 완료 처리 중 오류가 발생했습니다.");
        return;
      }
    }

    setLocalSession((prev) => ({ ...prev, status: "COMPLETED" }));
    onHandoverComplete(localSession.id);
    handleCloseConfirmModal();
  };

  if (!isOpen) return null;

  const statusLabel = localSession.status === "ONGOING" ? "이송 / 인계 진행 중" : "인계 완료";
  const sexLabel = patientMeta.patientSex === "M" ? "남" : patientMeta.patientSex === "F" ? "여" : "-";

  return (
    <div className="fixed inset-0 z-50 flex transition-all duration-300 ease-in-out">
      <div className="flex-1 bg-black/30 transition-opacity duration-300" onClick={onClose} />
      <div className="w-full max-w-6xl h-full bg-white shadow-2xl border-l border-slate-200 flex flex-col slide-in-from-right">
        {/* 상단 헤더 */}
        <header className="h-14 flex items-center justify-between px-4 border-b border-slate-200 bg-slate-50">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold tracking-wide text-emerald-700 uppercase">SAFE BRIDGE</span>
            <span className="w-px h-4 bg-slate-300" />
            <span className="text-sm font-semibold text-slate-900">구급대원 인계 채팅</span>
          </div>
          <button type="button" onClick={onClose} className="text-sm text-slate-500 hover:text-slate-700 px-3 py-1 rounded hover:bg-slate-100">
            닫기
          </button>
        </header>

        {/* 상태 / 병원 정보 */}
        <div className="px-4 py-3 border-b border-slate-200 bg-white flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-slate-900">{localSession.hospitalName} 응급실과의 인계 채팅</span>
              <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-700">
                {statusLabel}
              </span>
            </div>
            <div className="mt-1 text-xs text-slate-500">병원 분류: {localSession.regionLabel}</div>
          </div>
          <button
            type="button"
            onClick={handleOpenConfirmModal}
            disabled={localSession.status === "COMPLETED"}
            className="px-4 py-2 rounded-full text-xs font-semibold border border-emerald-600 text-emerald-700 bg-emerald-50 hover:bg-emerald-100 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            인계 처리
          </button>
        </div>

        {/* 채팅 + 메타 2-분할 */}
        <div className="flex flex-1 min-h-0">
          {/* 채팅 영역 */}
          <section className="flex-[3] flex flex-col min-w-[360px] border-r border-slate-200">
            <div className="flex-1 overflow-y-auto px-4 py-3 bg-slate-50">
              {messages.map((m) => (
                <ParamedicMessageBubble key={m.id} message={m} />
              ))}
            </div>
            <div className="border-t border-slate-200 bg-white px-4 py-3">
              {draftImage && (
                <div className="mb-2 flex items-center gap-2">
                  <div className="relative w-32 h-20 rounded-xl overflow-hidden border border-slate-200 bg-slate-50">
                    <img src={draftImage} alt="첨부 예정 이미지" className="w-full h-full object-cover" />
                  </div>
                  <div className="flex flex-col gap-1">
                    <button 
                      type="button" 
                      className="text-xs px-2 py-1 rounded bg-emerald-500 text-white hover:bg-emerald-600"
                      onClick={() => {
                        if (localSession.sessionId && fileInputRef.current && (fileInputRef.current as any).uploadFile) {
                          handleSendFromParamedic("", draftImage);
                        } else {
                          alert("이미지를 전송할 수 없습니다. 세션이 연결되지 않았습니다.");
                        }
                      }}
                      disabled={isSendingMessage}
                    >
                      전송
                    </button>
                    <button type="button" className="text-xs text-slate-600 underline" onClick={handleClearImage}>
                      제거
                    </button>
                  </div>
                </div>
              )}
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleClickAttach}
                  className="h-10 px-3 rounded-xl border border-slate-300 bg-slate-50 text-xs text-slate-700 hover:bg-slate-100 flex items-center gap-1"
                >
                  <span className="inline-block w-4 h-4 rounded-full border border-slate-400 flex items-center justify-center text-[10px]">+</span>
                  사진/이미지 첨부
                </button>
                <div className="flex-1">
                  <textarea
                    rows={1}
                    className="w-full bg-transparent text-sm leading-snug text-slate-900 placeholder:text-slate-400 focus:outline-none resize-none border border-emerald-500 rounded-xl px-3 py-2"
                    placeholder="응급실에 전달할 환자 상태, 처치 내용, 추가 정보를 입력하세요."
                    value={draftText}
                    onChange={(e) => {
                      // Enter 키로 인한 줄바꿈 제거 (Shift+Enter는 허용하지만, 일반 Enter는 제거)
                      let value = e.target.value;
                      // 줄바꿈이 있고, 마지막 문자가 줄바꿈이면 제거 (Enter 키 입력 방지)
                      if (value.includes('\n') && value.endsWith('\n')) {
                        // 마지막 줄바꿈 제거
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
                        
                        // Enter 키 입력 전의 현재 값을 가져옴
                        const textToSend = draftText.trim();
                        const imageToSend = draftImage;
                        
                        // 전송할 내용이 없으면 무시
                        if (!textToSend && !imageToSend) {
                          return;
                        }
                        
                        // 입력 필드를 즉시 초기화 (e.preventDefault()로 Enter 키 입력을 막았으므로 확실히 초기화)
                        setDraftText("");
                        handleClearImage();
                        
                        // 즉시 전송 (textOverride로 전달하여 중복 방지)
                        handleSendFromParamedic(textToSend, imageToSend);
                      }
                    }}
                  />
                </div>
                <button
                  type="button"
                  onClick={() => handleSendFromParamedic()}
                  disabled={(!draftText.trim() && !draftImage) || isSendingMessage}
                  className="h-10 px-4 rounded-xl text-sm font-semibold shadow-sm border border-slate-300 bg-emerald-600 text-white disabled:opacity-40 disabled:cursor-not-allowed hover:bg-emerald-700"
                >
                  {isSendingMessage ? "전송 중..." : "전송"}
                </button>
              </div>
              <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handleChangeFile} />
            </div>
          </section>

          {/* 오른쪽 메타 정보 */}
          <aside className="flex-[2] min-w-[320px] flex flex-col bg-slate-50">
            <div className="px-3 py-2 border-b border-slate-200 bg-slate-50">
              <div className="text-xs font-semibold text-slate-700 mb-1">환자 / 이송 정보 요약</div>
              <div className="text-xs text-slate-500">병원 기준 · {localSession.hospitalName}</div>
            </div>
            <div className="p-3 flex-1 flex flex-col gap-3 overflow-y-auto">
              <div className="rounded-xl border border-slate-200 bg-white overflow-hidden flex flex-col min-h-[220px]">
                <div className="px-3 py-2 border-b border-slate-200 flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-800">현재 위치 / 경로</span>
                  <span className="text-[10px] text-slate-500">구급차 기준</span>
                </div>
                {hospital ? (
                  <MapDisplay
                    coords={mapCoords}
                    hospitals={[hospital]}
                    routePaths={mapRoutePaths}
                    approvedHospital={hospital}
                    resolveHospitalColor={resolveHospitalColor}
                    compact
                    compactHeightClass="h-[240px]"
                  />
                ) : (
                  <div className="flex-1 bg-slate-100 flex flex-col items-center justify-center text-xs text-slate-500 gap-1 p-4">
                    <div>표시할 병원 정보가 없습니다.</div>
                  </div>
                )}
              </div>
              <div className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs text-slate-800">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold">예상 도착 시간</span>
                  <span className="text-xs text-slate-500">{patientMeta.lastUpdated || "업데이트 중"}</span>
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-semibold text-slate-900">
                    {patientMeta.etaMinutes !== undefined ? patientMeta.etaMinutes : "-"}
                  </span>
                  <span className="text-xs text-slate-600">분 후 도착 예상</span>
                </div>
                <div className="mt-1 text-xs text-slate-600">
                  남은 거리 약 {patientMeta.distanceKm !== undefined ? patientMeta.distanceKm.toFixed(1) : "-"} km
                </div>
                <div className="mt-2 text-xs text-slate-600">
                  이 화면에서는 이송 중 환자의 남은 거리와 예상 도착 시간을 한눈에 볼 수 있도록 간단한 요약 정보만 표시합니다.
                </div>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs text-slate-700">
                <div className="font-semibold mb-2">환자 정보 / 인계 체크 포인트</div>
                <div className="mb-2 text-slate-700">
                  {patientMeta.patientAge && patientMeta.patientSex ? (
                    <>
                      현재 이송 중인 환자: {patientMeta.patientAge}세 {sexLabel} · Pre-KTAS {patientMeta.preKtasLevel || "-"}점.
                    </>
                  ) : (
                    "환자 정보가 입력되지 않았습니다."
                  )}
                </div>
                {patientMeta.chiefComplaint && (
                  <div className="mb-2 text-slate-700">
                    <span className="font-semibold">주요 증상:</span> {patientMeta.chiefComplaint}
                  </div>
                )}
                {patientMeta.vitalsSummary && (
                  <div className="mb-2 text-slate-700">
                    <span className="font-semibold">생체 징후:</span> {patientMeta.vitalsSummary}
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
          </aside>
        </div>

        {/* 인계 완료 확인 모달 */}
        <HandoverConfirmModal
          isOpen={isConfirmOpen}
          paramedicId={PARAMEDIC_ID}
          confirmCode={confirmCode}
          errorMessage={confirmError ?? undefined}
          onChangeCode={setConfirmCode}
          onClose={handleCloseConfirmModal}
          onConfirm={handleConfirmHandoverComplete}
        />
      </div>
    </div>
  );
};

// 메시지 버블 컴포넌트
interface ParamedicMessageBubbleProps {
  message: ChatMessage;
}

const ParamedicMessageBubble: React.FC<ParamedicMessageBubbleProps> = ({ message }) => {
  const isParamedic = message.role === "PARAMEDIC";
  const senderLabel = isParamedic ? "구급대원" : "응급실";

  return (
    <div className={`mb-3 flex ${isParamedic ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[70%] rounded-2xl px-3 py-2 text-sm shadow-sm ${
          isParamedic ? "bg-emerald-600 text-white rounded-br-sm" : "bg-white text-slate-900 border border-slate-200 rounded-bl-sm"
        }`}
      >
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-semibold opacity-80">{senderLabel}</span>
          <span className="text-[10px] opacity-60">{message.sentAt}</span>
        </div>
        {message.content && <p className="whitespace-pre-wrap leading-snug">{message.content}</p>}
        {message.imageUrl && (
          <div className="mt-2">
            <img src={message.imageUrl} alt="구급대원 전송 이미지" className="rounded-xl border border-slate-200 w-full max-h-64 object-cover" />
            {isParamedic && (
              <p className="mt-1 text-[10px] opacity-70">실제 서비스에서는 의료정보 보호를 위해 암호화와 접근 권한 제어가 필요합니다.</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

// 인계 완료 확인 모달
interface HandoverConfirmModalProps {
  isOpen: boolean;
  paramedicId: string;
  confirmCode: string;
  errorMessage?: string;
  onChangeCode: (value: string) => void;
  onClose: () => void;
  onConfirm: () => void;
}

const HandoverConfirmModal: React.FC<HandoverConfirmModalProps> = ({
  isOpen,
  paramedicId,
  confirmCode,
  errorMessage,
  onChangeCode,
  onClose,
  onConfirm,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40">
      <div className="w-full max-w-sm rounded-2xl bg-white shadow-xl p-5">
        <div className="text-sm font-semibold text-slate-900 mb-1">환자 인계 처리</div>
        <p className="text-xs text-slate-600 mb-4">
          정말 환자 인계 완료 상태로 전환하시겠습니까?
          <br />
          구급대원 본인이 맞는지 확인하기 위해 식별코드를 한 번 더 입력해 주세요.
        </p>
        <div className="mb-3">
          <label className="block text-xs text-slate-700 mb-1">구급대원 식별코드 재입력 (예: {paramedicId})</label>
          <input
            type="text"
            value={confirmCode}
            onChange={(e) => onChangeCode(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
            placeholder="식별코드를 입력하세요."
          />
          {errorMessage && <p className="mt-1 text-xs text-red-600">{errorMessage}</p>}
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-full text-xs border border-slate-300 text-slate-700 bg-white hover:bg-slate-50"
          >
            취소
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="px-4 py-2 rounded-full text-xs font-semibold border border-emerald-600 text-white bg-emerald-600 hover:bg-emerald-700"
          >
            인계 처리
          </button>
        </div>
      </div>
    </div>
  );
};

