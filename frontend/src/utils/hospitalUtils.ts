import type { Hospital, SymptomRule } from "../types";
import { SYMPTOM_RULES, facilityNames, bedNames } from "../constants";

export const getRequiredFacilities = (symptomName: string): string[] => {
  const rule = SYMPTOM_RULES[symptomName];
  if (!rule) return [];
  return rule.bool_any.map(([key]) => facilityNames[key]).filter((name): name is string => !!name);
};

export const getRequiredBeds = (symptomName: string): string[] => {
  const rule = SYMPTOM_RULES[symptomName];
  if (!rule) return [];
  return rule.min_ge1.map(([key]) => bedNames[key]).filter((name): name is string => !!name);
};

export const getNiceToHaveBeds = (symptomName: string): string[] => {
  const rule = SYMPTOM_RULES[symptomName];
  if (!rule) return [];
  return rule.nice_to_have.map(([key]) => bedNames[key]).filter((name): name is string => !!name);
};

export const formatBedValue = (value: string | number | undefined): string => {
  if (!value || value === "없음" || value === "None" || value === "nan") return "없음";
  if (typeof value === "string" && value.toUpperCase() === "Y") return "있음";
  if (typeof value === "string" && value.toUpperCase() === "N") return "없음";
  if (typeof value === "number") return `${value}개`;
  return String(value);
};

export const formatHvidate = (value?: string): string => {
  if (!value) return "업데이트 시간 정보 없음";
  const digitsOnly = value.replace(/\D/g, "");
  if (digitsOnly.length < 12) {
    return value;
  }
  const year = digitsOnly.slice(0, 4);
  const month = digitsOnly.slice(4, 6);
  const day = digitsOnly.slice(6, 8);
  const hour = digitsOnly.slice(8, 10);
  const minute = digitsOnly.slice(10, 12);
  return `${year}-${month}-${day} ${hour}:${minute}`;
};

/**
 * STT 텍스트에서 환자 연령 정보를 추출하여 성인/소아 판단
 * @param sttText STT로 입력받은 텍스트
 * @returns "adult" | "pediatric" | null (판단 불가능한 경우)
 */
export function detectPatientAgeGroup(sttText: string | null | undefined): "adult" | "pediatric" | null {
  if (!sttText) return null;
  
  // sttText가 문자열이 아닌 경우 처리
  if (typeof sttText !== 'string') {
    console.warn('detectPatientAgeGroup: sttText is not a string', typeof sttText, sttText);
    return null;
  }

  const text = sttText.toLowerCase();

  // 소아 관련 키워드 (우선순위 높음)
  const pediatricKeywords = [
    "생후",
    "신생아",
    "영아",
    "유아",
    "소아",
    "아동",
    "어린이",
    "신생아실",
    "소아과",
    "소아청소년",
    "소아중환자",
    "미숙아",
    "조산아",
    "신생아중환자",
    "인큐베이터",
    "소아용",
    "소아기",
  ];

  // 성인 관련 키워드
  const adultKeywords = [
    "성인",
    "성인 남성",
    "성인 여성",
    "남성",
    "여성",
    "10대",
    "20대",
    "30대",
    "40대",
    "50대",
    "60대",
    "70대",
    "80대",
    "90대",
    "청년",
    "중년",
    "장년",
    "노인",
    "고령",
  ];

  // 소아 키워드 확인
  for (const keyword of pediatricKeywords) {
    if (text.includes(keyword)) {
      return "pediatric";
    }
  }

  // 성인 키워드 확인
  for (const keyword of adultKeywords) {
    if (text.includes(keyword)) {
      return "adult";
    }
  }

  // 숫자 + "세", "살", "개월" 패턴 확인
  const agePatterns = [/(\d+)\s*(?:세|살|년생)/g, /생후\s*(\d+)\s*(?:주|개월|일)/g, /(\d+)\s*(?:개월|주|일)\s*(?:된|된\s*영유아|된\s*아기)/g];

  for (const pattern of agePatterns) {
    const matches = text.match(pattern);
    if (matches) {
      for (const match of matches) {
        const ageMatch = match.match(/(\d+)/);
        if (ageMatch) {
          const age = parseInt(ageMatch[1]);
          // 생후, 개월, 주, 일 단위는 소아로 판단
          if (match.includes("생후") || match.includes("개월") || match.includes("주") || match.includes("일")) {
            return "pediatric";
          }
          // 나이로 판단 (19세 이하는 소아로 간주, 다만 10대는 성인 키워드가 있으면 성인)
          if (age <= 19) {
            // "10대 소아" 같은 경우는 소아로 판단
            if (match.includes("소아") || match.includes("아동")) {
              return "pediatric";
            }
            // "10대 성인" 같은 경우는 성인으로 판단
            if (match.includes("성인")) {
              return "adult";
            }
            // 기본적으로 19세 이하는 소아로 판단
            return "pediatric";
          } else {
            return "adult";
          }
        }
      }
    }
  }

  return null;
}

/**
 * STT 텍스트에서 환자 나이 추출 (DB 저장용 - 숫자만 반환)
 * @param sttText STT로 입력받은 텍스트
 * @returns 나이 숫자 또는 undefined
 */
export function extractPatientAge(sttText: string | null | undefined): number | undefined {
  if (!sttText) return undefined;
  
  // sttText가 문자열이 아닌 경우 처리
  if (typeof sttText !== 'string') {
    console.warn('extractPatientAge: sttText is not a string', typeof sttText, sttText);
    return undefined;
  }

  const text = sttText;
  
  // 먼저 정확한 나이 추출 ("60세", "60살", "60년생")
  const exactAgePattern = /(\d+)\s*(?:세|살|년생)/;
  const exactMatch = text.match(exactAgePattern);
  if (exactMatch && exactMatch[1]) {
    const age = parseInt(exactMatch[1]);
    if (age > 0 && age < 150) {
      return age;
    }
  }
  
  // 연령대 추출 ("20대", "30대" 등) - 중간값으로 변환하여 DB에 저장
  const ageBandPattern = /(\d+)\s*대/;
  const bandMatch = text.match(ageBandPattern);
  if (bandMatch && bandMatch[1]) {
    const decade = parseInt(bandMatch[1]);
    if (decade >= 0 && decade < 15) {
      // 연령대의 중간값 반환
      // 10대는 10-19세이므로 중간값 15세
      // 20대는 20-29세이므로 중간값 25세
      if (decade === 10) {
        return 15; // 10대는 15세
      } else if (decade === 0) {
        return 1; // 0대(영유아)는 1세
      } else {
        return decade * 10 + 5; // 20대 → 25세, 30대 → 35세 등
      }
    }
  }

  return undefined;
}

/**
 * STT 텍스트에서 환자 연령대 추출 (표시용 - "20대" 형식으로 반환)
 * @param sttText STT로 입력받은 텍스트
 * @returns "20대", "30세" 등의 문자열 또는 undefined
 */
export function extractPatientAgeDisplay(sttText: string | null | undefined): string | undefined {
  if (!sttText) return undefined;
  
  // sttText가 문자열이 아닌 경우 처리
  if (typeof sttText !== 'string') {
    console.warn('extractPatientAgeDisplay: sttText is not a string', typeof sttText, sttText);
    return undefined;
  }
  
  const text = sttText;
  
  // 먼저 정확한 나이 추출 ("60세", "60살", "60년생")
  const exactAgePattern = /(\d+)\s*(?:세|살|년생)/;
  const exactMatch = text.match(exactAgePattern);
  if (exactMatch && exactMatch[1]) {
    const age = parseInt(exactMatch[1]);
    if (age > 0 && age < 150) {
      return `${age}세`;
    }
  }
  
  // 연령대 추출 ("20대", "30대" 등) - 그대로 반환
  const ageBandPattern = /(\d+)\s*대/;
  const bandMatch = text.match(ageBandPattern);
  if (bandMatch && bandMatch[1]) {
    const decade = parseInt(bandMatch[1]);
    if (decade >= 0 && decade < 15) {
      return `${decade}대`;
    }
  }
  
  return undefined;
}

/**
 * STT 텍스트에서 환자 성별 추출
 * @param sttText STT로 입력받은 텍스트
 * @returns "M" (남성) | "F" (여성) | undefined
 */
export function extractPatientSex(sttText: string | null | undefined): "M" | "F" | undefined {
  if (!sttText) return undefined;
  
  // sttText가 문자열이 아닌 경우 처리
  if (typeof sttText !== 'string') {
    console.warn('extractPatientSex: sttText is not a string', typeof sttText, sttText);
    return undefined;
  }

  const text = sttText.toLowerCase();
  
  // 여성 키워드 (우선순위 높음 - "여성"이 "남성"보다 먼저 나올 수 있음)
  const femaleKeywords = [
    "여성", "여자", "female", "f/", "f ", "여 ", "여성인", "여자분"
  ];
  for (const keyword of femaleKeywords) {
    if (text.includes(keyword)) {
      return "F";
    }
  }
  
  // 남성 키워드
  const maleKeywords = [
    "남성", "남자", "male", "m/", "m ", "남 ", "남성인", "남자분"
  ];
  for (const keyword of maleKeywords) {
    if (text.includes(keyword)) {
      return "M";
    }
  }

  return undefined;
}

/**
 * STT 텍스트에서 Pre-KTAS 레벨 추출
 * @param sttText STT로 입력받은 텍스트
 * @returns Pre-KTAS 레벨 (1-5) 또는 undefined
 */
export function extractPreKtasLevel(sttText: string | null | undefined): number | undefined {
  if (!sttText) return undefined;
  
  // sttText가 문자열이 아닌 경우 처리
  if (typeof sttText !== 'string') {
    console.warn('extractPreKtasLevel: sttText is not a string', typeof sttText, sttText);
    return undefined;
  }

  const text = sttText.toLowerCase();
  
  // "Pre-KTAS 1점", "Pre-KTAS 2점", "pre-ktas 2", "2점 분류" 등의 패턴
  // 우선순위: "Pre-KTAS {숫자}점" 형식이 가장 정확함
  const patterns = [
    /pre-ktas\s*(\d+)\s*점/i,  // "Pre-KTAS 1점", "Pre-KTAS 2점" 형식
    /pre-ktas\s*(\d+)/i,        // "Pre-KTAS 1", "pre-ktas 2" 형식
    /ktas\s*(\d+)\s*점/i,       // "KTAS 1점" 형식
    /ktas\s*(\d+)/i,            // "KTAS 1" 형식
    /(\d+)\s*점\s*분류/,        // "1점 분류" 형식
  ];
  
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match && match[1]) {
      const level = parseInt(match[1]);
      if (level >= 1 && level <= 5) {
        console.log(`✅ Pre-KTAS 레벨 추출 성공: ${level} (텍스트: "${sttText}")`);
        return level;
      }
    }
  }
  
  // "2점", "3점" 같은 단순 형식도 추출 (Pre-KTAS 없이 점수만 있는 경우)
  const simplePointPattern = /(\d+)\s*점/;
  const simpleMatch = text.match(simplePointPattern);
  if (simpleMatch && simpleMatch[1]) {
    const level = parseInt(simpleMatch[1]);
    if (level >= 1 && level <= 5) {
      console.log(`✅ Pre-KTAS 레벨 추출 성공 (단순 형식): ${level} (텍스트: "${sttText}")`);
      return level;
    }
  }
  
  // Pre-KTAS 레벨 추출 실패는 정상적인 경우가 많으므로 로그 제거 (너무 많은 경고 발생)
  // console.log(`⚠️ Pre-KTAS 레벨 추출 실패 (텍스트: "${sttText}")`);
  return undefined;
}

/**
 * 한 줄 텍스트에서 환자 정보를 통합 파싱 (중증탭 입력용)
 * 예: "30대 심근경색 의심(STEMI), 2점" → { age: 35, sex: undefined, preKtas: 2, symptom: "심근경색 의심(STEMI)" }
 * @param text 입력 텍스트
 * @returns 파싱된 환자 정보
 */
export function parsePatientInfoFromText(text: string | null | undefined): {
  age?: number;
  sex?: "M" | "F";
  preKtas?: number;
  symptom?: string;
} {
  if (!text || typeof text !== 'string') {
    return {};
  }

  const result: {
    age?: number;
    sex?: "M" | "F";
    preKtas?: number;
    symptom?: string;
  } = {};

  // 나이 추출
  const age = extractPatientAge(text);
  if (age) {
    result.age = age;
  }

  // 성별 추출
  const sex = extractPatientSex(text);
  if (sex) {
    result.sex = sex;
  }

  // Pre-KTAS 점수 추출 (개선된 버전)
  const preKtas = extractPreKtasLevel(text);
  if (preKtas) {
    result.preKtas = preKtas;
  }

  // 증상 추출 (심근경색, 뇌졸중, 외상 등)
  const symptomPatterns = [
    { pattern: /심근경색\s*의심\s*\(?\s*STEMI\s*\)?/i, symptom: "심근경색 의심(STEMI)" },
    { pattern: /심근경색\s*의심/i, symptom: "심근경색 의심(STEMI)" },
    { pattern: /STEMI/i, symptom: "심근경색 의심(STEMI)" },
    { pattern: /뇌졸중\s*의심/i, symptom: "뇌졸중 의심(FAST+)" },
    { pattern: /FAST\s*[+양]성/i, symptom: "뇌졸중 의심(FAST+)" },
    { pattern: /다발성\s*외상/i, symptom: "다발성 외상/중증 외상" },
    { pattern: /중증\s*외상/i, symptom: "다발성 외상/중증 외상" },
    { pattern: /외상\s*중증/i, symptom: "다발성 외상/중증 외상" },
    { pattern: /소아\s*중증/i, symptom: "소아 중증(신생아/영아)" },
    { pattern: /신생아|영아/i, symptom: "소아 중증(신생아/영아)" },
  ];

  for (const { pattern, symptom } of symptomPatterns) {
    if (pattern.test(text)) {
      result.symptom = symptom;
      break;
    }
  }

  // 증상이 없으면 텍스트에서 주요 키워드 추출
  if (!result.symptom) {
    const cleanedText = text
      .replace(/\d+\s*대/g, '') // 나이 제거
      .replace(/\d+\s*점/g, '') // 점수 제거
      .replace(/남성|여성|남자|여자/g, '') // 성별 제거
      .replace(/프리케이타스|Pre-KTAS|KTAS/gi, '') // Pre-KTAS 제거
      .replace(/[,，]/g, ' ') // 쉼표를 공백으로
      .trim();

    if (cleanedText.length > 0 && cleanedText.length < 50) {
      result.symptom = cleanedText;
    }
  }

  return result;
}
