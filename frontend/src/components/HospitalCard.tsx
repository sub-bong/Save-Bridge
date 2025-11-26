import React from "react";
import type { Hospital, ApprovalStatus, Region } from "../types";
import { formatBedValue, formatHvidate } from "../utils/hospitalUtils";

const HOSPITAL_CLASS_MAP: Record<string, string> = {
  "1": "권역응급의료센터 (상급)",
  "2": "지역응급의료센터 (3차)",
  "3": "지역응급의료기관 (2차)",
  "4": "소아전문응급의료센터",
  "5": "기타 응급의료기관",
};

interface HospitalCardProps {
  hospital: Hospital;
  index: number;
  region: Region | null;
  approvalStatus: ApprovalStatus;
  isRejected: boolean;
  isActiveCandidate: boolean;
  canInteract: boolean;
  onApprove: (hospital: Hospital) => void;
  onReject: (hospital: Hospital) => void;
  onStartCall: (hospital: Hospital) => void;
  onOpenChat?: (hospital: Hospital) => void;
}

export const HospitalCard: React.FC<HospitalCardProps> = ({
  hospital,
  index,
  region,
  approvalStatus,
  isRejected,
  isActiveCandidate,
  canInteract,
  onApprove,
  onReject,
  onStartCall,
  onOpenChat,
}) => {
  const meetsConditions = hospital._meets_conditions ?? false;
  const statusKey: ApprovalStatus = isRejected ? "rejected" : approvalStatus;
  const statusMap: Record<ApprovalStatus, { label: string; className: string }> = {
    pending: { label: "대기 중", className: "bg-gray-200 text-gray-800" },
    calling: { label: "환자 수용 요청중...", className: "bg-amber-100 text-amber-900 border border-amber-300" },
    approved: { label: "환자 수용 확정", className: "bg-green-100 text-green-800 border border-green-400" },
    rejected: { label: "환자 수용 거절", className: "bg-red-100 text-red-800 border border-red-300" },
  };
  const statusMeta = statusMap[statusKey];
  const distanceLabel =
    typeof hospital.distance_km === "number" ? `${hospital.distance_km.toFixed(2)} km` : hospital.distance_km || "-";
  const etaLabel =
    typeof hospital.eta_minutes === "number" ? `${hospital.eta_minutes}분 예상` : hospital.eta_minutes ? `${hospital.eta_minutes}` : "-";
  const lastUpdated = formatHvidate(hospital.hvidate);
  const classKey = hospital.dutyEmcls as keyof typeof HOSPITAL_CLASS_MAP | undefined;
  const emergencyClass =
    hospital.dutyEmclsName || (classKey ? HOSPITAL_CLASS_MAP[classKey] : "") || "응급의료기관 등급 정보 없음";
  const emergencyBadge = emergencyClass.includes("권역")
    ? "권역센터"
    : emergencyClass.includes("지역")
    ? "지역센터"
    : emergencyClass.includes("소아")
    ? "소아센터"
    : emergencyClass.includes("기타")
    ? "기타 응급기관"
    : null;
  const cardTone =
    statusKey === "approved"
      ? "bg-emerald-50 border-emerald-500"
      : statusKey === "rejected"
      ? "bg-gray-100 border-gray-300 opacity-80"
      : isActiveCandidate
      ? "bg-white border-blue-500 shadow-lg"
      : meetsConditions
      ? "bg-blue-50 border-blue-300"
      : "bg-gray-50 border-gray-200";

  return (
    <div
      key={hospital.hpid || index}
      className={`rounded-2xl border-2 p-5 shadow-sm flex flex-col gap-3 transition ${cardTone}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 flex-1">
          <div className="flex-shrink-0 w-9 h-9 rounded-full bg-gray-900 text-white flex items-center justify-center font-bold text-sm">
            {index + 1}
          </div>
          <div className="flex-1 space-y-1">
            <div className="text-base font-bold text-gray-900 flex items-center gap-2 flex-wrap">
              {hospital.dutyName || "병원 명칭 미상"}
              {isActiveCandidate && (
                <span className="text-xs bg-blue-700 text-white px-3 py-1 rounded-full font-semibold">
                  현재 요청 대상
                </span>
              )}
              {meetsConditions && (
                <span className="text-xs bg-blue-100 text-blue-800 px-3 py-1 rounded-full font-semibold">
                  증상 맞춤 병원
                </span>
              )}
            </div>
            <div className="text-sm text-gray-600">{hospital.dutyAddr || "주소 정보 없음"}</div>
            <div className="text-xs text-gray-600">
              <span className="font-semibold text-gray-900">행정구역:</span>{" "}
              {`${region?.sido || ""} ${hospital.region_name || region?.sigungu || "미상"}`}
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
              <span className="px-2 py-1 rounded-full bg-gray-200 text-gray-800 font-semibold">
                {emergencyClass}
              </span>
              {emergencyBadge && (
                <span className="px-2 py-1 rounded-full bg-indigo-100 text-indigo-800 font-semibold">
                  {emergencyBadge}
                </span>
              )}
              {region?.sigungu && hospital.region_name && hospital.region_name !== region.sigungu && (
                <span className="px-2 py-1 rounded-full bg-amber-100 text-amber-800 font-semibold">
                  인접 행정구역
                </span>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className={`px-3 py-1 rounded-full font-semibold ${statusMeta.className}`}>
                {statusMeta.label}
              </span>
            </div>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1 min-w-[150px] text-right text-sm text-gray-700">
          <div>
            <div className="font-semibold text-base text-gray-900">{distanceLabel}</div>
            <div className="text-xs text-gray-600">{etaLabel}</div>
          </div>
          <div className="text-xs text-gray-500">데이터 기준 {lastUpdated}</div>
        </div>
      </div>

      {hospital.hv1 && (
        <div className="flex flex-wrap items-center gap-3 text-sm text-gray-700">
          <span className="font-semibold text-gray-800">응급실 당직의</span>
          <span className="font-mono text-base">{hospital.hv1}</span>
        </div>
      )}

      {statusKey === "calling" && (
        <div className="text-sm text-amber-900 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          Twilio ARS에서 환자 수용 여부를 확인 중입니다. 응답이 입력되면 상태가 자동으로 업데이트됩니다.
        </div>
      )}
      {statusKey === "rejected" && (
        <div className="text-sm text-red-900 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          해당 병원이 환자 수용을 거절했습니다. 자동으로 다음 후보 병원을 탐색합니다.
        </div>
      )}
      {statusKey === "approved" && (
        <div className="text-sm text-emerald-900 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
          환자 수용이 확정되었습니다. 추가 병원 탐색과 통화 시도를 중단합니다.
        </div>
      )}

      {meetsConditions && (
        <div className="mt-2 p-3 bg-white rounded-lg border-2 border-gray-200">
          <p className="text-sm font-bold mb-2 text-gray-900">이용 가능한 병상</p>
          <div className="grid grid-cols-2 gap-2 text-sm">
            {hospital.hvec && formatBedValue(hospital.hvec) !== "없음" && (
              <div className="text-gray-700">
                응급실: <span className="font-semibold">{formatBedValue(hospital.hvec)}</span>
              </div>
            )}
            {hospital.hvoc && formatBedValue(hospital.hvoc) !== "없음" && (
              <div className="text-gray-700">
                수술실: <span className="font-semibold">{formatBedValue(hospital.hvoc)}</span>
              </div>
            )}
            {hospital.hvicc && formatBedValue(hospital.hvicc) !== "없음" && (
              <div className="text-gray-700">
                일반중환자실: <span className="font-semibold">{formatBedValue(hospital.hvicc)}</span>
              </div>
            )}
            {hospital.hv6 && formatBedValue(hospital.hv6) !== "없음" && (
              <div className="text-gray-700">
                신경외과중환자실: <span className="font-semibold">{formatBedValue(hospital.hv6)}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {hospital.hvdnm && (
        <div className="text-sm text-gray-700">
          <span className="font-semibold">당직의:</span> {hospital.hvdnm} {hospital.hv1 && `(${hospital.hv1})`}
        </div>
      )}

      <div className="flex flex-wrap gap-2 mt-3">
        <a
          href={hospital.dutytel3 ? `tel:${hospital.dutytel3}` : undefined}
          onClick={(e) => {
            if (!hospital.dutytel3) e.preventDefault();
          }}
          className={`flex-1 inline-flex items-center justify-center gap-2 rounded-lg px-4 py-3 text-sm font-bold transition shadow-md min-h-[48px] ${
            hospital.dutytel3 ? "bg-red-700 text-white hover:bg-red-800" : "bg-gray-300 text-gray-500 cursor-not-allowed"
          }`}
        >
          <span>응급실 전화</span>
          <span className="font-mono">{hospital.dutytel3 || "정보 없음"}</span>
        </a>
        {statusKey === "approved" && onOpenChat && (
          <button
            className="flex-1 inline-flex items-center justify-center gap-2 rounded-lg px-4 py-3 text-sm font-bold transition shadow-md min-h-[48px] bg-emerald-600 text-white hover:bg-emerald-700"
            onClick={() => onOpenChat(hospital)}
          >
            수용 가능
          </button>
        )}
        {canInteract && (
          <>
            <button
              className="px-4 py-3 rounded-lg bg-green-700 text-white text-sm font-bold hover:bg-green-800 transition shadow-md min-h-[48px]"
              onClick={() => onApprove(hospital)}
            >
              승낙
            </button>
            <button
              className="px-4 py-3 rounded-lg bg-red-700 text-white text-sm font-bold hover:bg-red-800 transition shadow-md min-h-[48px]"
              onClick={() => onReject(hospital)}
            >
              거절
            </button>
            <button
              className="px-4 py-3 rounded-lg bg-blue-700 text-white text-sm font-bold hover:bg-blue-800 transition shadow-md min-h-[48px]"
              onClick={() => onStartCall(hospital)}
            >
              ARS 자동요청
            </button>
          </>
        )}
      </div>
    </div>
  );
};

