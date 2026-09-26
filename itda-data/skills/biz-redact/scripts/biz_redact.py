#!/usr/bin/env python3
"""biz_redact.py — 업무 문서 영업기밀 마스킹·왕복 복원 게이트 코어.

사용자 용어집(glossary.json) 기반 **결정론 마스킹 게이트**. 로컬 Python 이 AI 접촉
전에 영업기밀(거래처명·프로젝트코드·담당자·단가 등 용어집 등재 항목)을 토큰으로
치환하고, AI 산출물의 토큰을 원값으로 왕복 복원하며, 잔존·변형을 검증한다.

stdlib only (re·json·argparse·hashlib·datetime·pathlib·os). 외부 의존 0.

핵심 원리:
- 토큰 = ⟦{category}_{n}⟧ (예: ⟦거래처_1⟧). n 은 카테고리 내 entry 정의 순번.
  용어집이 순번의 진실 소스이므로 같은 용어집을 쓰는 모든 문서에서 토큰이 일관된다.
- 원값 평문은 map.json 에만 존재. masked.txt·report.json·verify/restore 리포트·
  audit.jsonl 은 기밀값 미포함(에이전트 가독 신뢰 산출물).
- 예상외 실패(자체 잔존 검증 실패·map 무결성 위반·변형 토큰)는 조용히 우회하지
  않고 exit≠0 으로 표면화한다(no-silent-fallback).

CLI:
  # 1) 마스킹 (masked.txt / map.json / report.json 생성, report JSON 을 stdout 으로도)
  python3 biz_redact.py mask <input.txt> --glossary <glossary.json> \\
      [--out-dir <dir>] [--doc-id <id>] [--now <ISO8601>] [--audit-log <path>]
  # 2) 잔존 검증 (리포트 JSON stdout)
  python3 biz_redact.py verify <text.txt> --glossary <glossary.json>
  # 3) 왕복 복원 + 변형 감지 (restored 파일 생성, 복원 리포트 JSON stdout)
  python3 biz_redact.py restore <ai_output.txt> --map <map.json> \\
      [--out <restored.txt>] [--now <ISO8601>] [--audit-log <path>]

  Windows: python3 → `py -3`

exit code: 0 성공 / 1 게이트 실패(잔존·변형·환각) / 2 사용 오류(입력없음·스키마 위반).

라이브러리:
  from biz_redact import mask, verify, restore
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

if sys.version_info < (3, 10):
    sys.exit("Python 3.10+ 가 필요합니다.")

SCHEMA_VERSION = "1.0"

# 토큰: ⟦{category}_{n}⟧ — category 는 공백·꺾쇠(⟦⟧) 불가·1~24자, n 은 1~4자리.
# rsplit("_", 1) 결정론 파싱과 등가인 greedy 매칭(category 내 _ 허용).
TOKEN_RE = re.compile(r"⟦([^⟦⟧\s]{1,24})_(\d{1,4})⟧")

WORKSPACE_ROOT = Path("_workspace/biz-redact")


# ──────────────────────────────────────────────────────────────────
# 예외 — exit code 매핑
# ──────────────────────────────────────────────────────────────────


class UsageError(Exception):
    """exit 2 — 사용 오류(입력 파일 없음·glossary/map 스키마 위반).

    보안 원칙: 메시지에 기밀값(value/alias)을 절대 넣지 않는다. entry 는 인덱스로만
    참조한다(stderr 도 에이전트가 읽을 수 있으므로 평문 유출 차단).
    """


# ──────────────────────────────────────────────────────────────────
# 직렬화 / I/O — 결정론·바이트 보존
# ──────────────────────────────────────────────────────────────────


def _dump_json(obj) -> str:
    """map·report·verify/restore 리포트용 — ensure_ascii=False·sort_keys·indent=2 + 말미 개행."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _dump_json_line(obj) -> str:
    """audit 라인용 — 1줄(indent 없음) + 말미 개행."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n"


def _read_text(path: Path) -> str:
    """UTF-8·newline="" 로 읽어 개행(\\r\\n/\\n)·마지막 개행을 원형 보존.

    비 UTF-8(예: cp949) 입력은 traceback 대신 명시 UsageError(exit 2)로 표면화한다.
    """
    try:
        with open(path, encoding="utf-8", newline="") as f:
            return f.read()
    except FileNotFoundError:
        raise UsageError(f"입력 파일이 없습니다: {path}")
    except UnicodeDecodeError:
        raise UsageError(f"UTF-8 텍스트가 아닙니다(UTF-8 로 저장해 다시 시도): {path}")


def _restrict_opener(path, flags):
    """평문 기밀 파일 생성 opener — mode 0o600(owner rw only)."""
    return os.open(path, flags, 0o600)


def _write_atomic(path: Path, content: str, *, secret: bool = False) -> None:
    """임시 파일에 쓰고 os.replace 로 원자적 승격(부분 파일 방지).

    secret=True 는 평문 기밀 산출물(map.json·restored.txt)로, group/other 가독을 막기
    위해 **0600** 으로 생성한다(POSIX). rename 은 tmp 의 inode·mode 를 그대로 승격하므로
    최종 파일도 0600 이다. 비기밀(masked.txt·report.json·audit.jsonl)은 기본 umask 유지.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    opener = _restrict_opener if secret else None
    with open(tmp, "w", encoding="utf-8", newline="", opener=opener) as f:
        if secret and hasattr(os, "fchmod"):
            os.fchmod(f.fileno(), 0o600)  # 기존 tmp 잔재의 느슨한 권한도 강제 조임
        f.write(content)
    os.replace(tmp, path)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _nfc(s: str) -> str:
    """유니코드 NFC 정규화.

    macOS 등에서 흔한 NFD(분해형) 한글 문서에서 등재 기밀이 안 가려지는(조용한
    위음성) 것을 막기 위해, 매칭 전 텍스트·표면형을 NFC 로 통일한다. 안전 우선 —
    기밀 마스킹이 원문 바이트 보존보다 우선한다(원문이 NFD 였으면 리포트에 플래그).
    NFC 는 결정론적이라 같은 입력 → 같은 출력이 유지된다.
    """
    return unicodedata.normalize("NFC", s)


def _norm_key(s: str) -> str:
    """검증 비교용 정규화 키 — 매처와 동일 기준(NFC + **ASCII 한정** casefold).

    validate_glossary 의 모든 비교 사이트(중복·category/name 비기밀·겹침)는 이 키로
    비교한다. 매처(_compile_matcher)는 표면형을 NFC 로 통일하고 **순수 ASCII 알파벳만**
    case-insensitive 로 매칭하며 그 외(한국어·혼합·비ASCII)는 exact(대소문자 구분)로
    매칭한다. 검증 casefold 를 ASCII 에 한정해 이 의미론과 1:1 로 맞춘다 — 'HDEL'·'hdel'
    (ASCII) 은 여전히 동형으로 차단하되, 'straße'·'strasse'(비ASCII ß) 는 매처가 별개로
    보므로 검증도 별개로 취급한다('매칭은 다른데 검증만 같게 보는' 역방향 불일치 제거).
    """
    n = _nfc(s)
    return n.casefold() if n.isascii() else n


# ──────────────────────────────────────────────────────────────────
# 용어집 로드·검증 (C1)
# ──────────────────────────────────────────────────────────────────


def _default_warn(msg: str) -> None:
    sys.stderr.write(msg + "\n")


MAX_ENTRIES_PER_CATEGORY = 9999  # 토큰 번호 \d{1,4} 상한(TOKEN_RE 와 정합)


def _label_overlap_action(label_nfc: str, surface_nfc: str):
    """비기밀 라벨(name/category) ↔ 표면형 겹침 판정 — 방향 인지형(과차단 완화).

    반환: "block" | "warn" | None. 입력은 NFC 정규화된 문자열.

    - **동일**(casefold) 또는 **기밀 전체가 라벨에 포함**(casefold) → block.
      토큰·리포트에 노출되는 라벨이 기밀 case-variant 를 그대로 드러내거나, 라벨 경유로
      기밀 전체가 새기 때문(실증 공격: category 'HDEL' + value 'hdel').
    - **라벨이 기밀 속 부분문자열**: 원문(NFC, 대소문자 구분) 일치면 block(실제 텍스트
      겹침 — R2 동작 유지), casefold 로만 걸리는 우연 겹침('IT' ⊂ 'digital…')이면 warn
      으로 완화 — 짧은 ASCII 라벨(IT·PO·PJ) 사용성 복원.
    """
    # 라벨 검사는 **full casefold** — 혼합 스크립트 라벨('PJ담당')의 ASCII 부분('PJ')도
    # 접어야 기밀 'pj'/'PJ' 노출을 잡는다(보안 검사라 보수적. dedup 의 ASCII 한정과 별개).
    nl = label_nfc.casefold()
    ns = surface_nfc.casefold()
    if ns in nl:                       # 동일 or 기밀이 라벨에 포함 → 차단
        return "block"
    if nl in ns:                       # 라벨이 기밀 부분문자열
        if label_nfc in surface_nfc:   # 원문 대소문자 구분 실제 겹침 → 차단
            return "block"
        return "warn"                  # casefold-only 우연 겹침 → 경고(차단 안 함)
    return None


def validate_glossary(data, *, warn=None) -> None:
    """용어집 스키마 검증. 위반 = UsageError(exit 2).

    검증: 필수 키·타입, name·category 비기밀 제약, 표면형 최소 길이 2,
    표면형 중복, 토큰 패턴 포함 금지, 표면형이 생성 토큰의 부분문자열 금지(토큰 내부
    기밀 은닉 차단), 카테고리당 entry 상한, 생성 토큰 전역 유일성. 짧은(2~3자)
    단어경계 미적용 표면형은 오폭 위험 WARN(stderr) 하되 차단하지 않는다.

    **정규화 통일**: 모든 비교(중복·category/name 비기밀·겹침·부분문자열)는 `_norm_key`
    (NFC + ASCII casefold)로 판정한다 — 매처와 동일 기준이어야 '매칭은 같게 보나 검증은
    다르게 봐서 통과'하는 회피(category 'HDEL'+value 'hdel', NFC/NFD 이중등재, NFD
    겹침 우회, NFD 표면형 min-length 우회)가 생기지 않는다.

    보안: 에러/경고 메시지에 기밀값을 넣지 않는다(entry 인덱스로만 참조).
    """
    warn = warn or _default_warn
    if not isinstance(data, dict):
        raise UsageError("용어집 최상위는 객체여야 합니다.")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise UsageError(f"용어집 schema_version 은 '{SCHEMA_VERSION}' 이어야 합니다.")
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise UsageError("용어집 name 은 비어있지 않은 문자열이어야 합니다.")
    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        raise UsageError("용어집 entries 는 비어있지 않은 배열이어야 합니다.")

    seen_surface = {}   # _norm_key(surface) -> 최초 등장 entry index (중복 검출)
    all_surfaces = []   # (nfc_surface, entry_index)
    norm_cats = []      # entry 순서의 NFC category (겹침 검사용)
    tokens = []         # 생성 토큰(부분문자열·전역 유일성 검증용, NFC category 기반)
    cat_counts = {}

    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            raise UsageError(f"entries[{i}] 는 객체여야 합니다.")
        cat = e.get("category")
        val = e.get("value")
        aliases = e.get("aliases", [])

        # category 검증 — NFC 정규화 후 판정(토큰 생성 기준과 동일)
        if not isinstance(cat, str) or not cat:
            raise UsageError(f"entries[{i}].category 는 비어있지 않은 문자열이어야 합니다.")
        norm_cat = _nfc(cat)
        if not (1 <= len(norm_cat) <= 24):
            raise UsageError(f"entries[{i}].category 는 1~24자여야 합니다.")
        if "⟦" in norm_cat or "⟧" in norm_cat or any(ch.isspace() for ch in norm_cat):
            raise UsageError(f"entries[{i}].category 에 공백·꺾쇠(⟦⟧) 를 쓸 수 없습니다.")
        norm_cats.append(norm_cat)

        # value 검증
        if not isinstance(val, str) or not val:
            raise UsageError(f"entries[{i}].value 는 비어있지 않은 문자열이어야 합니다.")

        # aliases 검증
        if not isinstance(aliases, list):
            raise UsageError(f"entries[{i}].aliases 는 배열이어야 합니다.")
        for a in aliases:
            if not isinstance(a, str) or not a:
                raise UsageError(f"entries[{i}].aliases 원소는 비어있지 않은 문자열이어야 합니다.")

        # 표면형(value + aliases) 검증 — NFC 정규화 후(min-length·중복·부분문자열 모두)
        for surface in [val] + list(aliases):
            nfc_surface = _nfc(surface)
            if len(nfc_surface) < 2:  # NFC 기준 길이(NFD "가"=2코드포인트 우회 차단)
                raise UsageError(f"entries[{i}] 표면형 최소 길이는 2 입니다.")
            if "⟦" in nfc_surface or "⟧" in nfc_surface:
                raise UsageError(f"entries[{i}] 표면형에 토큰 문자(⟦⟧) 를 쓸 수 없습니다.")
            # 중복은 _norm_key(NFC+casefold) 로 판정 — 매처가 ASCII IGNORECASE·NFC 라
            # 'HDEL'·'hdel'·NFC/NFD 동형은 같은 텍스트를 가로채는 이중 등재다.
            key = _norm_key(surface)
            if key in seen_surface:
                raise UsageError(
                    f"표면형 중복(정규화 동형): entries[{i}] 가 "
                    f"entries[{seen_surface[key]}] 와 같은 텍스트를 등재했습니다"
                    "(결정론 붕괴 방지)."
                )
            seen_surface[key] = i
            all_surfaces.append((nfc_surface, i))
            # 짧은(2~3자) 단어경계 미적용 표면형은 일반 텍스트에 substring 오폭 위험 →
            # WARN(차단 안 함). NFC 기준 길이·모드로 판정. 과마스킹은 안전 방향.
            if 2 <= len(nfc_surface) <= 3 and not _is_ascii_mode(nfc_surface):
                warn(
                    f"[WARN] entries[{i}] 의 짧은 표면형(2~3자, 단어경계 미적용)은 일반 "
                    "텍스트와 오폭할 수 있습니다(사용자 선택 존중, 차단하지 않음)."
                )

        # 토큰 생성(NFC category, 순번 = 카테고리 내 entry 정의 순번) + 카테고리당 상한
        cat_counts[norm_cat] = cat_counts.get(norm_cat, 0) + 1
        if cat_counts[norm_cat] > MAX_ENTRIES_PER_CATEGORY:
            raise UsageError(
                f"카테고리당 entry 수 상한({MAX_ENTRIES_PER_CATEGORY})을 초과했습니다"
                "(토큰 번호 4자리 초과 → 토큰 파싱 붕괴 방지)."
            )
        tokens.append(f"⟦{norm_cat}_{cat_counts[norm_cat]}⟧")

    # name·category ↔ 표면형 겹침 — 둘 다 토큰·리포트·감사로그에 노출되는 비기밀 라벨이라
    # 기밀값(value/alias)과 실질 겹침이면 차단한다. 방향 인지형(_label_overlap_action):
    # 동일·기밀⊆라벨·라벨이 기밀에 원문 겹침 = 차단, casefold 우연 겹침만 = WARN.
    name_nfc = _nfc(name)
    for nfc_surface, _si in all_surfaces:
        action = _label_overlap_action(name_nfc, nfc_surface)
        if action == "block":
            raise UsageError(
                "용어집 name 이 표면형(value/alias)과 동일하거나 기밀을 포함/노출하는 "
                "관계입니다. name 은 리포트·감사로그에 노출되는 비기밀 라벨이어야 합니다."
            )
        if action == "warn":
            warn(
                f"[WARN] entries[{_si}] 표면형이 용어집 name 과 대소문자 무시 시 우연히 "
                "겹칩니다(원문 불일치 — 차단하지 않음)."
            )
    for i, norm_cat in enumerate(norm_cats):
        for nfc_surface, _si in all_surfaces:
            action = _label_overlap_action(norm_cat, nfc_surface)
            if action == "block":
                raise UsageError(
                    f"entries[{i}].category 가 표면형(value/alias)과 동일하거나 기밀을 "
                    "포함/노출하는 관계입니다. category 는 토큰·리포트에 노출되는 비기밀 "
                    "라벨이어야 하므로 기밀값과 겹칠 수 없습니다."
                )
            if action == "warn":
                warn(
                    f"[WARN] entries[{i}].category 가 entries[{_si}] 표면형과 대소문자 "
                    "무시 시 우연히 겹칩니다(원문 불일치 — 차단하지 않음)."
                )

    # 표면형이 생성 토큰의 부분문자열이면 거부 — 그런 표면형(예 value '_1' / case-variant
    # 'pj_1')은 토큰 내부에 노출되고 잔존 스캔이 토큰을 격리하므로 검사를 회피한다.
    # 토큰 **interior**(브래킷 제외 `{cat}_{n}`)로 _norm_key 비교 — ASCII 카테고리 interior
    # ('PJ_1')는 casefold 되어 case-variant('pj_1')를 잡고, 비ASCII interior('거래처_1')는
    # exact 로 매처와 정합. 토큰 문자 알파벳 밖이면 조기 skip(성능).
    norm_tokens = [_norm_key(t[1:-1]) for t in tokens]
    token_alphabet = set("_0123456789")
    for norm_cat in norm_cats:
        token_alphabet.update(_norm_key(norm_cat))
    for nfc_surface, i in all_surfaces:
        ns = _norm_key(nfc_surface)
        if not set(ns) <= token_alphabet:
            continue
        if any(ns in nt for nt in norm_tokens):
            raise UsageError(
                f"entries[{i}] 표면형이 생성 토큰의 부분문자열입니다 — 토큰 내부에 "
                "기밀이 은닉돼 잔존 검사를 회피할 수 있습니다."
            )

    # 생성 토큰 전역 유일성(구성상 충돌 불가하나 방어적 재검증)
    if len(set(tokens)) != len(tokens):
        raise UsageError("생성 토큰 전역 유일성 위반(내부 불변식 오류).")


def _load_glossary_file(path: Path):
    """(raw_bytes, validated_dict) 반환. glossary_sha256 은 raw_bytes 기준."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise UsageError(f"용어집 파일이 없습니다: {path}")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UsageError(f"용어집 JSON 파싱 실패: {exc}")
    validate_glossary(data)
    return raw, data


# ──────────────────────────────────────────────────────────────────
# 매칭 — 표면형 → 매처 (C2.3)
# ──────────────────────────────────────────────────────────────────


def _is_ascii_mode(surface: str) -> bool:
    """ASCII 알파벳을 포함한 순수 ASCII 표면형 = case-insensitive + 단어 경계."""
    return surface.isascii() and any(ch.isalpha() for ch in surface)


def _compile_matcher(surface: str) -> re.Pattern:
    """표면형 매처.

    - ASCII 알파벳 표면형: case-insensitive + ASCII 영숫자 경계(HDEL 이 SHDELL
      내부에 오매칭되지 않게; 한국어 인접은 허용).
    - 그 외(한국어·혼합): 정확 부분문자열(조사 인접 "현대엘리베이터를" 정상 매칭).
    """
    if _is_ascii_mode(surface):
        return re.compile(
            r"(?<![A-Za-z0-9])" + re.escape(surface) + r"(?![A-Za-z0-9])",
            re.IGNORECASE,
        )
    return re.compile(re.escape(surface))


def _build_surfaces(glossary: dict) -> list:
    """표면형 디스크립터 목록을 (길이 내림차순, 정의 순서) 로 정렬해 반환.

    각 원소: {surface, token, category, value, entry_index, def_order, matcher}
    토큰 순번 n = 카테고리 내 entry 정의 순번(1부터) — 매칭과 무관, 용어집 위치가 진실 소스.
    """
    surfaces = []
    cat_counts = {}
    order = 0
    for i, e in enumerate(glossary["entries"]):
        cat = _nfc(e["category"])  # NFC 정규화 — 토큰 생성 기준을 validate_glossary 와 통일
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        token = f"⟦{cat}_{cat_counts[cat]}⟧"
        val = _nfc(e["value"])  # NFC 정규화 — NFD 문서와의 표면형 정합(조용한 위음성 차단)
        for surface in [val] + [_nfc(a) for a in e.get("aliases", [])]:
            surfaces.append({
                "surface": surface,
                "token": token,
                "category": cat,
                "value": val,
                "entry_index": i,
                "def_order": order,
                "matcher": _compile_matcher(surface),
            })
            order += 1
    # ① 길이 내림차순 ② 동률 시 정의 순서(먼저 정의된 표면형이 이긴다)
    surfaces.sort(key=lambda s: (-len(s["surface"]), s["def_order"]))
    return surfaces


# ──────────────────────────────────────────────────────────────────
# 토큰 격리 스캔 — mask 자체검증 / verify / restore 평문 유출 공용
# ──────────────────────────────────────────────────────────────────


def _free_segments(text: str, valid_tokens):
    """발행 가능 토큰(⟦…⟧) 영역을 제외한 (절대 offset, 조각) 목록.

    격리는 **현 용어집/맵이 실제로 발행 가능한 토큰 집합**(valid_tokens)에 한정한다.
    TOKEN_RE 문법에만 맞고 발행 불가한 ⟦…⟧(예: 기밀을 토큰 문법으로 감싼 변조
    `⟦현대엘리베이터_1⟧`)는 격리하지 않고 일반 텍스트로 두어 잔존 스캔 대상이 되게 한다.
    """
    segs = []
    last = 0
    for m in TOKEN_RE.finditer(text):
        if m.group(0) not in valid_tokens:
            continue  # 발행 불가 토큰 문법 → 일반 텍스트로 취급(격리하지 않음)
        if m.start() > last:
            segs.append((last, text[last:m.start()]))
        last = m.end()
    if last < len(text):
        segs.append((last, text[last:]))
    return segs


def _scan_occurrences(text: str, descriptors: list):
    """토큰 격리 후 각 표면형의 출현 위치를 스캔.

    반환: [(descriptor, positions)] — positions 는 0-base 코드포인트 [start, end) 목록.
    출현이 0 인 표면형은 제외한다. 격리 대상 토큰은 descriptors 가 발행하는 토큰 집합.
    """
    valid_tokens = {d["token"] for d in descriptors}
    segs = _free_segments(text, valid_tokens)
    out = []
    for d in descriptors:
        matcher = d["matcher"]
        positions = []
        for offset, content in segs:
            for m in matcher.finditer(content):
                positions.append([offset + m.start(), offset + m.end()])
        if positions:
            positions.sort()
            out.append((d, positions))
    return out


def _self_verify(masked_text: str, glossary: dict) -> int:
    """마스킹 결과의 자체 잔존 검증 — 잔존 출현 수를 반환.

    module-level 로 두어 산출 원자성(실패 시 미승격) 테스트에서 주입할 수 있게 한다.
    """
    surfaces = _build_surfaces(glossary)
    return sum(len(pos) for _d, pos in _scan_occurrences(masked_text, surfaces))


# ──────────────────────────────────────────────────────────────────
# mask (C2)
# ──────────────────────────────────────────────────────────────────


def mask(text: str, glossary: dict, *, glossary_sha256: str, doc_id: str, now: str):
    """결정론 치환. (masked_text, map_dict, report_dict) 반환.

    - 입력 텍스트·표면형을 NFC 정규화 후 처리(NFD 문서의 조용한 위음성 차단).
      원문이 NFD 였으면 report.normalized=True 로 정직 표기한다(바이트 roundtrip 은
      NFC 문서 기준 — SKILL.md 한계 참조).
    - 표면형을 (길이 내림차순 → 정의 순서) 우선순위로 순차 전역 치환.
    - 이미 치환된 토큰 영역은 후속 매칭에서 격리(토큰 내부 재매칭 방지).
    - map.json 에만 원값 평문 존재; report.json 은 기밀값 미포함.
    - 자체 잔존 검증(_self_verify) 결과를 report.residual_count/result 로 고정.
    """
    # 라이브러리 진입점 가드 — CLI 미경유 직접 호출에서도 스키마·비기밀 제약을 강제한다
    # (WARN 은 중복 억제; 하드 거부만 필요). category=기밀 같은 위반은 여기서 exit 2.
    validate_glossary(glossary, warn=lambda _m: None)
    norm_text = _nfc(text)
    normalized = norm_text != text
    text = norm_text
    surfaces = _build_surfaces(glossary)

    segments = [("free", text)]
    entry_data = {}  # entry_index -> {token, category, value, matched_surfaces:{surface:count}}

    for s in surfaces:
        matcher = s["matcher"]
        token = s["token"]
        count = 0
        new_segments = []
        for kind, content in segments:
            if kind == "token":
                new_segments.append((kind, content))
                continue
            last = 0
            for m in matcher.finditer(content):
                if m.start() > last:
                    new_segments.append(("free", content[last:m.start()]))
                new_segments.append(("token", token))
                last = m.end()
                count += 1
            if last < len(content):
                new_segments.append(("free", content[last:]))
        if count > 0:
            d = entry_data.setdefault(s["entry_index"], {
                "token": token,
                "category": s["category"],
                "value": s["value"],
                "matched_surfaces": {},
            })
            d["matched_surfaces"][s["surface"]] = count
        segments = new_segments

    masked = "".join(content for _kind, content in segments)

    matched_indices = sorted(entry_data.keys())  # 정의 순서 = 결정론
    # map 에 entry 의 전체 alias(NFC)를 기록 — restore 평문유출 스캔이 문서에 안 쓰인
    # 다른 표면형까지 포괄해 AI 가 대표값·타 alias 를 평문 재생산해도 감지하게 한다.
    map_entries = [{
        "token": entry_data[i]["token"],
        "category": entry_data[i]["category"],
        "value": entry_data[i]["value"],
        "aliases": [_nfc(a) for a in glossary["entries"][i].get("aliases", [])],
        "matched_surfaces": entry_data[i]["matched_surfaces"],
    } for i in matched_indices]

    map_dict = {
        "schema_version": SCHEMA_VERSION,
        "doc_id": doc_id,
        "glossary_name": glossary["name"],
        "glossary_sha256": glossary_sha256,
        "created_at": now,
        "entries": map_entries,
    }

    tokens = [entry_data[i]["token"] for i in matched_indices]
    # by_category = 카테고리별 **치환 출현 건수**(occurrence) — matched_surfaces 합.
    # restore·matched_surfaces 와 같은 occurrence 의미로 통일(감사 정확성).
    # tokens_total 은 별개로 **고유 토큰 수**(len(tokens)).
    by_category = {}
    for i in matched_indices:
        cat = entry_data[i]["category"]
        occ = sum(entry_data[i]["matched_surfaces"].values())
        by_category[cat] = by_category.get(cat, 0) + occ

    residual_count = _self_verify(masked, glossary)
    result = "pass" if residual_count == 0 else "fail"

    report_dict = {
        "schema_version": SCHEMA_VERSION,
        "doc_id": doc_id,
        "glossary_name": glossary["name"],
        "glossary_sha256": glossary_sha256,
        "created_at": now,
        "by_category": by_category,
        "tokens_total": len(tokens),
        "tokens": tokens,
        "residual_count": residual_count,
        "normalized": normalized,
        "result": result,
    }
    return masked, map_dict, report_dict


# ──────────────────────────────────────────────────────────────────
# verify (C3)
# ──────────────────────────────────────────────────────────────────


def verify(text: str, glossary: dict) -> dict:
    """잔존 검증 리포트(평문 미수록).

    스키마: {"verified", "residual_count", "residuals":[{category, entry_index,
    surface_len, positions}], "normalized"} — entry_index 는 용어집 0-base,
    positions 0-base [start,end). 입력 텍스트를 NFC 정규화 후 스캔한다(mask 와 동일 —
    NFD 문서에서 verified=true 로 조용히 통과하던 위음성 차단). normalized=원문 NFD 여부.
    """
    validate_glossary(glossary, warn=lambda _m: None)  # 라이브러리 진입점 가드(mask 동형)
    norm_text = _nfc(text)
    normalized = norm_text != text
    surfaces = _build_surfaces(glossary)
    residuals = []
    for d, positions in _scan_occurrences(norm_text, surfaces):
        residuals.append({
            "category": d["category"],
            "entry_index": d["entry_index"],
            "surface_len": len(d["surface"]),
            "positions": positions,
        })
    residuals.sort(key=lambda r: (r["entry_index"], r["surface_len"], r["positions"][0]))
    residual_count = sum(len(r["positions"]) for r in residuals)
    return {
        "verified": residual_count == 0,
        "residual_count": residual_count,
        "residuals": residuals,
        "normalized": normalized,
    }


# ──────────────────────────────────────────────────────────────────
# restore (C4)
# ──────────────────────────────────────────────────────────────────


def validate_map(data) -> None:
    """map.json 무결성 선검증. 위반 = UsageError(exit 2).

    변조·중복 토큰·형식 오류는 조용히 적용하지 않는다(no-silent-fallback).
    토큰 문자열은 비기밀(category+번호)이라 메시지에 노출해도 안전하다.
    """
    if not isinstance(data, dict):
        raise UsageError("map 최상위는 객체여야 합니다.")
    # created_at 포함 필수 키 전부 존재 확인 — 잘린 map(created_at 누락)이 성공 처리되지 않게.
    for key in ("schema_version", "doc_id", "glossary_name", "glossary_sha256",
                "created_at", "entries"):
        if key not in data:
            raise UsageError(f"map 필수 키 누락: {key}")
    if data["schema_version"] != SCHEMA_VERSION:
        raise UsageError(f"map schema_version 은 '{SCHEMA_VERSION}' 이어야 합니다.")
    # 필드 타입 검증 — 변조 map(doc_id=int·sha256=dict 등)이 조용히 처리되지 않게.
    for key in ("doc_id", "glossary_name", "glossary_sha256", "created_at"):
        if not isinstance(data[key], str) or not data[key]:
            raise UsageError(f"map.{key} 는 비어있지 않은 문자열이어야 합니다.")
    entries = data["entries"]
    if not isinstance(entries, list):
        raise UsageError("map.entries 는 배열이어야 합니다.")
    seen_tokens = set()
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            raise UsageError(f"map.entries[{i}] 는 객체여야 합니다.")
        for k in ("token", "category", "value"):
            if not isinstance(e.get(k), str) or not e.get(k):
                raise UsageError(f"map.entries[{i}].{k} 는 비어있지 않은 문자열이어야 합니다.")
        tok = e["token"]
        # 메시지에 tok 원문을 넣지 않는다 — 변조 토큰에 기밀이 들어있으면 stderr 로
        # 평문이 샌다(기밀 미노출 자기계약, entry 인덱스만 참조).
        if not TOKEN_RE.fullmatch(tok):
            raise UsageError(f"map.entries[{i}].token 형식이 올바르지 않습니다(⟦범주_번호⟧).")
        if tok in seen_tokens:
            raise UsageError(f"map.entries[{i}].token 이 앞선 entry 와 중복입니다.")
        seen_tokens.add(tok)
        # matched_surfaces 는 필수 — 누락을 허용하면 restore 평문유출 스캔이 조용히
        # 생략된다(선택 항목이면 변조 map 으로 유출 감지를 무력화할 수 있음).
        ms = e.get("matched_surfaces")
        if not isinstance(ms, dict):
            raise UsageError(
                f"map.entries[{i}].matched_surfaces 는 필수 객체입니다"
                "(누락 시 평문유출 스캔 생략 방지)."
            )
        # aliases 는 선택(구 map 하위호환) — 존재하면 문자열 배열이어야 한다.
        al = e.get("aliases", [])
        if not isinstance(al, list) or any(not isinstance(a, str) or not a for a in al):
            raise UsageError(f"map.entries[{i}].aliases 는 비어있지 않은 문자열의 배열이어야 합니다.")


def restore(ai_output: str, map_data: dict, *, now: str):
    """왕복 복원 + 변형 감지. (restored_text, report_dict) 반환.

    - 산출물을 NFC 정규화 후 처리(NFD AI 산출물의 토큰·표면형 정합). normalized 플래그 표기.
    - map 토큰 → 대표값(value) 치환. alias 로 매칭됐던 출현도 대표값으로 정규화.
    - 변형 감지는 **치환 전 원본 산출물 기준**(nested/leftover 괄호가 치환 후 정상
      토큰으로 위장되는 것 차단): 환각 토큰(map 부재 유효 토큰)·변형 괄호(⟦⟧ 잔존) → exit 1.
    - 평문 유출(원값·alias 가 복원 전부터 등장) → 경고(exit code 불변, entry 참조 기록).
    - 리포트는 기밀값 미수록(hallucinated 은 category+번호만, 나머지는 위치·건수).
    """
    validate_map(map_data)
    norm_output = _nfc(ai_output)
    normalized = norm_output != ai_output
    token_to_entry = {e["token"]: {"value": e["value"], "category": e["category"]}
                      for e in map_data["entries"]}
    known_categories = {e["category"] for e in map_data["entries"]}

    # 복원 패스 — 유효 토큰만 소비, 환각 토큰은 원형 보존(restored.txt 는 기밀 파일)
    parts = []
    last = 0
    tokens_restored = 0
    by_category = {}
    hallucinated = {}  # token -> {category|None, token_number, known_category, count}
    for m in TOKEN_RE.finditer(norm_output):
        parts.append(norm_output[last:m.start()])
        tok = m.group(0)
        if tok in token_to_entry:
            cat = token_to_entry[tok]["category"]
            parts.append(token_to_entry[tok]["value"])
            by_category[cat] = by_category.get(cat, 0) + 1
            tokens_restored += 1
        else:
            cat_component, num = m.group(1), m.group(2)
            known = cat_component in known_categories
            h = hallucinated.setdefault(tok, {
                "category": cat_component if known else None,
                "token_number": int(num),
                "known_category": known,
                "count": 0,
            })
            h["count"] += 1
            parts.append(tok)  # 원형 유지(투명성)
        last = m.end()
    parts.append(norm_output[last:])
    restored_text = "".join(parts)

    # 변형 괄호: **치환 전** 산출물에서 인식된 토큰(TOKEN_RE 완전매칭 = map+환각) span
    # 밖의 ⟦/⟧ 문자(공백삽입·빈괄호·중첩 잔여 등). 치환 후 텍스트로 판정하면
    # ⟦⟦거래처_1⟧_1⟧ → ⟦현대엘리베이터_1⟧ 처럼 잔여 괄호가 정상 토큰으로 위장돼 은닉된다.
    valid_spans = [(m.start(), m.end()) for m in TOKEN_RE.finditer(norm_output)]

    def _in_valid(pos):
        return any(s <= pos < e for s, e in valid_spans)

    variant_positions = [idx for idx, ch in enumerate(norm_output)
                         if ch in ("⟦", "⟧") and not _in_valid(idx)]

    # 평문 유출: entry 의 value·전체 alias·matched_surfaces 표면형이 산출물에 복원 전부터
    # 평문 등장 → entry(token) 참조. 대표값(value)·타 alias 를 항상 스캔해, alias 로만
    # 마스킹된 문서에서 AI 가 대표값을 평문 재생산해도 감지한다.
    scan_desc = []
    for e in map_data["entries"]:
        surfaces = {e["value"]}
        surfaces.update(e.get("aliases", []))
        surfaces.update(e.get("matched_surfaces", {}).keys())
        for surface in sorted(surfaces):  # 결정론
            scan_desc.append({
                "surface": surface,
                "token": e["token"],
                "category": e["category"],
                "matcher": _compile_matcher(surface),
            })
    leak_by_token = {}
    for d, positions in _scan_occurrences(norm_output, scan_desc):
        agg = leak_by_token.setdefault(d["token"], {
            "token": d["token"], "category": d["category"], "count": 0,
        })
        agg["count"] += len(positions)
    plaintext_leak = sorted(leak_by_token.values(), key=lambda x: x["token"])

    # 미사용 토큰(info) — map 토큰이 산출물에 0회 등장
    present = {m.group(0) for m in TOKEN_RE.finditer(norm_output)}
    unused_tokens = sorted(e["token"] for e in map_data["entries"]
                           if e["token"] not in present)

    # 환각 토큰 리포트(기밀 미수록 — known 은 category+번호, unknown 은 위치·건수만)
    hallu_report = []
    for tok in sorted(hallucinated, key=lambda t: (hallucinated[t]["token_number"], t)):
        h = hallucinated[tok]
        elem = {
            "known_category": h["known_category"],
            "token_number": h["token_number"],
            "count": h["count"],
        }
        if h["known_category"]:
            elem["category"] = h["category"]
            elem["token"] = f"⟦{h['category']}_{h['token_number']}⟧"
        else:
            elem["category"] = None
            elem["token"] = None
        hallu_report.append(elem)

    anomaly = bool(hallucinated) or bool(variant_positions)
    report = {
        "restored": not anomaly,
        "doc_id": map_data.get("doc_id"),
        "glossary_name": map_data.get("glossary_name"),
        "glossary_sha256": map_data.get("glossary_sha256"),
        "created_at": now,
        "tokens_restored": tokens_restored,
        "normalized": normalized,
        "by_category": by_category,
        "anomalies": {
            "hallucinated_tokens": hallu_report,
            "variant_brackets": {"count": len(variant_positions), "positions": variant_positions},
            "plaintext_leak": plaintext_leak,
            "unused_tokens": unused_tokens,
        },
    }
    return restored_text, report


def _load_map_file(path: Path):
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise UsageError(f"map 파일이 없습니다: {path}")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UsageError(f"map JSON 파싱 실패: {exc}")
    validate_map(data)
    return raw, data


# ──────────────────────────────────────────────────────────────────
# doc_id / audit (C5·C6)
# ──────────────────────────────────────────────────────────────────


def _sanitize_doc_id(raw: str) -> str:
    """사용자 지정 doc_id 를 [A-Za-z0-9._-] 로 sanitize(경로 traversal 차단).

    경로 구분자·기타 문자 제거 후, 빈 문자열·전부 점(., .., ...)이면 거부(exit 2).
    """
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "", raw)
    if not cleaned or set(cleaned) <= {"."}:
        raise UsageError("유효하지 않은 --doc-id 입니다(경로 traversal 차단).")
    return cleaned


def _append_audit(audit_log: Path, record: dict) -> None:
    """감사 로그 append(한 줄 단일 write — 부분 라인 방지). 기밀값 미포함."""
    audit_log.parent.mkdir(parents=True, exist_ok=True)
    with open(audit_log, "a", encoding="utf-8", newline="") as f:
        f.write(_dump_json_line(record))


# ──────────────────────────────────────────────────────────────────
# CLI 커맨드
# ──────────────────────────────────────────────────────────────────


def cmd_mask(args) -> int:
    text = _read_text(Path(args.input))
    glossary_bytes, glossary = _load_glossary_file(Path(args.glossary))
    glossary_sha256 = hashlib.sha256(glossary_bytes).hexdigest()

    doc_id = _sanitize_doc_id(args.doc_id) if args.doc_id else \
        hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    now = args.now or _utc_now_iso()
    out_dir = Path(args.out_dir) if args.out_dir else WORKSPACE_ROOT / doc_id
    audit_log = Path(args.audit_log) if args.audit_log else WORKSPACE_ROOT / "audit.jsonl"

    masked, map_dict, report_dict = mask(
        text, glossary, glossary_sha256=glossary_sha256, doc_id=doc_id, now=now)

    # 리포트 JSON 은 성공·실패 모두 stdout 으로(구조화 실패 리포트)
    sys.stdout.write(_dump_json(report_dict))

    # 감사 로그(성공·실패 모두)
    _append_audit(audit_log, {
        "ts": now,
        "action": "mask",
        "result": report_dict["result"],
        "doc_id": doc_id,
        "glossary_name": glossary["name"],
        "glossary_sha256": glossary_sha256,
        "by_category": report_dict["by_category"],
        "tokens_total": report_dict["tokens_total"],
        "residual_count": report_dict["residual_count"],
        "anomalies": 0,
    })

    if report_dict["result"] != "pass":
        # 산출 원자성: 자체 잔존 검증 실패 시 신뢰 산출물을 디스크에 승격하지 않는다
        sys.stderr.write(
            f"[mask] 자체 잔존 검증 실패(잔존 {report_dict['residual_count']}건) — "
            "산출물을 승격하지 않습니다.\n"
        )
        return 1

    _write_atomic(out_dir / "masked.txt", masked)
    _write_atomic(out_dir / "map.json", _dump_json(map_dict), secret=True)  # 평문 기밀 → 0600
    _write_atomic(out_dir / "report.json", _dump_json(report_dict))
    sys.stderr.write(f"[mask] {report_dict['tokens_total']} 토큰 → {out_dir / 'masked.txt'}\n")
    return 0


def cmd_verify(args) -> int:
    text = _read_text(Path(args.text))
    _raw, glossary = _load_glossary_file(Path(args.glossary))
    report = verify(text, glossary)
    sys.stdout.write(_dump_json(report))
    if not report["verified"]:
        sys.stderr.write(f"[verify] 잔존 {report['residual_count']}건 검출.\n")
        return 1
    return 0


def cmd_restore(args) -> int:
    ai_output = _read_text(Path(args.ai_output))
    _raw, map_data = _load_map_file(Path(args.map))
    now = args.now or _utc_now_iso()

    restored_text, report = restore(ai_output, map_data, now=now)

    # 리포트 JSON(기밀 미포함)은 성공·실패 모두 stdout 으로 + 감사 로그 append.
    sys.stdout.write(_dump_json(report))

    result = "pass" if report["restored"] else "fail"
    anomalies_n = (len(report["anomalies"]["hallucinated_tokens"])
                   + report["anomalies"]["variant_brackets"]["count"]
                   + len(report["anomalies"]["plaintext_leak"]))
    audit_log = Path(args.audit_log) if args.audit_log else WORKSPACE_ROOT / "audit.jsonl"
    _append_audit(audit_log, {
        "ts": now,
        "action": "restore",
        "result": result,
        "doc_id": map_data.get("doc_id"),
        "glossary_name": map_data.get("glossary_name"),
        "glossary_sha256": map_data.get("glossary_sha256"),
        "by_category": report["by_category"],
        "tokens_total": report["tokens_restored"],
        "residual_count": report["anomalies"]["variant_brackets"]["count"],
        "anomalies": anomalies_n,
    })

    if report["anomalies"]["plaintext_leak"]:
        sys.stderr.write("[restore] 경고: 산출물에 기밀 표면형이 복원 전부터 평문 등장(마스킹 우회 의심).\n")

    # 산출 원자성: 이상(변형·환각) 검출 시 restored.txt 를 생성·승격하지 않는다 —
    # 실패 복원본이 정상처럼 남거나 기존 정상본을 덮어쓰지 않게(mask 원자성과 동일 계약).
    if not report["restored"]:
        sys.stderr.write(
            "[restore] 변형·환각 토큰 검출 — 복원 무결성 실패, restored 파일을 "
            "생성·변경하지 않습니다.\n"
        )
        return 1

    # restored.txt 기본 위치 = map.json 디렉토리(항상 _workspace 가드 안, ai_output 위치 무관)
    out_path = Path(args.out) if args.out else Path(args.map).parent / "restored.txt"
    _write_atomic(out_path, restored_text, secret=True)  # 평문 기밀 → 0600
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="biz_redact.py",
        description="업무 문서 영업기밀 마스킹·왕복 복원 게이트",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    pm = sub.add_parser("mask", help="원문 마스킹 → masked.txt/map.json/report.json")
    pm.add_argument("input", help="원문 파일 경로")
    pm.add_argument("--glossary", required=True, help="용어집 JSON 경로")
    pm.add_argument("--out-dir", dest="out_dir", help="산출 디렉토리(기본 _workspace/biz-redact/<doc-id>)")
    pm.add_argument("--doc-id", dest="doc_id", help="문서 식별자(기본 원문 SHA256 앞 12hex)")
    pm.add_argument("--now", help="타임스탬프 고정 주입(ISO8601, 테스트 결정론용)")
    pm.add_argument("--audit-log", dest="audit_log", help="감사 로그 경로")

    pv = sub.add_parser("verify", help="잔존 검증")
    pv.add_argument("text", help="검증 대상 텍스트 파일")
    pv.add_argument("--glossary", required=True, help="용어집 JSON 경로")

    pr = sub.add_parser("restore", help="왕복 복원 + 변형 감지")
    pr.add_argument("ai_output", help="AI 산출물 텍스트 파일")
    pr.add_argument("--map", required=True, help="복원키 map.json 경로")
    pr.add_argument("--out", help="복원본 경로(기본 map.json 디렉토리/restored.txt)")
    pr.add_argument("--now", help="타임스탬프 고정 주입(ISO8601, 테스트 결정론용)")
    pr.add_argument("--audit-log", dest="audit_log", help="감사 로그 경로")
    return parser


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.cmd == "mask":
            return cmd_mask(args)
        if args.cmd == "verify":
            return cmd_verify(args)
        if args.cmd == "restore":
            return cmd_restore(args)
    except UsageError as exc:
        sys.stderr.write(f"오류: {exc}\n")
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
