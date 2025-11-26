import React from "react";
import { getRequiredFacilities, getRequiredBeds, getNiceToHaveBeds } from "../utils/hospitalUtils";

interface SymptomSelectorProps {
  symptom: string;
  setSymptom: (symptom: string) => void;
  filteredSymptomOptions: string[];
  patientAgeGroup: "adult" | "pediatric" | null;
}

export const SymptomSelector: React.FC<SymptomSelectorProps> = ({
  symptom,
  setSymptom,
  filteredSymptomOptions,
  patientAgeGroup,
}) => {
  // 증상에 따른 자동 우선순위 안내 메시지
  const getPriorityMessage = () => {
    if (symptom === "다발성 외상/중증 외상") {
      return "권역외상센터 및 외상센터를 우선 검색합니다.";
    }
    if (symptom === "소아 중증(신생아/영아)") {
      return "3차 상급종합병원 또는 소아전문병원(소아중환자실 보유)을 우선 검색합니다.";
    }
    return "거리와 가용성을 기준으로 적절한 응급의료기관을 검색합니다.";
  };

  return (
    <div>
      <h2 className="text-lg font-bold mb-4 text-gray-900 border-b-2 border-gray-300 pb-2">
        응급환자 증상 분류
      </h2>
      
      <label className="text-sm font-semibold text-gray-700 mb-2 block">증상 카테고리 선택</label>
      {patientAgeGroup && (
        <div className="mb-2 text-xs text-blue-700 font-semibold">
          {patientAgeGroup === "adult" ? "성인 환자로 감지됨" : "소아 환자로 감지됨"}
        </div>
      )}
      <select
        className="w-full rounded-lg border-2 border-gray-300 px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        value={symptom}
        onChange={(e) => setSymptom(e.target.value)}
      >
        {filteredSymptomOptions.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>
      {filteredSymptomOptions.length === 0 && (
        <p className="mt-2 text-sm text-gray-600">STT 텍스트에서 환자 연령 정보를 확인할 수 없습니다.</p>
      )}
      
      {/* 증상 기반 자동 우선순위 안내 */}
      <div className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
        <p className="text-xs text-blue-800 font-semibold">
          {getPriorityMessage()}
        </p>
      </div>

      {/* 필수 장비/병상 정보 표시 */}
      <div className="mt-4 p-4 bg-blue-50 border-2 border-blue-300 rounded-lg">
        <p className="text-sm text-blue-900 font-bold mb-2">필요한 병원 시설</p>
        {getRequiredFacilities(symptom).length > 0 && (
          <p className="text-sm text-gray-800 mb-2">
            <span className="font-semibold text-red-700">필수 장비:</span> {getRequiredFacilities(symptom).join(", ")}
          </p>
        )}
        {getRequiredBeds(symptom).length > 0 && (
          <p className="text-sm text-gray-800 mb-2">
            <span className="font-semibold text-red-700">필수 병상:</span> {getRequiredBeds(symptom).join(", ")}
          </p>
        )}
        {getNiceToHaveBeds(symptom).length > 0 && (
          <p className="text-sm text-gray-800">
            <span className="font-semibold text-blue-700">우선 병상:</span> {getNiceToHaveBeds(symptom).join(", ")}
          </p>
        )}
      </div>
    </div>
  );
};

interface HospitalSearchButtonsProps {
  onSearchHospitals: () => void;
  loadingHospitals: boolean;
  hasCoords: boolean;
  hasRegion: boolean;
  hospitalsLength: number;
  rerollCount: number;
  rejectedHospitalsSize: number;
  hasCallableHospital: boolean;
  approvedHospital: any;
  twilioAutoCalling: boolean;
  onStartTwilioCall: () => void;
  onStopTwilioCall: () => void;
  currentHospitalIndex: number;
  hospitals: any[];
}

export const HospitalSearchButtons: React.FC<HospitalSearchButtonsProps> = ({
  onSearchHospitals,
  loadingHospitals,
  hasCoords,
  hasRegion,
  hospitalsLength,
  rerollCount,
  rejectedHospitalsSize,
  hasCallableHospital,
  approvedHospital,
  twilioAutoCalling,
  onStartTwilioCall,
  onStopTwilioCall,
  currentHospitalIndex,
  hospitals,
}) => {
  return (
    <div className="mt-4">
      <button
        className="w-full rounded-lg bg-green-700 text-white text-base font-bold py-4 flex items-center justify-center hover:bg-green-800 active:bg-green-900 disabled:bg-gray-400 disabled:text-gray-600 transition shadow-lg min-h-[56px]"
        onClick={onSearchHospitals}
        disabled={loadingHospitals || !hasCoords || !hasRegion}
      >
        {loadingHospitals ? (
          <span>병원 탐색 중...</span>
        ) : (
          <span>응급 병동 탐색 시작</span>
        )}
      </button>
      {hospitalsLength > 0 && (
        <div className="mt-3 text-sm text-gray-600">
          조회 횟수: <span className="font-semibold">{rerollCount}</span>회 | 거절: <span className="font-semibold">{rejectedHospitalsSize}</span>곳
        </div>
      )}
      <div className="mt-4 flex flex-col gap-2">
        <button
          className={`w-full rounded-full bg-blue-700 text-white text-base font-semibold py-4 shadow-md transition hover:bg-blue-800 active:bg-blue-900 min-h-[52px] ${
            !hasCallableHospital || !!approvedHospital || hospitalsLength === 0 || twilioAutoCalling
              ? "opacity-60 cursor-not-allowed"
              : ""
          }`}
          disabled={!hasCallableHospital || !!approvedHospital || hospitalsLength === 0 || twilioAutoCalling}
          onClick={onStartTwilioCall}
        >
          Twilio 자동 전화
        </button>
        {twilioAutoCalling && (
          <>
            <button
              className="w-full rounded-full bg-gray-800 text-white text-sm font-semibold py-3 shadow hover:bg-gray-900 min-h-[48px]"
              onClick={onStopTwilioCall}
            >
              자동 전화 중지
            </button>
            {hospitals[currentHospitalIndex] && (
              <p className="text-xs text-gray-600">
                현재 {currentHospitalIndex + 1}번째 병원({hospitals[currentHospitalIndex]?.dutyName || "병원"})에 ARS 요청 중입니다.
              </p>
            )}
          </>
        )}
        {!twilioAutoCalling && hospitalsLength > 0 && !approvedHospital && !hasCallableHospital && (
          <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
            이미 모든 병원이 거절했습니다. 새로운 병원을 탐색하거나 행정구역을 변경해주세요.
          </p>
        )}
      </div>
    </div>
  );
};

