#!/usr/bin/env python3
"""itda-email: attachment_validator.py — 첨부파일 사전 검증 모듈."""
from __future__ import annotations

from pathlib import Path

# 프로바이더별 첨부 제한 상수
PROVIDER_LIMITS: dict[str, dict] = {
    "gmail": {
        "max_single_file_mb": 25.0,
        "max_total_mb": 25.0,
        "warn_threshold_ratio": 0.75,
        "warn_large_file_mb": 0.0,
        "blocked_extensions": frozenset({
            ".ade", ".adp", ".apk", ".appx", ".bat", ".cab", ".chm", ".cmd",
            ".com", ".cpl", ".diagcab", ".diagcfg", ".diagpack", ".dll", ".dmg",
            ".exe", ".hta", ".img", ".ins", ".iso", ".isp", ".jar", ".jnlp",
            ".js", ".jse", ".lib", ".lnk", ".mde", ".msc", ".msi", ".msix",
            ".msixbundle", ".msp", ".mst", ".nsh", ".pif", ".ps1", ".scr",
            ".sct", ".shb", ".sys", ".vb", ".vbe", ".vbs", ".vhd", ".vxd",
            ".wsc", ".wsf", ".wsh",
        }),
    },
    "naver": {
        "max_single_file_mb": 10.0,
        "max_total_mb": 20.0,
        "warn_threshold_ratio": 0.75,
        "warn_large_file_mb": 0.0,
        "blocked_extensions": frozenset({
            ".bat", ".cmd", ".com", ".cpl", ".exe", ".js", ".scr", ".vbs", ".wsf",
        }),
    },
    "daum": {
        # Daum/Kakao mail: ~25MB per file, same blocked extensions as Naver.
        # Source: Daum mail help — SMTP attachment limit mirrors webmail limit.
        "max_single_file_mb": 25.0,
        "max_total_mb": 25.0,
        "warn_threshold_ratio": 0.75,
        "warn_large_file_mb": 0.0,
        "blocked_extensions": frozenset({
            ".bat", ".cmd", ".com", ".cpl", ".exe", ".js", ".scr", ".vbs", ".wsf",
        }),
    },
    "icloud": {
        # iCloud Mail: 20MB per attachment, 20MB total.
        # Source: Apple Support — iCloud Mail attachment limits.
        "max_single_file_mb": 20.0,
        "max_total_mb": 20.0,
        "warn_threshold_ratio": 0.75,
        "warn_large_file_mb": 0.0,
        "blocked_extensions": frozenset({
            ".bat", ".cmd", ".com", ".cpl", ".exe", ".js", ".scr", ".vbs", ".wsf",
        }),
    },
    "custom": {
        "max_single_file_mb": 0.0,
        "max_total_mb": 0.0,
        "warn_threshold_ratio": 0.75,
        "warn_large_file_mb": 25.0,  # 경고만 출력, 차단 없음
        "blocked_extensions": frozenset(),
    },
}


def validate_attachments(
    provider: str,
    file_paths: list[str],
) -> tuple[list[dict], list[str]]:
    """첨부파일 검증.

    Args:
        provider: 메일 프로바이더 ('gmail', 'naver', 'custom')
        file_paths: 첨부파일 경로 리스트

    Returns:
        (violations, warnings)
        - violations: 전송 차단 사유 리스트 (빈 리스트 = 통과)
        - warnings: 경고 메시지 리스트 (전송은 허용)
    """
    limits = PROVIDER_LIMITS.get(provider, PROVIDER_LIMITS["custom"])
    violations: list[dict] = []
    warnings: list[str] = []
    total_size_bytes = 0

    for fp in file_paths:
        path = Path(fp)
        ext = path.suffix.lower()

        # 차단 확장자 검사
        if ext in limits["blocked_extensions"]:
            violations.append({
                "file": path.name,
                "reason": "blocked_extension",
                "ext": ext,
            })
            continue

        # 파일 존재 여부
        if not path.exists():
            violations.append({"file": path.name, "reason": "file_not_found"})
            continue

        file_size_bytes = path.stat().st_size
        file_size_mb = file_size_bytes / (1024 * 1024)

        max_single = limits["max_single_file_mb"]
        warn_ratio = limits["warn_threshold_ratio"]

        # 단일 파일 크기 초과 차단 (초과 시 총합에 포함하지 않음)
        if max_single > 0 and file_size_mb > max_single:
            violations.append({
                "file": path.name,
                "reason": "size_exceeded",
                "size_mb": round(file_size_mb, 2),
                "limit_mb": max_single,
            })
            continue

        total_size_bytes += file_size_bytes

        # Base64 오버헤드 경고 (단일 파일 한도의 75% 초과)
        if max_single > 0:
            single_warn_mb = max_single * warn_ratio
            if file_size_mb > single_warn_mb:
                warnings.append(
                    f"파일 '{path.name}' ({file_size_mb:.1f}MB)이 "
                    f"{provider.upper()} 단일 파일 한도({max_single:.0f}MB)의 75%를 초과합니다. "
                    f"Base64 인코딩 후 제한을 초과할 수 있습니다."
                )

        # custom 전용: 권장 크기 초과 경고 (차단 없음)
        warn_large = limits["warn_large_file_mb"]
        if warn_large > 0 and file_size_mb > warn_large:
            warnings.append(
                f"파일 '{path.name}' ({file_size_mb:.1f}MB)이 권장 크기({warn_large:.0f}MB)를 초과합니다. "
                f"메일 서버에 따라 전송이 실패할 수 있습니다."
            )

    # 총합 크기 초과 검사 (차단되지 않은 파일들의 합)
    total_size_mb = total_size_bytes / (1024 * 1024)
    max_total = limits["max_total_mb"]
    if max_total > 0 and total_size_mb > max_total:
        violations.append({
            "file": "__total__",
            "reason": "total_size_exceeded",
            "size_mb": round(total_size_mb, 2),
            "limit_mb": max_total,
        })

    return violations, warnings
