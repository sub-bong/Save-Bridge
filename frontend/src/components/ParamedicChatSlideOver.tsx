import React, { useState, useEffect, useRef, ChangeEvent } from "react";
import type { HospitalHandoverSummary, ChatMessage, PatientTransportMeta, Hospital, Coords } from "../types";
// import { MapDisplay } from "./MapDisplay";
import { getChatMessages, sendChatMessage } from "../services/api";
import { KakaoAmbulanceMap } from "./KakaoAmbulanceMap";

interface ParamedicChatSlideOverProps {
  isOpen: boolean;
  session: HospitalHandoverSummary;
  hospital: Hospital;
  patientMeta: PatientTransportMeta;
  sttText?: string;
  onClose: () => void;
  onHandoverComplete: (sessionId: string) => void;
  mapCoords: Coords;
  mapRoutePaths: Record<string, number[][]>;
  // resolveHospitalColor: (hospital: Hospital, index: number) => string;
}

const PARAMEDIC_ID = "A100"; // 구급대원 식별코드 (실제로는 설정에서 가져올 수 있음)

export const ParamedicChatSlideOver: React.FC<ParamedicChatSlideOverProps> = ({
  isOpen,
  session,
  hospital,
  patientMeta,
  sttText = "",
  onClose,
  onHandoverComplete,
  mapCoords,
  mapRoutePaths,
  // resolveHospitalColor,
}) => {
  const [localSession, setLocalSession] = useState<HospitalHandoverSummary>(session);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draftText, setDraftText] = useState("");
  const [draftImage, setDraftImage] = useState<string | undefined>();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const [confirmCode, setConfirmCode] = useState("");
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const initialMessageSentRef = useRef<boolean>(false);

  useEffect(() => {
    setLocalSession(session);
  }, [session]);

  // DB에서 기존 메시지 로드
  useEffect(() => {
    if (isOpen && localSession.sessionId) {
      const loadMessages = async () => {
        try {
          // 기존 메시지 로드
          const dbMessages = await getChatMessages(localSession.sessionId!);
          const formattedMessages: ChatMessage[] = dbMessages.map((msg) => ({
            id: `msg-${msg.message_id}`,
            role: msg.sender_type === "EMS" ? "PARAMEDIC" : "ER",
            content: msg.content,
            imageUrl: msg.image_url,
            sentAt: new Date(msg.sent_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: false }),
          }));

          setMessages(formattedMessages);
        } catch (error) {
          console.error("메시지 로드 실패:", error);
        }
      };

      // 초기 로드
      loadMessages();

      // 메시지 자동 새로고침 (3초마다 - 양방향 통신)
      const interval = setInterval(() => {
        if (localSession.sessionId) {
          loadMessages();
        }
      }, 3000);

      return () => clearInterval(interval);
    } else if (isOpen && messages.length === 0 && sttText) {
      // sessionId가 없으면 초기 메시지만 로컬에 표시
      const now = new Date();
      const initialMessages: ChatMessage[] = [
        {
          id: "s1-m1",
          role: "PARAMEDIC",
          content: `119 구급대원 ${PARAMEDIC_ID}입니다. 현재 ${sttText}`,
          sentAt: now.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: false }),
        },
      ];
      setMessages(initialMessages);
    }
  }, [isOpen, localSession.sessionId]);

  // 초기 메시지 전송 (sessionId가 있고 sttText가 있을 때 한 번만)
  useEffect(() => {
    if (!isOpen || !localSession.sessionId || !sttText) return;
    if (initialMessageSentRef.current) return;

    const sendInitialMessage = async () => {
      // 이미 전송 중이면 리턴
      if (initialMessageSentRef.current) return;

      // 플래그를 먼저 설정하여 중복 실행 방지
      initialMessageSentRef.current = true;

      // 기존 메시지 확인
      try {
        const dbMessages = await getChatMessages(localSession.sessionId!);
        // 이미 메시지가 있으면 초기 메시지 전송 안 함
        if (dbMessages.length > 0) {
          console.log("기존 메시지가 있어 초기 메시지 전송 건너뜀");
          return;
        }
      } catch (error) {
        console.error("기존 메시지 확인 실패:", error);
        initialMessageSentRef.current = false; // 에러 시 플래그 리셋
        return;
      }

      const initialContent = `119 구급대원 ${PARAMEDIC_ID}입니다. 현재 ${sttText}`;
      try {
        console.log("초기 메시지 전송 시도:", {
          sessionId: localSession.sessionId,
          senderType: "EMS",
          senderRefId: PARAMEDIC_ID,
          content: initialContent,
        });

        const savedMessage = await sendChatMessage(localSession.sessionId!, "EMS", PARAMEDIC_ID, initialContent);

        console.log("초기 메시지 저장 성공:", savedMessage);

        // 메시지 목록 다시 로드
        const dbMessages = await getChatMessages(localSession.sessionId!);
        const formattedMessages: ChatMessage[] = dbMessages.map((msg) => ({
          id: `msg-${msg.message_id}`,
          role: msg.sender_type === "EMS" ? "PARAMEDIC" : "ER",
          content: msg.content,
          imageUrl: msg.image_url,
          sentAt: new Date(msg.sent_at).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: false }),
        }));
        setMessages(formattedMessages);
      } catch (error) {
        console.error("초기 메시지 저장 실패:", error);
        initialMessageSentRef.current = false; // 에러 시 플래그 리셋하여 재시도 가능
      }
    };

    sendInitialMessage();
  }, [isOpen, localSession.sessionId, sttText]);

  // 세션이 변경되면 초기 메시지 전송 플래그 리셋
  useEffect(() => {
    if (localSession.sessionId) {
      initialMessageSentRef.current = false;
    }
  }, [localSession.sessionId]);

  const handleChangeFile = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const url = URL.createObjectURL(file);
    setDraftImage(url);
  };

  const handleClickAttach = () => {
    fileInputRef.current?.click();
  };

  const handleClearImage = () => {
    if (draftImage) URL.revokeObjectURL(draftImage);
    setDraftImage(undefined);
  };

  const handleSendFromParamedic = async () => {
    const text = draftText.trim();
    if (!text && !draftImage) return;

    const newMessage: ChatMessage = {
      id: `local-${Date.now()}`,
      role: "PARAMEDIC",
      content: text,
      imageUrl: draftImage,
      sentAt: new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: false }),
    };

    // 로컬 상태에 먼저 추가 (즉시 UI 업데이트)
    setMessages((prev) => [...prev, newMessage]);
    setDraftText("");
    handleClearImage();

    // DB에 저장 (sessionId가 있을 때만)
    if (localSession.sessionId) {
      try {
        console.log("메시지 전송 시도:", {
          sessionId: localSession.sessionId,
          senderType: "EMS",
          senderRefId: PARAMEDIC_ID,
          content: text,
        });
        const savedMessage = await sendChatMessage(
          localSession.sessionId,
          "EMS",
          PARAMEDIC_ID,
          text,
          draftImage ? undefined : undefined // TODO: 이미지 업로드 처리 필요
        );
        console.log("메시지 저장 성공:", savedMessage);
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
    } else {
      console.warn("sessionId가 없어 메시지를 DB에 저장할 수 없습니다. localSession:", localSession);
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

  const handleConfirmHandoverComplete = () => {
    const trimmed = confirmCode.trim();
    if (!trimmed) {
      setConfirmError("식별코드를 입력해 주세요.");
      return;
    }
    if (trimmed !== PARAMEDIC_ID) {
      setConfirmError("식별코드가 일치하지 않습니다. 다시 확인해 주세요.");
      return;
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
              <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-700">{statusLabel}</span>
            </div>
            <div className="mt-1 text-xs text-slate-500">병원 분류: {localSession.regionLabel}</div>
          </div>
          <button
            type="button"
            onClick={handleOpenConfirmModal}
            disabled={localSession.status === "COMPLETED"}
            className="px-4 py-2 rounded-full text-xs font-semibold border border-emerald-600 text-emerald-700 bg-emerald-50 hover:bg-emerald-100 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            환자 인계 완료
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
                  <button type="button" className="text-xs text-slate-600 underline" onClick={handleClearImage}>
                    이미지 제거
                  </button>
                </div>
              )}
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleClickAttach}
                  className="h-10 px-3 rounded-xl border border-slate-300 bg-slate-50 text-xs text-slate-700 hover:bg-slate-100 flex items-center gap-1"
                >
                  <span className=" w-4 h-4 rounded-full border border-slate-400 flex items-center justify-center text-[10px]">+</span>
                  사진/이미지 첨부
                </button>
                <div className="flex-1">
                  <textarea
                    rows={1}
                    className="w-full bg-transparent text-sm leading-snug text-slate-900 placeholder:text-slate-400 focus:outline-none resize-none border border-emerald-500 rounded-xl px-3 py-2"
                    placeholder="응급실에 전달할 환자 상태, 처치 내용, 추가 정보를 입력하세요."
                    value={draftText}
                    onChange={(e) => setDraftText(e.target.value)}
                  />
                </div>
                <button
                  type="button"
                  onClick={handleSendFromParamedic}
                  disabled={!draftText.trim() && !draftImage}
                  className="h-10 px-4 rounded-xl text-sm font-semibold shadow-sm border border-slate-300 bg-emerald-600 text-white disabled:opacity-40 disabled:cursor-not-allowed hover:bg-emerald-700"
                >
                  전송
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
                  <KakaoAmbulanceMap coords={mapCoords} hospitals={[hospital]} routePath={mapRoutePaths[hospital.hpid || ""] || []} tickMs={800} />
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
                  <span className="text-2xl font-semibold text-slate-900">{patientMeta.etaMinutes !== undefined ? patientMeta.etaMinutes : "-"}</span>
                  <span className="text-xs text-slate-600">분 후 도착 예상</span>
                </div>
                <div className="mt-1 text-xs text-slate-600">남은 거리 약 {patientMeta.distanceKm !== undefined ? patientMeta.distanceKm.toFixed(1) : "-"} km</div>
                <div className="mt-2 text-xs text-slate-600">이 화면에서는 이송 중 환자의 남은 거리와 예상 도착 시간을 한눈에 볼 수 있도록 간단한 요약 정보만 표시합니다.</div>
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
            {isParamedic && <p className="mt-1 text-[10px] opacity-70">실제 서비스에서는 의료정보 보호를 위해 암호화와 접근 권한 제어가 필요합니다.</p>}
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

const HandoverConfirmModal: React.FC<HandoverConfirmModalProps> = ({ isOpen, paramedicId, confirmCode, errorMessage, onChangeCode, onClose, onConfirm }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40">
      <div className="w-full max-w-sm rounded-2xl bg-white shadow-xl p-5">
        <div className="text-sm font-semibold text-slate-900 mb-1">환자 인계 완료 처리</div>
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
          <button type="button" onClick={onClose} className="px-4 py-2 rounded-full text-xs border border-slate-300 text-slate-700 bg-white hover:bg-slate-50">
            취소
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="px-4 py-2 rounded-full text-xs font-semibold border border-emerald-600 text-white bg-emerald-600 hover:bg-emerald-700"
          >
            인계 완료
          </button>
        </div>
      </div>
    </div>
  );
};
