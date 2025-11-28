#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
비밀번호 해싱 유틸리티
"""

from werkzeug.security import generate_password_hash, check_password_hash


def hash_password(password: str) -> str:
    """
    비밀번호를 해시로 변환
    
    Args:
        password: 평문 비밀번호
        
    Returns:
        해시된 비밀번호 문자열
    """
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """
    비밀번호 검증
    
    Args:
        password: 검증할 평문 비밀번호
        password_hash: 저장된 해시된 비밀번호
        
    Returns:
        비밀번호가 일치하면 True, 아니면 False
    """
    return check_password_hash(password_hash, password)


