#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STT (Speech-to-Text) 관련 라우트 - SBAR 변환 및 ARS 자연어 변환 포함"""

from flask import request, jsonify
import tempfile
import os
import datetime
from models import db, EmergencyRequest


def register_stt_routes(app, openai_client):
    """STT 라우트 등록"""
    
    @app.route('/api/stt/transcribe', methods=['POST'])
    def api_stt_transcribe():
        """음성을 텍스트로 변환하고 의학용어를 번역한 후 SBAR 형식으로 변환하는 API"""
        print(f"[STT] 요청 받음: Content-Type={request.content_type}, Files={list(request.files.keys())}")
        
        if not openai_client:
            print("[STT] OpenAI 클라이언트가 초기화되지 않음")
            return jsonify({"error": "OpenAI 클라이언트가 초기화되지 않았습니다. API 키를 확인하세요."}), 500
        
        tmp_file_path = None
        try:
            # 파일 업로드 확인
            if 'audio' not in request.files:
                print("[STT] 'audio' 파일이 요청에 없음")
                return jsonify({"error": "audio 파일이 필요합니다."}), 400
            
            audio_file = request.files['audio']
            if audio_file.filename == '':
                print("[STT] 파일명이 비어있음")
                return jsonify({"error": "파일이 선택되지 않았습니다."}), 400
            
            print(f"[STT] 파일명: {audio_file.filename}, Content-Type: {audio_file.content_type}")
            
            # 임시 파일로 저장
            audio_bytes = audio_file.read()
            print(f"[STT] 오디오 파일 크기: {len(audio_bytes)} bytes")
            
            if len(audio_bytes) == 0:
                print("[STT] 오디오 파일이 비어있음")
                return jsonify({"error": "파일이 비어있습니다."}), 400
            
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
                    tmp_file.write(audio_bytes)
                    tmp_file_path = tmp_file.name
            
                print(f"[STT] 임시 파일 생성: {tmp_file_path}")
                
                # Whisper STT
                print("[STT] Whisper API 호출 시작...")
                # Whisper가 Pre-KTAS 관련 용어를 더 정확하게 인식하도록 prompt 제공
                whisper_prompt = """Pre-KTAS 1점, Pre-KTAS 2점, Pre-KTAS 3점, Pre-KTAS 4점, Pre-KTAS 5점, 프리케이타스, KTAS, 응급의료, 구급대원, 환자 상태, 심정지, 뇌졸중, 심근경색, 외상"""
                with open(tmp_file_path, "rb") as audio_file_obj:
                    transcript = openai_client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file_obj,
                        response_format="text",
                        language="ko",
                        prompt=whisper_prompt
                    )
                print(f"[STT] Whisper 변환 완료: {transcript[:50]}...")
            except Exception as stt_error:
                print(f"[STT] Whisper STT 오류: {type(stt_error).__name__}: {str(stt_error)}")
                import traceback
                print(f"[STT] Traceback: {traceback.format_exc()}")
                # 임시 파일 정리
                if tmp_file_path and os.path.exists(tmp_file_path):
                    try:
                        os.remove(tmp_file_path)
                    except:
                        pass
                raise stt_error
            
            # GPT-4-turbo로 의학용어 번역 (1단계)
            print("[STT] GPT-4-turbo 의학용어 번역 시작...")
            
            medical_keywords = """M/S, mental state, Alert, confusion, drowsy, stupor, semicoma, coma, V/S, vital sign, TPR, temperature, pulse, respiration, HR, heart rate, PR, pulse rate, BP, blood pressure, BT, body temperature, RR, respiratory rate, BST, blood sugar test, SpO2, sat, saturation of percutaneous oxygen, Abdomen, Abdominal pain, Abnormal, Abrasion, Abscess, Acetaminophen, Acidosis, Acute, Acute abdomen, Acute bronchitis, Acute coronary syndrome, Acute myocardial infarction, Acute renal failure, Acute respiratory distress syndrome, Acute stroke, Airway, Airway obstruction, Alcohol intoxication, Allergy, Allergic reaction, Amnesia, Anaphylactic shock, Anaphylaxis, Analgesic, Anemia, Aneurysm, Angina, Angina pectoris, Angiography, Arrhythmia, Arterial bleeding, Asphyxia, Aspiration, Asthma, Cardiac Arrest, Cardiac tamponade, Cardiogenic shock, Cardiopulmonary arrest, Cardiopulmonary resuscitation (CPR), Cerebral hemorrhage, Cerebral infarction, Cerebrovascular accident (CVA), Chest compression, Chest pain, Choking, Chronic obstructive pulmonary disease (COPD), Coma, Concussion, Confusion, Convulsion, Coronary artery disease (CAD), Cough, Cyanosis, Defibrillation, Dehydration, Dementia, Diabetes mellitus, Diabetic ketoacidosis, Diarrhea, Dizziness, Drowning, Drowsy, Dyspnea, ECG (Electrocardiogram), Edema, Electrocution, Embolism, Emphysema, Endotracheal intubation, Epilepsy, Epistaxis, Fever, Fracture, GCS (Glasgow Coma Scale), Headache, Head injury, Heart arrest, Heart failure, Heart rate, Hematoma, Hematuria, Hemoptysis, Hemorrhage, Hyperglycemia, Hypertension, Hyperthermia, Hyperventilation, Hypoglycemia, Hypotension, Hypothermia, Hypovolemic shock, Hypoxia, Intoxication, Intracranial pressure, Ischemia, Laceration, Myocardial infarction, Nausea, Oxygen therapy, Pneumonia, Pneumothorax, Respiratory arrest, Respiratory distress, Respiratory failure, Seizure, Sepsis, Septic shock, Shock, Stroke, Stupor, Syncope, Tachycardia, Trauma, Unconsciousness, Ventilation, Vertigo, Vomiting, Wound"""
            
            # 1단계 System 메시지
            system_message_1 = """너는 대한민국 응급의료 현장의 대화를 전문적으로 해석하는 의료용어 번역 전문가이다.

- 한국 119 구급대원과 응급실 의료진 사이에서 오가는 보고 내용을 잘 이해한다.

- 구어체, 비표준 표현, 약어, 오타, STT(음성 인식) 오류가 섞여 있어도 문맥을 기반으로 의미를 해석할 수 있어야 한다.

- **모든 일반 문장은 반드시 자연스러운 한국어로 유지**합니다. 절대 영어로 변환하지 않습니다.

- **의학 용어(증상, 상태, 생체징후, 진단명, 약어)만 영어로 변환**합니다.

- 입력에 명시되지 않은 수치나 정보는 절대 임의로 생성하지 않는다.

- 환자 이름, 주민등록번호, 전화번호, 정확한 집 주소 등 개인을 식별할 수 있는 정보가 있다면, 출력에서는 제거하거나 "환자", "보호자" 등으로 일반화한다."""
            
            # 1단계 User 프롬프트
            user_prompt_1 = f"""아래는 응급의료 상황에서 구급대원이 말한 대화/보고 텍스트입니다.

역할과 목표:

- 이 텍스트를 분석하여, **모든 일반 문장은 자연스러운 한국어로 유지**하세요.

- **의학 용어(증상, 상태, 생체징후, 진단명, 약어)만 영어로 변환**하세요.

- 예: "60대 남성, 숨이 안 쉬어짐" → "60대 남성, severe dyspnea" (일반 문장은 한국어 유지, 의학 용어만 영어)

      "약 20분 전" → "약 20분 전" (일반 문장이므로 한국어 유지, 변환하지 않음)

      "도로에서 발견" → "도로에서 발견" (일반 문장이므로 한국어 유지, 변환하지 않음)

      "말이 꼬인다" → "dysarthria" (의학 용어만 영어로 변환)

      "말이 잘 안 나온다" → "aphasia" (의학 용어만 영어로 변환)

출력 형식:

- 내가 전달한 모든 문장을 **하나도 빠뜨리지 말고** 정리하세요. (요약·축약 금지)

- 출력에는 **정리된 문장만** 포함하세요.  

  - 앞뒤에 "다음은 번역입니다" 같은 설명 문장은 절대 쓰지 마세요.

- 오타나 STT 오류로 인해 의미를 완전히 알 수 없는 단어나 구는, 그대로 두거나 자연스럽게 정리하되, 새로운 의미를 임의로 만들지 마세요.

변환 규칙:

1. **일반 문장은 절대 영어로 변환하지 않고 반드시 한국어로 유지**합니다.
   - 예: "60대 남성" → "60대 남성" (변환하지 않음)
   - 예: "약 20분 전" → "약 20분 전" (변환하지 않음)
   - 예: "도로에서 발견" → "도로에서 발견" (변환하지 않음)
   - 예: "갑작스럽게 발생" → "갑작스럽게 발생" (변환하지 않음)

2. **의학 용어만 영어로 변환**합니다.
   - 증상: "숨이 안 쉬어짐" → "severe dyspnea" 또는 "respiratory arrest"
   - 상태: "말이 꼬인다" → "dysarthria", "말이 잘 안 나온다" → "aphasia"
   - 생체징후: "혈압" → "BP", "심박수" → "HR"
   - 진단명: "뇌졸중" → "stroke", "심근경색" → "myocardial infarction"

3. 구급대원이 사용하는 비표준 표현은 문맥을 보고 가능한 한 표준 의학 용어로 변환합니다.

   - 예: "숨이 안 쉬어짐" → "severe dyspnea" 또는 "respiratory distress" (심정지 상황이면 "respiratory arrest")

   - 예: "말이 어눌해짐" → "dysarthria"

4. 오타·발음 착오 등으로 애매한 표현은, 가능한 경우 가장 안전하고 넓은 범위의 의학 표현으로 변환합니다.

   - 예: "혈압 이백에 일백" → "BP 200/100"

   - 예: "20분 전 추정" → "약 20분 전" (일반 문장이므로 한국어 유지)

5. 명확하지 않은 진단을 확정적으로 쓰지 말고, "의심", "추정" 등을 사용해 **의심 수준**으로 표현합니다.
   - 예: "뇌졸중 의심" (한국어 유지)

6. Pre-KTAS 점수 또는 등급 정보는 반드시 정확히 보존하세요.
   - "Pre-KTAS 1점", "Pre-KTAS 2점", "Pre-KTAS 3점", "Pre-KTAS 4점", "Pre-KTAS 5점" 형식으로 표기
   - "프리케이타스", "프리 케이타스", "pre ktas", "pre-ktas" 등 다양한 변형 표현을 "Pre-KTAS"로 통일
   - 점수 숫자(1-5)는 반드시 정확히 보존 (예: "2점" → "2점", "이점" → "2점"으로 수정)
   - "Pre-KTAS 1단계", "Pre-KTAS 2단계" 같은 표현도 점수로 변환 (1단계→1점, 2단계→2점)
   - Pre-KTAS 정보가 잘못 인식되거나 변형된 경우, 원래 의도된 점수를 복원하세요.

참고 키워드(예시):

- M/S, mental state, Alert, confusion, drowsy, stupor, semicoma, coma

- V/S, vital sign, TPR, temperature, pulse, respiration

- HR (heart rate), PR (pulse rate), BP (blood pressure), BT (body temperature), RR (respiratory rate)

- BST (blood sugar test), SpO2 (saturation of percutaneous oxygen), sat, O2

- GCS, KTAS, Pre-KTAS, FAST, CPR, ROSC 등

- {medical_keywords}

텍스트:

{transcript}"""
            
            try:
                completion = openai_client.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=[
                        {"role": "system", "content": system_message_1},
                        {"role": "user", "content": user_prompt_1}
                    ],
                    temperature=0.2
                )
                
                translated_text = completion.choices[0].message.content
                print(f"[STT] 의학용어 번역 완료: {translated_text[:50]}...")
            except Exception as translation_error:
                print(f"[STT] 의학용어 번역 오류: {type(translation_error).__name__}: {str(translation_error)}")
                import traceback
                print(f"[STT] Traceback: {traceback.format_exc()}")
                raise translation_error
            
            # GPT-4-turbo로 SBAR 형식 변환 (2단계)
            print("[STT] SBAR 형식 변환 시작...")
            
            # 2단계 System 메시지
            system_message_2 = """너는 대한민국 응급의료 현장에서 구급대원 보고 내용을 **SBAR 형식**으로 정리하는 전문가이다.

- 입력은 이미 1단계에서 전처리된 텍스트로, 일반 문장은 한국어, 의학 용어는 영어(또는 약어)로 표기되어 있다.

- 너의 목표는 이 정보를 기반으로, **Pre-KTAS 등급을 문장 맨 앞에 두고**, SBAR(Situation, Background, Assessment, Recommendation) 요소를 모두 포함한 전문적인 한국어 요약 문장을 생성하는 것이다.

- SBAR 문장은 병원 응급실 의료진에게 전달되는 것을 가정한다.

- 입력에 없는 정보(Pre-KTAS, 시간, V/S 등)는 절대 임의로 생성하지 않는다."""
            
            # 2단계 User 프롬프트
            user_prompt_2 = f"""아래는 응급의료 현장에서 구급대원이 보고한 환자 상태 정보입니다.

이 정보는 1단계에서 한 번 정리된 상태로, 일반 문장은 한국어, 의학 용어는 영어로 표기되어 있습니다.

이 정보를 바탕으로, SBAR(Situation, Background, Assessment, Recommendation) 형식의 요소들을 모두 포함하여,

**병원 의료진에게 전달할 한 문장(또는 2~3문장)의 요약**으로 변환하세요.

중요 규칙:

1. Pre-KTAS 위치 및 존재 여부

   - 입력에 Pre-KTAS 등급이 **명시되어 있는 경우**,  

     문장은 반드시 `"Pre-KTAS X점 환자, ..."` 형태로 시작합니다.

   - 입력에 Pre-KTAS 등급이 **명시되어 있지 않은 경우**,  

     임의로 등급을 추론하지 말고  

     `"Pre-KTAS 등급 미측정 환자, ..."` 또는 `"Pre-KTAS 등급 정보 없음, ..."`으로 시작합니다.

   - 시스템 정책상 Pre-KTAS를 추론해야 한다면,  

     `"Pre-KTAS 2점으로 추정되는 환자, ..."`처럼 **'추정'이라는 표현을 반드시 포함**하세요.

2. 문장 길이 및 개수

   - 기본적으로 **하나의 완전한 문장**으로 작성합니다.

   - 포함해야 할 핵심 정보가 **7개 이상**이어서 문장이 지나치게 길어지는 경우에는 **최대 2~3문장**으로 나눌 수 있습니다.

     - 1문장: S(상황) + A(평가)를 중심으로 기술

     - 2문장: 첫 문장에 S+A, 두 번째 문장에 B(배경)+R(권고)

3. SBAR 요소 연결

   - SBAR 요소는 기본적으로 다음 순서로 자연스럽게 연결합니다.  

     `Pre-KTAS + S → B → A → R`

   - 접속어 예시:

     - S 시작: "…환자로", "…환자이며"

     - B 연결: "과거력으로", "V/S는", "현재 BP ~, HR ~, SpO2 ~로"

     - A 연결: "이러한 소견으로", "현재 상태는 ~가 의심되는 상태이며"

     - R 연결: "이에", "따라서", "이로 인해 ~~로의 (긴급) 이송이 필요합니다."

   - 예시 패턴:

     `"Pre-KTAS 2점 환자, 60대 남성으로 약 20분 전부터 갑작스러운 언어장애와 우측 편마비가 발생하였고, 과거력으로 당뇨병이 있으며 현재 BP 180/100, HR 110, SpO2 95%로, 급성 뇌졸중이 의심되는 상태로, 뇌혈관중재술이 가능한 3차 응급의료센터로의 긴급 이송이 필요합니다."`

4. 의학 용어 표기

   - SBAR 단계에서는 **의학 용어/약어는 영어(또는 국제 표준 약어)로 유지**합니다.  

     (예: BP, HR, RR, SpO2, GCS, FAST, CPR, ROSC 등)

   - 한글로 바꾸지 말고 그대로 사용하세요.

5. 시간·생체징후·불확실성 처리

   - 증상 발생 시점이나 경과 시간이 입력에 있는 경우, 반드시 포함합니다.

     - 예: "about 20 minutes ago" → "약 20분 전부터"

     - "추정" 정보는 "약/approximately" 등의 표현을 유지하여 불확실성을 표현합니다.

   - 생체징후(V/S: BP, HR, RR, SpO2, BT 등)가 입력에 있는 경우, 가능한 한 포함합니다.

     - 입력에 없는 V/S를 새로 만들지 마세요.

     - V/S 정보가 전혀 없으면 생략하거나 "vital signs not reported" 같은 표현을 쓸 수 있습니다(정책에 따라).

   - 불확실한 진단은 "의심되는 상태", "suspected" 등으로 표현합니다.

     - 예: "acute stroke is suspected", "acute coronary syndrome is suspected"

6. 환자 유형별 주의점 (선택적)

   - 심정지/CPR:

     - 심정지 발생 시각, CPR 시작 시각, ROSC 여부 등 핵심 정보 우선 포함.

   - 뇌졸중 의심:

     - 증상 발생(또는 마지막 정상) 시각, 편마비/언어장애, 혈압 등 우선 포함.

   - 외상:

     - 외상 기전, 주요 출혈 부위, 의식 상태(GCS), 혈압/맥박 등 우선 포함.

   - 복합 상황(예: 외상 + 심정지)이면, **심정지/생명 위협 정보**를 가장 먼저 기술합니다.

7. 문체

   - 항상 정중하고 전문적인 **평서문**으로 작성합니다.

   - "인 것 같습니다" 등 모호한 표현보다, "~~이 의심되는 상태입니다", "~~가 필요합니다"처럼 명확한 존댓말을 사용합니다.

SBAR 요소 정의(요약):

- S (Situation): 현재 상황 - 환자 기본 정보(나이, 성별), 주요 증상, 증상 발생 시점

- B (Background): 배경 정보 - 기저질환, 복용 약물, 생체 징후(V/S), 과거력

- A (Assessment): 평가 - 의식 상태, 주요 의심 질환, 생명 위협 여부

- R (Recommendation): 권고 - 필요한 이송 병원 유형(예: 3차 응급의료센터, 권역외상센터 등), 긴급도(즉시/긴급/준응급), 필요 자원(예: stroke team, cath lab, trauma team 등)

입력 텍스트:

{translated_text}

Pre-KTAS를 제일 앞에 놓고, 위 규칙에 따라 SBAR 요소를 포함한 자연스러운 문장으로 변환:"""

            sbar_completion = openai_client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": system_message_2},
                    {"role": "user", "content": user_prompt_2}
                ],
                temperature=0.3
            )
            
            sbar_summary = sbar_completion.choices[0].message.content
            print(f"[STT] SBAR 구조화 완료: {sbar_summary[:100]}...")
            
            # SBAR 형식을 자연스러운 문장으로 변환 (ARS 서비스용, 3단계)
            print("[STT] SBAR → 자연스러운 문장 변환 시작...")
            try:
                # 3단계 System 메시지
                system_message_3 = """너는 응급의료 현장의 SBAR 형식 정보를, ARS(자동응답서비스) 음성 안내에 최적화된 자연스러운 문장으로 변환하는 전문가이다.

- 입력은 이미 2단계에서 생성된 SBAR 기반 요약 문장이다.

- 너의 목표는 이 문장을, 전화 ARS 음성으로 한 번 들었을 때 의료진이 핵심 내용을 빠르게 이해할 수 있도록 **길이·리듬·발음** 측면에서 다듬는 것이다.

- "Pre-KTAS"는 음성에서 자연스럽게 읽히도록 "프리케이타스"로 한글 표기를 사용한다.

- 숫자와 생체징후는 명확하게 들리도록, 필요시 단위나 설명을 덧붙인다.

- 출력은 항상 정중하고 전문적인 한국어 존댓말 문장이어야 한다."""
                
                # 3단계 User 프롬프트
                user_prompt_3 = f"""아래는 SBAR 형식으로 정리된 응급환자 정보(2단계 출력)입니다.

이 정보를 ARS(자동응답서비스)에서 의료진이 전화를 통해 들었을 때,

한 번에 핵심 내용을 이해할 수 있도록 **자연스럽고 명확한 한국어 문장**으로 변환하세요.

요구사항:

1. SBAR 순서 유지 + 핵심 먼저

   - 전체 정보는 기본적으로 S(상황) → B(배경) → A(평가) → R(권고) 순서로 전달되도록 유지합니다.

   - 문장 앞부분에는 **프리케이타스 등급, 생명 위협 여부, 주요 의심 질환** 등 가장 중요한 정보를 먼저 배치합니다.

2. Pre-KTAS 표기

   - "Pre-KTAS"는 반드시 "프리케이타스"로 발음 기반 한글 표기를 사용합니다.

     - 예: "Pre-KTAS 2점" → "프리케이타스 2점"

   - SBAR 문장에 "Pre-KTAS"가 없다면 새로 생성하지 말고, 없는 상태대로 진행합니다.

3. 의학 용어 처리

   - BP, HR, RR, SpO2, GCS, FAST, CPR, ROSC 등 의학 약어는 **그대로 유지**합니다.

   - 필요시 뒤에 간단한 설명을 덧붙일 수 있습니다.

     - 예: "BP 180에 100", "HR 분당 120회", "SpO2 95퍼센트"

   - 진단명/상태명(예: acute stroke, acute coronary syndrome 등)은 한국어 표현 + 영어 용어를 함께 쓰거나, 한국어만 사용해도 됩니다. (서비스 정책에 맞게 선택 가능)

4. 숫자·시간 표현

   - 숫자와 시간은 **의미가 명확하게 들리도록** 표현합니다.

     - 예: "BP 180/100" → "혈압 비피 180에 100"

     - "HR 120" → "심박수 120회"

     - "20분 전" → "약 20분 전에"

   - 혼동될 수 있는 숫자는 단위·맥락과 함께 말하게 구성합니다.

     - 예: 그냥 "4" 보다는 "4회", "4센티미터" 등으로 표현.

5. 문장 길이와 개수

   - 한 문장은 대략 **8~12초 안에 읽을 수 있는 길이**를 목표로 합니다.

   - 너무 길다고 판단되면 **최대 2~3문장**으로 나누세요.

     - 1문장: 프리케이타스 등급 + 현재 상황 + 주요 평가

     - 2문장: 첫 문장(S+A), 두 번째 문장(B+R)

   - 같은 정보(시간, 수치)를 문장 안에서 **불필요하게 반복하지 않습니다.**

6. 문체

   - 항상 정중하고 전문적인 **존댓말**로 작성합니다. ("입니다", "합니다")

   - "인 것 같습니다", "보이는 것 같습니다" 등 애매한 표현은 피하고,

     "~로 의심되는 상태입니다", "~이 필요합니다"처럼 **단정적이되 진단은 '의심' 수준으로** 표현합니다.

7. 오류·불완전 정보 처리

   - SBAR 문장 안에 이미 "약", "추정", "의심" 등의 표현이 있다면, 해당 불확실성을 그대로 유지합니다.

   - 정보가 모호하거나 부족하다고 해서 새로운 수치나 사실을 임의로 추가하지 마세요.

8. 개인정보

   - 환자 이름, 구체 주소 등 개인을 식별할 수 있는 정보가 있다면, ARS 문장에서는 "환자", "보호자", "가정", "현장" 등으로 일반화합니다.

입력 (SBAR 형식 정보):

{sbar_summary}

위 요구사항을 반영하여, ARS 음성 안내용으로 자연스럽고 명확한 문장으로 변환:"""

                ars_narrative_completion = openai_client.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=[
                        {"role": "system", "content": system_message_3},
                        {"role": "user", "content": user_prompt_3}
                    ],
                    temperature=0.4
                )
                
                ars_narrative = ars_narrative_completion.choices[0].message.content
                print(f"[STT] ARS 문장 변환 완료: {ars_narrative[:100]}...")
            except Exception as narrative_error:
                print(f"[STT] ARS 문장 변환 오류: {type(narrative_error).__name__}: {str(narrative_error)}")
                import traceback
                print(f"[STT] Traceback: {traceback.format_exc()}")
                # 에러 발생 시 SBAR 원본 사용
                ars_narrative = sbar_summary
            
            # STT 결과 저장 (타임스탬프 포함, 누적 기록)
            save_stt_filepath = "stt_history.txt"
            with open(save_stt_filepath, "a", encoding="utf-8") as fh:
                timestr = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                fh.write(f"[{timestr}] 의학용어 변환: {translated_text}\n")
                fh.write(f"[{timestr}] SBAR 구조화: {sbar_summary}\n")
                fh.write(f"[{timestr}] ARS 문장 변환: {ars_narrative}\n")
            
            # STT 결과를 DB에 저장 (request_id가 제공된 경우)
            # multipart/form-data 요청이므로 form에서만 가져오기 (JSON은 사용 불가)
            request_id = request.form.get('request_id', type=int)
            if request_id:
                try:
                    with app.app_context():
                        emergency_request = EmergencyRequest.query.get(request_id)
                        if emergency_request:
                            emergency_request.stt_full_text = translated_text
                            emergency_request.rag_summary = sbar_summary
                            db.session.commit()
                except Exception as e:
                    print(f"STT 결과 DB 저장 오류: {e}")
            
                # 임시 파일 삭제
            if tmp_file_path and os.path.exists(tmp_file_path):
                try:
                    os.remove(tmp_file_path)
                except Exception as cleanup_error:
                    print(f"임시 파일 삭제 실패: {cleanup_error}")
            
            return jsonify({
                "text": translated_text,
                "sbar_summary": sbar_summary,
                "ars_narrative": ars_narrative  # ARS 서비스용 자연스러운 문장
            }), 200
                    
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            error_type = type(e).__name__
            error_message = str(e)
            
            print(f"[STT] 최종 에러 발생: {error_type}: {error_message}")
            print(f"[STT] 상세 에러:\n{error_detail}")
            
            # 임시 파일 정리 (에러 발생 시에도)
            try:
                if 'tmp_file_path' in locals() and tmp_file_path and os.path.exists(tmp_file_path):
                    os.remove(tmp_file_path)
                    print(f"[STT] 임시 파일 삭제됨: {tmp_file_path}")
            except Exception as cleanup_error:
                print(f"[STT] 임시 파일 정리 실패: {cleanup_error}")
            
            # 더 상세한 에러 메시지 반환
            if not openai_client:
                error_message = "OpenAI 클라이언트가 초기화되지 않았습니다. API 키를 확인하세요."
            elif "api_key" in error_message.lower() or "authentication" in error_message.lower() or "401" in error_message or "403" in error_message:
                error_message = "OpenAI API 키가 설정되지 않았거나 유효하지 않습니다."
            elif "rate limit" in error_message.lower() or "429" in error_message:
                error_message = "OpenAI API 사용량 한도를 초과했습니다. 잠시 후 다시 시도해주세요."
            elif "audio" in error_message.lower() or "file" in error_message.lower():
                error_message = "오디오 파일 처리 중 오류가 발생했습니다."
            elif "Invalid file format" in error_message or "unsupported" in error_message.lower():
                error_message = "지원하지 않는 오디오 파일 형식입니다."
            elif "network" in error_message.lower() or "connection" in error_message.lower():
                error_message = "네트워크 연결 오류가 발생했습니다. 인터넷 연결을 확인해주세요."
            
            return jsonify({
                "error": f"음성 인식 오류: {error_message}",
                "detail": str(e),
                "type": error_type
            }), 500

    @app.route('/api/stt/convert-to-sbar', methods=['POST', 'OPTIONS'])
    def api_stt_convert_to_sbar():
        """텍스트를 의학용어로 번역한 후 SBAR 형식으로 변환하는 API"""
        if request.method == 'OPTIONS':
            return '', 200
        
        if not openai_client:
            return jsonify({"error": "OpenAI 클라이언트가 초기화되지 않았습니다. API 키를 확인하세요."}), 500
        
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "JSON 데이터가 필요합니다."}), 400
            
            text = data.get('text', '').strip()
            if not text:
                return jsonify({"error": "text 파라미터가 필요합니다."}), 400
            
            # 1단계: 의학용어 번역
            medical_keywords = """M/S, mental state, Alert, confusion, drowsy, stupor, semicoma, coma, V/S, vital sign, TPR, temperature, pulse, respiration, HR, heart rate, PR, pulse rate, BP, blood pressure, BT, body temperature, RR, respiratory rate, BST, blood sugar test, SpO2, sat, saturation of percutaneous oxygen, Abdomen, Abdominal pain, Abnormal, Abrasion, Abscess, Acetaminophen, Acidosis, Acute, Acute abdomen, Acute bronchitis, Acute coronary syndrome, Acute myocardial infarction, Acute renal failure, Acute respiratory distress syndrome, Acute stroke, Airway, Airway obstruction, Alcohol intoxication, Allergy, Allergic reaction, Amnesia, Anaphylactic shock, Anaphylaxis, Analgesic, Anemia, Aneurysm, Angina, Angina pectoris, Angiography, Arrhythmia, Arterial bleeding, Asphyxia, Aspiration, Asthma, Cardiac Arrest, Cardiac tamponade, Cardiogenic shock, Cardiopulmonary arrest, Cardiopulmonary resuscitation (CPR), Cerebral hemorrhage, Cerebral infarction, Cerebrovascular accident (CVA), Chest compression, Chest pain, Choking, Chronic obstructive pulmonary disease (COPD), Coma, Concussion, Confusion, Convulsion, Coronary artery disease (CAD), Cough, Cyanosis, Defibrillation, Dehydration, Dementia, Diabetes mellitus, Diabetic ketoacidosis, Diarrhea, Dizziness, Drowning, Drowsy, Dyspnea, ECG (Electrocardiogram), Edema, Electrocution, Embolism, Emphysema, Endotracheal intubation, Epilepsy, Epistaxis, Fever, Fracture, GCS (Glasgow Coma Scale), Headache, Head injury, Heart arrest, Heart failure, Heart rate, Hematoma, Hematuria, Hemoptysis, Hemorrhage, Hyperglycemia, Hypertension, Hyperthermia, Hyperventilation, Hypoglycemia, Hypotension, Hypothermia, Hypovolemic shock, Hypoxia, Intoxication, Intracranial pressure, Ischemia, Laceration, Myocardial infarction, Nausea, Oxygen therapy, Pneumonia, Pneumothorax, Respiratory arrest, Respiratory distress, Respiratory failure, Seizure, Sepsis, Septic shock, Shock, Stroke, Stupor, Syncope, Tachycardia, Trauma, Unconsciousness, Ventilation, Vertigo, Vomiting, Wound"""
            
            # 1단계 System 메시지 (음성 입력과 동일)
            system_msg_1 = """너는 대한민국 응급의료 현장의 대화를 전문적으로 해석하는 의료용어 번역 전문가이다.

- 한국 119 구급대원과 응급실 의료진 사이에서 오가는 보고 내용을 잘 이해한다.

- 구어체, 비표준 표현, 약어, 오타, STT(음성 인식) 오류가 섞여 있어도 문맥을 기반으로 의미를 해석할 수 있어야 한다.

- **모든 일반 문장은 반드시 자연스러운 한국어로 유지**합니다. 절대 영어로 변환하지 않습니다.

- **의학 용어(증상, 상태, 생체징후, 진단명, 약어)만 영어로 변환**합니다.

- 입력에 명시되지 않은 수치나 정보는 절대 임의로 생성하지 않는다.

- 환자 이름, 주민등록번호, 전화번호, 정확한 집 주소 등 개인을 식별할 수 있는 정보가 있다면, 출력에서는 제거하거나 "환자", "보호자" 등으로 일반화한다."""
            
            user_prompt_1 = f"""아래는 응급의료 상황에서 구급대원이 말한 대화/보고 텍스트입니다.

역할과 목표:

- 이 텍스트를 분석하여, **모든 일반 문장은 자연스러운 한국어로 유지**하세요.

- **의학 용어(증상, 상태, 생체징후, 진단명, 약어)만 영어로 변환**하세요.

- 예: "60대 남성, 숨이 안 쉬어짐" → "60대 남성, severe dyspnea" (일반 문장은 한국어 유지, 의학 용어만 영어)

      "약 20분 전" → "약 20분 전" (일반 문장이므로 한국어 유지, 변환하지 않음)

      "도로에서 발견" → "도로에서 발견" (일반 문장이므로 한국어 유지, 변환하지 않음)

      "말이 꼬인다" → "dysarthria" (의학 용어만 영어로 변환)

      "말이 잘 안 나온다" → "aphasia" (의학 용어만 영어로 변환)

출력 형식:

- 내가 전달한 모든 문장을 **하나도 빠뜨리지 말고** 정리하세요. (요약·축약 금지)

- 출력에는 **정리된 문장만** 포함하세요.  

  - 앞뒤에 "다음은 번역입니다" 같은 설명 문장은 절대 쓰지 마세요.

- 오타나 STT 오류로 인해 의미를 완전히 알 수 없는 단어나 구는, 그대로 두거나 자연스럽게 정리하되, 새로운 의미를 임의로 만들지 마세요.

변환 규칙:

1. **일반 문장은 절대 영어로 변환하지 않고 반드시 한국어로 유지**합니다.
   - 예: "60대 남성" → "60대 남성" (변환하지 않음)
   - 예: "약 20분 전" → "약 20분 전" (변환하지 않음)
   - 예: "도로에서 발견" → "도로에서 발견" (변환하지 않음)
   - 예: "갑작스럽게 발생" → "갑작스럽게 발생" (변환하지 않음)

2. **의학 용어만 영어로 변환**합니다.
   - 증상: "숨이 안 쉬어짐" → "severe dyspnea" 또는 "respiratory arrest"
   - 상태: "말이 꼬인다" → "dysarthria", "말이 잘 안 나온다" → "aphasia"
   - 생체징후: "혈압" → "BP", "심박수" → "HR"
   - 진단명: "뇌졸중" → "stroke", "심근경색" → "myocardial infarction"

3. 구급대원이 사용하는 비표준 표현은 문맥을 보고 가능한 한 표준 의학 용어로 변환합니다.

   - 예: "숨이 안 쉬어짐" → "severe dyspnea" 또는 "respiratory distress" (심정지 상황이면 "respiratory arrest")

   - 예: "말이 어눌해짐" → "dysarthria"

4. 오타·발음 착오 등으로 애매한 표현은, 가능한 경우 가장 안전하고 넓은 범위의 의학 표현으로 변환합니다.

   - 예: "혈압 이백에 일백" → "BP 200/100"

   - 예: "20분 전 추정" → "약 20분 전" (일반 문장이므로 한국어 유지)

5. 명확하지 않은 진단을 확정적으로 쓰지 말고, "의심", "추정" 등을 사용해 **의심 수준**으로 표현합니다.
   - 예: "뇌졸중 의심" (한국어 유지)

6. Pre-KTAS 점수 또는 등급 정보는 반드시 정확히 보존하세요.
   - "Pre-KTAS 1점", "Pre-KTAS 2점", "Pre-KTAS 3점", "Pre-KTAS 4점", "Pre-KTAS 5점" 형식으로 표기
   - "프리케이타스", "프리 케이타스", "pre ktas", "pre-ktas" 등 다양한 변형 표현을 "Pre-KTAS"로 통일
   - 점수 숫자(1-5)는 반드시 정확히 보존 (예: "2점" → "2점", "이점" → "2점"으로 수정)
   - "Pre-KTAS 1단계", "Pre-KTAS 2단계" 같은 표현도 점수로 변환 (1단계→1점, 2단계→2점)
   - Pre-KTAS 정보가 잘못 인식되거나 변형된 경우, 원래 의도된 점수를 복원하세요.

참고 키워드(예시):

- M/S, mental state, Alert, confusion, drowsy, stupor, semicoma, coma

- V/S, vital sign, TPR, temperature, pulse, respiration

- HR (heart rate), PR (pulse rate), BP (blood pressure), BT (body temperature), RR (respiratory rate)

- BST (blood sugar test), SpO2 (saturation of percutaneous oxygen), sat, O2

- GCS, KTAS, Pre-KTAS, FAST, CPR, ROSC 등

- {medical_keywords}

텍스트:

{text}"""
            
            completion = openai_client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": system_msg_1},
                    {"role": "user", "content": user_prompt_1}
                ],
                temperature=0.2
            )
            
            translated_text = completion.choices[0].message.content
            
            # 2단계: SBAR 형식 변환
            # 2단계 System 메시지 (음성 입력과 동일)
            system_msg_2 = """너는 대한민국 응급의료 현장에서 구급대원 보고 내용을 **SBAR 형식**으로 정리하는 전문가이다.

- 입력은 이미 1단계에서 전처리된 텍스트로, 일반 문장은 한국어, 의학 용어는 영어(또는 약어)로 표기되어 있다.

- 너의 목표는 이 정보를 기반으로, **Pre-KTAS 등급을 문장 맨 앞에 두고**, SBAR(Situation, Background, Assessment, Recommendation) 요소를 모두 포함한 전문적인 한국어 요약 문장을 생성하는 것이다.

- SBAR 문장은 병원 응급실 의료진에게 전달되는 것을 가정한다.

- 입력에 없는 정보(Pre-KTAS, 시간, V/S 등)는 절대 임의로 생성하지 않는다."""
            
            user_prompt_2 = f"""아래는 응급의료 현장에서 구급대원이 보고한 환자 상태 정보입니다.

이 정보는 1단계에서 한 번 정리된 상태로, 일반 문장은 한국어, 의학 용어는 영어로 표기되어 있습니다.

이 정보를 바탕으로, SBAR(Situation, Background, Assessment, Recommendation) 형식의 요소들을 모두 포함하여,

**병원 의료진에게 전달할 한 문장(또는 2~3문장)의 요약**으로 변환하세요.

중요 규칙:

1. Pre-KTAS 위치 및 존재 여부

   - 입력에 Pre-KTAS 등급이 **명시되어 있는 경우**,  

     문장은 반드시 `"Pre-KTAS X점 환자, ..."` 형태로 시작합니다.

   - 입력에 Pre-KTAS 등급이 **명시되어 있지 않은 경우**,  

     임의로 등급을 추론하지 말고  

     `"Pre-KTAS 등급 미측정 환자, ..."` 또는 `"Pre-KTAS 등급 정보 없음, ..."`으로 시작합니다.

2. 문장 길이 및 개수

   - 기본적으로 **하나의 완전한 문장**으로 작성합니다.

   - 포함해야 할 핵심 정보가 **7개 이상**이어서 문장이 지나치게 길어지는 경우에는 **최대 2~3문장**으로 나눌 수 있습니다.

3. SBAR 요소 연결

   - SBAR 요소는 기본적으로 다음 순서로 자연스럽게 연결합니다.  

     `Pre-KTAS + S → B → A → R`

4. 의학 용어 표기

   - SBAR 단계에서는 **의학 용어/약어는 영어(또는 국제 표준 약어)로 유지**합니다.

5. 시간·생체징후·불확실성 처리

   - 증상 발생 시점이나 경과 시간이 입력에 있는 경우, 반드시 포함합니다.

   - 생체징후(V/S: BP, HR, RR, SpO2, BT 등)가 입력에 있는 경우, 가능한 한 포함합니다.

   - 불확실한 진단은 "의심되는 상태", "suspected" 등으로 표현합니다.

6. 문체

   - 항상 정중하고 전문적인 **평서문**으로 작성합니다.

SBAR 요소 정의(요약):

- S (Situation): 현재 상황 - 환자 기본 정보(나이, 성별), 주요 증상, 증상 발생 시점

- B (Background): 배경 정보 - 기저질환, 복용 약물, 생체 징후(V/S), 과거력

- A (Assessment): 평가 - 의식 상태, 주요 의심 질환, 생명 위협 여부

- R (Recommendation): 권고 - 필요한 이송 병원 유형(예: 3차 응급의료센터, 권역외상센터 등), 긴급도(즉시/긴급/준응급), 필요 자원(예: stroke team, cath lab, trauma team 등)

입력 텍스트:

{translated_text}

Pre-KTAS를 제일 앞에 놓고, 위 규칙에 따라 SBAR 요소를 포함한 자연스러운 문장으로 변환:"""

            sbar_completion = openai_client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": system_msg_2},
                    {"role": "user", "content": user_prompt_2}
                ],
                temperature=0.3
            )
            
            sbar_summary = sbar_completion.choices[0].message.content
            
            # 3단계: ARS 자연어 변환
            try:
                # 3단계 System 메시지 (음성 입력과 동일)
                system_msg_3 = """너는 응급의료 현장의 SBAR 형식 정보를, ARS(자동응답서비스) 음성 안내에 최적화된 자연스러운 문장으로 변환하는 전문가이다.

- 입력은 이미 2단계에서 생성된 SBAR 기반 요약 문장이다.

- 너의 목표는 이 문장을, 전화 ARS 음성으로 한 번 들었을 때 의료진이 핵심 내용을 빠르게 이해할 수 있도록 **길이·리듬·발음** 측면에서 다듬는 것이다.

- "Pre-KTAS"는 음성에서 자연스럽게 읽히도록 "프리케이타스"로 한글 표기를 사용한다.

- 숫자와 생체징후는 명확하게 들리도록, 필요시 단위나 설명을 덧붙인다.

- 출력은 항상 정중하고 전문적인 한국어 존댓말 문장이어야 한다."""
                
                user_prompt_3 = f"""아래는 SBAR 형식으로 정리된 응급환자 정보(2단계 출력)입니다.

이 정보를 ARS(자동응답서비스)에서 의료진이 전화를 통해 들었을 때,

한 번에 핵심 내용을 이해할 수 있도록 **자연스럽고 명확한 한국어 문장**으로 변환하세요.

요구사항:

1. SBAR 순서 유지 + 핵심 먼저

   - 전체 정보는 기본적으로 S(상황) → B(배경) → A(평가) → R(권고) 순서로 전달되도록 유지합니다.

   - 문장 앞부분에는 **프리케이타스 등급, 생명 위협 여부, 주요 의심 질환** 등 가장 중요한 정보를 먼저 배치합니다.

2. Pre-KTAS 표기

   - "Pre-KTAS"는 반드시 "프리케이타스"로 발음 기반 한글 표기를 사용합니다.

3. 의학 용어 처리

   - BP, HR, RR, SpO2, GCS, FAST, CPR, ROSC 등 의학 약어는 **그대로 유지**합니다.

4. 숫자·시간 표현

   - 숫자와 시간은 **의미가 명확하게 들리도록** 표현합니다.

5. 문장 길이와 개수

   - 한 문장은 대략 **8~12초 안에 읽을 수 있는 길이**를 목표로 합니다.

   - 너무 길다고 판단되면 **최대 2~3문장**으로 나누세요.

6. 문체

   - 항상 정중하고 전문적인 **존댓말**로 작성합니다. ("입니다", "합니다")

입력 (SBAR 형식 정보):

{sbar_summary}

위 요구사항을 반영하여, ARS 음성 안내용으로 자연스럽고 명확한 문장으로 변환:"""

                ars_narrative_completion = openai_client.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=[
                        {"role": "system", "content": system_msg_3},
                        {"role": "user", "content": user_prompt_3}
                    ],
                    temperature=0.4
                )
                
                ars_narrative = ars_narrative_completion.choices[0].message.content
            except Exception as narrative_error:
                print(f"ARS 문장 변환 오류: {narrative_error}")
                # 에러 발생 시 SBAR 원본 사용
                ars_narrative = sbar_summary
            
            return jsonify({
                "text": translated_text,
                "sbar_summary": sbar_summary,
                "ars_narrative": ars_narrative  # ARS 서비스용 자연스러운 문장
            }), 200
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"텍스트→SBAR 변환 오류: {error_detail}")
            return jsonify({"error": f"텍스트 변환 오류: {str(e)}"}), 500
