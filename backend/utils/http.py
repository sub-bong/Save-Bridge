#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTTP 유틸리티 함수"""

import requests
from urllib.parse import urlparse
from typing import Optional, Dict, Any

from config import DATA_GO_KR_KEY


def http_get(url: str, params: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> requests.Response:
    """HTTP GET 요청 헬퍼 함수"""
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


def safe_int(x) -> int:
    """안전한 정수 변환"""
    try:
        return int(str(x).strip()) if str(x).strip() not in ("", "None", "nan") else 0
    except:
        return 0

