export interface Coords {
  lat: number | null;
  lon: number | null;
}

export interface Region {
  sido: string;
  sigungu: string;
}

export interface Hospital {
  hpid?: string;
  dutyName?: string;
  dutyAddr?: string;
  distance_km?: string | number;
  eta_minutes?: number;
  dutytel3?: string;
  wgs84Lat?: number;
  wgs84Lon?: number;
  dutyDiv?: string;
  dutyDivNam?: string;
  dutyEmcls?: string;
  dutyEmclsName?: string;
  hvec?: string | number;
  hvoc?: string | number;
  hvicc?: string | number;
  hvgc?: string | number;
  hvcc?: string | number;
  hvncc?: string | number;
  hvccc?: string | number;
  hvctayn?: string;
  hvmriayn?: string;
  hvangioayn?: string;
  hvventiayn?: string;
  hv1?: string;
  hv2?: string | number;
  hv3?: string | number;
  hv4?: string | number;
  hv5?: string | number;
  hv6?: string | number;
  hv7?: string | number;
  hv8?: string | number;
  hv9?: string | number;
  hv10?: string;
  hv11?: string;
  hvdnm?: string;
  hvidate?: string;
  _meets_conditions?: boolean;
  region_name?: string;
}

export type ApprovalStatus = "pending" | "approved" | "rejected" | "calling";

export interface SymptomRule {
  bool_any: Array<[string, string]>;
  min_ge1: Array<[string, number]>;
  nice_to_have: Array<[string, number]>;
}

export interface CriticalPreset {
  id: string;
  label: string;
  english?: string;
  preKtasLevel?: string;
  preKtasEvidence?: string;
}

export type InputMode = "stt" | "critical";

// 채팅 관련 타입 정의
export type UserRole = "PARAMEDIC" | "ER";

export type HandoverStatus = "ONGOING" | "COMPLETED";

export interface HospitalHandoverSummary {
  id: string;
  hospitalName: string;
  regionLabel: string;
  status: HandoverStatus;
  sessionId?: number; // 실제 DB의 ChatSession session_id (optional)
  requestId?: number; // EmergencyRequest request_id (optional)
  assignmentId?: number; // RequestAssignment assignment_id (optional)
}

export interface ChatMessage {
  id: string;
  role: UserRole;
  content: string;
  imageUrl?: string;
  sentAt: string;
}

export interface PatientTransportMeta {
  sessionId: string;
  patientAge?: number;
  patientSex?: "M" | "F";
  preKtasLevel?: number;
  chiefComplaint?: string;
  vitalsSummary?: string;
  etaMinutes?: number;
  distanceKm?: number;
  lastUpdated?: string;
}

