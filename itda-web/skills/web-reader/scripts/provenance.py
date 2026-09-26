"""provenance.py — 페이지 봉투(provenance envelope) 조립 (web-reader v7.1.0, hyve #1600 T0).

봉투는 "이 시각에 이 URL 에서 이 바이트를 가져왔다"의 출처 증명이다. 요약·정제 결과가
아니라 원본에 대한 사실만 담는다. extract_content(JSON `provenance`·프론트매터)와
extract_records(`page`)가 같은 조립 함수를 쓴다 — 두 표면이 갈리지 않게 하기 위함.

키 계약(추가만 허용, 이름 변경 금지 — web-scout #1600 이 소비):
  requested_url  호출자가 준 URL (파일 입력이면 --url 값 또는 null)
  final_url      리다이렉트 후 최종 URL (파일 입력이면 requested_url)
  status         HTTP 상태코드 (파일 입력이면 null)
  fetched_at     UTC ISO-8601 (파일 입력이면 null — 지어내지 않는다)
  encoding       감지 인코딩 (파일 입력이면 null)
  fetch_phase    성공한 fetch 단계 — "static" | "degraded_static" | "input"(파일·stdin)
  waf_profile    적용된 WAF 프로파일 (없으면 null)
  content_hash   sha256("정제 전 HTML 문자열".encode("utf-8")) — 회차 간 변경 감지 키
  extractor_version  web-reader 버전
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

EXTRACTOR_VERSION = "7.1.1"


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
) -> dict[str, Any]:
    return {
        "requested_url": requested_url,
        "final_url": final_url if final_url else requested_url,
        "status": status,
        "fetched_at": fetched_at,
        "encoding": encoding,
        "fetch_phase": fetch_phase,
        "waf_profile": waf_profile,
        # 원 응답 bytes 의 sha256 이 있으면 그것(EUC-KR 등 비UTF-8 에서 문자열 재인코딩 해시와 다르다 — R-impl P2);
        # 파일·stdin 입력처럼 bytes 를 모를 때만 UTF-8 재인코딩 해시(그 사실을 hash_basis 로 남긴다)
        "content_hash": raw_sha256 or content_hash(html),
        "hash_basis": "raw_bytes" if raw_sha256 else "utf8_text",
        "extractor_version": EXTRACTOR_VERSION,
    }


def provenance_from_fetch_extra(html: str, requested_url: str, final_url: str, extra: dict[str, Any]) -> dict[str, Any]:
    """fetch_pipeline.FetchResult.extra (또는 fetch_html 결과 dict) 에서 봉투를 조립한다."""
    return build_provenance(
        html,
        raw_sha256=extra.get("content_sha256"),
        requested_url=requested_url,
        final_url=final_url,
        status=extra.get("status_code"),
        fetched_at=extra.get("fetched_at"),
        encoding=extra.get("encoding"),
        fetch_phase=str(extra.get("fetch_phase") or "static"),
        waf_profile=extra.get("waf_profile"),
    )
