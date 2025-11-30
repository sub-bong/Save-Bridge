#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTTP 유틸리티 함수"""

import requests
from urllib.parse import urlparse
from typing import Optional, Dict, Any
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import DATA_GO_KR_KEY

# 세션 생성 (연결 풀 재사용 및 재시도 설정)
_session = None

def get_session():
    """재사용 가능한 requests 세션 생성"""
    global _session
    if _session is None:
        _session = requests.Session()
        # 재시도 전략 설정
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10)
        _session.mount("http://", adapter)
        _session.mount("https://", adapter)
    return _session


def http_get(url: str, params: Dict[str, Any], headers: Optional[Dict[str, str]] = None, max_retries: int = 3) -> requests.Response:
    """HTTP GET 요청 헬퍼 함수 (재시도 로직 포함)"""
    timeout = (10, 30)  # 연결 타임아웃 10초, 읽기 타임아웃 30초로 증가
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
    
    # 세션 사용 (연결 풀 재사용 및 자동 재시도)
    session = get_session()
    
    # DNS 해석을 먼저 수행하여 DNS 타임아웃 문제 방지
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if hostname:
            import socket
            # DNS 해석을 먼저 수행 (타임아웃 5초)
            try:
                socket.setdefaulttimeout(5)
                ip_address = socket.gethostbyname(hostname)
                print(f"DNS 해석 성공: {hostname} -> {ip_address}")
            except socket.gaierror as dns_error:
                print(f"DNS 해석 실패: {hostname} - {dns_error}")
                # DNS 해석 실패해도 요청은 시도 (requests가 자체 DNS 해석 시도)
            finally:
                socket.setdefaulttimeout(None)  # 타임아웃 초기화
    except Exception as dns_check_error:
        print(f"DNS 사전 해석 중 오류 (무시하고 계속): {dns_check_error}")
    
    # 재시도 로직 (추가 수동 재시도)
    last_error = None
    for attempt in range(max_retries):
        try:
            resp = session.get(url, params=params, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.RequestException) as e:
            last_error = e
            if attempt < max_retries - 1:
                import time
                wait_time = (attempt + 1) * 2  # 2초, 4초, 6초 대기
                print(f"HTTP 요청 실패 (시도 {attempt + 1}/{max_retries}), {wait_time}초 후 재시도: {e}")
                time.sleep(wait_time)
            else:
                print(f"HTTP 요청 최종 실패 (시도 {max_retries}/{max_retries}): {e}")
                raise


def safe_int(x) -> int:
    """안전한 정수 변환"""
    try:
        return int(str(x).strip()) if str(x).strip() not in ("", "None", "nan") else 0
    except:
        return 0

