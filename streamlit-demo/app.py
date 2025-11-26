# Flask 서버 실행 방법:
# cd /Users/sondongbin/Downloads
# python twilio_flask_server.py
# 새 터미널 열어서: ngrok http 5001
# Streamlit 앱의 'Twilio 다이얼 입력 설정'에 ngrok URL 입력

# er_triage_streamlit_app.py
# -*- coding: utf-8 -*-
import os, math, tempfile
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse

import requests, pandas as pd, streamlit as st, pydeck as pdk
from geopy.distance import geodesic

# OpenAI for STT
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
# Twilio for Auto Calling
try:
    from twilio.rest import Client as TwilioClient
    from twilio.twiml.voice_response import VoiceResponse, Gather
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False

# Flask for Twilio Callback
try:
    from flask import Flask, request as flask_request
    import threading
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

# Pyproj for coordinate transformation (WGS84 -> TM)
try:
    from pyproj import Transformer
    PYPROJ_AVAILABLE = True
except ImportError:
    PYPROJ_AVAILABLE = False

# API 키는 환경 변수에서만 가져옴 (기본값 없음)
DATA_GO_KR_KEY = os.getenv("DATA_GO_KR_SERVICE_KEY")
KAKAO_KEY = os.getenv("KAKAO_REST_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Twilio 인증 정보 (환경 변수에서만 가져옴)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "+14647682979")

# 시연용 전화번호 목록 (각 병원마다 다른 번호로 전화)
DEMO_PHONE_NUMBERS = [
    "010-2994-5413",
    #"010-4932-3766",  # 1번 병원 (1순위) ⭐
    #"010-5091-3281",
]

# OpenAI Client 초기화
if OPENAI_AVAILABLE and OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
else:
    openai_client = None

# Twilio Client 초기화
if TWILIO_AVAILABLE and TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
else:
    twilio_client = None

# Flask 서버 URL (별도 실행)
FLASK_SERVER_URL = "http://localhost:5001"  # macOS AirPlay가 5000번 포트를 사용하므로 5001 사용

def get_call_response(call_sid: str) -> Optional[Dict[str, Any]]:
    """Flask 서버에서 특정 Call SID의 다이얼 응답 가져오기"""
    try:
        response = requests.get(f"{FLASK_SERVER_URL}/api/response/{call_sid}", timeout=1)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None

def get_all_call_responses() -> Dict[str, Any]:
    """Flask 서버에서 모든 다이얼 응답 가져오기"""
    try:
        response = requests.get(f"{FLASK_SERVER_URL}/api/responses", timeout=1)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return {}

# Flask 서버 상태 확인
def check_flask_server() -> bool:
    """Flask 서버가 실행 중인지 확인"""
    try:
        response = requests.get(FLASK_SERVER_URL, timeout=1)
        return response.status_code == 200
    except Exception:
        return False

ER_BED_URL = "https://apis.data.go.kr/B552657/ErmctInfoInqireService/getEmrrmRltmUsefulSckbdInfoInqire"
EGET_BASE_URL = "https://apis.data.go.kr/B552657/ErmctInfoInqireService/getEgytBassInfoInqire"
KAKAO_COORD2REGION_URL = "https://dapi.kakao.com/v2/local/geo/coord2regioncode.json"
KAKAO_COORD2ADDR_URL   = "https://dapi.kakao.com/v2/local/geo/coord2address.json"
KAKAO_ADDRESS_URL      = "https://dapi.kakao.com/v2/local/search/address.json"

def _http_get(url: str, params: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> requests.Response:
    timeout = (5, 15)
    params = dict(params) if params else {}
    if url.startswith("http://apis.data.go.kr/"):
        url = url.replace("http://", "https://", 1)
    netloc = urlparse(url).netloc
    if "apis.data.go.kr" in netloc:
        svc_key = params.pop("serviceKey", DATA_GO_KR_KEY)
        if svc_key:
            if "%" in svc_key:
                join = "&" if ("?" in url) else "?"
                url = f"{url}{join}serviceKey={svc_key}"
            else:
                params["serviceKey"] = svc_key
    resp = requests.get(url, params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp

def kakao_coord2region(lon: float, lat: float, kakao_key: str) -> Optional[Tuple[str, str, str]]:
    if not kakao_key: return None
    headers = {"Authorization": f"KakaoAK {kakao_key}"}
    params = {"x": lon, "y": lat}
    try:
        r = _http_get(KAKAO_COORD2REGION_URL, params=params, headers=headers)
        data = r.json(); docs = data.get("documents", [])
        target = next((d for d in docs if d.get("region_type")=="B"), docs[0] if docs else None)
        if not target: return None
        return target.get("region_1depth_name"), target.get("region_2depth_name"), target.get("code")
    except Exception:
        return None

def kakao_coord2address(lon: float, lat: float, kakao_key: str) -> Optional[str]:
    if not kakao_key: return None
    headers = {"Authorization": f"KakaoAK {kakao_key}"}
    params = {"x": lon, "y": lat}
    try:
        r = _http_get(KAKAO_COORD2ADDR_URL, params=params, headers=headers)
        data = r.json(); docs = data.get("documents", [])
        if not docs: return None
        d0 = docs[0]
        if d0.get("road_address") and d0["road_address"].get("address_name"):
            return d0["road_address"]["address_name"]
        if d0.get("address") and d0["address"].get("address_name"):
            return d0["address"]["address_name"]
        return None
    except Exception:
        return None

def kakao_address2coord(address: str, kakao_key: str) -> Optional[Tuple[float, float]]:
    if not kakao_key: return None
    headers = {"Authorization": f"KakaoAK {kakao_key}"}
    params = {"query": address}
    try:
        r = _http_get(KAKAO_ADDRESS_URL, params=params, headers=headers)
        data = r.json(); docs = data.get("documents", [])
        if not docs: return None
        first = docs[0]; lon = float(first["x"]); lat = float(first["y"])
        return (lat, lon)
    except Exception:
        return None

def wgs84_to_naver_katech(lon: float, lat: float) -> Tuple[float, float]:
    """
    WGS84 좌표(경도, 위도)를 네이버 지도 Katech 좌표로 변환
    
    Args:
        lon: WGS84 경도
        lat: WGS84 위도
    
    Returns:
        (katech_x, katech_y): Katech 좌표
    """
    if not PYPROJ_AVAILABLE:
        # pyproj가 없으면 근사 변환 (정확하지 않음)
        return (lon * 100000, lat * 100000)
    
    try:
        # WGS84 (EPSG:4326)
        wgs84 = "EPSG:4326"
        
        # 네이버 지도 Katech 좌표계 (GRS80 타원체, TM 투영)
        # Katech는 네이버/다음 지도에서 사용하는 한국 전용 좌표계
        # 원점: 동경 128도, 북위 38도
        # False Easting: 400000m, False Northing: 600000m
        katech = "+proj=tmerc +lat_0=38 +lon_0=128 +k=0.9999 +x_0=400000 +y_0=600000 +ellps=bessel +units=m +no_defs +towgs84=-115.80,474.99,674.11,1.16,-2.31,-1.63,6.43"
        
        # Transformer 생성
        transformer = Transformer.from_crs(wgs84, katech, always_xy=True)
        
        # 좌표 변환 (lon, lat -> katech_x, katech_y)
        katech_x, katech_y = transformer.transform(lon, lat)
        
        return (katech_x, katech_y)
    except Exception as e:
        # 변환 실패 시 근사값 반환
        return (lon * 100000, lat * 100000)

def fetch_baseinfo_by_hpid(hpid: str, service_key: str) -> Optional[Dict[str, Any]]:
    from xml.etree import ElementTree as ET
    try:
        r = _http_get(EGET_BASE_URL, {"HPID": hpid, "pageNo": 1, "numOfRows": 1, "serviceKey": service_key})
        root = ET.fromstring(r.content); it = root.find(".//item")
        if it is None: return None
        def g(tag):
            el = it.find(tag); return el.text.strip() if el is not None and el.text is not None else None
        return {
            "hpid": g("hpid"), "dutyName": g("dutyName") or g("dutyname"), "dutyAddr": g("dutyAddr"),
            "dutytel3": g("dutyTel3"),
            "wgs84Lat": float(g("wgs84Lat")) if g("wgs84Lat") else None,
            "wgs84Lon": float(g("wgs84Lon")) if g("wgs84Lon") else None,
        }
    except Exception:
        return None

@st.cache_data(ttl=60)
def fetch_emergency_hospitals_in_region(sido: str, sigungu: str, service_key: str, max_items: int = 200) -> pd.DataFrame:
    from xml.etree import ElementTree as ET
    r = _http_get(ER_BED_URL, {"STAGE1": sido, "STAGE2": sigungu, "pageNo": 1, "numOfRows": 500, "serviceKey": service_key})
    root = ET.fromstring(r.content); hpids = []
    for it in root.findall(".//item"):
        el = it.find("hpid"); 
        if el is not None and el.text: hpids.append(el.text.strip())
    hpids = list(dict.fromkeys(hpids))[:max_items]
    rows = []
    for h in hpids:
        info = fetch_baseinfo_by_hpid(h, service_key)
        if info and info.get("wgs84Lat") and info.get("wgs84Lon"): rows.append(info)
    df = pd.DataFrame(rows)
    if not df.empty: df = df.dropna(subset=["wgs84Lat","wgs84Lon"])
    return df

@st.cache_data(ttl=30)
def fetch_er_beds(sido: str, sigungu: str, service_key: str, rows: int = 500) -> pd.DataFrame:
    from xml.etree import ElementTree as ET
    params = {"STAGE1": sido, "STAGE2": sigungu, "pageNo": 1, "numOfRows": rows, "serviceKey": service_key}
    resp = _http_get(ER_BED_URL, params=params); root = ET.fromstring(resp.content); items = root.findall(".//item")
    rows_list = []
    for it in items:
        def g(tag):
            el = it.find(tag); return el.text.strip() if el is not None and el.text is not None else None
        rows_list.append({
            "hpid": g("hpid"), "dutyName": g("dutyname"), "hvidate": g("hvidate"),
            "hvec": g("hvec"), "hvoc": g("hvoc"), "hvicc": g("hvicc"), "hvgc": g("hvgc"),
            "hvcc": g("hvcc"), "hvncc": g("hvncc"), "hvccc": g("hvccc"),
            "hvctayn": g("hvctayn"), "hvmriayn": g("hvmriayn"), "hvangioayn": g("hvangioayn"), "hvventiayn": g("hvventiayn"),
            "hv1": g("hv1"), "hv2": g("hv2"), "hv3": g("hv3"), "hv4": g("hv4"),
            "hv5": g("hv5"), "hv6": g("hv6"), "hv7": g("hv7"), "hv8": g("hv8"),
            "hv9": g("hv9"), "hv10": g("hv10"), "hv11": g("hv11"), "hv12": g("hv12"),
            "dutytel3": g("dutytel3") or g("hv1"), "hvdnm": g("hvdnm"),
        })
    df = pd.DataFrame(rows_list)
    if not df.empty: df = df.dropna(subset=["hpid"])
    return df

def add_distance_km(df: pd.DataFrame, user_lat: float, user_lon: float) -> pd.DataFrame:
    if df.empty:
        df["distance_km"] = []; return df
    distances = []
    for _, row in df.iterrows():
        try:
            lat, lon = float(row["wgs84Lat"]), float(row["wgs84Lon"])
            d = geodesic((user_lat, user_lon), (lat, lon)).km
        except Exception:
            d = math.nan
        distances.append(d)
    df = df.copy(); df["distance_km"] = distances
    return df.sort_values("distance_km")

def _safe_int(x):
    try: return int(str(x).strip()) if str(x).strip() not in ("", "None", "nan") else 0
    except: return 0

SYMPTOM_RULES = {
    "뇌졸중 의심(FAST+)": {"bool_any":[("hvctayn","Y")], "min_ge1":[("hvicc",1)], "nice_to_have":[("hv5",1),("hv6",1)]},
    "심근경색 의심(STEMI)": {"bool_any":[("hvangioayn","Y")], "min_ge1":[("hvoc",1),("hvicc",1)], "nice_to_have":[]},
    "다발성 외상/중증 외상": {"bool_any":[("hvventiayn","Y")], "min_ge1":[("hvoc",1),("hvicc",1)], "nice_to_have":[("hv9",1)]},
    "소아 중증(호흡곤란/경련 등)": {"bool_any":[("hv10","Y"),("hv11","Y")], "min_ge1":[("hvncc",1)], "nice_to_have":[]},
    "정형외과 중증(대형골절/절단)": {"bool_any":[], "min_ge1":[("hvoc",1),("hv3",1),("hv4",1)], "nice_to_have":[]},
    "신경외과 응급(의식저하/외상성출혈)": {"bool_any":[("hvctayn","Y")], "min_ge1":[("hv6",1),("hvicc",1)], "nice_to_have":[]},
}

def meets_requirements(row: pd.Series, rule: Dict[str, Any]) -> bool:
    for key, want in rule.get("bool_any", []):
        if str(row.get(key, "")).strip().upper() != want: return False
    for key, thr in rule.get("min_ge1", []):
        if _safe_int(row.get(key)) < thr: return False
    return True

def guess_region_from_address(addr: Optional[str]) -> Optional[Tuple[str, str]]:
    if not addr: return None
    parts = str(addr).strip().split()
    if len(parts)>=2: return parts[0], parts[1]
    return None

# 📞 Twilio 자동 전화 함수
def make_call_to_hospital(phone_number: str, hospital_name: str, patient_info: str = None, callback_url: str = None) -> Optional[Dict[str, Any]]:
    """Twilio를 사용하여 병원에 자동으로 전화를 겁니다."""
    if not twilio_client:
        return {"status": "error", "message": "Twilio 클라이언트가 초기화되지 않았습니다."}
    
    try:
        # 전화번호를 국제 형식으로 변환
        clean_number = phone_number.replace("-", "").replace(" ", "")
        
        # 이미 국제 형식이면 그대로 사용
        if clean_number.startswith("+82"):
            international_number = clean_number
        # 휴대폰 번호 (010, 011, 016, 017, 018, 019)
        elif clean_number.startswith("01"):
            international_number = f"+82{clean_number[1:]}"
        # 지역 번호 (02, 031, 032 등)
        elif clean_number.startswith("0"):
            international_number = f"+82{clean_number[1:]}"
        else:
            # 시연용 번호로 대체 (안전장치)
            international_number = "+8229945413"
            st.warning(f"⚠️ 전화번호 형식 오류: {phone_number} → 시연용 번호 사용")
        
        # TwiML 생성: STT 텍스트를 음성으로 전달 + Gather로 입력 받기
        response = VoiceResponse()
        
        # 기본 안내 메시지
        response.say(
            f"안녕하세요. {hospital_name} 응급실입니다.",
            language="ko-KR",
            voice="Polly.Seoyeon"
        )
        
        # STT로 입력받은 환자 정보가 있으면 전달
        if patient_info:
            response.say(
                f"응급 환자 정보를 전달드립니다. {patient_info}",
                language="ko-KR",
                voice="Polly.Seoyeon"
            )
        else:
            response.say(
                "응급 환자 입실 요청 드립니다.",
                language="ko-KR",
                voice="Polly.Seoyeon"
            )
        
        response.pause(length=1)
        
        # Gather: 다이얼 입력 받기
        if callback_url:
            gather = Gather(
                num_digits=1,  # 1자리 숫자만
                action=callback_url,  # 입력 후 콜백 URL
                method='POST',
                timeout=60  # 60초 대기 (1분)
            )
            gather.say(
                "해당 응급 환자 진료가 가능하시면 다이얼 1번을, 진료가 불가능하시면 2번을 눌러주세요.",
                language="ko-KR",
                voice="Polly.Seoyeon"
            )
            response.append(gather)
            
            # 입력이 없을 경우
            response.say(
                "입력이 없습니다. 다른 병원을 찾겠습니다.",
                language="ko-KR",
                voice="Polly.Seoyeon"
            )
        else:
            # 콜백 URL이 없으면 기본 메시지만
            response.say(
                "병상 가용 여부를 확인해주시기 바랍니다. 감사합니다.",
                language="ko-KR",
                voice="Polly.Seoyeon"
            )
        
        # TwiML을 문자열로 변환
        twiml_str = str(response)
        
        # Twilio로 전화 걸기 (TwiML 직접 전달)
        call = twilio_client.calls.create(
            to=international_number,
            from_=TWILIO_FROM_NUMBER,
            twiml=twiml_str,
            status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
            status_callback_method='POST'
        )
        
        return {
            "status": "success",
            "call_sid": call.sid,
            "to": international_number,
            "from": TWILIO_FROM_NUMBER,
            "hospital_name": hospital_name,
            "call_status": call.status,
            "patient_info": patient_info,
            "twiml_preview": twiml_str[:200] + "..." if len(twiml_str) > 200 else twiml_str
        }
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        return {
            "status": "error",
            "message": f"전화 연결 실패: {str(e)}",
            "error_detail": error_detail,
            "hospital_name": hospital_name,
            "attempted_number": phone_number
        }

def check_call_status(call_sid: str) -> str:
    """Twilio 통화 상태를 확인합니다."""
    if not twilio_client:
        return "no_client"
    
    try:
        call = twilio_client.calls(call_sid).fetch()
        # 가능한 상태: queued, ringing, in-progress, completed, busy, failed, no-answer, canceled
        return call.status
    except Exception as e:
        return f"error: {str(e)}"

# 🧠 STT + 의학용어 번역 함수
def transcribe_and_translate_audio(audio_bytes):
    """음성을 텍스트로 변환하고 의학용어를 번역합니다."""
    if not openai_client:
        return "⚠️ OpenAI 클라이언트가 초기화되지 않았습니다. API 키를 확인하세요."
    
    try:
        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            tmp_file.write(audio_bytes)
            tmp_file_path = tmp_file.name
        
        # Whisper STT
        with open(tmp_file_path, "rb") as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text",
                language="ko"
            )
        
        # GPT-4-turbo로 의학용어 번역
        medical_keywords = """M/S, mental state, Alert, confusion, drowsy, stupor, semicoma, coma, V/S, vital sign, TPR, temperature, pulse, respiration, HR, heart rate, PR, pulse rate, BP, blood pressure, BT, body temperature, RR, respiratory rate, BST, blood sugar test, SpO2, sat, saturation of percutaneous oxygen, Abdomen, Abdominal pain, Abnormal, Abrasion, Abscess, Acetaminophen, Acidosis, Acute, Acute abdomen, Acute bronchitis, Acute coronary syndrome, Acute myocardial infarction, Acute renal failure, Acute respiratory distress syndrome, Acute stroke, Airway, Airway obstruction, Alcohol intoxication, Allergy, Allergic reaction, Amnesia, Anaphylactic shock, Anaphylaxis, Analgesic, Anemia, Aneurysm, Angina, Angina pectoris, Angiography, Arrhythmia, Arterial bleeding, Asphyxia, Aspiration, Asthma, Cardiac Arrest, Cardiac tamponade, Cardiogenic shock, Cardiopulmonary arrest, Cardiopulmonary resuscitation (CPR), Cerebral hemorrhage, Cerebral infarction, Cerebrovascular accident (CVA), Chest compression, Chest pain, Choking, Chronic obstructive pulmonary disease (COPD), Coma, Concussion, Confusion, Convulsion, Coronary artery disease (CAD), Cough, Cyanosis, Defibrillation, Dehydration, Dementia, Diabetes mellitus, Diabetic ketoacidosis, Diarrhea, Dizziness, Drowning, Drowsy, Dyspnea, ECG (Electrocardiogram), Edema, Electrocution, Embolism, Emphysema, Endotracheal intubation, Epilepsy, Epistaxis, Fever, Fracture, GCS (Glasgow Coma Scale), Headache, Head injury, Heart arrest, Heart failure, Heart rate, Hematoma, Hematuria, Hemoptysis, Hemorrhage, Hyperglycemia, Hypertension, Hyperthermia, Hyperventilation, Hypoglycemia, Hypotension, Hypothermia, Hypovolemic shock, Hypoxia, Intoxication, Intracranial pressure, Ischemia, Laceration, Myocardial infarction, Nausea, Oxygen therapy, Pneumonia, Pneumothorax, Respiratory arrest, Respiratory distress, Respiratory failure, Seizure, Sepsis, Septic shock, Shock, Stroke, Stupor, Syncope, Tachycardia, Trauma, Unconsciousness, Ventilation, Vertigo, Vomiting, Wound"""
        
        prompt = f"""아래는 응급의료 상황 대화의 텍스트입니다.
        전반적으로 한국어로 번역하되, 텍스트에서 등장하는 의학 관련 용어(약어 포함)는 응급의료 문맥에 맞게 올바르게 영어로 번역하세요.
내가 너에게 전달해준 문장을 누락없이 번역해야해.
단, 출력문장은 오직 번역문장만 남겨서 깔끔하게 출력하세요.

참고 키워드: {medical_keywords}

텍스트:
{transcript}
"""
        
        completion = openai_client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "너는 응급의료 현장의 대화를 전문적으로 해석하는 의료용어 번역 전문가이다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        translated_text = completion.choices[0].message.content
        
        # STT 결과 저장 (타임스탬프 포함, 누적 기록)
        import datetime
        save_stt_filepath = "stt_history.txt"
        with open(save_stt_filepath, "a", encoding="utf-8") as fh:
            timestr = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            fh.write(f"[{timestr}] {translated_text}\n")
        
        # 임시 파일 삭제
        os.remove(tmp_file_path)
        
        return translated_text
        
    except Exception as e:
        return f"❌ 음성 인식 오류: {str(e)}"

st.set_page_config(page_title="증상맞춤 응급 병상 Top3", page_icon="🚑")
st.title("SAFE BRIDGE")
st.caption("• 데이터: 국립중앙의료원 응급의료 Open API / 카카오 로컬 • 데모 목적 — 실제 운용 전 기관 협의 및 데이터 검증 필요")

st.divider()

# API 키 상태 체크 (디버깅용 - 실제 키는 노출하지 않음)
with st.expander("🔧 시스템 상태 확인", expanded=False):
    flask_server_running = check_flask_server()
    st.markdown(f"""
    - **OpenAI API**: {'✅ 설정됨' if OPENAI_AVAILABLE and openai_client else '❌ 미설정'}
    - **Twilio API**: {'✅ 설정됨' if TWILIO_AVAILABLE and twilio_client else '❌ 미설정'}
    - **Flask 서버**: {'✅ 실행 중 (localhost:5001)' if flask_server_running else '❌ 미실행'}
    - **Pyproj (좌표 변환)**: {'✅ 설치됨' if PYPROJ_AVAILABLE else '❌ 미설치'}
    - **Streamlit 버전**: {st.__version__}
    - **마이크 입력**: {'✅ 지원됨' if callable(getattr(st, 'audio_input', None)) else '❌ 미지원'}
    """)
    
    if not flask_server_running:
        st.warning("⚠️ Flask 서버가 실행되지 않았습니다. Twilio 다이얼 입력을 받을 수 없습니다.")
        st.code("python /Users/sondongbin/Downloads/twilio_flask_server.py", language="bash")
        st.caption("💡 포트 5001 사용 (macOS AirPlay가 5000 사용)")

for k, v in [("auto_lat", None), ("auto_lon", None), ("auto_addr", ""), ("address_search_trigger", False)]:
    if k not in st.session_state: st.session_state[k] = v

# 주소 검색 함수 (엔터 또는 검색 버튼 클릭 시)
def search_address():
    if st.session_state.get("auto_addr") and KAKAO_KEY:
        coord = kakao_address2coord(st.session_state["auto_addr"], KAKAO_KEY)
        if coord:
            st.session_state["auto_lat"], st.session_state["auto_lon"] = coord[0], coord[1]
            st.success(f"✅ 좌표 변환 성공: {st.session_state['auto_addr']}")
        else:
            st.error("❌ 주소 → 좌표 변환 실패. 주소를 다시 확인하세요.")

st.subheader("📍 내 위치")
col_addr, col_search, col_gps = st.columns([5, 1, 2], vertical_alignment="bottom")
with col_addr:
    # on_change로 엔터 시 자동 검색
    st.text_input("내 위치 (주소)", key="auto_addr", placeholder="예: 서울특별시 종로구 종로1길 50", 
                  on_change=search_address)
with col_search:
    # 검색 버튼 (모바일 친화적)
    if st.button("🔍", use_container_width=True, help="주소 검색"):
        search_address()
with col_gps:
    if st.button("📍 GPS", use_container_width=True, help="현재 위치로 재설정"):
        lat = lon = None
        try:
            from streamlit_js_eval import get_geolocation
            loc = get_geolocation()
            if loc and isinstance(loc, dict):
                coords = loc.get("coords") or loc
                lat = coords.get("latitude"); lon = coords.get("longitude")
        except Exception: pass
        if lat is None or lon is None:
            try:
                from streamlit_geolocation import geolocation
                g = geolocation("📍 위치 권한을 허용해 주세요")
                if g and g.get("latitude") and g.get("longitude"):
                    lat = g["latitude"]; lon = g["longitude"]
            except Exception: pass
        if lat is not None and lon is not None:
            st.session_state["auto_lat"] = float(lat); st.session_state["auto_lon"] = float(lon)
            addr = kakao_coord2address(float(lon), float(lat), KAKAO_KEY) or ""
            st.session_state["auto_addr"] = addr  # 주소 자동 입력
            st.success(f"✅ GPS 위치 설정 완료!")
            st.rerun()  # 주소 입력란에 즉시 반영
        else:
            st.error("❌ 브라우저 위치를 가져올 수 없습니다. HTTPS(또는 localhost)에서 위치 권한을 허용해 주세요.")

lat_show = st.session_state.get("auto_lat"); lon_show = st.session_state.get("auto_lon")
st.caption(f"📌 현재 좌표: {f'{lat_show:.6f}' if lat_show is not None else '—'}, {f'{lon_show:.6f}' if lon_show is not None else '—'}")

user_lat = st.session_state.get("auto_lat"); user_lon = st.session_state.get("auto_lon")
if user_lat is None or user_lon is None:
    st.info("🔍 위치를 설정해주세요: GPS 버튼 또는 주소 입력 후 검색"); st.stop()

region = kakao_coord2region(user_lon, user_lat, KAKAO_KEY) if KAKAO_KEY else None
guessed = None
if region:
    sido, sigungu, code = region
    st.caption(f"📍 행정구역: **{sido} {sigungu}**")
else:
    guessed = guess_region_from_address(st.session_state.get("auto_addr"))
    if guessed:
        sido, sigungu = guessed
        st.caption(f"📍 행정구역 (주소 기반 추정): **{sido} {sigungu}**")
    else:
        st.warning("⚠️ 행정구역 자동 인식 실패 — 시/도, 시/군/구를 직접 입력하세요.")
        colr1, colr2 = st.columns(2)
        with colr1:  sido = st.text_input("시/도 (예: 광주광역시)", value="광주광역시")
        with colr2:  sigungu = st.text_input("시/군/구 (예: 동구)", value="동구")

with st.expander("🔍 진단 (위치 확인)", expanded=False):
    st.write("현재 좌표:", user_lat, user_lon)
    try:
        st.write("coord2address:", kakao_coord2address(user_lon, user_lat, KAKAO_KEY))
    except Exception as e:
        st.error(f"coord2address 에러: {e}")
    try:
        st.write("coord2region:", kakao_coord2region(user_lon, user_lat, KAKAO_KEY))
    except Exception as e:
        st.error(f"coord2region 에러: {e}")

st.divider()

# 🎤 음성 입력 섹션
st.subheader("🎤 음성으로 증상 설명하기")

# Session state 초기화
if "stt_result" not in st.session_state:
    st.session_state.stt_result = ""
if "voice_mode" not in st.session_state:
    st.session_state.voice_mode = False
if "rejected_hospitals" not in st.session_state:
    st.session_state.rejected_hospitals = set()
if "reroll_count" not in st.session_state:
    st.session_state.reroll_count = 0
if "hospital_approval_status" not in st.session_state:
    st.session_state.hospital_approval_status = {}
if "show_results" not in st.session_state:
    st.session_state.show_results = False
if "pending_approval" not in st.session_state:
    st.session_state.pending_approval = False
if "top3_data" not in st.session_state:
    st.session_state.top3_data = None
if "route_paths_data" not in st.session_state:
    st.session_state.route_paths_data = {}
if "backup_hospitals" not in st.session_state:
    st.session_state.backup_hospitals = None
if "rejection_log" not in st.session_state:
    st.session_state.rejection_log = []
if "hospital_stack" not in st.session_state:
    st.session_state.hospital_stack = []  # 모든 병원 카드 히스토리
if "approved_hospital" not in st.session_state:
    st.session_state.approved_hospital = None  # 승인된 병원 정보
if "auto_simulation_active" not in st.session_state:
    st.session_state.auto_simulation_active = False
if "current_hospital_index" not in st.session_state:
    st.session_state.current_hospital_index = 0
if "simulation_stage" not in st.session_state:
    st.session_state.simulation_stage = "ready"  # ready, calling, deciding
if "simulation_start_time" not in st.session_state:
    st.session_state.simulation_start_time = None
if "active_calls" not in st.session_state:
    st.session_state.active_calls = {}
if "twilio_auto_calling" not in st.session_state:
    st.session_state.twilio_auto_calling = False

# 큰 버튼 스타일
st.markdown("""
<style>
.big-voice-button {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 3rem 2rem;
    border-radius: 20px;
    text-align: center;
    font-size: 1.8rem;
    font-weight: bold;
    cursor: pointer;
    box-shadow: 0 8px 16px rgba(102, 126, 234, 0.4);
    transition: all 0.3s;
    margin: 1rem 0;
    border: 3px solid #764ba2;
}
.big-voice-button:hover {
    transform: translateY(-3px);
    box-shadow: 0 12px 24px rgba(102, 126, 234, 0.5);
}
.stt-result-box {
    background: #f0f9ff;
    border: 2px solid #0284c7;
    border-radius: 12px;
    padding: 1.5rem;
    margin: 1rem 0;
    font-size: 1.1rem;
    line-height: 1.8;
}
</style>
""", unsafe_allow_html=True)

# 녹음 시작 버튼
col_btn1, col_btn2 = st.columns([3, 1])
with col_btn1:
    if st.button("🎤 녹음 시작하기", key="start_recording", use_container_width=True, type="primary"):
        st.session_state.voice_mode = True
        st.rerun()

with col_btn2:
    if st.session_state.stt_result:
        if st.button("🗑️ 초기화", use_container_width=True):
            st.session_state.stt_result = ""
            st.session_state.voice_mode = False
            st.rerun()

# 녹음 모드일 때만 오디오 입력 표시
if st.session_state.voice_mode:
    st.info("🎙️ 마이크로 증상을 말씀해주세요.")
    
    # 마이크 사용 참고사항
    st.markdown("""
    <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 1rem; margin: 1rem 0; border-radius: 4px;">
        <b>⚠️ 마이크 녹음 사용 시 주의사항:</b>
        <ul style="margin: 0.5rem 0;">
            <li>✅ <b>Chrome 또는 Edge 최신버전</b> 사용 권장</li>
            <li>✅ <b>HTTPS 또는 localhost</b>에서만 작동 (보안 정책)</li>
            <li>✅ 브라우저에서 <b>마이크 권한 허용</b> 필요</li>
            <li>❌ Safari, Firefox는 지원 불안정</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    # Streamlit 버전 확인: audio_input 기능이 있는지 체크
    has_audio_input = callable(getattr(st, 'audio_input', None))
    
    if has_audio_input:
        # 마이크 권한 확인 및 안내
        st.markdown("""
        <div style="background: #e3f2fd; border-left: 4px solid #2196f3; padding: 1rem; margin: 1rem 0; border-radius: 4px;">
            <b>🎤 마이크 사용 전 확인사항:</b>
            <ol style="margin: 0.5rem 0;">
                <li>브라우저 주소창 왼쪽의 <b>🔒 또는 🎤 아이콘</b>을 클릭하세요</li>
                <li><b>"마이크" 권한을 "허용"</b>으로 설정하세요</li>
                <li>페이지를 새로고침하세요 (F5 또는 Ctrl+R)</li>
            </ol>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("**마이크 버튼을 눌러 녹음을 시작하세요:**")
        
        # 에러 상태 추적
        if "audio_error_count" not in st.session_state:
            st.session_state.audio_error_count = 0
        
        try:
            audio_data = st.audio_input("🎤 증상 녹음", key="audio_input_mic")
            
            # 정상 작동하면 에러 카운트 초기화
            st.session_state.audio_error_count = 0
            
            if audio_data is not None:
                with st.spinner("🧠 음성을 분석하고 의학용어를 번역하는 중..."):
                    try:
                        audio_bytes = audio_data.read()
                        if len(audio_bytes) == 0:
                            st.error("❌ 녹음된 음성이 없습니다. 다시 시도해주세요.")
                        else:
                            # OpenAI 클라이언트 체크
                            if not openai_client:
                                st.error("❌ OpenAI API 클라이언트가 초기화되지 않았습니다.")
                                st.info("앱을 재시작해주세요: Ctrl+C 후 `streamlit run message.py`")
                                st.stop()
                            
                            result_text = transcribe_and_translate_audio(audio_bytes)
                            if result_text and not result_text.startswith("❌"):
                                st.session_state.stt_result = result_text
                                st.session_state.voice_mode = False
                                st.rerun()
                            else:
                                st.error(result_text)
                    except Exception as e:
                        import traceback
                        st.error(f"❌ 음성 처리 오류: {str(e)}")
                        with st.expander("🐛 상세 에러 정보 (디버깅용)"):
                            st.code(traceback.format_exc())
        except Exception as e:
            st.session_state.audio_error_count += 1
            import traceback
            
            st.error(f"⚠️ 마이크 접근 오류: {str(e)}")
            
            # 반복 에러 시 더 자세한 안내
            if st.session_state.audio_error_count >= 2:
                st.markdown("""
                <div style="background: #ffebee; border-left: 4px solid #f44336; padding: 1rem; margin: 1rem 0; border-radius: 4px;">
                    <b>❌ 마이크 권한이 거부되었습니다</b>
                    <br><br>
                    <b>Chrome 사용자:</b>
                    <ol>
                        <li>주소창 왼쪽 <b>🔒</b> 아이콘 클릭</li>
                        <li>"사이트 설정" 클릭</li>
                        <li>"마이크" 찾아서 <b>"허용"</b> 선택</li>
                        <li>페이지 새로고침 (F5)</li>
                    </ol>
                    
                    <b>대안: 파일 업로드 사용</b><br>
                    아래 "파일 업로드" 옵션을 사용하세요.
                </div>
                """, unsafe_allow_html=True)
            
            with st.expander("🐛 상세 에러 정보 (디버깅용)"):
                st.code(traceback.format_exc())
                st.markdown(f"""
                **에러 발생 횟수**: {st.session_state.audio_error_count}회
                
                **해결 방법:**
                1. 브라우저 주소창의 마이크 권한 허용
                2. localhost로 접속 중인지 확인
                3. Chrome 브라우저 사용
                4. 아래 "파일 업로드" 옵션 사용
                """)
    else:
        st.warning("⚠️ 마이크 녹음이 지원되지 않습니다.")
        st.info("Streamlit 1.28.0 이상 필요: `pip install --upgrade streamlit`")
    
    # 대안: 파일 업로드
    st.divider()
    st.markdown("### 📤 또는 음성 파일 업로드")
    st.caption("마이크가 작동하지 않으면 미리 녹음한 음성 파일(.wav, .mp3, .m4a)을 업로드하세요")
    
    uploaded_audio = st.file_uploader(
        "음성 파일 선택",
        type=["wav", "mp3", "m4a", "ogg", "webm"],
        key="audio_file_upload",
        help="휴대폰 녹음 앱으로 녹음한 파일을 업로드하세요"
    )
    
    if uploaded_audio is not None:
        st.audio(uploaded_audio, format=f"audio/{uploaded_audio.name.split('.')[-1]}")
        
        if st.button("🧠 음성 파일 분석 시작", type="primary", use_container_width=True):
            with st.spinner("🧠 음성을 분석하고 의학용어를 번역하는 중..."):
                try:
                    audio_bytes = uploaded_audio.read()
                    
                    if len(audio_bytes) == 0:
                        st.error("❌ 파일이 비어있습니다.")
                    else:
                        # OpenAI 클라이언트 체크
                        if not openai_client:
                            st.error("❌ OpenAI API 클라이언트가 초기화되지 않았습니다.")
                            st.info("앱을 재시작해주세요: Ctrl+C 후 `streamlit run message.py`")
                            st.stop()
                        
                        result_text = transcribe_and_translate_audio(audio_bytes)
                        if result_text and not result_text.startswith("❌"):
                            st.session_state.stt_result = result_text
                            st.session_state.voice_mode = False
                            st.success("✅ 음성 인식 완료!")
                            st.rerun()
                        else:
                            st.error(result_text)
                except Exception as e:
                    import traceback
                    st.error(f"❌ 파일 처리 오류: {str(e)}")
                    with st.expander("🐛 상세 에러 정보"):
                        st.code(traceback.format_exc())

# 결과 표시
if st.session_state.stt_result:
    st.markdown("### ✅ 음성 인식 결과:")
    st.markdown(f'<div class="stt-result-box">📝 {st.session_state.stt_result}</div>', unsafe_allow_html=True)
    st.caption("💡 이 정보는 참고용입니다. 아래에서 증상을 다시 선택할 수 있습니다.")
    
    # 💾 음성결과 저장 버튼
    if st.button("💾 음성결과 저장"):
        from datetime import datetime
        try:
            with open("stt_history.txt", "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {st.session_state.stt_result}\n")
            st.success("저장 완료!")
        except Exception as e:
            st.error(f"저장 오류: {str(e)}")
    
    # 🔊 TTS 음성으로 듣기 버튼
    if st.button("🔊 음성으로 듣기"):
        if openai_client:
            import io
            with st.spinner("TTS 변환 중..."):
                try:
                    response = openai_client.audio.speech.create(
                        model="tts-1",
                        input=st.session_state.stt_result,
                        voice="nova",  # nova, alloy, echo 등 선택 가능
                        response_format="mp3"
                    )
                    audio_bin = io.BytesIO(response.content)
                    st.audio(audio_bin, format="audio/mp3")
                except Exception as e:
                    st.error(f"TTS 변환 오류: {str(e)}")
        else:
            st.error("OpenAI API 키가 설정되지 않았습니다 (TTS 사용 불가)")

st.divider()

st.subheader("🩺 환자 증상 선택")
symptom = st.selectbox("지금 환자에게 가장 가까운 카테고리를 고르세요", list(SYMPTOM_RULES.keys()), index=0)

# 선택한 증상에 필요한 병상/장비 표시
rule = SYMPTOM_RULES.get(symptom, {})

# 필수 장비/시설 매핑
facility_names = {
    "hvctayn": "CT",
    "hvmriayn": "MRI",
    "hvangioayn": "조영촬영기",
    "hvventiayn": "인공호흡기",
    "hv10": "VENTI(소아)",
    "hv11": "인큐베이터",
}

bed_names = {
    "hvec": "응급실",
    "hvoc": "수술실",
    "hvicc": "일반중환자실",
    "hvncc": "신생중환자",
    "hvcc": "신경중환자",
    "hvccc": "흉부중환자",
    "hvgc": "입원실",
    "hv2": "내과중환자실",
    "hv3": "외과중환자실",
    "hv4": "외과입원실(정형외과)",
    "hv5": "신경과입원실",
    "hv6": "신경외과중환자실",
    "hv7": "약물중환자",
    "hv8": "화상중환자",
    "hv9": "외상중환자",
}

st.markdown(f"""
<div style="
    padding: 1rem; 
    border-left: 4px solid #0284c7; 
    background: #f0f9ff; 
    border-radius: 8px; 
    margin: 1rem 0;
">
    <p style="margin: 0.3rem 0; font-size: 1rem; color: #0c4a6e;"><b>📋 이 증상에 필요한 병원 시설:</b></p>
""", unsafe_allow_html=True)

# 필수 장비
required_facilities = [facility_names.get(k) for k, _ in rule.get("bool_any", []) if k in facility_names]
if required_facilities:
    st.markdown(f"<p style='margin: 0.3rem 0 0.3rem 1rem; font-size: 0.95rem;'>🔴 <b>필수 장비:</b> {', '.join(required_facilities)}</p>", unsafe_allow_html=True)

# 필수 병상
required_beds = [bed_names.get(k) for k, _ in rule.get("min_ge1", []) if k in bed_names]
if required_beds:
    st.markdown(f"<p style='margin: 0.3rem 0 0.3rem 1rem; font-size: 0.95rem;'>🔴 <b>필수 병상:</b> {', '.join(required_beds)}</p>", unsafe_allow_html=True)

# 권장 병상
nice_beds = [bed_names.get(k) for k, _ in rule.get("nice_to_have", []) if k in bed_names]
if nice_beds:
    st.markdown(f"<p style='margin: 0.3rem 0 0.3rem 1rem; font-size: 0.95rem;'>🟡 <b>권장 병상:</b> {', '.join(nice_beds)}</p>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

# 병원 조회 버튼
col_search, col_refresh = st.columns([3, 1])
with col_search:
    if st.button("🚨 근처 응급 병동 탐색 시작", type="primary", use_container_width=True, key="search_hospitals"):
        st.session_state.show_results = True
        st.session_state.reroll_count += 1
        st.session_state.hospital_approval_status = {}  # 승인 상태 초기화
        st.session_state.pending_approval = True
        st.session_state.top3_data = None  # 데이터 초기화
        st.session_state.route_paths_data = {}  # 경로 데이터 초기화
        st.session_state.backup_hospitals = None  # 백업 데이터 초기화
        st.session_state.auto_simulation_active = False  # 시뮬레이션 초기화
        st.session_state.current_hospital_index = 0
        st.session_state.simulation_stage = "ready"
        st.session_state.approved_hospital = None

with col_refresh:
    if st.session_state.show_results:
        if st.button("🔄 새로고침", use_container_width=True, key="refresh_hospitals"):
            st.session_state.reroll_count += 1
            st.session_state.hospital_approval_status = {}  # 승인 상태 초기화
            st.session_state.show_results = True
            st.session_state.pending_approval = True
            st.session_state.top3_data = None  # 데이터 초기화
            st.session_state.route_paths_data = {}  # 경로 데이터 초기화
            st.session_state.backup_hospitals = None  # 백업 데이터 초기화
            st.session_state.auto_simulation_active = False  # 시뮬레이션 초기화
            st.session_state.current_hospital_index = 0
            st.session_state.simulation_stage = "ready"
            st.session_state.approved_hospital = None

if st.session_state.show_results:
    # 데이터가 없거나 새로 조회해야 할 때만 조회
    if st.session_state.top3_data is None:
         if not DATA_GO_KR_KEY: st.error("DATA_GO_KR_SERVICE_KEY가 필요합니다."); st.stop()
    with st.spinner("병원 기본정보(좌표) 조회 중..."):
        hospitals = fetch_emergency_hospitals_in_region(sido, sigungu, DATA_GO_KR_KEY, max_items=200)
    if hospitals.empty: st.error("해당 행정구역의 응급 대상 병원을 찾지 못했습니다."); st.stop()

    with st.spinner("실시간 응급 병상/장비 조회 중..."):
        beds = fetch_er_beds(sido, sigungu, DATA_GO_KR_KEY, rows=500)

    all_merged = pd.merge(hospitals, beds, on="hpid", how="left", suffixes=("", "_bed"))
    if all_merged.empty: st.error("병원 기본정보와 병상 정보가 조인되지 않았습니다."); st.stop()

    rule = SYMPTOM_RULES.get(symptom, {})
    needed_cols = set([k for k,_ in rule.get("bool_any", [])] + [k for k,_ in rule.get("min_ge1", [])] +
                              ["dutytel3","hvdnm","dutyName","dutyAddr","hvec","hvoc","hvgc",
                               "hv1","hv2","hv3","hv4","hv5","hv6","hv7","hv8","hv9",
                               "hvicc","hvcc","hvncc","hvccc","hvidate"])
    for c in needed_cols:
        if c not in all_merged.columns: all_merged[c] = None

        # 거절된 병원 필터링
        if st.session_state.rejected_hospitals:
            all_merged = all_merged[~all_merged["hpid"].isin(st.session_state.rejected_hospitals)]
        
        # 거리 계산
        all_sorted = add_distance_km(all_merged, user_lat, user_lon)
        all_sorted["__fresh_m"] = all_sorted["hvidate"].map(lambda s: 0 if s else 9999)
        
        # 먼저 모든 병원에 대해 조건 만족 여부 체크
        all_sorted["_meets_conditions"] = all_sorted.apply(lambda r: meets_requirements(r, rule), axis=1)
        
        # 조건을 만족하는 병원만 필터링
        eligible_hospitals = all_sorted[all_sorted["_meets_conditions"] == True].copy()
        
        # 조건 만족 병원을 거리순 정렬
        eligible_hospitals = eligible_hospitals.sort_values(by=["distance_km", "__fresh_m"], ascending=[True, True])
        
        # 조건 만족 병원 전체를 백업으로 저장 (최대 10개)
        st.session_state.backup_hospitals = eligible_hospitals.head(10).copy()
        
        # 조건 만족 병원에서 상위 3개 선택 (거리 제한 없음)
        top3 = eligible_hospitals.head(3).copy()
        
        # 만약 조건 만족 병원이 3개 미만이면, 나머지는 가까운 병원으로 채우기
        if len(top3) < 3:
            remaining_count = 3 - len(top3)
            # 조건 미달 병원 중 가까운 순서로
            non_eligible = all_sorted[all_sorted["_meets_conditions"] == False].copy()
            non_eligible = non_eligible.sort_values(by=["distance_km", "__fresh_m"], ascending=[True, True])
            additional = non_eligible.head(remaining_count).copy()
            
            # 병합
            top3 = pd.concat([top3, additional], ignore_index=False)
        
        # session_state에 저장
        st.session_state.top3_data = top3
    else:
        # 저장된 데이터 사용
        top3 = st.session_state.top3_data
        rule = SYMPTOM_RULES.get(symptom, {})
    
    # 리롤 카운트 표시 (간단하게)
    st.caption(f"🔄 조회 횟수: {st.session_state.reroll_count}회 | 거절: {len(st.session_state.rejected_hospitals)}곳 | 조건 만족: {top3['_meets_conditions'].sum()}개")

    # 카카오 길찾기 API로 정확한 경로 및 소요 시간 계산
    def get_driving_info_kakao(origin_lat, origin_lon, dest_lat, dest_lon, kakao_key):
        """카카오 모빌리티 길찾기 API 호출 - 경로 좌표 포함"""
        if not kakao_key:
            return None, None, None
        
        url = "https://apis-navi.kakaomobility.com/v1/directions"
        headers = {"Authorization": f"KakaoAK {kakao_key}"}
        params = {
            "origin": f"{origin_lon},{origin_lat}",
            "destination": f"{dest_lon},{dest_lat}",
            "priority": "RECOMMEND",  # 추천 경로
        }
        
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                routes = data.get("routes", [])
                if routes:
                    route = routes[0]
                    summary = route.get("summary", {})
                    distance_m = summary.get("distance", 0)  # 미터
                    duration_sec = summary.get("duration", 0)  # 초
                    
                    distance_km = distance_m / 1000
                    duration_min = int(duration_sec / 60)
                    
                    # 실제 경로 좌표 추출
                    path_coords = []
                    sections = route.get("sections", [])
                    for section in sections:
                        roads = section.get("roads", [])
                        for road in roads:
                            for vertex in road.get("vertexes", []):
                                # vertexes는 [lon, lat, lon, lat, ...] 형식
                                pass
                            # 더 간단하게: section의 guides 사용
                        guides = section.get("guides", [])
                        for guide in guides:
                            x = guide.get("x")  # 경도
                            y = guide.get("y")  # 위도
                            if x and y:
                                path_coords.append([x, y])
                    
                    return distance_km, duration_min, path_coords
        except Exception as e:
            print(f"Kakao API error: {e}")
        
        return None, None, None
    
    # 각 병원에 대해 카카오 API로 경로 조회 (첫 조회 시에만)
    if not st.session_state.route_paths_data:
        route_paths = {}  # 병원별 실제 경로 좌표 저장
        
        if KAKAO_KEY:
            with st.spinner("🚗 실제 경로 및 소요 시간 계산 중..."):
                for idx in top3.index:
                    h_lat = top3.at[idx, "wgs84Lat"]
                    h_lon = top3.at[idx, "wgs84Lon"]
                    
                    if h_lat and h_lon:
                        real_dist, real_eta, path_coords = get_driving_info_kakao(user_lat, user_lon, h_lat, h_lon, KAKAO_KEY)
                        
                        if real_dist and real_eta:
                            top3.at[idx, "distance_km"] = real_dist
                            top3.at[idx, "eta_minutes"] = real_eta
                            if path_coords:
                                route_paths[idx] = path_coords  # 경로 저장
                        else:
                            # API 실패 시 기존 추정값 사용
                            if isinstance(top3.at[idx, "distance_km"], (float, int)):
                                dist = top3.at[idx, "distance_km"]
                                top3.at[idx, "eta_minutes"] = int((dist * 1.3 / 40) * 60)
        
        st.session_state.route_paths_data = route_paths
        st.session_state.top3_data = top3  # 업데이트된 데이터 저장
    else:
        route_paths = st.session_state.route_paths_data
        top3 = st.session_state.top3_data
    
    if "distance_km" in top3.columns:
        top3["distance_km"] = top3["distance_km"].map(lambda x: f"{x:.2f} km" if isinstance(x,(float,int)) else x)
    
    # hvidate 포맷 변환: "20250130141500" → "2025-01-30 14:15"
    def format_hvidate(date_str):
        if not date_str or str(date_str).strip() in ("", "None", "nan"): return "없음"
        s = str(date_str).strip()
        if len(s) >= 12:
            return f"{s[0:4]}-{s[4:6]}-{s[6:8]} {s[8:10]}:{s[10:12]}"
        return s
    
    if "hvidate" in top3.columns:
        top3["hvidate"] = top3["hvidate"].map(format_hvidate)
    
    # 당직의명 + 전화번호 결합
    def format_doctor_info(row):
        doc_name = row.get("hvdnm")
        tel = row.get("dutytel3")
        if doc_name and str(doc_name).strip() not in ("", "None", "nan", "없음"):
            doc_name = str(doc_name).strip()
            if tel and str(tel).strip() not in ("", "None", "nan", "없음"):
                tel = str(tel).strip()
                return f"{doc_name} (☎️ {tel})"
            return doc_name
        return "없음"
    
    if "hvdnm" in top3.columns:
        top3["당직의정보"] = top3.apply(format_doctor_info, axis=1)
    
    # None 값을 "없음"으로 일괄 변환
    def replace_none(val):
        if val is None or str(val).strip() in ("None", "nan", ""): return "없음"
        return val
    
    for col in top3.columns:
        if col not in ["distance_km", "hvidate", "당직의정보"]:  # 이미 처리된 컬럼 제외
            top3[col] = top3[col].map(replace_none)

    # 병원 스택에 현재 병원 추가 (중복 제외)
    current_hpids_in_stack = {h.get("hpid") for h in st.session_state.hospital_stack}
    for _, row in top3.iterrows():
        hpid = row.get("hpid")
        if hpid not in current_hpids_in_stack:
            st.session_state.hospital_stack.append(row.to_dict())
    
    # 자동 전화/시뮬레이션 버튼
    st.divider()
    col_auto_btn, col_sim_btn, col_stop_btn = st.columns([2, 2, 1])
    
    # ngrok URL 자동 감지 (start_service.sh에서 생성한 파일 읽기)
    if "ngrok_url" not in st.session_state:
        # .ngrok_url 파일에서 자동으로 읽기
        try:
            ngrok_url_file = os.path.join(os.path.dirname(__file__), ".ngrok_url")
            if os.path.exists(ngrok_url_file):
                with open(ngrok_url_file, "r") as f:
                    auto_ngrok_url = f.read().strip()
                    if auto_ngrok_url:
                        st.session_state.ngrok_url = auto_ngrok_url
                    else:
                        st.session_state.ngrok_url = ""
            else:
                st.session_state.ngrok_url = ""
        except Exception:
            st.session_state.ngrok_url = ""
    
    # ngrok URL 상태 표시 (시연용으로 숨김)
    
    # Twilio 자동 전화 버튼
    with col_auto_btn:
        if not st.session_state.twilio_auto_calling and not st.session_state.auto_simulation_active and twilio_client:
            if st.button("📞 Twilio 자동 전화", type="primary", use_container_width=True, key="start_twilio_call"):
                st.session_state.twilio_auto_calling = True
                st.session_state.current_hospital_index = 0
                st.rerun()
        elif not twilio_client:
            st.warning("⚠️ Twilio 미설정")
    
    # Twilio 무료 계정 안내 (시연용으로 숨김)
    
    # 시뮬레이션 버튼
    with col_sim_btn:
        if not st.session_state.auto_simulation_active:
            if st.button("🤖 자동 시뮬레이션", use_container_width=True, key="start_auto_sim"):
                st.session_state.auto_simulation_active = True
                st.session_state.current_hospital_index = 0
                st.session_state.simulation_stage = "calling"
                import time
                st.session_state.simulation_start_time = time.time()
                st.rerun()
    
    with col_stop_btn:
        if st.session_state.auto_simulation_active or st.session_state.twilio_auto_calling:
            if st.button("⏹️ 중지", use_container_width=True, key="stop_auto_sim"):
                st.session_state.auto_simulation_active = False
                st.session_state.twilio_auto_calling = False
                st.session_state.simulation_stage = "ready"
                st.rerun()
    
    # 자동 시뮬레이션 로직
    if st.session_state.auto_simulation_active and st.session_state.approved_hospital is None:
        import time
        import random
        
        top3_list = top3.to_dict('records')
        
        if st.session_state.current_hospital_index < len(top3_list):
            current_hospital = top3_list[st.session_state.current_hospital_index]
            hospital_id = current_hospital.get("hpid")
            hospital_name = current_hospital.get("dutyName")
            
            elapsed_time = time.time() - st.session_state.simulation_start_time
            
            # 단계별 진행
            if st.session_state.simulation_stage == "calling":
                st.info(f"📞 [{st.session_state.current_hospital_index + 1}번째 병원] {hospital_name}에 전화 거는 중...")
                
                if elapsed_time >= 3:  # 3초 후
                    st.session_state.simulation_stage = "deciding"
                    st.session_state.simulation_start_time = time.time()
                    time.sleep(0.1)
                    st.rerun()
                else:
                    time.sleep(0.5)
                    st.rerun()
            
            elif st.session_state.simulation_stage == "deciding":
                # 70% 확률로 거절, 30% 확률로 승인
                if random.random() < 0.3:
                    # 승인
                    st.success(f"✅ {hospital_name} 승인! 입실 가능합니다.")
                    st.session_state.hospital_approval_status[hospital_id] = "approved"
                    st.session_state.approved_hospital = {
                        "name": current_hospital.get("dutyName"),
                        "lat": current_hospital.get("wgs84Lat"),
                        "lon": current_hospital.get("wgs84Lon"),
                        "addr": current_hospital.get("dutyAddr"),
                        "tel": current_hospital.get("dutytel3")
                    }
                    st.session_state.auto_simulation_active = False
                    st.session_state.pending_approval = False
                    time.sleep(2)
                    st.rerun()
                else:
                    # 거절
                    st.warning(f"❌ {hospital_name} 통화 불가 (병상 부족/전화 미수신), 다음 병원 시도 중...")
                    st.session_state.hospital_approval_status[hospital_id] = "rejected"
                    st.session_state.rejected_hospitals.add(hospital_id)
                    st.session_state.current_hospital_index += 1
                    st.session_state.simulation_stage = "calling"
                    st.session_state.simulation_start_time = time.time()
                    
                    # 다음 병원이 없으면 백업에서 가져오기
                    if st.session_state.current_hospital_index >= len(top3_list):
                        if st.session_state.backup_hospitals is not None:
                            backup = st.session_state.backup_hospitals
                            current_hpids = set(top3["hpid"].tolist())
                            available_backup = backup[~backup["hpid"].isin(st.session_state.rejected_hospitals)]
                            available_backup = available_backup[~available_backup["hpid"].isin(current_hpids)]
                            
                            if len(available_backup) >= 1:
                                new_hospital = available_backup.head(1).copy()
                                st.session_state.top3_data = pd.concat([st.session_state.top3_data, new_hospital], ignore_index=False)
                                st.session_state.hospital_stack.append(new_hospital.iloc[0].to_dict())
                    
                    time.sleep(2)
                    st.rerun()
        else:
            st.error("❌ 모든 병원이 거절했습니다. 다른 지역을 검색하세요.")
            st.session_state.auto_simulation_active = False
    
    # Twilio 자동 전화 로직
    if st.session_state.twilio_auto_calling and st.session_state.approved_hospital is None and twilio_client:
        import time
        
        # Flask 서버는 start_service.sh로 별도 실행됨
        # ngrok URL이 설정되어 있는지 확인
        if not st.session_state.ngrok_url:
            st.error("❌ ngrok URL이 설정되지 않았습니다. 'Twilio 다이얼 입력 설정'에서 URL을 입력하세요.")
            st.session_state.twilio_auto_calling = False
            st.stop()
        
        top3_list = top3.to_dict('records')
        
        if st.session_state.current_hospital_index < len(top3_list):
            current_hospital = top3_list[st.session_state.current_hospital_index]
            hospital_id = current_hospital.get("hpid")
            hospital_name = current_hospital.get("dutyName")
            hospital_tel = current_hospital.get("dutytel3", DEMO_PHONE_NUMBERS[0])  # 기본값: 첫 번째 시연 번호
            
            # 아직 전화를 걸지 않았다면
            if hospital_id not in st.session_state.active_calls:
                st.info(f"📞 [{st.session_state.current_hospital_index + 1}번째 병원] {hospital_name}에 전화 거는 중...")
                
                # STT 결과 가져오기 (환자 정보)
                patient_info = st.session_state.get("stt_result", None)
                
                # 콜백 URL 설정 (ngrok URL 사용)
                callback_url = None
                if st.session_state.ngrok_url:
                    # ngrok URL이 있으면 콜백 경로 추가
                    base_url = st.session_state.ngrok_url.rstrip('/')
                    callback_url = f"{base_url}/twilio/gather"
                
                # Twilio로 전화 걸기 (STT 텍스트 + Gather 콜백 포함)
                # 🔴 디버깅: 실제 전화번호 강제 설정 (시연용)
                # 병원 인덱스에 따라 다른 전화번호 사용 (순환)
                phone_index = st.session_state.current_hospital_index % len(DEMO_PHONE_NUMBERS)
                actual_phone = DEMO_PHONE_NUMBERS[phone_index]
                
                st.warning(f"🔍 디버깅: [{phone_index + 1}번 병원] {hospital_name} ({hospital_tel}) → 시연번호 {actual_phone}로 전화 시도")
                
                call_result = make_call_to_hospital(actual_phone, hospital_name, patient_info, callback_url)
                
                # 🔴 상세 디버깅 정보 표시
                with st.expander("🐛 Twilio 호출 상세 정보", expanded=True):
                    st.json(call_result)
                
                if call_result and call_result.get("status") == "success":
                    call_sid = call_result["call_sid"]
                    st.session_state.active_calls[hospital_id] = {
                        "call_sid": call_sid,
                        "start_time": time.time(),
                        "hospital_name": hospital_name
                    }
                    st.success(f"✅ {hospital_name}에 전화 연결!")
                    st.info(f"📞 수신 번호: {call_result.get('to')}")
                    st.info(f"📞 Call SID: {call_sid}")
                    st.info(f"📞 상태: {call_result.get('call_status')}")
                    
                    # 환자 정보가 전달되었는지 표시
                    if call_result.get("patient_info"):
                        st.info(f"📋 환자 정보: {call_result['patient_info']}")
                    
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error(f"❌ {hospital_name} 전화 연결 실패!")
                    st.error(f"🔴 에러: {call_result.get('message', '알 수 없는 오류')}")
                    st.session_state.hospital_approval_status[hospital_id] = "rejected"
                    st.session_state.rejected_hospitals.add(hospital_id)
                    st.session_state.current_hospital_index += 1
                    time.sleep(1)
                    st.rerun()
            else:
                # 전화 상태 확인
                call_info = st.session_state.active_calls[hospital_id]
                call_sid = call_info["call_sid"]
                elapsed = time.time() - call_info["start_time"]
                
                # 🔹 Flask 서버에서 다이얼 입력 확인
                call_response = get_call_response(call_sid)
                if call_response:
                    digit = call_response.get("digit")
                    
                    if digit == "1":
                        # ✅ 1번 누름 → 입실 승인
                        st.success(f"✅ {hospital_name} 승인! (다이얼 1번 입력됨)")
                        st.session_state.hospital_approval_status[hospital_id] = "approved"
                        st.session_state.approved_hospital = {
                            "name": hospital_name,
                            "lat": current_hospital.get("wgs84Lat"),
                            "lon": current_hospital.get("wgs84Lon"),
                            "addr": current_hospital.get("dutyAddr"),
                            "tel": hospital_tel
                        }
                        st.session_state.twilio_auto_calling = False
                        st.session_state.pending_approval = False
                        
                        time.sleep(2)
                        st.rerun()
                        
                    elif digit == "2":
                        # ❌ 2번 누름 → 입실 거절, 다음 병원으로
                        st.warning(f"❌ {hospital_name} 입실 불가 (다이얼 2번 입력됨), 다음 병원 시도 중...")
                        st.session_state.hospital_approval_status[hospital_id] = "rejected"
                        st.session_state.rejected_hospitals.add(hospital_id)
                        st.session_state.current_hospital_index += 1
                        
                        time.sleep(2)
                        st.rerun()
                    else:
                        # 잘못된 입력 → 다음 병원으로
                        st.warning(f"⚠️ {hospital_name} 잘못된 입력 ({digit}), 다음 병원 시도 중...")
                        st.session_state.hospital_approval_status[hospital_id] = "rejected"
                        st.session_state.rejected_hospitals.add(hospital_id)
                        st.session_state.current_hospital_index += 1
                        
                        time.sleep(2)
                        st.rerun()
                
                # 통화 연결 대기: 30초까지 대기
                # 다이얼 입력 대기: 전화 연결 후 60초(1분)까지 대기
                # 총 최대 대기: 90초 (30초 연결 + 60초 입력)
                elif elapsed < 90:
                    call_status = check_call_status(call_sid)
                    
                    # 통화 연결 단계 (0~30초)
                    if elapsed < 30:
                        if call_status in ["queued", "ringing"]:
                            st.info(f"📞 {hospital_name} 전화 연결 중... ({int(elapsed)}초 경과)")
                            st.caption("🔔 벨이 울리는 중입니다...")
                        elif call_status in ["in-progress", "answered"]:
                            st.info(f"📞 {hospital_name} 통화 연결됨! 다이얼 입력 대기 중... ({int(elapsed)}초 경과)")
                            st.caption("💬 \"진료 가능하면 1번, 불가능하면 2번을 눌러주세요\" 안내 중")
                        elif call_status in ["busy", "failed", "no-answer"]:
                            # 30초 이내에 연결 실패 → 즉시 거절
                            st.warning(f"❌ {hospital_name} 전화 연결 실패 ({call_status}), 다음 병원 시도 중...")
                            st.session_state.hospital_approval_status[hospital_id] = "rejected"
                            st.session_state.rejected_hospitals.add(hospital_id)
                            st.session_state.current_hospital_index += 1
                            time.sleep(2)
                            st.rerun()
                        elif call_status == "completed":
                            # 입력 없이 끊김
                            st.warning(f"❌ {hospital_name} 다이얼 입력 없이 통화 종료, 다음 병원 시도 중...")
                            st.session_state.hospital_approval_status[hospital_id] = "rejected"
                            st.session_state.rejected_hospitals.add(hospital_id)
                            st.session_state.current_hospital_index += 1
                            time.sleep(2)
                            st.rerun()
                    # 다이얼 입력 대기 단계 (30~90초)
                    else:
                        if call_status in ["in-progress", "answered"]:
                            st.info(f"📞 {hospital_name} 다이얼 입력 대기 중... ({int(elapsed)}초 경과)")
                            st.caption("💬 \"진료 가능하면 1번, 불가능하면 2번을 눌러주세요\"")
                        elif call_status == "completed":
                            # 입력 없이 끊김
                            st.warning(f"❌ {hospital_name} 다이얼 입력 없이 통화 종료, 다음 병원 시도 중...")
                            st.session_state.hospital_approval_status[hospital_id] = "rejected"
                            st.session_state.rejected_hospitals.add(hospital_id)
                            st.session_state.current_hospital_index += 1
                            time.sleep(2)
                            st.rerun()
                        elif call_status in ["busy", "failed", "no-answer", "canceled"]:
                            st.warning(f"❌ {hospital_name} 통화 종료 ({call_status}), 다음 병원 시도 중...")
                            st.session_state.hospital_approval_status[hospital_id] = "rejected"
                            st.session_state.rejected_hospitals.add(hospital_id)
                            st.session_state.current_hospital_index += 1
                            time.sleep(2)
                            st.rerun()
                    
                    # 계속 대기
                    time.sleep(1)
                    st.rerun()
                else:
                    # 90초 타임아웃 (30초 연결 대기 + 60초 입력 대기)
                    call_status = check_call_status(call_sid)
                    if call_status in ["queued", "ringing"]:
                        # 30초 동안 전화를 안 받음
                        st.warning(f"⏱️ {hospital_name} 응답 없음 (30초 타임아웃), 다음 병원 시도 중...")
                    else:
                        # 전화는 받았지만 1분 동안 다이얼 입력 없음
                        st.warning(f"⏱️ {hospital_name} 다이얼 입력 없음 (1분 타임아웃), 다음 병원 시도 중...")
                    
                    st.session_state.hospital_approval_status[hospital_id] = "rejected"
                    st.session_state.rejected_hospitals.add(hospital_id)
                    st.session_state.current_hospital_index += 1
                    time.sleep(1)
                    st.rerun()
        else:
            st.error("❌ 모든 병원에 전화를 시도했습니다.")
            st.session_state.twilio_auto_calling = False
    
    st.divider()
    st.subheader("🏆 병원 입실 요청 현황")
    st.caption(f"총 {len(st.session_state.hospital_stack)}곳에 요청 | 거절: {len(st.session_state.rejected_hospitals)}곳")
    
    # 스택에 있는 모든 병원 표시 (최신순)
    for stack_idx, row in enumerate(reversed(st.session_state.hospital_stack), 1):
        hospital_id = row.get("hpid")
        meets_cond = row.get("_meets_conditions", False)
        
        # 현재 병원의 승인 상태 확인
        approval_status = st.session_state.hospital_approval_status.get(hospital_id, "pending")
        is_rejected = hospital_id in st.session_state.rejected_hospitals
        
        with st.container():
            # 헤더 박스 - 거절된 병원은 더 어둡게 표시
            eta = row.get('eta_minutes', 0)
            eta_text = f"약 {eta}분" if eta else "계산 중"
            
            # 승인/거절 상태에 따라 스타일 변경
            if approval_status == "approved":
                border_color = "#10b981"
                bg_gradient = "linear-gradient(to right, #d1fae5, #a7f3d0)"
                text_color = "#065f46"
                status_badge = '<span style="background: #10b981; color: white; padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.9rem; margin-left: 1rem;">✅ 승낙됨</span>'
                card_opacity = "1.0"
            elif is_rejected:
                border_color = "#6b7280"
                bg_gradient = "linear-gradient(to right, #f3f4f6, #e5e7eb)"
                text_color = "#4b5563"
                status_badge = '<span style="background: #ef4444; color: white; padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.9rem; margin-left: 1rem;">❌ 거절됨</span>'
                card_opacity = "0.5"
            elif meets_cond:
                # 조건 만족 + 대기 중
                border_color = "#0284c7"
                bg_gradient = "linear-gradient(to right, #f0f9ff, #e0f2fe)"
                text_color = "#0c4a6e"
                status_badge = '<span style="background: #fbbf24; color: white; padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.9rem; margin-left: 1rem;">⏳ 대기중</span>'
                card_opacity = "1.0"
            else:
                # 조건 미달 + 대기 중
                border_color = "#9ca3af"
                bg_gradient = "linear-gradient(to right, #f3f4f6, #e5e7eb)"
                text_color = "#6b7280"
                status_badge = '<span style="background: #ef4444; color: white; padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.9rem; margin-left: 1rem;">⚠️ 필수 병상 없음</span>'
                card_opacity = "0.7"
            
            st.markdown(f"""
            <div style="padding: 1.5rem; border: 3px solid {border_color}; border-radius: 12px; margin-bottom: 0.5rem; background: {bg_gradient}; box-shadow: 0 4px 8px rgba(0,0,0,0.1); opacity: {card_opacity};">
                <h2 style="color: {text_color}; margin: 0 0 1rem 0; font-size: 1.8rem;">🏥 #{stack_idx}: {row.get('dutyName')}{status_badge}</h2>
                <p style="margin: 0.5rem 0; font-size: 1.3rem; color: {text_color};"><b>📍 거리:</b> <span style="color: {'#dc2626' if meets_cond else '#9ca3af'}; font-weight: bold;">{row.get('distance_km')}</span></p>
                <p style="margin: 0.5rem 0; font-size: 1.1rem; color: {text_color};"><b>🚗 예상 소요시간:</b> <span style="color: {'#ea580c' if meets_cond else '#9ca3af'}; font-weight: bold;">{eta_text}</span> <span style="font-size: 0.9rem; color: #64748b;">(자가용 기준)</span></p>
                <p style="margin: 0.5rem 0; font-size: 1.15rem; color: {text_color};"><b>🏠 주소:</b> {row.get('dutyAddr')}</p>
            </div>
            """, unsafe_allow_html=True)
            
            # 병상 정보 - 선택한 증상에 필요한 것만 표시
            if meets_cond:
                st.markdown("### ✅ 이용 가능한 병상:")
            else:
                st.markdown("### ⚠️ 병상 정보 (필수 조건 미달):")
            
            # 전체 병상 정보 매핑
            all_bed_mapping = {
                "hvec": ("🚨 응급실", row.get("hvec", "없음")),
                "hvoc": ("🏥 수술실", row.get("hvoc", "없음")),
                "hvgc": ("🏨 입원실", row.get("hvgc", "없음")),
                "hv2": ("💊 내과중환자실", row.get("hv2", "없음")),
                "hv3": ("🔪 외과중환자실", row.get("hv3", "없음")),
                "hv4": ("🦴 외과입원실(정형외과)", row.get("hv4", "없음")),
                "hv5": ("🧠 신경과입원실", row.get("hv5", "없음")),
                "hv6": ("🧠 신경외과중환자실", row.get("hv6", "없음")),
                "hvicc": ("⚕️ 일반중환자실", row.get("hvicc", "없음")),
                "hvcc": ("🧠 신경중환자", row.get("hvcc", "없음")),
                "hvncc": ("👶 신생중환자", row.get("hvncc", "없음")),
                "hvccc": ("🫁 흉부중환자", row.get("hvccc", "없음")),
                "hv7": ("💉 약물중환자", row.get("hv7", "없음")),
                "hv8": ("🔥 화상중환자", row.get("hv8", "없음")),
                "hv9": ("🚑 외상중환자", row.get("hv9", "없음")),
            }
            
            # 선택한 증상에 필요한 병상만 필터링
            needed_beds = set()
            for key, _ in rule.get("min_ge1", []):
                if key in all_bed_mapping:
                    needed_beds.add(key)
            for key, _ in rule.get("nice_to_have", []):
                if key in all_bed_mapping:
                    needed_beds.add(key)
            
            # 필요한 병상만 표시
            bed_items = [all_bed_mapping[key] for key in needed_beds if key in all_bed_mapping]
            
            # 있는 병상만 표시
            available = [(name, val) for name, val in bed_items if str(val) != "없음" and val]
            unavailable = [name for name, val in bed_items if str(val) == "없음" or not val]
            
            if available:
                cols = st.columns(min(len(available), 4))
                for i, (name, value) in enumerate(available):
                    with cols[i % 4]:
                        # Y/N 값은 "있음"으로, 숫자는 "N개"로 표시
                        if str(value).strip().upper() in ("Y", "N"):
                            display_value = "있음" if str(value).strip().upper() == "Y" else "없음"
                        else:
                            try:
                                num = int(value)
                                display_value = f"{num}개"
                            except:
                                display_value = str(value)
                        st.metric(name, display_value, delta=None)
            else:
                st.warning("⚠️ 현재 가용 병상 정보 없음")
            
            if unavailable:
                st.caption(f"미보유: {', '.join(unavailable)}")
            
            # 전화번호와 승인 상태
            col_phone, col_approval = st.columns([3, 2])
            with col_phone:
                tel = row.get("dutytel3")
                if tel and str(tel).strip() not in ("없음", "None", "nan", ""):
                    tel_clean = str(tel).strip()
                    # 발표용: 실제 연결은 010-2994-5413으로
                    demo_phone = "010-2994-5413"
                    st.markdown(f"""
                    <a href="tel:{demo_phone}" style="text-decoration: none;">
                        <button style="
                            background: #dc2626; 
                            color: white; 
                            padding: 1.2rem 2rem; 
                            border: none; 
                            border-radius: 10px; 
                            font-size: 1.3rem; 
                            font-weight: bold; 
                            cursor: pointer;
                            width: 100%;
                            box-shadow: 0 4px 8px rgba(220,38,38,0.3);
                            transition: all 0.3s;
                        " onmouseover="this.style.background='#b91c1c'" onmouseout="this.style.background='#dc2626'">
                            📞 응급실 바로 전화: {tel_clean}
                        </button>
                    </a>
                    """, unsafe_allow_html=True)
                    
                    # ARS 직통 버튼 (당직의 직통 연락처가 있는 경우)
                    direct_tel = row.get("hv1")  # 응급실 당직의 직통연락처
                    if direct_tel and str(direct_tel).strip() not in ("없음", "None", "nan", ""):
                        direct_tel_clean = str(direct_tel).strip()
                        st.markdown(f"""
                        <a href="tel:{demo_phone}" style="text-decoration: none;">
                            <button style="
                                background: #ea580c; 
                                color: white; 
                                padding: 0.8rem 1.5rem; 
                                border: none; 
                                border-radius: 8px; 
                                font-size: 1rem; 
                                font-weight: bold; 
                                cursor: pointer;
                                width: 100%;
                                margin-top: 0.5rem;
                                box-shadow: 0 2px 4px rgba(234,88,12,0.3);
                            " onmouseover="this.style.background='#c2410c'" onmouseout="this.style.background='#ea580c'">
                                📱 당직의 직통: 있음
                            </button>
                        </a>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div style="
                            background: #94a3b8; 
                            color: white; 
                            padding: 0.8rem 1.5rem; 
                            border-radius: 8px; 
                            font-size: 1rem; 
                            font-weight: bold; 
                            text-align: center;
                            width: 100%;
                            margin-top: 0.5rem;
                            opacity: 0.7;
                        ">
                            📱 당직의 직통: 없음
                        </div>
                        """, unsafe_allow_html=True)
                        st.caption("💡 연결 후 ARS 안내에 따라 응급실로 연결하세요")
                else:
                    st.info("📞 응급실 전화번호 정보 없음")
                
                # 당직의 정보 - 이름과 전화번호 분리 표시
                doc_name = row.get("hvdnm")
                doc_tel = row.get("hv1")
                
                if doc_name and str(doc_name).strip() not in ("없음", "None", "nan", ""):
                    doc_name_clean = str(doc_name).strip()
                    if doc_tel and str(doc_tel).strip() not in ("없음", "None", "nan", ""):
                        doc_tel_clean = str(doc_tel).strip()
                        st.markdown(f"""
                        <p style='font-size: 1.1rem; margin-top: 0.8rem;'>
                            👨‍⚕️ <b>당직의:</b> {doc_name_clean}<br/>
                            <span style='margin-left: 2rem; color: #0284c7;'>☎️ {doc_tel_clean}</span>
                        </p>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"<p style='font-size: 1.1rem; margin-top: 0.8rem;'>👨‍⚕️ <b>당직의:</b> {doc_name_clean}</p>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<p style='font-size: 1.1rem; margin-top: 0.8rem;'>👨‍⚕️ <b>당직의:</b> 없음</p>", unsafe_allow_html=True)
                
                # 병상정보 업데이트 시간
                update_time = row.get("hvidate", "없음")
                st.caption(f"🕐 병상정보 업데이트: {update_time}")
            
            # 병원 승인 상태 표시 (우측 컬럼)
            with col_approval:
                # Pending 상태 처리 - 전화하기 버튼 표시
                in_current_top3 = hospital_id in [r.get("hpid") for _, r in top3.iterrows()] if 'top3' in locals() else False
                
                # 통화 중 상태 체크
                calling_status = st.session_state.hospital_approval_status.get(hospital_id)
                
                if calling_status == "calling":
                    # 통화 중 - 승낙/거절 버튼 표시
                    st.markdown("""
                    <div style="background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%); 
                                color: white; 
                                padding: 1rem; 
                                border-radius: 10px; 
                                text-align: center;
                                margin-bottom: 0.5rem;">
                        <h3 style="margin: 0; font-size: 1.2rem;">📞 통화중</h3>
                        <p style="margin: 0.3rem 0 0 0; font-size: 0.85rem;">통화 후 결과 입력</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col_accept, col_reject = st.columns(2)
                    with col_accept:
                        if st.button("✅ 승낙", key=f"accept_{hospital_id}", use_container_width=True, type="primary"):
                            st.session_state.hospital_approval_status[hospital_id] = "approved"
                            # 승인된 병원 정보 저장
                            st.session_state.approved_hospital = {
                                "name": row.get("dutyName"),
                                "lat": row.get("wgs84Lat"),
                                "lon": row.get("wgs84Lon"),
                                "addr": row.get("dutyAddr"),
                                "tel": row.get("dutytel3")
                            }
                            st.session_state.pending_approval = False
                            st.rerun()
                    
                    with col_reject:
                        if st.button("❌ 거절", key=f"reject_{hospital_id}", use_container_width=True):
                            st.session_state.hospital_approval_status[hospital_id] = "rejected"
                            st.session_state.rejected_hospitals.add(hospital_id)
                            st.session_state.rejection_log.append(f"❌ {row.get('dutyName')} - 전화 거절 (통화 불가)")
                            
                            # 다음 병원 자동 조회
                            if st.session_state.backup_hospitals is not None:
                                backup = st.session_state.backup_hospitals
                                current_hpids = set(top3["hpid"].tolist())
                                available_backup = backup[~backup["hpid"].isin(st.session_state.rejected_hospitals)]
                                available_backup = available_backup[~available_backup["hpid"].isin(current_hpids)]
                                
                                if len(available_backup) >= 1:
                                    approved_hospitals = top3[~top3["hpid"].isin(st.session_state.rejected_hospitals)].copy()
                                    new_hospitals = available_backup.head(1).copy()
                                    top3_updated = pd.concat([approved_hospitals, new_hospitals], ignore_index=False)
                                    st.session_state.top3_data = top3_updated
                            
                            st.rerun()
                
                else:
                    # 승인/거절 결과 표시
                    approval_status = st.session_state.hospital_approval_status.get(hospital_id)
                    
                    if approval_status == "approved":
                        st.markdown("""
                        <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); 
                                    color: white; 
                                    padding: 2rem 1rem; 
                                    border-radius: 10px; 
                                    text-align: center;
                                    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
                                    height: 100%;">
                            <h3 style="margin: 0; font-size: 1.5rem;">✅ 승낙됨</h3>
                        </div>
                        """, unsafe_allow_html=True)
                    elif approval_status == "rejected":
                        st.markdown("""
                        <div style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); 
                                    color: white; 
                                    padding: 2rem 1rem; 
                                    border-radius: 10px; 
                                    text-align: center;
                                    box-shadow: 0 4px 12px rgba(239, 68, 68, 0.4);
                                    height: 100%;">
                            <h3 style="margin: 0; font-size: 1.5rem;">❌ 거절됨</h3>
                            <p style="margin: 0.5rem 0 0 0; font-size: 0.9rem;">병원 거절</p>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        # 승인 상태가 없는 경우 (초기 상태)
                        st.info("대기중")
            
            st.markdown("---")

    st.subheader("🗺️ 지도")
    
    # 순위별 색상
    rank_colors = [
        [220, 38, 38],    # 1위: 빨강
        [234, 88, 12],    # 2위: 주황
        [250, 204, 21],   # 3위: 노랑
    ]
    
    # 사용자 위치 (파란색)
    user_layer = pdk.Layer(
        "ScatterplotLayer",
        data=[{"lat": user_lat, "lon": user_lon, "color": [37, 99, 235]}],
        get_position="[lon, lat]",
        get_fill_color="color",
        get_radius=50,  # 크기 줄임
        pickable=False
    )
    
    # 사용자 위치 텍스트 레이어
    user_text_layer = pdk.Layer(
        "TextLayer",
        data=[{"lat": user_lat, "lon": user_lon, "text": "현위치", "bg": [37, 99, 235, 220]}],
        get_position="[lon, lat]",
        get_text="text",
        get_size=20,
        get_color=[255, 255, 255],  # 흰색 텍스트
        get_angle=0,
        get_text_anchor='"middle"',
        get_alignment_baseline='"bottom"',
        get_pixel_offset=[0, -30],
        background=True,
        get_background_color="bg",
        background_padding=[10, 6, 10, 6]
    )
    
    # 병원 마커 & 경로선 데이터
    marker_data = []
    path_data = []  # 실제 도로 경로용
    text_data = []  # 텍스트 레이블용
    
    for idx, (row_idx, r) in enumerate(top3.iterrows()):
        try:
            h_lat = float(r["wgs84Lat"])
            h_lon = float(r["wgs84Lon"])
            meets_cond = r.get("_meets_conditions", False)
            
            # 조건 미달 시 회색, 조건 만족 시 순위별 색상
            if meets_cond:
                color = rank_colors[idx] if idx < 3 else [100, 100, 100]
            else:
                color = [156, 163, 175]  # 회색
            
            # 병원 마커
            eta = r.get("eta_minutes", 0)
            eta_text = f"약 {eta}분" if eta else "계산 중"
            hospital_name = r.get("dutyName", "")
            
            marker_data.append({
                "lat": h_lat,
                "lon": h_lon,
                "name": hospital_name,
                "addr": r.get("dutyAddr"),
                "dist": r.get("distance_km"),
                "eta": eta_text,
                "color": color,
                "rank": idx + 1
            })
            
            # 병원 이름 텍스트 레이블
            if meets_cond:
                rank_emoji = ["🥇", "🥈", "🥉"][idx]
                label_text = f"{hospital_name[:10]}"  # 이름 길이 제한
                text_bg_color = color + [220]
            else:
                label_text = f"{hospital_name[:10]}"
                text_bg_color = [156, 163, 175, 220]  # 회색
            
            text_data.append({
                "lat": h_lat,
                "lon": h_lon,
                "text": label_text,
                "bg": text_bg_color
            })
            
            # 실제 경로가 있으면 사용, 없으면 직선
            if row_idx in route_paths and route_paths[row_idx]:
                # 실제 도로 경로 좌표를 PathLayer용으로 변환
                path_coords = [[coord[0], coord[1]] for coord in route_paths[row_idx]]
                # 시작점 추가
                full_path = [[user_lon, user_lat]] + path_coords + [[h_lon, h_lat]]
                
                path_data.append({
                    "path": full_path,
                    "color": color + [200],  # 투명도
                    "width": 5
                })
            else:
                # API 실패 시 직선 경로 (대체)
                path_data.append({
                    "path": [[user_lon, user_lat], [h_lon, h_lat]],
                    "color": color + [150],
                    "width": 3
                })
        except Exception as e:
            print(f"Map data error: {e}")
            continue
    
    # 실제 경로 레이어 (PathLayer 사용)
    path_layer = pdk.Layer(
        "PathLayer",
        data=path_data,
        get_path="path",
        get_color="color",
        get_width="width",
        width_min_pixels=2,
        pickable=False
    )
    
    # 병원 마커 레이어
    hospital_layer = pdk.Layer(
        "ScatterplotLayer",
        data=marker_data,
        get_position="[lon, lat]",
        get_fill_color="color",
        get_radius=60,  # 크기 줄임
        pickable=True
    )
    
    # 병원 이름 텍스트 레이어
    hospital_text_layer = pdk.Layer(
        "TextLayer",
        data=text_data,
        get_position="[lon, lat]",
        get_text="text",
        get_size=18,
        get_color=[255, 255, 255],  # 흰색 텍스트
        get_angle=0,
        get_text_anchor='"middle"',
        get_alignment_baseline='"bottom"',
        get_pixel_offset=[0, -30],
        background=True,
        get_background_color="bg",  # 각 병원별 색상 배경
        background_padding=[10, 6, 10, 6]
    )
    
    tooltip = {
        "html": "<b>🏥 {rank}위: {name}</b><br/>📍 {dist}<br/>🚗 {eta} (자가용)<br/>🏠 {addr}",
        "style": {"backgroundColor": "rgba(0,0,0,0.8)", "color": "white", "fontSize": "14px", "padding": "10px"}
    }
    
    # 지도 중심 계산
    mid_lat, mid_lon = (user_lat, user_lon)
    if marker_data:
        avg_lat = sum(m["lat"] for m in marker_data) / len(marker_data)
        avg_lon = sum(m["lon"] for m in marker_data) / len(marker_data)
        mid_lat = (user_lat + avg_lat) / 2
        mid_lon = (user_lon + avg_lon) / 2
    
    st.pydeck_chart(pdk.Deck(
        map_style=None,  # 기본 OpenStreetMap 스타일 (API 키 불필요)
        initial_view_state=pdk.ViewState(
            latitude=mid_lat,
            longitude=mid_lon,
            zoom=11.5,
            pitch=0
        ),
        layers=[path_layer, user_layer, hospital_layer, user_text_layer, hospital_text_layer],  # 텍스트 레이어 추가
        tooltip=tooltip
    ))
    
    # 범례
    st.markdown("""
    <div style="display: flex; gap: 1rem; margin-top: 0.5rem; font-size: 0.9rem; flex-wrap: wrap;">
        <span>🔵 내 위치</span>
        <span style="color: #dc2626;">🔴 1위 (조건 만족)</span>
        <span style="color: #ea580c;">🟠 2위 (조건 만족)</span>
        <span style="color: #facc15;">🟡 3위 (조건 만족)</span>
        <span style="color: #9ca3af;">⚪ 필수 병상 없음</span>
    </div>
    """, unsafe_allow_html=True)
    
    st.success("조회 완료!")

