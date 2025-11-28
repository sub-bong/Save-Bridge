#!/usr/bin/env python3
"""
ngrok URL을 활용해 Twilio 인바운드 번호의 Voice/Status 콜백을 갱신하는 스크립트.

환경변수:
  - TWILIO_ACCOUNT_SID (필수)
  - TWILIO_AUTH_TOKEN (필수)
  - TWILIO_PHONE_NUMBER_SID 또는 TWILIO_INCOMING_NUMBER_SID (선택)
  - TWILIO_PHONE_NUMBER (선택, SID가 없을 때 사용)
"""

import os
import sys
from pathlib import Path
from typing import Optional

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

# .env 파일 로드 (프로젝트 루트에서 찾기)
try:
    from dotenv import load_dotenv
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    env_path = project_root / '.env'
    load_dotenv(dotenv_path=env_path)
except ImportError:
    # python-dotenv가 없으면 환경변수에서 직접 읽기
    pass


def log(msg: str) -> None:
    print(f"[Twilio] {msg}")


def resolve_target_sid(client: Client) -> str:
    """환경변수에서 대상 인바운드 번호 SID를 찾는다."""
    # 1. SID 직접 지정 (최우선)
    sid = os.getenv("TWILIO_PHONE_NUMBER_SID") or os.getenv("TWILIO_INCOMING_NUMBER_SID")
    if sid:
        log(f"환경변수에서 인바운드 SID 확인: {sid}")
        return sid

    # 2. 전화번호로 조회 (TWILIO_PHONE_NUMBER 또는 TWILIO_CALLER_NUMBER)
    phone_number = os.getenv("TWILIO_PHONE_NUMBER") or os.getenv("TWILIO_CALLER_NUMBER")
    if phone_number:
        # 전화번호 정규화 (공백, 하이픈 제거)
        normalized = phone_number.replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
        if normalized.startswith("+82"):
            # +8210... 형식을 +8210... 또는 010... 형식으로 변환
            normalized = normalized.replace("+82", "0", 1)
        
        log(f"전화번호로 인바운드 번호 조회 시도: {phone_number} (정규화: {normalized})")
        matches = client.incoming_phone_numbers.list(limit=20)
        
        # 정확한 매칭 시도
        for num in matches:
            num_normalized = num.phone_number.replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
            if num_normalized.endswith(normalized[-10:]) or normalized.endswith(num_normalized[-10:]):
                sid = num.sid
                log(f"번호 {num.phone_number} ({sid}) 매칭됨")
                return sid
        
        # 매칭 실패 시 에러
        raise ValueError(f"Twilio 계정에서 번호 {phone_number} 를 찾을 수 없습니다. "
                         f"계정에 등록된 번호를 확인하세요.")

    # 3. 모든 인바운드 번호 중 첫 번째 사용 (폴백)
    log("환경변수에서 번호 정보를 찾을 수 없어, 계정의 첫 번째 인바운드 번호를 사용합니다.")
    all_numbers = client.incoming_phone_numbers.list(limit=1)
    if not all_numbers:
        raise ValueError("Twilio 계정에 인바운드 번호가 없습니다. "
                         "Twilio 콘솔에서 번호를 구매하거나 환경변수를 설정하세요.")
    
    sid = all_numbers[0].sid
    phone = all_numbers[0].phone_number
    log(f"첫 번째 인바운드 번호 사용: {phone} ({sid})")
    return sid


def update_webhook(base_url: str) -> Optional[str]:
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")

    if not account_sid or not auth_token:
        raise ValueError("TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN 환경변수가 필요합니다.")

    client = Client(account_sid, auth_token)
    target_sid = resolve_target_sid(client)

    voice_url = f"{base_url}/twilio/gather"
    status_callback = f"{base_url}/twilio/status"

    log(f"VoiceUrl 설정: {voice_url}")
    log(f"StatusCallback 설정: {status_callback}")

    incoming_number = client.incoming_phone_numbers(target_sid).update(
        voice_url=voice_url,
        voice_method="POST",
        status_callback=status_callback,
        status_callback_method="POST",
    )

    log(f"번호 {incoming_number.phone_number} ({incoming_number.sid}) 설정 완료")
    return incoming_number.sid


def main() -> int:
    if len(sys.argv) < 2:
        print("사용법: update_twilio_webhook.py <ngrok_url>", file=sys.stderr)
        return 1

    ngrok_url = sys.argv[1].strip().rstrip("/")
    if not ngrok_url.startswith("http"):
        print("ngrok URL이 올바르지 않습니다.", file=sys.stderr)
        return 1

    try:
        update_webhook(ngrok_url)
    except (ValueError, TwilioRestException) as exc:
        print(f"[Twilio] 웹훅 업데이트 실패: {exc}", file=sys.stderr)
        return 1

    log("웹훅 업데이트 성공")
    return 0


if __name__ == "__main__":
    sys.exit(main())

