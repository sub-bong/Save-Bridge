#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STT (Speech-to-Text) 관련 라우트"""

from flask import request, jsonify
import tempfile
import os
from config import OPENAI_API_KEY


def register_stt_routes(app, openai_client):
    """STT 라우트 등록"""
    
    @app.route('/api/stt/transcribe', methods=['POST'])
    def api_stt_transcribe():
        """음성을 텍스트로 변환하고 의학용어를 번역하는 API"""
        if not openai_client:
            return jsonify({"error": "OpenAI 클라이언트가 초기화되지 않았습니다. API 키를 확인하세요."}), 500
        
        try:
            # 파일 업로드 확인
            if 'audio' not in request.files:
                return jsonify({"error": "audio 파일이 필요합니다."}), 400
            
            audio_file = request.files['audio']
            if audio_file.filename == '':
                return jsonify({"error": "파일이 선택되지 않았습니다."}), 400
            
            # 임시 파일로 저장
            with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as tmp_file:
                audio_file.save(tmp_file.name)
                tmp_path = tmp_file.name
            
            try:
                # Whisper API로 음성 인식
                with open(tmp_path, 'rb') as f:
                    transcript = openai_client.audio.transcriptions.create(
                        model="whisper-1",
                        file=f,
                        language="ko"
                    )
                
                stt_text = transcript.text
                
                # GPT-4로 의학용어 번역 및 요약
                prompt = f"""다음은 구급대원이 음성으로 전달한 환자 상태 정보입니다. 
의학 용어를 일반인도 이해할 수 있는 표현으로 번역하고, 핵심 정보만 간단히 요약해주세요.

원문: {stt_text}

번역 및 요약:"""
                
                completion = openai_client.chat.completions.create(
                    model="gpt-4-turbo-preview",
                    messages=[
                        {"role": "system", "content": "당신은 응급의료 전문가입니다. 구급대원의 음성 전달 내용을 정확하게 번역하고 요약합니다."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=500
                )
                
                translated_text = completion.choices[0].message.content
                
                return jsonify({
                    "stt_text": stt_text,
                    "translated_text": translated_text
                }), 200
                
            finally:
                # 임시 파일 삭제
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                    
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"STT 처리 오류: {error_detail}")
            return jsonify({"error": f"STT 처리 중 오류가 발생했습니다: {str(e)}"}), 500

