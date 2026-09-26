"""IMAP draft 스크립트(save/send/delete/read/list)가 공유하는 오류·정리·접속 헬퍼.

5개 draft 스크립트가 동일하게 반복하던 예외 출력(JSON→stderr→exit 1),
finally 시 IMAP logout 정리, RFC 2047 헤더 디코딩, Drafts 폴더 해석,
IMAP 접속 preamble 을 한 곳으로 모은다. sibling import 로 사용:

    from _draft_imap import fail, safe_logout, decode_header, connect_drafts

배포 격리: email 스킬 내부(scripts/) sibling 모듈이므로 각 스크립트가
sys.path.insert(0, __file__.parent) 후 import 한다(env_loader·email_providers 동형).

⚠️ 테스트 계약: 각 스크립트는 merged_env()·get_provider() 호출을 자기 모듈에
유지한다(테스트가 `<script>.merged_env` 를 monkeypatch 하는 표면). 이 모듈은
그 이후 단계(자격 검증→접속→select)만 받는다.
"""

from __future__ import annotations

import email.header
import imaplib
import json
import sys
from typing import NoReturn

from email_providers import resolve_provider_name

# argparse --provider choices (draft 스크립트 5종 공통)
PROVIDER_CHOICES = ["naver", "google", "gmail", "daum", "icloud", "custom"]

# provider별 Drafts 폴더 이름
_DRAFTS_FOLDER: dict[str, str] = {
    "naver": "Drafts",
    "google": "[Gmail]/Drafts",
    "daum": "Drafts",
    "custom": "Drafts",
}


def fail(error_key: str, detail: str) -> NoReturn:
    """오류를 {"error", "detail"} JSON 으로 stderr 에 출력하고 exit 1.

    IMAP4.error·network 오류 등 draft 스크립트의 종단 실패 경로가 공유한다.
    """
    print(json.dumps({"error": error_key, "detail": detail}), file=sys.stderr)
    sys.exit(1)


def fail_uid_not_found(uid: int) -> NoReturn:
    """UID 부재를 {"error": "uid_not_found", "uid": N} JSON 으로 출력하고 exit 1."""
    print(json.dumps({"error": "uid_not_found", "uid": uid}), file=sys.stderr)
    sys.exit(1)


def safe_logout(imap) -> None:
    """IMAP 연결이 열려 있으면 조용히 logout 한다(finally 정리용).

    imap 이 None 이거나 logout 이 실패해도 예외를 전파하지 않는다.
    """
    if imap is not None:
        try:
            imap.logout()
        except Exception:
            pass


def decode_header(raw: str) -> str:
    """RFC 2047 인코딩된 이메일 헤더를 UTF-8 문자열로 디코딩한다."""
    parts = []
    for chunk, charset in email.header.decode_header(raw or ""):
        if isinstance(chunk, bytes):
            for enc in [charset or "utf-8", "utf-8", "euc-kr", "cp949", "latin-1"]:
                try:
                    parts.append(chunk.decode(enc))
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            else:
                parts.append(chunk.decode("latin-1", errors="replace"))
        else:
            parts.append(chunk or "")
    return "".join(parts)


def get_drafts_folder(provider_name: str) -> str:
    """provider 이름으로 Drafts 폴더 경로를 반환한다."""
    canonical = resolve_provider_name(provider_name)
    return _DRAFTS_FOLDER.get(canonical, "Drafts")


def require_credentials(provider_cfg: dict | None, provider: str) -> None:
    """provider 설정에 email/password 가 없으면 credentials_missing 으로 exit 1."""
    if not provider_cfg or not provider_cfg.get("email") or not provider_cfg.get("password"):
        print(
            json.dumps({
                "error": "credentials_missing",
                "detail": f"provider '{provider}'에 대한 인증 정보가 없습니다.",
            }),
            file=sys.stderr,
        )
        sys.exit(1)


def connect_drafts(
    provider_cfg: dict,
    folder: str | None = None,
    readonly: bool = False,
) -> imaplib.IMAP4_SSL:
    """IMAP SSL 접속 + login (+ folder select) 공통 preamble.

    folder=None 이면 select 를 생략한다(save_draft 의 APPEND 경로).
    login/select 실패 시 연결을 정리한 뒤 예외를 그대로 전파한다
    (호출자의 except imaplib.IMAP4.error → fail 경로 보존).
    """
    imap = imaplib.IMAP4_SSL(
        provider_cfg["imap_host"],
        provider_cfg["imap_port"],
    )
    try:
        imap.login(provider_cfg["email"], provider_cfg["password"])
        if folder is not None:
            imap.select(folder, readonly=readonly)
    except BaseException:
        safe_logout(imap)
        raise
    return imap


def first_message_bytes(fetch_data: list | None) -> bytes | None:
    """IMAP FETCH 응답에서 첫 메시지 바이트를 추출한다. 없으면 None."""
    if not fetch_data or fetch_data[0] is None:
        return None
    for item in fetch_data:
        if isinstance(item, tuple) and len(item) >= 2:
            return item[1]
    return None


def fetch_message(imap: imaplib.IMAP4_SSL, uid: int) -> bytes | None:
    """IMAP에서 UID로 전체 메시지 바이트를 가져온다. UID가 없으면 None을 반환한다."""
    _status, fetch_data = imap.uid("FETCH", str(uid).encode(), "(BODY[])")
    return first_message_bytes(fetch_data)
