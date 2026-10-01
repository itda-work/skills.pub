#!/usr/bin/env python3
# Portions derived from ir-search (https://github.com/djfksjd/ir-search, MIT)
# 개작 요지: 요청은 itda-hyve 가 보낸다 — 이 파일은 저장된 상세 HTML 판독(본문·첨부 링크)과
# 소스별 호스트·robots 상수만 둔다(itda-work/skills#45). 목록 판독은 listing.py.
# 라이선스 전문·차용 파일 목록은 ../references/third-party.md 참조.
"""기업마당·NIPA·KOCCA·SMTECH 상세 판독기 (네트워크 없음).

첨부 계약(소스별 robots 실측)은 ../references/sources.md, 종료코드·jsonl·매니페스트 계약은
../references/cli-contract.md 가 정본이다.
"""
import html as htmllib
import re
import urllib.parse


def clean(s):
    return re.sub(r"\s+", " ", htmllib.unescape(s or "")).strip()


SOURCE_DOMAINS = {
    "bizinfo": ("=www.bizinfo.go.kr", "=bizinfo.go.kr"),
    "nipa": ("=www.nipa.kr", "=nipa.kr"),
    "kocca": ("=www.kocca.kr", "=kocca.kr"),
    "smtech": ("=www.smtech.go.kr", "=smtech.go.kr"),
}


def strip_html(text):
    text = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", "", text)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = htmllib.unescape(text)
    return re.sub(r"\n\s*\n+", "\n", text)


ALLOWED_DOMAINS = ("bizinfo.go.kr", "nipa.kr", "kocca.kr", "smtech.go.kr", "k-startup.go.kr")


def host_allowed(url, domains=None):
    """Exact-match domain check on the URL's real hostname (https only).

    Uses urlsplit().hostname so userinfo/port tricks ("bizinfo.go.kr:443@evil.example")
    cannot spoof the allowlist — naive string slicing was bypassable. The scheme
    must be https: every allowed source serves https, so a plain-http URL is
    either a typo or a downgrade attempt and is rejected.

    *domains* narrows the allowlist (e.g. per-source redirect checks);
    default is the full ALLOWED_DOMAINS. An entry prefixed with '=' matches
    the EXACT host only (no subdomain wildcard) — e.g. '=www.kocca.kr' does
    not admit pms.kocca.kr (attach_download.host_allowed와 동일 규약).
    """
    if domains is None:
        domains = ALLOWED_DOMAINS
    try:
        parts = urllib.parse.urlsplit(url)
        host = (parts.hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    if parts.scheme != "https":
        return False
    for d in domains:
        if d.startswith("="):
            if host == d[1:]:
                return True
        elif host == d or host.endswith("." + d):
            return True
    return False


# ---- bizinfo 첨부 슬라이스 (sole-search 이식, 2026-07-23 실측) ---------------

# robots.txt(2026-07-23 확인)가 /upload·/download 접두를 불허한다 —
# /uploads/ 첨부 링크는 수집하되 다운로드하지 않는다(skipped_robots).
BIZINFO_ROBOTS_DISALLOWED = ("/super", "/upload", "/html", "/images", "/agspa",
                             "/error", "/common", "/lib", "/WEB-INF",
                             "/download", "/direct_do")

# 본문 시작 마커 — 여는 태그만 잡는다 (중첩 div를 regex로 균형 매칭할 수 없으므로)
BIZINFO_START_MARKERS = (r'<div[^>]+class="[^"]*view_cont[^"]*"',
                         r'<div[^>]+id="print_area"')
# 본문 끝 마커 — 시작 마커부터 푸터/다음 주요 섹션까지를 본문으로 자른다
BIZINFO_END_MARKERS = (r'<div[^>]+id="footer"', r'<footer\b',
                       r'<div[^>]+class="[^"]*footer',
                       r'<div[^>]+class="[^"]*btn_area',
                       r'<div[^>]+class="[^"]*paging',
                       r'목록으로|이전글|다음글')


def extract_body(h, start_markers=BIZINFO_START_MARKERS,
                 end_markers=BIZINFO_END_MARKERS):
    """시작 마커 ~ 첫 끝 마커(없으면 문서 끝) 구간의 텍스트. 마커 미발견 시 전체 폴백."""
    sm = None
    for p in start_markers:
        sm = re.search(p, h)
        if sm:
            break
    seg = h[sm.start():] if sm else h
    ends = [m.start() for p in end_markers for m in [re.search(p, seg)] if m]
    if ends:
        seg = seg[:min(ends)]
    return strip_html(seg)


def parse_bizinfo_attachments(h):
    """상세 페이지의 첨부 링크(/cmm/fms/, /uploads/) — 이름은 다운로드 링크의 title
    ("첨부파일 <이름> 다운로드")에서 읽는다(2026-09-30 실측). 옛 판은 URL 끝(fileDown.do)을
    이름으로 적었다 — 저장 파일에는 Content-Disposition 이 없으므로 이름은 페이지가 정본이다."""
    out, seen = [], set()
    for m in re.finditer(r'<a[^>]*href="(/cmm/fms/[^"]+|/uploads/[^"]+)"[^>]*>', h):
        href = htmllib.unescape(m.group(1))
        if href in seen:
            continue
        seen.add(href)
        t = re.search(r'title="([^"]*)"', m.group(0))
        name = clean(t.group(1)) if t else ""
        name = re.sub(r"^첨부파일\s*", "", re.sub(r"\s*다운로드$", "", name)).strip()
        out.append({"url": "https://www.bizinfo.go.kr" + href,
                    "filename": name or href.rsplit("/", 1)[-1].split("?")[0]})
    return out


# ---- NIPA·KOCCA·SMTECH 첨부 계약 (2026-07-24 실호출로 확인 — references/sources.md)

# NIPA robots.txt(2026-07-24): `User-agent: *` 블록이 없다(Googlebot 전용
# 규칙 /sea·/tota + Allow:/ 뿐) — 우리 크롤러에 적용되는 불허 경로 없음.
NIPA_ROBOTS_DISALLOWED = ()

# KOCCA robots.txt(2026-07-24) User-agent:* 블록 전사. 첨부 다운로드 엔드포인트
# /kocca/noticeFileDown.do는 "/*/FileDown.do" 패턴(리터럴 "/FileDown.do" 세그먼트
# 필요)과 불일치 — 허용. 와일드카드 패턴은 attach_download._robots_path_match가 처리.
KOCCA_ROBOTS_DISALLOWED = (
    "/kocca/member/", "/kocca/online", "/*/FileDown.do", "/kocca/counsel/",
    "/kocca/bbs/view/userInstRegPage.do", "/kocca/bbs/view/regContent.do",
    "/story/requestResult/", "/story/request/", "/curoms/", "/gamehubpms/",
    "/ourcharacter/", "/bestgame/", "/seriousgame/", "/gameguide/",
    "/broadcastdb.", "/cop/", "/portal/", "/kocca/searchList.do",
    "/kocca/*/list.do", "/kocca/bbs/list/*.do",
)

# SMTECH robots.txt(2026-07-24) User-agent:* 블록 전사(절대 URL 1건은 경로로 변환).
# 첨부 다운로드 엔드포인트 /front/comn/AtchFileDownload.do는 목록에 없음 — 허용.
SMTECH_ROBOTS_DISALLOWED = (
    "/SBA/SA/SbjtAppl_selectSbjtApplList.do",
    "/SBA/SA/HealthMngSbjtRcpt_selectSbjtApplPrg.do",
    "/SBA/ETC/EtcSbjtAppl_forwardEtcSbjtApplList.do",
    "/SBA/ETC/RechSbjtAppl_forwardRechSbjtApplList.do?RECH_ANCM_ID=S20131",
    "/SBA/ETC/RechSbjtAppl_forwardRechSbjtApplList.do?RECH_ANCM_ID=S20132",
    "/SBA/SA/SbjtAppl_selectSbjtPtcpList.do?gMenu=SBA",
    "/SBA/SA/SA_SbjtMbrSprtAncmList.do", "/SBA/SA/SA_SbjtNseeTdpList.do",
    "/sba/ee/ElecEvalSbjtLst.do", "/sba/se/OnlineEval.do",
    "/sba/se/SvorgnSelfEval.do",
    "/SBA/RE/PosnRechEqpm_getPosnRechEqpmMain.do",
    "/SBA/RE/RechEqpmRead_getRechEqpmRead.do",
    "/SBA/RE/BexpPayReq_viewBexpPayReq.do",
    "/SBA/RE/RechEqpmUseSituSv_viewRechEqpmUseSitu.do",
    "/SBA/RE/RechEqpmRevSv_viewRechEqpmRev.do",
    "/SBA/RE/PtcpReqListSv_viewPtcpReqList.do",
    "/SBA/RE/RechEqpmMentor_viewMentorList.do",
    "/SBA/RE/RechEqpmMentorAns_viewMentoringList.do",
    "/SBA/RE/VchrReqSitu_viewVchrReqSitu.do",
    "/SBA/RE/RechEqpmRev_viewRechEqpmRev.do",
    "/SBA/RE/RechEqpmUseSitu_viewRechEqpmUseSitu.do",
    "/SBA/RE/OftnUseEqpm_viewOftnUseEqpm.do",
    "/SBA/RE/PtcpReqList_viewPtcpReqList.do",
    "/SBA/RE/PtcpObjtSbjt_selectPtcpObjtSbjt.do",
    "/SBA/RE/RechEqpmMentoring_viewMentoringList.do",
    "/SBA/EA/AgreAppl_selectAgreWrtSbjt.do",
    "/SBA/EA/StepAgreAppl_selectAgreWrtSbjt.do",
    "/SBA/EA/AgreChng_selectAgreChngObjtSbjt.do",
    "/SBA/EA/ChrgrChng_selectChrgrChngSbjtLst.do",
    "/SBA/EA/MngAdmn_viewMngAdmn.do", "/SBA/EA/AgreRead_selectAgreRead.do",
    "/SBA/RR/PrgrtRptpLst_getPrgrtRptLst.do",
    "/SBA/RR/StepRptpLst_getStepRptLst.do",
    "/SBA/RR/LastRptpLst_getLastRptLst.do",
    "/SBA/RR/MngRsltRptp_viewMngRsltRptp.do",
    "/SBA/RN/RechNoteList_viewRechNoteList.do",
    "/SBA/FA/RechMtrsEstmAdmn.do", "/SBA/FA/KldgPrgtAdmn.do",
    "/SBA/FA/SbjtThesAdmn.do", "/sba/sc/SmbaSancAct.do",
    "/sba/sc/OgovdSancAct.do",
    "/SBA/DR/DemResearch_forwardDemResearchApplMain.do",
    "/SBA/DR/DemResearch_forwardDemResearchApplTeclMain.do",
    "/main/bankLoginGW.do", "/main/bankFrame.do",
    "/OSA/BR/BR_RtrtGuid.do", "/OSA/BR/BR_RtrtSituRead.do",
    "/OSA/BR/BR_PntRtrt.do", "/OSA/BR/BR_CardRtrt.do",
    "/OSA/BR/BR_CardCanRtrt.do", "/OSA/BR/BR_StaxRtrt.do",
    "/OSA/BR/BR_TrstDvlpRtrt.do", "/OSA/PS/PS_PaymPlanRead.do",
    "/OSA/PS/PaymPlanWriteRead.do", "/OSA/OS/OS_CommEvdn.do",
    "/OSA/OS/OS_ExecBrdnRead.do", "/OSA/OS/OS_SetlRpt.do",
    "/OSA/OS/OS_SetlRslt.do", "/csg/qn/qna_list.do",
    "/csg/hi/confirmationInfo.do", "/csg/hi/confirmation.do",
    "/gpin/gPinAuthRequest.do", "/front/nmbi/", "/nmbi/",
    "/csg/cr/crn_list.do", "/csg/id/insusDclr.do",
    "/csg/id/insusDclr_safDclr.do",
)

# 첨부 다운로드 허용 호스트 — **정확한 호스트만**('=' 접두, 실측값). 페이지
# 크롤링(SOURCE_DOMAINS)과 달리 서브도메인 와일드카드를 배제한다: kocca.kr로
# 두면 계약 미확정 pms.kocca.kr로의 리다이렉트가 host 검사를 통과해 버린다.
ATTACH_HOSTS = {
    "bizinfo": ("=www.bizinfo.go.kr", "=bizinfo.go.kr"),
    "nipa": ("=www.nipa.kr", "=nipa.kr"),
    "kocca": ("=www.kocca.kr",),  # pms.kocca.kr 등 서브도메인 배제(계약 미확정)
    "smtech": ("=www.smtech.go.kr", "=smtech.go.kr"),
}

# 첨부 슬라이스 소스별 설정: robots 불허 접두, 공고 id 추출, 본문 마커.
ATTACH_ROBOTS = {
    "bizinfo": BIZINFO_ROBOTS_DISALLOWED,
    "nipa": NIPA_ROBOTS_DISALLOWED,
    "kocca": KOCCA_ROBOTS_DISALLOWED,
    "smtech": SMTECH_ROBOTS_DISALLOWED,
}
# 본문 시작/끝 마커 (컨테이너 실측 2026-07-24; bizinfo는 2026-07-23)
BODY_MARKERS = {
    "bizinfo": (BIZINFO_START_MARKERS, BIZINFO_END_MARKERS),
    "nipa": ((r'<div[^>]+class="[^"]*tbWrap[^"]*gonggo[^"]*"',
              r'<div[^>]+class="[^"]*hwp_editor_board_content[^"]*"'),
             (r'<footer\b', r'<div[^>]+id="footer"')),
    "kocca": ((r'<div[^>]+id="contents_body"',),
              (r'<footer\b', r'<div[^>]+id="footer"')),
    "smtech": ((r'<div[^>]+id="subcontent"',),
               (r'<div[^>]+id="footer"', r'<footer\b')),
}


def parse_nipa_attachments(h):
    """NIPA 상세의 첨부(/comm/getFile?...) — 실측 2026-07-24.

    <a href="/comm/getFile?srvcId=...&fileNo=...">파일명.hwp (파일크기: 134 KB)</a>
    앵커 텍스트에서 '(파일크기: …)' 꼬리를 제거해 파일명을 얻는다."""
    out, seen = [], set()
    for m in re.finditer(r'href="(/comm/getFile\?[^"]+)"[^>]*>([\s\S]*?)</a>', h):
        url = "https://www.nipa.kr" + htmllib.unescape(m.group(1))
        if url in seen:
            continue
        seen.add(url)
        name = clean(re.sub(r"<[^>]+>", " ",
                            re.sub(r"\(파일크기[\s\S]*$", "", m.group(2))))
        out.append({"url": url, "filename": name or None})
    return out


def parse_smtech_attachments(h):
    """SMTECH 상세의 첨부 — 실측 2026-07-24.

    <a ... onclick="cfn_AtchFileDownload('<ID>','/front','fileDownFrame')">파일명</a>
    (href="javascript:cfn_..." 변형 포함). 다운로드 URL은 common.js의
    cfn_AtchFileDownloadUrl 계약: <context>/comn/AtchFileDownload.do?atchFileId=<ID>"""
    out, seen = [], set()
    for m in re.finditer(
            r"<a[^>]*cfn_AtchFileDownload\('([0-9A-Fa-f]+)'\s*,\s*'([^']*)'"
            r"[^>]*>([\s\S]*?)</a>", h):
        fid, ctx = m.group(1), m.group(2) or "/front"
        url = f"https://www.smtech.go.kr{ctx}/comn/AtchFileDownload.do?atchFileId={fid}"
        if url in seen:
            continue
        seen.add(url)
        name = clean(re.sub(r"<[^>]+>", " ", m.group(3)))
        out.append({"url": url, "filename": name or None})
    return out


def _kocca_popup_looks_valid(ph):
    """파일 행 0건인 팝업이 '정상 빈 팝업'인지 판별 — 실측(2026-07-24) 기준
    빈 팝업은 '해당자료가 존재하지 않습니다' 명시 문구를 가진다. **명시 문구만**
    승인한다: '공고관련자료'/board_write01 같은 레이아웃 마커는 Access Denied·
    파일행 마크업 개편 페이지에도 남을 수 있어, 행 0건 + 레이아웃 마커만으로
    '첨부 없음'을 승인하면 fail-open이 된다 — 그 경우는 차단/개편 의심으로
    fail-closed(첨부 유무 불명)."""
    return "해당자료가 존재하지 않습니다" in ph


def kocca_popup_refs(h):
    """KOCCA 상세의 팝업 지목 — (팝업1 intcNo 목록, 팝업2 pblancId 목록).

    1. openNoticeFileList1('<intcNo>') → /kocca/noticeFilePop.do?intcNo=… (robots 허용) — 팝업을
       따로 받아(``kocca_popup_url``) fn_fileDownload 행을 읽는다(``parse_kocca_popup``).
    2. openNoticeFileList2('<pblancId>') → pms.kocca.kr(별도 PMS, JS 팝업) — 다운로드 계약 미확정:
       링크만 기록(``skipped_unverified``)."""
    p1 = list(dict.fromkeys(re.findall(r"openNoticeFileList1\('([^']+)'\)", h)))
    p2 = list(dict.fromkeys(re.findall(r"openNoticeFileList2\('([^']+)'\)", h)))
    return p1, p2


def kocca_popup_url(intc):
    return "https://www.kocca.kr/kocca/noticeFilePop.do?intcNo=" + urllib.parse.quote(str(intc), safe="")


def kocca_pms_url(pid):
    return "https://pms.kocca.kr/pblanc/pblancPopupViewPage.do?pblancId=" + urllib.parse.quote(str(pid), safe="")


def parse_kocca_popup(ph):
    """팝업1 본문의 첨부 행. 행 0건이면 명시 문구('해당자료가 존재하지 않습니다')일 때만 빈 목록,
    아니면 None(구조 미확인 — 차단·개편 의심, fail-closed)."""
    out, seen = [], set()
    for m in re.finditer(r"<a[^>]*fn_fileDownload\('([^']+)'\s*,\s*'?(\d+)'?\)[^>]*>([\s\S]*?)</a>", ph):
        url = ("https://www.kocca.kr/kocca/noticeFileDown.do?intcNo="
               f"{urllib.parse.quote(m.group(1), safe='')}&seqNo={m.group(2)}")
        if url in seen:
            continue
        seen.add(url)
        out.append({"url": url, "filename": clean(re.sub(r"<[^>]+>", " ", m.group(3))) or None})
    if not out and not _kocca_popup_looks_valid(ph):
        return None
    return out


def collect_attachments(source, h):
    """kocca 를 뺀 소스의 첨부 링크(kocca 는 팝업을 따로 받는다 — kocca_popup_refs)."""
    if source == "bizinfo":
        return parse_bizinfo_attachments(h)
    if source == "nipa":
        return parse_nipa_attachments(h)
    if source == "smtech":
        return parse_smtech_attachments(h)
    return []


def source_of_url(url):
    for name, domains in SOURCE_DOMAINS.items():
        if host_allowed(url, domains):
            return name
    return None
