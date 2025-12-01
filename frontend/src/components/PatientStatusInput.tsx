import React, { useEffect, useMemo, useRef, useState } from "react";
import { generateSBARSummary } from "../utils/sbarUtils";
import { convertTextToSBAR } from "../services/api";
import type { CriticalPreset } from "../types";

interface PatientStatusInputProps {
  sttText: string;
  setSttText: (text: string) => void;
  sbarText: string;
  setSbarText: (text: string) => void;
  symptom: string;
  setSymptom: (symptom: string) => void;
  arsSource: "stt" | "sbar" | null;
  setArsSource: (source: "stt" | "sbar" | null) => void;
  inputMode: "stt" | "critical";
  setInputMode: (mode: "stt" | "critical") => void;
  isRecording: boolean;
  onToggleRecording: () => void;
  micLevel: number;
  recordingError: string;
  patientSex: "male" | "female" | null;
  setPatientSex: (sex: "male" | "female" | null) => void;
  patientAgeBand: string | null;
  setPatientAgeBand: (band: string | null) => void;
  onArsNarrativeChange?: (narrative: string) => void;  // ARS 서비스용 자연스러운 문장 전달 콜백
}

export const CRITICAL_PRESETS: CriticalPreset[] = [
  {
    id: "cardiac_arrest",
    label: "심정지",
    english: "Cardiac Arrest",
    preKtasLevel: "Pre-KTAS 1단계·소생",
    preKtasEvidence: "심정지/ROSC 예시",
  },
  {
    id: "stroke",
    label: "뇌졸중 의심(FAST+)",
    english: "Acute Ischemic Stroke",
    preKtasLevel: "Pre-KTAS 2단계·긴급",
    preKtasEvidence: "발병 6시간 이내",
  },
  {
    id: "stemi",
    label: "심근경색 의심(STEMI)",
    english: "ST-Elevation Myocardial Infarction",
    preKtasLevel: "Pre-KTAS 2단계·긴급",
    preKtasEvidence: "심인성 흉통",
  },
  {
    id: "poly_trauma",
    label: "다발성 중증 외상",
    english: "Polytrauma",
    preKtasLevel: "Pre-KTAS 1단계·소생",
    preKtasEvidence: "중증외상(쇼크)",
  },
];

export const PatientStatusInput: React.FC<PatientStatusInputProps> = ({
  sttText,
  setSttText,
  sbarText,
  setSbarText,
  symptom,
  setSymptom,
  arsSource,
  setArsSource,
  inputMode,
  setInputMode,
  isRecording,
  onToggleRecording,
  micLevel,
  recordingError,
  patientSex,
  setPatientSex,
  patientAgeBand,
  setPatientAgeBand,
  onArsNarrativeChange,
}) => {
  const [isConvertingSBAR, setIsConvertingSBAR] = useState<boolean>(false);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const lastConvertedTextRef = useRef<string>("");

  // 텍스트 입력 시 실시간 SBAR 변환 (debounce 적용)
  useEffect(() => {
    // 빈 텍스트인 경우 변환하지 않음
    if (!sttText || !sttText.trim()) {
      setSbarText("");
      lastConvertedTextRef.current = "";
      return;
    }

    // 이전에 변환한 텍스트와 동일하면 변환하지 않음
    if (sttText === lastConvertedTextRef.current) {
      return;
    }

    // 이전 타이머가 있으면 취소
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    // 1.5초 후에 SBAR 변환 API 호출 (debounce)
    debounceTimerRef.current = setTimeout(async () => {
      try {
        setIsConvertingSBAR(true);
        const result = await convertTextToSBAR(sttText);
        
        if (result.sbarSummary) {
          setSbarText(result.sbarSummary);
          lastConvertedTextRef.current = sttText;
        } else {
          // SBAR 변환 실패 시 원본 텍스트 사용
          setSbarText(sttText);
        }
        
        // ARS 서비스용 자연스러운 문장을 상위 컴포넌트로 전달
        if (result.arsNarrative && onArsNarrativeChange) {
          onArsNarrativeChange(result.arsNarrative);
        }
      } catch (error: any) {
        console.error("SBAR 변환 실패:", error);
        // 에러 발생 시 원본 텍스트 사용
    setSbarText(sttText);
      } finally {
        setIsConvertingSBAR(false);
      }
    }, 1500); // 1.5초 debounce

    // cleanup 함수
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [sttText, setSbarText]);

  const buildArsButtonClass = (active: boolean) => {
    const base = "inline-flex items-center gap-1 rounded-md border px-3 md:px-4 py-1.5 text-xs md:text-sm";
    return active
      ? base + " border-slate-700 bg-slate-700 text-white font-semibold shadow-sm"
      : base + " border-slate-300 bg-white text-slate-700 hover:bg-slate-50";
  };

  const canUseMic = typeof navigator !== "undefined" && !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
  const micBars = useMemo(() => {
    const base = [0.45, 0.8, 0.6, 0.9, 0.5, 0.75, 0.55, 0.85, 0.5, 0.7, 0.6, 0.8];
    return base.map((ratio, idx) => {
      const dynamic = Math.min(1, micLevel * (1.2 + (idx % 4) * 0.15));
      const height = 18 + (ratio + dynamic) * 36;
      return `${height}px`;
    });
  }, [micLevel]);
  const ageBandOptions = [
    "영유아(0~1세)",
    "소아(2~9세)",
    "10대",
    "20대",
    "30대",
    "40대",
    "50대",
    "60대",
    "70대",
    "80대 이상",
  ];

  return (
    <section className="bg-white rounded-xl shadow-sm p-3 md:p-4 border border-slate-200 flex-1">
      <h2 className="text-sm md:text-base font-semibold mb-2">환자 상태 입력</h2>
      <p className="text-[11px] md:text-xs text-slate-500 mb-3">
        텍스트 입력 및 음성 인식(STT), 또는 중증(Pre-KTAS 1~2점) 환자용 빠른 선택 중 하나를 사용할 수 있습니다.
      </p>

      <div className="border-b border-slate-200 flex text-xs md:text-sm">
        <button
          type="button"
          onClick={() => setInputMode("stt")}
          className={`px-3 md:px-4 py-2 border-b-2 font-medium ${
            inputMode === "stt" ? "border-slate-900 text-slate-900" : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          텍스트 입력 및 음성 인식(STT)
        </button>
        <button
          type="button"
          onClick={() => setInputMode("critical")}
          className={`px-3 md:px-4 py-2 border-b-2 font-medium ${
            inputMode === "critical"
              ? "border-slate-900 text-slate-900"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          중증(Pre-KTAS 1~2점)
        </button>
      </div>

      {inputMode === "stt" && (
        <div className="mt-3 md:mt-4 flex flex-col gap-3 md:gap-4">
          {/* 음성 인식 사용 안내 */}
          <div className="rounded-lg border-2 border-blue-200 bg-blue-50 p-4">
            <h3 className="text-sm md:text-base font-semibold text-slate-900 mb-2">음성 인식 사용 안내</h3>
            <p className="text-xs md:text-sm text-slate-700 mb-3">
              음성 인식 사용 시, 먼저 Pre-KTAS 점수를 말하고, 이어서 환자 상태 정보를 말씀해주세요.
            </p>
            <div className="rounded-lg border border-blue-200 bg-white p-3">
              <p className="text-xs font-semibold text-slate-900 mb-2">사용 예시:</p>
              <div className="space-y-2 text-[11px] md:text-xs text-slate-700 font-mono bg-slate-50 p-2 rounded border border-slate-200">
                <p className="leading-relaxed">
                  "Pre-KTAS 2점. 60대 남성, 뇌졸중 의심, 증상 시작 약 20분 전. 갑작스러운 언어장애와 우측 편마비 발생. 혈압 180/100, 의식 혼미."
                </p>
                <p className="leading-relaxed">
                  "Pre-KTAS 1점. 심정지 상태, 심폐소생술 진행 중. 50대 남성, 도로에서 발견."
                </p>
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-xs md:text-sm font-semibold text-slate-700">환자 상태 텍스트 또는 음성 인식 입력</h3>
              <span className="text-[11px] md:text-xs text-slate-500">
                {isRecording ? "마이크가 활성화되어 있습니다." : "버튼을 눌러 즉시 음성 보고를 시작하세요."}
              </span>
            </div>
            <div className="flex flex-col md:flex-row items-stretch gap-3 md:gap-4">
              <div className="md:w-[280px] flex-shrink-0">
                <div
                  className={`relative overflow-hidden rounded-2xl border-2 shadow-lg ${
                    isRecording
                      ? "border-rose-200 bg-gradient-to-br from-rose-500 via-orange-500 to-amber-400"
                      : "border-slate-900/20 bg-gradient-to-br from-slate-900 to-slate-700"
                  }`}
                >
                  <button
                    type="button"
                    onClick={onToggleRecording}
                    disabled={!canUseMic}
                    className={`w-full px-4 py-6 text-center transition-transform duration-150 ${
                      canUseMic ? "active:scale-[0.98]" : "cursor-not-allowed opacity-40"
                    }`}
                    aria-pressed={isRecording}
                  >
                    <span className="flex items-center justify-center gap-2 text-base font-semibold text-white">
                      <svg
                        className="h-5 w-5"
                        viewBox="0 0 24 24"
                        fill="none"
                        xmlns="http://www.w3.org/2000/svg"
                      >
                        <path
                          d="M12 15a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3z"
                          stroke="currentColor"
                          strokeWidth="1.8"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                        <path
                          d="M19 10v2a7 7 0 0 1-14 0v-2M12 21v-4"
                          stroke="currentColor"
                          strokeWidth="1.8"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                        <path
                          d="M8 21h8"
                          stroke="currentColor"
                          strokeWidth="1.8"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                      {isRecording ? "녹음 중지" : "긴급 음성 입력"}
                    </span>
                    <span className="mt-1 block text-[11px] uppercase tracking-[0.3em] text-white/80">
                      {isRecording ? "Tap to stop" : "Tap to start"}
                    </span>
                  </button>

                  {isRecording ? (
                    <div className="mt-4 flex h-16 items-end justify-center gap-1 px-4 pb-5">
                      {micBars.map((height, idx) => (
                        <span
                          key={`wave-${idx}`}
                          style={{ height }}
                          className="w-1.5 rounded-full bg-white/90 transition-[height] duration-100 ease-out"
                        />
                      ))}
                    </div>
                  ) : (
                    <div className="mt-4 px-5 pb-5 text-[11px] leading-relaxed text-white/80">
                      <p>한 번 탭하면 즉시 녹음이 시작되며, 다시 누르면 종료됩니다.</p>
                      {!canUseMic && <p className="mt-1 text-rose-100">브라우저 마이크 권한을 허용해주세요.</p>}
                    </div>
                  )}

                  <div className="absolute top-3 right-3 flex items-center gap-2 text-[11px] font-semibold text-white">
                    <span className="relative flex h-2.5 w-2.5">
                      <span
                        className={`absolute inline-flex h-full w-full rounded-full opacity-75 ${
                          isRecording ? "bg-white animate-ping" : "bg-slate-300"
                        }`}
                      ></span>
                      <span
                        className={`relative inline-flex h-2.5 w-2.5 rounded-full ${
                          isRecording ? "bg-white" : "bg-slate-500"
                        }`}
                      ></span>
                    </span>
                    {isRecording ? "녹음 중" : "대기"}
                  </div>
                </div>
                {recordingError && (
                  <div className="mt-2 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-[11px] font-semibold text-rose-700">
                    {recordingError}
                  </div>
                )}
              </div>
              <div className="flex-1 flex flex-col gap-2">
                <textarea
                  className="w-full min-h-[160px] rounded-lg border border-slate-200 px-3 py-3 text-sm md:text-base focus:outline-none focus:ring-1 focus:ring-slate-500 focus:border-slate-500 bg-white"
                  value={sttText}
                  onChange={(e) => setSttText(e.target.value)}
                  placeholder="음성 인식 결과가 여기에 표시됩니다. 필요한 경우 내용을 직접 수정하세요."
                />
                <div className="mt-1 flex justify-end">
                  <button
                    type="button"
                    onClick={() => setArsSource(arsSource === "stt" ? null : "stt")}
                    className={buildArsButtonClass(arsSource === "stt")}
                  >
                    {arsSource === "stt" && <span>✓</span>}
                    <span>{arsSource === "stt" ? "병원 추천·ARS 기준으로 STT 원문 선택됨" : "병원 추천·ARS 기준으로 STT 원문 선택"}</span>
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-xs md:text-sm font-semibold text-slate-700">SBAR 형식 요약</h3>
              {isConvertingSBAR && (
                <span className="text-[11px] text-slate-500 flex items-center gap-1">
                  <span className="inline-block w-3 h-3 border-2 border-slate-400 border-t-transparent rounded-full animate-spin"></span>
                  변환 중...
                </span>
              )}
            </div>
            <textarea
              className="w-full min-h-[120px] md:min-h-[150px] rounded-lg border border-slate-200 px-3 py-2 text-sm md:text-base focus:outline-none focus:ring-1 focus:ring-slate-500 focus:border-slate-500 bg-white"
              value={sbarText}
              readOnly
              placeholder={isConvertingSBAR ? "SBAR 형식으로 변환 중..." : "텍스트를 입력하면 자동으로 SBAR 형식으로 변환됩니다."}
            />
            <div className="mt-1 flex justify-end">
              <button
                type="button"
                onClick={() => setArsSource(arsSource === "sbar" ? null : "sbar")}
                className={buildArsButtonClass(arsSource === "sbar")}
              >
                {arsSource === "sbar" && <span>✓</span>}
                <span>{arsSource === "sbar" ? "병원 추천·ARS 기준으로 SBAR 요약 선택됨" : "병원 추천·ARS 기준으로 SBAR 요약 선택"}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {inputMode === "critical" && (
        <div className="mt-3 md:mt-4 flex flex-col gap-3 md:gap-4">
          <p className="text-[11px] md:text-xs text-slate-500">
            3대 중증(뇌졸중, 심근경색, 중증 외상)과 심정지 등, STT 단계를 생략하고 바로 유형을 선택할 수 있는 영역입니다.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="p-3 rounded-xl border border-slate-200 bg-slate-50 flex flex-col gap-2">
              <p className="text-xs font-semibold text-slate-700">성별 선택</p>
              <div className="relative w-full h-20 rounded-2xl bg-slate-200 shadow-inner flex items-center px-1">
                <div
                  className={`absolute top-2 bottom-2 w-1/2 rounded-2xl shadow transition-all duration-200 ${
                    patientSex === "male"
                      ? "bg-gradient-to-r from-blue-400 to-blue-600"
                      : patientSex === "female"
                      ? "bg-gradient-to-r from-rose-400 to-rose-600"
                      : "bg-white/80"
                  } ${
                    patientSex === "female"
                      ? "translate-x-full"
                      : patientSex === "male"
                      ? "translate-x-0"
                      : "translate-x-0 opacity-0"
                  }`}
                />
                {[
                  { key: "male" as const, label: "남자" },
                  { key: "female" as const, label: "여자" },
                ].map((option) => (
                  <button
                    key={option.key}
                    type="button"
                    onClick={() => setPatientSex(patientSex === option.key ? null : option.key)}
                    className={`flex-1 relative z-10 h-full text-sm font-semibold transition ${
                      patientSex === option.key ? "text-white" : "text-slate-500"
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
              <div className="text-[11px] text-slate-500">한 번 더 누르면 선택 해제가 됩니다.</div>
            </div>
            <div className="p-3 rounded-xl border border-slate-200 bg-slate-50">
              <p className="text-xs font-semibold text-slate-700 mb-2">나이대 선택</p>
              <div className="flex flex-wrap gap-2">
                {ageBandOptions.map((band) => (
                  <button
                    key={band}
                    type="button"
                    onClick={() => setPatientAgeBand(patientAgeBand === band ? null : band)}
                    className={`rounded-full px-3 py-1.5 text-[11px] font-semibold border ${
                      patientAgeBand === band
                        ? "bg-slate-700 text-white border-slate-700 shadow"
                        : "bg-white text-slate-700 border-slate-300 hover:border-slate-400"
                    }`}
                  >
                    {band}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {CRITICAL_PRESETS.map((p) => {
              let presetSymptom = "";
              let presetSttText = "";
              
              if (p.id === "cardiac_arrest") {
                presetSymptom = "심정지/심폐정지";
                presetSttText = "심정지, Pre-KTAS 1점";
              } else if (p.id === "stroke") {
                presetSymptom = "뇌졸중 의심(FAST+)";
                presetSttText = "뇌졸중 의심(FAST+), Pre-KTAS 2점";
              } else if (p.id === "stemi") {
                presetSymptom = "심근경색 의심(STEMI)";
                presetSttText = "심근경색 의심(STEMI), Pre-KTAS 2점";
              } else if (p.id === "poly_trauma") {
                presetSymptom = "다발성 외상/중증 외상";
                presetSttText = "다발성 중증 외상, Pre-KTAS 1점";
              }
              
              // 버튼 활성화 상태 확인
              const active = symptom === presetSymptom;
              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log("중증 버튼 클릭됨:", p.id, presetSymptom);
                    console.log("현재 선택된 성별:", patientSex, "연령대:", patientAgeBand);
                    setSymptom(presetSymptom);
                    
                    // 성별과 연령대 정보를 포함한 텍스트 생성
                    // 형식: "{연령대} {성별} {증상}, Pre-KTAS {점수}점"
                    let fullText = presetSttText;
                    if (patientSex || patientAgeBand) {
                      const sexText = patientSex === "male" ? "남성" : patientSex === "female" ? "여성" : "";
                      const ageText = patientAgeBand || "";
                      if (sexText || ageText) {
                        const patientInfo = [ageText, sexText].filter(Boolean).join(" ");
                        // 증상명 추출 (presetSttText에서 Pre-KTAS 앞부분만)
                        const symptomPart = presetSttText.split(", Pre-KTAS")[0];
                        const ktasPart = presetSttText.split(", Pre-KTAS")[1] || "";
                        fullText = `${patientInfo} ${symptomPart}${ktasPart ? `, Pre-KTAS${ktasPart}` : ""}`;
                        console.log("환자 정보 포함 텍스트 생성:", fullText);
                      }
                    } else {
                      console.log("성별 또는 연령대가 선택되지 않아 기본 텍스트 사용:", fullText);
                    }
                    console.log("최종 sttText 설정:", fullText);
                    setSttText(fullText);
                  }}
                  className={`text-left rounded-lg border-2 px-4 py-4 text-sm font-semibold transition-all cursor-pointer ${
                    active 
                      ? "border-slate-900 bg-slate-900 text-white shadow-lg" 
                      : "border-slate-200 bg-slate-50 hover:bg-slate-100 hover:border-slate-300 text-slate-800"
                  }`}
                  style={{ pointerEvents: "auto", touchAction: "manipulation" }}
                >
                  <div className="space-y-1">
                    <div className={`text-base ${active ? "text-white" : "text-slate-800"}`}>
                      {p.label}
                      {p.english && (
                        <span className={`ml-2 text-xs font-normal ${active ? "text-slate-200" : "text-slate-500"}`}>
                          ({p.english})
                        </span>
                      )}
                    </div>
                    {p.preKtasLevel && (
                      <div
                        className={`text-[11px] font-semibold ${
                          active ? "text-slate-200" : "text-slate-500"
                        }`}
                      >
                        {p.preKtasLevel}
                        {p.preKtasEvidence && <span className="ml-1">· {p.preKtasEvidence}</span>}
                      </div>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
};

