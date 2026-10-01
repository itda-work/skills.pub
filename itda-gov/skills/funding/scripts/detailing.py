# Portions derived from ir-search (https://github.com/djfksjd/ir-search, MIT)
# 개작 요지: sources_crawl.cmd_detail·kstartup_crawl.collect_detail·merge_detail 을 계획/판정 두 단계로 나눔.
# 라이선스 전문·차용 파일 목록은 ../references/third-party.md 참조.
"""상세 본문·첨부 — 호출 계획과 판정 (네트워크 없음).

요청은 itda-hyve 가 보낸다(itda-work/skills#45). 흐름:

  plan detail <대상…>  → 상세 페이지 GET 계획(raw/detail/)
  collect detail       → 상세를 읽어 첨부 링크를 거르고(robots·정확한 호스트) 첨부 GET 계획(raw/att/),
                         KOCCA 는 첨부 목록 팝업부터 계획. 다 모이면 파일을 검사하고 해시·병합.

저장 이름이 식별 계약이다:
  raw/detail/<source>-<id>[-r2].html      상세 페이지(이상하면 한 번 다시 받는다)
  raw/detail/kocca-<intcNo>-pop1.html     KOCCA 첨부 목록 팝업
  raw/att/<source>-<id>-<NN>.<ext>        첨부(확장자는 상세 페이지가 준 파일 이름에서)

대상 지목: ``<source>:<id>``(목록 jsonl 에서 url 을 찾는다), 상세 URL, 또는 K-Startup 공고번호(숫자).
"""
from __future__ import annotations

import hashlib
import html as htmllib
import json
import os
import re
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import attach_download
import kstartup_crawl
import sources_crawl
from hyve_input import HyveFailure, HyveInputError, read_input, unwrap
from plan_io import ATTACH_TIMEOUT_SEC, PlanLog, http_call
from run_manifest import _reject_dup_keys

DETAIL_DIR = "raw/detail"
ATT_DIR = "raw/att"
MAX_DETAIL_RETAKE = 1   # 상세 페이지는 한 번 다시 받는다(-r2)
MAX_PLANNED = 3         # 같은 저장 이름을 이만큼 시도했는데 파일이 없으면 받지 못한 것으로 확정한다(listing 과 같다)
MAX_DETAIL_ROUNDS = 8   # 대상 하나에 계획 회전 상한 — 상세·팝업·첨부·다시 받기를 다 해도 5회전 안쪽이다

# 상세 대상 경로 허용 목록 — 호스트·robots 에 더해 **소스별 상세 화면 경로만** 계획한다(M8·m5).
# 공고 본문이 시킨 아무 경로(`/comm/getFile?…`, `pbancSn=` 만 붙인 다른 화면)가 상세로 새어 나가지 않는다.
# 경로는 퍼센트 인코딩·``..``·``;`` 없이 글자 그대로 맞아야 한다.
DETAIL_PATHS = {
    "kstartup": re.compile(r"/web/contents/bizpbanc-ongoing\.do"),
    "bizinfo": re.compile(r"/sii/siia/selectSIIA200Detail\.do"),
    "nipa": re.compile(r"/home/2-2/\d+"),
    "smtech": re.compile(r"/front/ifg/no/notice02_detail\.do"),
    "kocca": re.compile(r"/kocca/pims/view\.do"),
}

ID_RE = {
    "kstartup": re.compile(r"pbancSn=(\d+)"),
    "bizinfo": re.compile(r"pblancId=(PBLN_\d+)"),
    "nipa": re.compile(r"/home/2-2/(\d+)"),
    "kocca": re.compile(r"intcNo=([A-Za-z0-9]+)"),
}


class TargetError(ValueError):
    pass


@dataclass
class Target:
    source: str
    id: str
    url: str
    title: str = ""
    record: bool = False

    @property
    def sid(self) -> str:
        return re.sub(r"[^A-Za-z0-9_-]", "_", self.id)

    def to_json(self) -> dict[str, Any]:
        return {"source": self.source, "id": self.id, "url": self.url, "title": self.title, "record": self.record}


def load_records(survey: Path) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    if not survey.is_file():
        return out
    for line in survey.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line, object_pairs_hook=_reject_dup_keys)
        src = rec.get("source") or ("kstartup" if "pbancSn" in rec else "")
        rid = str(rec.get("id") or rec.get("pbancSn") or "")
        out[(src, rid)] = rec
    return out


def _source_of(url: str) -> Optional[str]:
    if attach_download.host_allowed(url, kstartup_crawl.ALLOWED_DOMAINS):
        return "kstartup"
    return sources_crawl.source_of_url(url)


def _id_of(source: str, url: str) -> Optional[str]:
    if source == "smtech":
        anc = re.search(r"ancmId=([A-Za-z0-9]+)", url)
        dtl = re.search(r"dtlAncmSn=(\d+)", url)
        return f"{anc.group(1)}-{dtl.group(1) if dtl else '0'}" if anc else None
    m = ID_RE[source].search(url)
    return m.group(1) if m else None


def _check_url(source: str, url: str) -> None:
    hosts = kstartup_crawl.KSTARTUP_ATTACH_HOSTS if source == "kstartup" else sources_crawl.ATTACH_HOSTS[source]
    robots = kstartup_crawl.KSTARTUP_ROBOTS_DISALLOWED if source == "kstartup" else sources_crawl.ATTACH_ROBOTS[source]
    if not attach_download.host_allowed(url, hosts):
        raise TargetError(f"허용 호스트가 아니다(https·정확한 호스트만): {url[:90]}")
    if not attach_download.robots_allowed(url, robots):
        raise TargetError(f"robots 불허 경로라 요청하지 않는다: {url[:90]}")
    try:
        path = urllib.parse.urlsplit(url).path
    except ValueError:
        path = ""
    if not DETAIL_PATHS[source].fullmatch(path):
        raise TargetError(f"{source} 상세 화면 경로가 아니다(허용: {DETAIL_PATHS[source].pattern}) — 요청하지 않는다: {url[:90]}")


def resolve(spec: str, records: dict[tuple[str, str], dict[str, Any]]) -> Target:
    """대상 한 개를 푼다. 요청하지 않을 대상은 TargetError(사유)."""
    spec = spec.strip()
    if spec.startswith("http"):
        url = htmllib.unescape(spec)
        source = _source_of(url)
        if source is None:
            raise TargetError(f"다섯 소스의 정확한 호스트가 아니다 — robots·호스트 정책이 없어 요청하지 않는다: {url[:90]}")
        rid = _id_of(source, url)
        if not rid:
            raise TargetError(f"URL 에서 {source} 공고 id 를 읽을 수 없다: {url[:90]}")
    elif ":" in spec:
        source, rid = spec.split(":", 1)
        if source not in ("kstartup", "bizinfo", "nipa", "smtech", "kocca"):
            raise TargetError(f"모르는 소스: {source}")
        rec = records.get((source, rid))
        if rec is None:
            raise TargetError(f"survey.jsonl 에 {source}:{rid} 가 없다 — collect list 뒤에 지목하거나 상세 URL 을 준다")
        url = rec.get("url") or ""
    elif spec.isdigit():
        source, rid = "kstartup", spec
        url = kstartup_crawl.DETAIL_URL.format(sn=spec)
    else:
        raise TargetError(f"대상은 <source>:<id>·상세 URL·K-Startup 공고번호 중 하나다: {spec}")
    rec = records.get((source, rid))
    if rec and rec.get("detail") == "iris":
        raise TargetError(f"{source}:{rid} 는 IRIS 공고다 — 상세는 IRIS 홈페이지(https://www.iris.go.kr/)에서 직접 확인한다")
    if rec and rec.get("url") and source != "kstartup":
        url = rec["url"]  # 목록이 준 url 전체(SMTECH 는 쿼리를 줄이면 intro 로 302 — 2026-09-30 실측)
    _check_url(source, url)
    return Target(source, rid, url, title=(rec or {}).get("title", ""), record=rec is not None)


# ---------------------------------------------------------------------------
# 호출
# ---------------------------------------------------------------------------

_DETAIL_NAME = re.compile(r"(kstartup|bizinfo|nipa|smtech|kocca)-[A-Za-z0-9_-]+\.html")
_ATT_NAME = re.compile(r"(kstartup|bizinfo|nipa|smtech|kocca)-[A-Za-z0-9_-]+-\d{2}\.[a-z0-9]{1,5}")


def check_names(run_dir: Path) -> None:
    """``raw/detail``·``raw/att`` 에 이름 규칙 밖 파일이 있으면 ValueError — 섞인 입력을 조용히 넘기지 않는다
    (``raw/list`` 와 같은 계약, m6)."""
    for sub_dir, rx, rule in ((DETAIL_DIR, _DETAIL_NAME, "<source>-<id>[-r2|-pop1].html"),
                              (ATT_DIR, _ATT_NAME, "<source>-<id>-<NN>.<ext>")):
        d = run_dir / sub_dir
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.name.startswith("."):
                continue
            if not p.is_file() or not rx.fullmatch(p.name):
                raise ValueError(f"{sub_dir}/ 에 이름 규칙({rule}) 밖 파일이 있다: {p.name}")


def detail_call(t: Target, retake: int = 1) -> dict[str, Any]:
    suffix = f"-r{retake}" if retake > 1 else ""
    return http_call(f"detail-{t.source}-{t.sid}{suffix}", t.url, f"{DETAIL_DIR}/{t.source}-{t.sid}{suffix}.html")


def popup_call(intc: str) -> dict[str, Any]:
    sid = re.sub(r"[^A-Za-z0-9_-]", "_", intc)
    return http_call(f"detail-kocca-{sid}-pop1", sources_crawl.kocca_popup_url(intc),
                     f"{DETAIL_DIR}/kocca-{sid}-pop1.html")


def att_name(t: Target, n: int, filename: str) -> str:
    return f"{ATT_DIR}/{t.source}-{t.sid}-{n:02d}.{attach_download.ext_of(filename)}"


# ---------------------------------------------------------------------------
# 판정
# ---------------------------------------------------------------------------

@dataclass
class DetailResult:
    target: Target
    status: str = "incomplete"          # ok · partial · fail · manual · incomplete
    reason: str = ""
    calls: list[dict[str, Any]] = field(default_factory=list)
    attachments: list[dict[str, Any]] = field(default_factory=list)
    content_hash: Optional[str] = None
    hash_version: Optional[int] = None
    text: str = ""
    warnings: list[str] = field(default_factory=list)


def _norm(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", htmllib.unescape(s or ""))


def _identity(t: Target, h: str) -> Optional[str]:
    """상세 본문이 그 공고인가. 목록 제목(정규화 앞 15자)이 본문에 있어야 한다. 목록 레코드가 없으면
    본문의 식별자로 본다(bizinfo pblancId·smtech ancmId·kocca 사업번호). 틀리면 사유, 확인 불가면 ""."""
    body = _norm(re.sub(r"<[^>]+>", " ", h))
    if t.title:
        key = _norm(t.title)[:15]
        return None if key and key in body else f"상세 본문에 목록 제목({t.title[:30]})이 없다 — 다른 공고·오류 본문"
    if t.source == "bizinfo":
        return None if t.id in h else "상세 본문에 pblancId 가 없다"
    if t.source == "smtech":
        return None if t.id.split("-")[0] in h else "상세 본문에 ancmId 가 없다"
    if t.source == "kocca":
        nums = {n.replace("-", "") for n in re.findall(r"\d-\d{2}-[A-Z]\d{5}-\d{3}", h)}
        return None if t.id in nums else "상세 본문의 사업번호가 intcNo 와 다르다"
    return ""  # kstartup·nipa 목록 밖 URL — 본문에 식별자가 없다(확인 불가, 경고)


def _latest(run_dir: Path, stem: str) -> tuple[int, Optional[Path]]:
    best, path = 0, None
    d = run_dir / DETAIL_DIR
    for p in d.glob(f"{stem}*.html") if d.is_dir() else []:
        m = re.fullmatch(rf"{re.escape(stem)}(?:-r(\d+))?\.html", p.name)
        if m:
            k = int(m.group(1) or 1)
            if k > best:
                best, path = k, p
    return best, path


def _read_html(path: Path) -> tuple[Optional[str], str]:
    try:
        body = read_input(path)
    except HyveFailure as exc:
        return None, f"hyve:{exc.code}"
    except HyveInputError as exc:
        return None, f"{exc.kind}: {exc}"
    return body.data.decode("utf-8", errors="replace"), ""


def _body_markers(source: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if source == "kstartup":
        return kstartup_crawl.KSTARTUP_START_MARKERS, kstartup_crawl.KSTARTUP_END_MARKERS
    return sources_crawl.BODY_MARKERS[source]


def _gate(t: Target, a: dict[str, Any]) -> dict[str, Any]:
    """첨부 링크를 계약으로 거른다 — 받을 것은 그대로, 받지 않을 것은 download_status 를 붙인다."""
    if "download_status" in a:
        return a
    hosts = kstartup_crawl.KSTARTUP_ATTACH_HOSTS if t.source == "kstartup" else sources_crawl.ATTACH_HOSTS[t.source]
    robots = kstartup_crawl.KSTARTUP_ROBOTS_DISALLOWED if t.source == "kstartup" else sources_crawl.ATTACH_ROBOTS[t.source]
    if not attach_download.host_allowed(a["url"], hosts):
        return {**a, "download_status": "skipped_unverified",
                "download_reason": "허용 호스트 밖 — 다운로드 계약 미확정(링크만 기록)"}
    if not attach_download.robots_allowed(a["url"], robots):
        return {**a, "download_status": "skipped_robots", "download_reason": "robots.txt 불허 경로 — 링크만 기록"}
    return a


def _read_attachment(path: Path, ext: str) -> tuple[Optional[bool], str, Optional[str], int]:
    """받은 첨부 검사. itda-hyve 실패 자리({"error"})·응답 JSON 전체(body_base64)도 읽는다.
    ok 가 None 이면 형식을 몰라 검사하지 못한 것(``unverified_format``)."""
    raw = path.read_bytes()
    if raw[:1] == b"{" and len(raw) < 1 << 20:
        try:
            raw = unwrap(raw, source=path).data
        except HyveFailure as exc:
            return False, f"hyve:{exc.code}", None, 0
        except HyveInputError as exc:
            return False, f"{exc.kind}: {exc}", None, 0
    return attach_download.verify_attachment(raw, ext)


def _gave_up(log: PlanLog, save_as: str, run_dir: Path) -> bool:
    """그 저장 이름을 ``MAX_PLANNED`` 번 **시도**했는데 파일이 없다 — 더 계획하지 않고 받지 못한 것으로 확정(M1·N3)."""
    return log.count(save_as) >= MAX_PLANNED and not (run_dir / save_as).exists()


def _has_body(source: str, h: str) -> bool:
    start, _ = _body_markers(source)
    return any(re.search(p, h) for p in start)


def collect_one(run_dir: Path, t: Target, planned: Optional[PlanLog] = None) -> DetailResult:
    """대상 하나를 판정한다. 더 받을 것이 있으면 ``calls``.

    끝: 같은 저장 이름을 ``MAX_PLANNED`` 번 **시도**했는데 파일이 없으면 받지 못함으로 확정하고, 이 대상의 계획 회전이
    ``MAX_DETAIL_ROUNDS`` 에 닿으면 아직 없는 것을 전부 받지 못함으로 확정한다(시도 흔적이 없는 계획은 계수에 들지
    않으므로 — 재리뷰 N3). 상세가 없으면 ``fail``, 첨부·팝업이 없으면 그 첨부만 ``failed``(결과는 partial)."""
    planned = planned or PlanLog([])
    stem = re.escape(f"{t.source}-{t.sid}")
    mine = re.compile(rf"(?:{DETAIL_DIR}/{stem}(?:-r\d+|-pop\d+)?\.html|{ATT_DIR}/{stem}-\d{{2}}\.[a-z0-9]+)")
    used = {rnd for rnd, names in planned.rounds("raw/").items() if any(mine.fullmatch(n) for n in names)}
    return _collect_one(run_dir, t, planned, capped=len(used) >= MAX_DETAIL_ROUNDS)


def _collect_one(run_dir: Path, t: Target, planned: PlanLog, *, capped: bool = False) -> DetailResult:
    res = DetailResult(t)
    stem = f"{t.source}-{t.sid}"

    def gave_up(save_as: str) -> bool:
        return (capped and not (run_dir / save_as).exists()) or _gave_up(planned, save_as, run_dir)

    attempt, path = _latest(run_dir, stem)
    missing = (f"회전 상한 {MAX_DETAIL_ROUNDS} — 받지 못했다" if capped
               else f"hyve:missing — 같은 저장 이름을 {MAX_PLANNED}번 시도했는데 파일이 없다(받지 못함)")
    if path is None:
        call = detail_call(t)
        if gave_up(call["args"]["save_as"]):
            res.status, res.reason = "fail", missing
            return res
        res.calls.append(call)
        return res
    h, err = _read_html(path)
    if h is not None and attach_download.looks_blocked(h):
        res.status, res.reason = "manual", "200 위장 차단(CAPTCHA/접근거부) — 우회하지 않고 수동 확인"
        return res
    unverified = False
    if h is not None:
        if not _has_body(t.source, h):
            # 본문 컨테이너가 없으면 공고 화면이 아니다 — 없는 번호의 셸·3xx 본문·오류 화면(M7).
            err = "unexpected_response: 본문 시작 표지가 없다 — 없는 공고·리다이렉트·오류 화면이거나 사이트 개편"
        else:
            bad = _identity(t, h)
            if bad == "":
                unverified = True
                res.warnings.append(f"{t.source}:{t.id} — 목록 레코드가 없어 본문이 그 공고인지 대조하지 못했다")
            elif bad:
                err = bad
    if err:
        if attempt <= MAX_DETAIL_RETAKE:
            call = detail_call(t, attempt + 1)
            if not gave_up(call["args"]["save_as"]):
                res.calls.append(call)
                return res
            err += f" (다시 받기 {call['args']['save_as']} 는 받지 못함)"
        res.status, res.reason = "fail", err
        return res

    # 첨부 링크 — KOCCA 는 팝업을 받아 읽는다
    if t.source == "kstartup":
        links = kstartup_crawl.parse_attachments(h)
    elif t.source == "kocca":
        p1, p2 = sources_crawl.kocca_popup_refs(h)
        links = []
        for intc in p1:
            pcall = popup_call(intc)
            pop = run_dir / pcall["args"]["save_as"]
            if not pop.exists():
                if not gave_up(pcall["args"]["save_as"]):
                    res.calls.append(pcall)
                    continue
                ph, perr = None, missing
            else:
                ph, perr = _read_html(pop)
            rows = sources_crawl.parse_kocca_popup(ph) if ph is not None and not attach_download.looks_blocked(ph) else None
            if rows is None:
                links.append({"url": sources_crawl.kocca_popup_url(intc), "filename": None,
                              "download_status": "failed",
                              "download_reason": f"첨부 목록 팝업을 읽지 못했다({perr or '구조 미확인·차단 의심'}) — 첨부 유무 불명"})
            else:
                links.extend(rows)
        for pid in p2:
            links.append({"url": sources_crawl.kocca_pms_url(pid), "filename": None,
                          "download_status": "skipped_unverified",
                          "download_reason": "pms.kocca.kr 팝업 — 다운로드 계약 미확정(링크만 기록)"})
        if res.calls:
            return res
    else:
        links = sources_crawl.collect_attachments(t.source, h)

    atts = []
    n = 0
    for a in links:
        a = _gate(t, dict(a))
        if "download_status" not in a:
            n += 1
            a["local_path"] = att_name(t, n, a.get("filename") or "")
            if not (run_dir / a["local_path"]).exists():
                if gave_up(a["local_path"]):
                    a.update(download_status="failed", download_reason=missing)
                else:
                    res.calls.append(http_call(f"att-{t.source}-{t.sid}-{n:02d}", a["url"], a["local_path"],
                                               timeout_sec=ATTACH_TIMEOUT_SEC))
        atts.append(a)
    if res.calls:
        return res

    for a in atts:
        if "download_status" in a:
            continue
        ext = a["local_path"].rsplit(".", 1)[-1]
        ok, why, digest, size = _read_attachment(run_dir / a["local_path"], ext)
        if ok is None:
            a.update(download_status="unverified_format", download_reason=why, size=size)
        elif ok:
            a.update(download_status="ok", sha256=digest, size=size)
        else:
            a.update(download_status="failed", download_reason=why)
    start, end = _body_markers(t.source)
    text = sources_crawl.extract_body(h, start, end)
    res.text = text
    res.attachments = atts
    res.content_hash = hashlib.sha256(text.encode()).hexdigest()
    res.hash_version = attach_download.HASH_VERSION_BODY
    complete = all(a.get("download_status") == "ok" for a in atts)
    if atts and complete:
        res.content_hash = attach_download.content_hash_of(text, [a["sha256"] for a in atts])
        res.hash_version = attach_download.HASH_VERSION_ATTACH
    reasons = []
    if not complete:
        bad_n = sum(1 for a in atts if a.get("download_status") != "ok")
        reasons.append(f"첨부 {bad_n}/{len(atts)}건 미검증(robots·계약 미확정·형식 미확인·실패)")
    if unverified:
        reasons.append("목록 레코드가 없어 본문이 그 공고인지 대조하지 못했다")
    res.status = "partial" if reasons else "ok"
    res.reason = " · ".join(reasons)
    return res


def write_detail(run_dir: Path, res: DetailResult) -> Path:
    d = run_dir / "details"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{res.target.source}-{res.target.sid}.txt"
    with open(p, "w", encoding="utf-8") as f:
        f.write(res.target.url + "\n")
        f.write(f"CONTENT_HASH: {res.content_hash}\n")
        f.write(f"HASH_VERSION: {res.hash_version}\n")
        f.write("ATTACHMENTS: " + json.dumps(res.attachments, ensure_ascii=False) + "\n\n")
        f.write(res.text)
    return p


def merge_detail(jsonl: Path, res: DetailResult) -> bool:
    """목록 jsonl 의 그 레코드에 상세 결과를 병합한다(원자적 교체). 못 찾으면 False."""
    t = res.target
    complete = all(a.get("download_status") == "ok" for a in res.attachments)
    tmp = jsonl.with_suffix(".jsonl.tmp")
    found = False
    with open(jsonl, encoding="utf-8") as src, open(tmp, "w", encoding="utf-8") as dst:
        for line in src:
            if not line.strip():
                continue
            r = json.loads(line, object_pairs_hook=_reject_dup_keys)
            key_src = r.get("source") or ("kstartup" if "pbancSn" in r else "")
            key_id = str(r.get("id") or r.get("pbancSn") or "")
            if key_src == t.source and key_id == t.id:
                r["content_hash"] = res.content_hash
                r["hash_version"] = res.hash_version
                r["attachments"] = res.attachments
                r["attachments_complete"] = complete
                found = True
            dst.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, jsonl)
    return found
