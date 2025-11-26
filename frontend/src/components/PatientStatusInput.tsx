import React, { useState, useEffect, useRef } from "react";
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
}

const CRITICAL_PRESETS: CriticalPreset[] = [
  { id: "cardiac_arrest", label: "심정지", english: "Cardiac Arrest" },
  { id: "stroke", label: "뇌졸중 의심(FAST+)", english: "Acute Ischemic Stroke" },
  { id: "stemi", label: "심근경색 의심(STEMI)", english: "ST-Elevation Myocardial Infarction" },
  { id: "poly_trauma", label: "다발성 중증 외상", english: "Polytrauma" },
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
}) => {
  useEffect(() => {
    if (!sttText.trim()) {
      setSbarText("");
      return;
    }
    const sbar = generateSBARSummary(sttText, symptom);
    setSbarText(sbar);
  }, [sttText, symptom, setSbarText]);

  const buildArsButtonClass = (active: boolean) => {
    const base = "inline-flex items-center gap-1 rounded-md border px-3 md:px-4 py-1.5 text-xs md:text-sm";
    return active
      ? base + " border-emerald-600 bg-emerald-600 text-white font-semibold shadow-sm"
      : base + " border-slate-300 bg-white text-slate-700 hover:bg-slate-50";
  };

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
              <button
                type="button"
                onClick={onToggleRecording}
                className="rounded-lg border border-slate-300 px-4 md:px-5 py-2 text-sm md:text-base font-semibold text-slate-800 bg-slate-50 hover:bg-slate-100"
              >
                {isRecording ? "녹음 중지" : "마이크 입력"}
              </button>
            </div>
            <textarea
              className="w-full min-h-[120px] md:min-h-[150px] rounded-lg border border-slate-200 px-3 py-2 text-sm md:text-base focus:outline-none focus:ring-1 focus:ring-slate-500 focus:border-slate-500 bg-white"
              value={sttText}
              onChange={(e) => setSttText(e.target.value)}
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
                  <div className={`text-base ${active ? "text-white" : "text-slate-800"}`}>
                    {p.label}
                    {p.english && (
                      <span className={`ml-2 text-xs font-normal ${active ? "text-slate-200" : "text-slate-500"}`}>
                        ({p.english})
                      </span>
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

