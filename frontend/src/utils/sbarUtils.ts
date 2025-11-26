/**
 * STT 텍스트에서 SBAR 형식 요약 생성
 * @param sttText STT로 입력받은 텍스트
 * @returns SBAR 형식 요약 문자열
 */
export function generateSBARSummary(sttText: string, symptom: string): string {
  if (!sttText || !sttText.trim()) {
    return "";
  }

  // Pre-KTAS 레벨 추출
  const preKtasMatch = sttText.match(/Pre-KTAS\s*(\d+)/i) || sttText.match(/(\d+)\s*점/i);
  const preKtasLevel = preKtasMatch ? preKtasMatch[1] : "2";

  // 나이 추출
  const ageMatch = sttText.match(/(\d+)\s*대/i) || sttText.match(/(\d+)\s*세/i);
  const age = ageMatch ? ageMatch[1] : "";

  // 성별 추출
  let sex = "";
  if (sttText.includes("남성") || sttText.includes("남자") || sttText.match(/남\s*성/i)) {
    sex = "남성";
  } else if (sttText.includes("여성") || sttText.includes("여자") || sttText.match(/여\s*성/i)) {
    sex = "여성";
  }

  // 증상 추출
  const symptomKeywords: Record<string, string[]> = {
    "뇌졸중": ["뇌졸중", "FAST", "편마비", "언어장애"],
    "심근경색": ["심근경색", "STEMI", "흉통", "심장"],
    "외상": ["외상", "골절", "출혈", "타박상"],
  };

  let chiefComplaint = "";
  for (const [key, keywords] of Object.entries(symptomKeywords)) {
    if (keywords.some((k) => sttText.includes(k))) {
      chiefComplaint = symptom || key;
      break;
    }
  }

  // 시간 추출 (예: "20분 전")
  const timeMatch = sttText.match(/(\d+)\s*분\s*(?:전|전부터)/i);
  const timeAgo = timeMatch ? timeMatch[1] : "";

  // 혈압 추출
  const bpMatch = sttText.match(/혈압\s*(\d+\/\d+)/i) || sttText.match(/(\d+\/\d+)\s*mmHg/i);
  const bloodPressure = bpMatch ? bpMatch[1] + " mmHg" : "";

  // 의식 상태 추출
  let consciousness = "";
  if (sttText.includes("의식 혼미") || sttText.includes("혼미")) {
    consciousness = "의식 혼미";
  } else if (sttText.includes("의식 명료") || sttText.includes("명료")) {
    consciousness = "의식 명료";
  }

  // FAST 양성 여부
  const fastPositive = sttText.includes("FAST") && (sttText.includes("양성") || sttText.includes("+") || sttText.includes("positive"));

  // 기저질환 추출
  const comorbidities: string[] = [];
  if (sttText.includes("고혈압") || sttText.includes("혈압")) {
    comorbidities.push("고혈압");
  }
  if (sttText.includes("당뇨")) {
    comorbidities.push("당뇨");
  }
  if (sttText.includes("심장질환")) {
    comorbidities.push("심장질환");
  }

  // SBAR 형식으로 구성
  let sbar = `Pre-KTAS ${preKtasLevel}점 분류 환자.\n`;

  // S (Situation)
  const situationParts: string[] = [];
  if (age && sex) {
    situationParts.push(`${age}대 ${sex}`);
  }
  if (chiefComplaint) {
    situationParts.push(chiefComplaint);
  }
  if (timeAgo) {
    situationParts.push(`발생 ${timeAgo}분`);
  }
  if (situationParts.length > 0) {
    sbar += `S: ${situationParts.join(", ")}.\n`;
  } else {
    sbar += `S: ${sttText.substring(0, 50)}...\n`;
  }

  // B (Background)
  const backgroundParts: string[] = [];
  if (comorbidities.length > 0) {
    backgroundParts.push(`${comorbidities.join(", ")} 기저질환`);
  }
  if (bloodPressure) {
    backgroundParts.push(`혈압 ${bloodPressure}`);
  }
  if (backgroundParts.length > 0) {
    sbar += `B: ${backgroundParts.join(", ")}.\n`;
  }

  // A (Assessment)
  const assessmentParts: string[] = [];
  if (consciousness) {
    assessmentParts.push(consciousness);
  }
  if (fastPositive) {
    assessmentParts.push("FAST 양성");
  }
  if (chiefComplaint) {
    assessmentParts.push(`${chiefComplaint} 강력 의심`);
  }
  if (assessmentParts.length > 0) {
    sbar += `A: ${assessmentParts.join(", ")}.\n`;
  }

  // R (Recommendation)
  if (chiefComplaint === "뇌졸중 의심(FAST+)" || sttText.includes("뇌졸중")) {
    sbar += "R: 24시간 뇌혈관중재술 가능 상급 응급의료센터로 신속 이송 필요.";
  } else if (chiefComplaint === "심근경색 의심(STEMI)" || sttText.includes("심근경색")) {
    sbar += "R: 24시간 관상동맥중재술 가능 상급 응급의료센터로 신속 이송 필요.";
  } else if (sttText.includes("외상") || sttText.includes("중증 외상")) {
    sbar += "R: 외상 전문의가 있는 상급 응급의료센터로 신속 이송 필요.";
  } else {
    sbar += "R: 적절한 응급의료기관으로 신속 이송 필요.";
  }

  return sbar.trim();
}

