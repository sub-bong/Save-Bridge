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
from typing import Optional

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client


def log(msg: str) -> None:
    print(f"[Twilio] {msg}")


def resolve_target_sid(client: Client) -> str:
    """환경변수에서 대상 인바운드 번호 SID를 찾는다."""
    sid = os.getenv("TWILIO_PHONE_NUMBER_SID") or os.getenv("TWILIO_INCOMING_NUMBER_SID")
    if sid:
        log(f"환경변수에서 인바운드 SID 확인: {sid}")
        return sid

    phone_number = os.getenv("TWILIO_PHONE_NUMBER")
    if not phone_number:
        raise ValueError("TWILIO_PHONE_NUMBER_SID/TWILIO_INCOMING_NUMBER_SID 또는 "
                         "TWILIO_PHONE_NUMBER 중 하나는 반드시 설정해야 합니다.")

    matches = client.incoming_phone_numbers.list(phone_number=phone_number, limit=1)
    if not matches:
        raise ValueError(f"Twilio 계정에서 번호 {phone_number} 를 찾을 수 없습니다.")

    sid = matches[0].sid
    log(f"번호 {phone_number} 에 해당하는 SID 조회: {sid}")
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

