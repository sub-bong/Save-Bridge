export const symptomOptions: string[] = [
  "뇌졸중 의심(FAST+)",
  "심근경색 의심(STEMI)",
  "다발성 외상/중증 외상",
  "심정지/심폐정지",
  "성인 호흡곤란",
  "소아 호흡곤란",
  "성인 경련",
  "소아 경련",
  "정형외과 중증(대형골절/절단)",
  "신경외과 응급(의식저하/외상성출혈)",
  "소아 중증(신생아/영아)",
];

export const SYMPTOM_RULES: Record<string, import("../types").SymptomRule> = {
  "뇌졸중 의심(FAST+)": {
    bool_any: [["hvctayn", "Y"]],
    min_ge1: [["hvicc", 1]],
    nice_to_have: [["hv5", 1], ["hv6", 1]],
  },
  "심근경색 의심(STEMI)": {
    bool_any: [["hvangioayn", "Y"]],
    min_ge1: [["hvoc", 1], ["hvicc", 1]],
    nice_to_have: [],
  },
  "다발성 외상/중증 외상": {
    bool_any: [["hvventiayn", "Y"]],
    min_ge1: [["hvoc", 1], ["hvicc", 1]],
    nice_to_have: [["hv9", 1]],
  },
  "성인 호흡곤란": {
    bool_any: [["hvventiayn", "Y"]],
    min_ge1: [["hvicc", 1], ["hvcc", 1]],
    nice_to_have: [],
  },
  "소아 호흡곤란": {
    bool_any: [["hv10", "Y"], ["hv11", "Y"]],
    min_ge1: [["hvncc", 1]],
    nice_to_have: [],
  },
  "성인 경련": {
    bool_any: [["hvctayn", "Y"]],
    min_ge1: [["hvicc", 1], ["hv5", 1]],
    nice_to_have: [],
  },
  "소아 경련": {
    bool_any: [["hv10", "Y"], ["hv11", "Y"]],
    min_ge1: [["hvncc", 1]],
    nice_to_have: [],
  },
  "정형외과 중증(대형골절/절단)": {
    bool_any: [],
    min_ge1: [["hvoc", 1], ["hv3", 1], ["hv4", 1]],
    nice_to_have: [],
  },
  "신경외과 응급(의식저하/외상성출혈)": {
    bool_any: [["hvctayn", "Y"]],
    min_ge1: [["hv6", 1], ["hvicc", 1]],
    nice_to_have: [],
  },
  "소아 중증(신생아/영아)": {
    bool_any: [["hv10", "Y"], ["hv11", "Y"]],
    min_ge1: [["hvncc", 1]],
    nice_to_have: [],
  },
  "심정지/심폐정지": {
    bool_any: [],
    min_ge1: [],
    nice_to_have: [],
  },
};

export const facilityNames: Record<string, string> = {
  hvctayn: "CT",
  hvmriayn: "MRI",
  hvangioayn: "조영촬영기",
  hvventiayn: "인공호흡기",
  hv10: "VENTI(소아)",
  hv11: "인큐베이터",
};

export const bedNames: Record<string, string> = {
  hvec: "응급실",
  hvoc: "수술실",
  hvicc: "일반중환자실",
  hvncc: "신생중환자",
  hvcc: "신경중환자",
  hvccc: "흉부중환자",
  hvgc: "입원실",
  hv2: "내과중환자실",
  hv3: "외과중환자실",
  hv4: "외과입원실(정형외과)",
  hv5: "신경과입원실",
  hv6: "신경외과중환자실",
  hv7: "약물중환자",
  hv8: "화상중환자",
  hv9: "외상중환자",
};

