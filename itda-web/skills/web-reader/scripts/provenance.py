"""provenance.py — 페이지 봉투(provenance envelope) 조립 (web-reader v7.1.0, hyve #1600 T0).

봉투는 "이 시각에 이 URL 에서 이 바이트를 가져왔다"의 출처 증명이다. 요약·정제 결과가
아니라 원본에 대한 사실만 담는다. extract_content(JSON `provenance`·프론트매터)와
extract_records(`page`)가 같은 조립 함수를 쓴다 — 두 표면이 갈리지 않게 하기 위함.

키 계약(추가만 허용, 이름 변경 금지 — 처음 소비자였던 web-scout(#1600)는 2026-10-01 제거됐지만 출력 계약이라 그대로 둔다):
  requested_url  호출자가 준 URL (--url, 없으면 null)
  final_url      마지막 홉 URL (--final-url, 없으면 requested_url)
  status         HTTP 상태코드 (도구 응답 값을 넘겼을 때만, 아니면 null — 지어내지 않는다)
  fetched_at     UTC ISO-8601 (plan.py done 출력 값을 넘겼을 때만, 아니면 null)
  encoding       판정한 코덱(page_input — Content-Type charset·BOM·meta·UTF-8·CP949 순)
  fetch_phase    "hyve"(itda-hyve 로 받은 파일에 도구 응답 값을 함께 넘김) | "input"(그 밖의 파일·stdin).
                 8.0.0 전 값 "static"·"degraded_static" 은 더는 나오지 않는다
  waf_profile    늘 null (8.0.0 에서 WAF 격자를 없앴다 — 키는 계약이라 남긴다)
  content_type   도구 응답의 Content-Type (8.0.0 추가, 없으면 null)
  content_hash   원 응답 bytes 의 sha256 — 회차 간 변경 감지 키
  extractor_version  web-reader 버전
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

EXTRACTOR_VERSION = "8.1.0"


def content_hash(html: str) -> str:
    return hashlib.sha256(html.encode("utf-8")).hexdigest()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_provenance(
    html: str,
    *,
    raw_sha256: str | None = None,
    requested_url: str | None,
    final_url: str | None = None,
    status: int | None = None,
    fetched_at: str | None = None,
    encoding: str | None = None,
    fetch_phase: str = "input",
    waf_profile: str | None = None,
    content_type: str | None = None,
) -> dict[str, Any]:
    return {
        "requested_url": requested_url,
        "final_url": final_url if final_url else requested_url,
        "status": status,
        "fetched_at": fetched_at,
        "encoding": encoding,
        "fetch_phase": fetch_phase,
        "waf_profile": waf_profile,
        "content_type": content_type,
        # 원 응답 bytes 의 sha256 이 있으면 그것(EUC-KR 등 비UTF-8 에서 문자열 재인코딩 해시와 다르다 — R-impl P2);
        # 파일·stdin 입력처럼 bytes 를 모를 때만 UTF-8 재인코딩 해시(그 사실을 hash_basis 로 남긴다)
        "content_hash": raw_sha256 or content_hash(html),
        "hash_basis": "raw_bytes" if raw_sha256 else "utf8_text",
        "extractor_version": EXTRACTOR_VERSION,
    }
