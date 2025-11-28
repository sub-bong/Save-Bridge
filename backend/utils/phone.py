#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""전화번호 유틸리티 함수"""

from typing import Optional
from pathlib import Path

from config import TWILIO_CALLBACK_BASE_URL


def normalize_phone_number(raw: Optional[str]) -> Optional[str]:
    """전화번호 정규화"""
    if not raw:
        return None
    digits = "".join(ch for ch in str(raw) if ch.isdigit())
    if not digits:
        return None
    if digits.startswith("0"):
        digits = "82" + digits[1:]
    if not digits.startswith("+"):
        digits = f"+{digits}"
    return digits


def resolve_callback_base(preferred: Optional[str] = None) -> Optional[str]:
    """Twilio 콜백 URL 결정"""
    if preferred:
        return preferred.rstrip("/")
    if TWILIO_CALLBACK_BASE_URL:
        return TWILIO_CALLBACK_BASE_URL.rstrip("/")
    try:
        logs_path = Path(__file__).resolve().parent.parent.parent / "logs" / ".ngrok_url"
        if logs_path.exists():
            return logs_path.read_text().strip()
    except Exception:
        pass
    return None

