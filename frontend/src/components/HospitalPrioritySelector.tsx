import React from "react";

export type PriorityMode = "distance" | "beds" | "equipment";

interface HospitalPrioritySelectorProps {
  priorityModes: PriorityMode[];
  onTogglePriority: (mode: PriorityMode) => void;
}

export const HospitalPrioritySelector: React.FC<HospitalPrioritySelectorProps> = ({
  priorityModes,
  onTogglePriority,
}) => {
  const getPriorityLabel = (mode: PriorityMode) => {
    if (mode === "distance") return "거리 우선";
    if (mode === "beds") return "병상 여유 우선";
    return "장비·전담팀 우선";
  };

  const getPriorityDescription = (mode: PriorityMode) => {
    if (mode === "distance") return "이동 시간 최소화가 가장 중요할 때";
    if (mode === "beds") return "수용 가능성이 높은 병원을 우선";
    return "뇌혈관중재술, 심혈관센터 등 장비 중심";
  };

  const buildPrioritySummaryLabel = (modes: PriorityMode[]) => {
    if (modes.length === 0) return "선택 없음";
    return modes.map(getPriorityLabel).join(" + ");
  };

  const buildPrioritySummaryDescription = (modes: PriorityMode[]) => {
    if (modes.length === 0) return "현재 우선조건이 선택되지 않았습니다. 기본값으로 거리 우선을 사용합니다.";
    if (modes.length === 1) return getPriorityDescription(modes[0]);
    return "여러 우선조건을 함께 고려합니다. (예: 거리 + 병상 여유 + 장비 적합도)";
  };

  return (
    <section className="bg-white rounded-xl shadow-sm p-4 border border-slate-200">
      <h2 className="text-base font-semibold mb-3">병원 조회 우선조건</h2>
      <p className="text-xs text-slate-500 mb-4">
        구급대원이 현재 상황에서 무엇을 가장 우선할지 직접 선택합니다. 여러 항목을 동시에 선택할 수 있으며, 선택된 우선조건은 병원 추천 알고리즘의 가중치 방향으로 사용될 수 있습니다.
      </p>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
        <button
          type="button"
          onClick={() => onTogglePriority("distance")}
          className={`rounded-lg border-2 px-4 py-3 text-sm text-left transition-all ${
            priorityModes.includes("distance")
              ? "border-slate-900 bg-slate-900 text-white shadow-lg"
              : "border-slate-200 bg-slate-50 hover:bg-slate-100 hover:border-slate-300 text-slate-800"
          }`}
        >
          <div className="font-semibold mb-1">거리 우선</div>
          <div className="text-xs opacity-90">이동 시간 최소화가 가장 중요할 때</div>
        </button>
        
        <button
          type="button"
          onClick={() => onTogglePriority("beds")}
          className={`rounded-lg border-2 px-4 py-3 text-sm text-left transition-all ${
            priorityModes.includes("beds")
              ? "border-slate-900 bg-slate-900 text-white shadow-lg"
              : "border-slate-200 bg-slate-50 hover:bg-slate-100 hover:border-slate-300 text-slate-800"
          }`}
        >
          <div className="font-semibold mb-1">병상 여유 우선</div>
          <div className="text-xs opacity-90">수용 가능성이 높은 병원을 우선</div>
        </button>
        
        <button
          type="button"
          onClick={() => onTogglePriority("equipment")}
          className={`rounded-lg border-2 px-4 py-3 text-sm text-left transition-all ${
            priorityModes.includes("equipment")
              ? "border-slate-900 bg-slate-900 text-white shadow-lg"
              : "border-slate-200 bg-slate-50 hover:bg-slate-100 hover:border-slate-300 text-slate-800"
          }`}
        >
          <div className="font-semibold mb-1">장비·전담팀 우선</div>
          <div className="text-xs opacity-90">뇌혈관중재술, 심혈관센터 등 장비 중심</div>
        </button>
      </div>
      
      <div className="rounded-lg bg-slate-50 border border-dashed border-slate-200 px-4 py-3 text-xs text-slate-600">
        <div className="font-semibold mb-1">현재 선택된 우선조건: {buildPrioritySummaryLabel(priorityModes)}</div>
        <div>{buildPrioritySummaryDescription(priorityModes)}</div>
      </div>
    </section>
  );
};

