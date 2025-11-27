import React, { useEffect, useMemo } from "react";
import { generateSBARSummary } from "../utils/sbarUtils";
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
}) => {
  useEffect(() => {
    setSbarText(sttText);
  }, [sttText, setSbarText]);

  const buildArsButtonClass = (active: boolean) => {
    const base = "inline-flex items-center gap-1 rounded-md border px-3 md:px-4 py-1.5 text-xs md:text-sm";
    return active
      ? base + " border-emerald-600 bg-emerald-600 text-white font-semibold shadow-sm"
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
                          isRecording ? "bg-white animate-ping" : "bg-emerald-200"
                        }`}
                      ></span>
                      <span
                        className={`relative inline-flex h-2.5 w-2.5 rounded-full ${
                          isRecording ? "bg-white" : "bg-emerald-400"
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
            </div>
            <textarea
              className="w-full min-h-[120px] md:min-h-[150px] rounded-lg border border-slate-200 px-3 py-2 text-sm md:text-base focus:outline-none focus:ring-1 focus:ring-slate-500 focus:border-slate-500 bg-white"
              value={sbarText}
              readOnly
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
                        ? "bg-emerald-500 text-white border-emerald-500 shadow"
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
                presetSttText = "심정지/심폐정지, Pre-KTAS 1점. 심정지 상태, 심폐소생술 진행 중.";
              } else if (p.id === "stroke") {
                presetSymptom = "뇌졸중 의심(FAST+)";
                presetSttText = "뇌졸중 의심(FAST+), Pre-KTAS 2점. 갑작스러운 언어장애, 우측 편마비 발생, 증상 시작 시각 20분 전 추정. 혈압 180/100, 의식 혼미. 뇌졸중 의심 소견.";
              } else if (p.id === "stemi") {
                presetSymptom = "심근경색 의심(STEMI)";
                presetSttText = "심근경색 의심(STEMI), Pre-KTAS 2점. 흉통, 호흡곤란, 발한, 전신 무력감.";
              } else if (p.id === "poly_trauma") {
                presetSymptom = "다발성 외상/중증 외상";
                presetSttText = "다발성 중증 외상, Pre-KTAS 1점. 다발성 골절, 출혈, 의식 저하.";
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
                    console.log("버튼 클릭됨:", p.id, presetSymptom);
                    setSymptom(presetSymptom);
                    setSttText(presetSttText);
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
                          active ? "text-emerald-100" : "text-slate-500"
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

