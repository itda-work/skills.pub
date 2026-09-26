#!/usr/bin/env python3
"""gov-report header.xml 에서 official-letter·briefing 템플릿의 header.xml 을 파생한다.

두 템플릿은 글꼴 목록·기본 스타일을 gov-report(kist-aix/hwpx MIT 파생)와 공유하고,
자기 조판에 필요한 charPr/paraPr/borderFill 만 **뒤에 덧붙인다**(기존 id 불변 →
tables/basic.xml 등 공용 표 템플릿을 그대로 쓴다). 재실행해도 결과가 같다(멱등).

    python3 scripts/derive_template_headers.py          # 파생 실행
    python3 scripts/derive_template_headers.py --check  # 커밋본과 diff 0 인지 검사

#1651 — 외부 스킬(gonggong_hwpxskills)에서 얻은 것은 "표지·목차·섹션바·□○―※ 4단" 과
"기안문 항목기호 8단·여백·끝 표시" 라는 **양식 지식**뿐이다. XML·수치·팔레트는 여기서 새로 정한다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "hwpx_report" / "assets" / "templates"
SRC = BASE / "gov-report" / "header.xml"

# fontRef hangul id (gov-report fontface 순서): 2=맑은 고딕 4=휴먼명조 5=HY헤드라인M 6=한양신명조 7=한양중고딕


def char_pr(cid: int, height: int, font: int, *, color: str = "#000000", bold: bool = False, spacing: int = 0) -> str:
    # 한자·일어·기타는 gov-report 관례대로 hangul id+1 계열을 쓰되, 없으면 같은 id 로 둔다.
    other = font + 1 if font in (4, 5, 6, 7) else font
    bold_xml = "<hh:bold/>" if bold else ""
    return (
        f'<hh:charPr id="{cid}" height="{height}" textColor="{color}" shadeColor="none" useFontSpace="0" '
        f'useKerning="0" symMark="NONE" borderFillIDRef="2">'
        f'<hh:fontRef hangul="{font}" latin="{font}" hanja="{other}" japanese="{other}" other="{other}" symbol="{other}" user="{other}"/>'
        '<hh:ratio hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>'
        f'<hh:spacing hangul="{spacing}" latin="{spacing}" hanja="{spacing}" japanese="{spacing}" other="{spacing}" symbol="{spacing}" user="{spacing}"/>'
        '<hh:relSz hangul="100" latin="100" hanja="100" japanese="100" other="100" symbol="100" user="100"/>'
        '<hh:offset hangul="0" latin="0" hanja="0" japanese="0" other="0" symbol="0" user="0"/>'
        f"{bold_xml}"
        '<hh:underline type="NONE" shape="SOLID" color="#000000"/><hh:strikeout shape="NONE" color="#000000"/>'
        '<hh:outline type="NONE"/><hh:shadow type="NONE" color="#C0C0C0" offsetX="10" offsetY="10"/></hh:charPr>'
    )


def para_pr(pid: int, align: str, *, left: int = 0, intent: int = 0, prev: int = 0, next_: int = 0, line: int = 160) -> str:
    margin = (
        f'<hh:margin><hc:intent value="{intent}" unit="HWPUNIT"/><hc:left value="{left}" unit="HWPUNIT"/>'
        f'<hc:right value="0" unit="HWPUNIT"/><hc:prev value="{prev}" unit="HWPUNIT"/><hc:next value="{next_}" unit="HWPUNIT"/></hh:margin>'
        f'<hh:lineSpacing type="PERCENT" value="{line}" unit="HWPUNIT"/>'
    )
    return (
        f'<hh:paraPr id="{pid}" tabPrIDRef="0" condense="0" fontLineHeight="0" snapToGrid="0" suppressLineNumbers="0" checked="0">'
        f'<hh:align horizontal="{align}" vertical="BASELINE"/><hh:heading type="NONE" idRef="0" level="0"/>'
        '<hh:breakSetting breakLatinWord="KEEP_WORD" breakNonLatinWord="KEEP_WORD" widowOrphan="0" keepWithNext="0" keepLines="0" pageBreakBefore="0" lineWrap="BREAK"/>'
        '<hh:autoSpacing eAsianEng="0" eAsianNum="0"/>'
        f'<hp:switch><hp:case hp:required-namespace="http://www.hancom.co.kr/hwpml/2016/HwpUnitChar">{margin}</hp:case><hp:default>{margin}</hp:default></hp:switch>'
        '<hh:border borderFillIDRef="2" offsetLeft="0" offsetRight="0" offsetTop="0" offsetBottom="0" connect="0" ignoreMargin="0"/></hh:paraPr>'
    )


def border_fill(bid: int, *, fill: str | None, top: str | None = None, bottom: str | None = None, sides: str | None = None) -> str:
    def side(name: str, color: str | None) -> str:
        if color:
            return f'<hh:{name} type="SOLID" width="0.12 mm" color="{color}"/>'
        return f'<hh:{name} type="NONE" width="0.1 mm" color="#000000"/>'

    brush = (
        f'<hc:fillBrush><hc:winBrush faceColor="{fill}" hatchColor="#000000" alpha="0"/></hc:fillBrush>' if fill else ""
    )
    return (
        f'<hh:borderFill id="{bid}" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0">'
        '<hh:slash type="NONE" Crooked="0" isCounter="0"/><hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
        f"{side('leftBorder', sides)}{side('rightBorder', sides)}{side('topBorder', top)}{side('bottomBorder', bottom)}"
        f'<hh:diagonal type="SOLID" width="0.1 mm" color="#000000"/>{brush}</hh:borderFill>'
    )


# ── official-letter(기안문): 맑은 고딕 11.5pt 본문, 항목 4단 내어쓰기, 기관명·발신명의 ──────────
OFFICIAL_CHAR = [
    char_pr(31, 1150, 2),                 # 본문
    char_pr(32, 1150, 2, bold=True),      # 수신·제목 라벨
    char_pr(33, 2000, 5, spacing=-4),     # 상단 기관명
    char_pr(34, 1500, 2, bold=True),      # 발신명의
    char_pr(35, 900, 2),                  # 하단 시행·주소 정보
]
# 한컴 실렌더 실측(#1651, pdf 좌표): paraPr `left` 는 **첫 줄** 시작 위치, 둘째 줄부터 `left + |intent|` 에 선다
# (내어쓰기 = 본문 줄을 오른쪽으로). 11.5pt 한글 1자 ≈ 1150 HWPUNIT = 2타.
# 시행규칙: 1단계는 기본선에서, 이후 단계는 상위보다 2타 오른쪽에서 시작, 둘째 줄은 내용 첫 글자에 맞춘다.
OFFICIAL_PARA = [
    para_pr(25, "LEFT", line=130),                                   # 수신·경유·제목
    para_pr(26, "JUSTIFY", left=0, intent=-1150, line=130),          # 1단계 1.  (첫 줄 0, 둘째 줄 1150)
    para_pr(27, "JUSTIFY", left=1150, intent=-1150, line=130),       # 2단계 가.
    para_pr(28, "JUSTIFY", left=2300, intent=-1150, line=130),       # 3단계 1)
    para_pr(29, "JUSTIFY", left=3450, intent=-1150, line=130),       # 4단계 가)
    para_pr(30, "CENTER", line=130, prev=600, next_=600),            # 기관명·발신명의
    para_pr(31, "LEFT", left=0, intent=-3450, prev=400, line=130),   # 붙임 첫 줄 ("붙임  " 뒤 3자 폭에 둘째 줄)
    para_pr(32, "LEFT", line=110),                                   # 하단 정보
    para_pr(33, "LEFT", left=3450, intent=-1150, line=130),          # 붙임 둘째 항목부터 (첫 항목 번호 위치에 정렬)
]
OFFICIAL_BORDER = [
    border_fill(11, fill=None, bottom="#000000"),   # 제목 아래 구분선(문단 테두리용)
]

# ── briefing(내부 보고서): 표지·목차·섹션바·□○―※ ───────────────────────────────────────────
NAVY, LIGHT, RULE = "#1F4E79", "#EEF2F7", "#9DB2CC"
BRIEF_CHAR = [
    char_pr(31, 3000, 5),                  # 표지 기관명
    char_pr(32, 2200, 5),                  # 표지 제목·작성일 (25pt 는 긴 제목이 글자 단위로 깨져 22pt — 한컴 실렌더 #1651)
    char_pr(33, 2800, 5),                  # "목 차"
    char_pr(34, 1800, 4),                  # 목차 항목
    char_pr(35, 1700, 4, color="#FFFFFF"), # 섹션바 로마숫자(남색 위 흰 글자)
    char_pr(36, 1700, 5),                  # 섹션바 제목
    char_pr(37, 2200, 5),                  # 본문 제목
    char_pr(38, 1600, 5),                  # □
    char_pr(39, 1500, 4),                  # ○
    char_pr(40, 1500, 4),                  # ―
    char_pr(41, 1300, 7),                  # ※
]
BRIEF_PARA = [
    para_pr(25, "CENTER", line=160),                                  # 표지·본문 제목
    para_pr(26, "JUSTIFY", left=0, intent=0, prev=1500, line=160),    # □
    para_pr(27, "JUSTIFY", left=2000, intent=-900, prev=1000, line=160),  # ○
    para_pr(28, "JUSTIFY", left=3000, intent=-900, prev=600, line=160),   # ―
    para_pr(29, "JUSTIFY", left=4000, intent=-900, prev=300, line=160),   # ※
    para_pr(30, "LEFT", left=1500, prev=500, line=180),               # 목차 항목
    para_pr(31, "CENTER", line=130),                                  # 섹션바 셀
    para_pr(32, "LEFT", left=800, line=130),                          # 섹션바 제목 셀
]
BRIEF_BORDER = [
    border_fill(11, fill=NAVY),                            # 로마숫자 셀
    border_fill(12, fill=LIGHT, top=RULE, bottom=RULE),    # 제목 셀
    border_fill(13, fill=None),                            # 간격 셀
]

# ── ai-report(행안부 AI 친화적 보고서, 2026-08-24 보도자료 예시 실측 비례): 장식 없음 ───────────
# 실측(보도자료 '적용 후' 축소 예시): 절 제목 맑은 고딕 12pt B · 본문 함초롬바탕 11pt · 표 제목 맑은 고딕 9pt B 중앙
# · 메타 줄 맑은 고딕 9pt 중앙. 실제 보고서 크기로 비례 확대(본문 13pt 기준). 바탕(8)을 함초롬바탕 대용으로 쓴다.
AI_CHAR = [
    char_pr(31, 1800, 2, bold=True),   # 문서 제목
    char_pr(32, 1100, 2),              # 메타 줄(보고 유형 / 일자 / 부서 담당자)
    char_pr(33, 1400, 2, bold=True),   # 절 제목 1. 2.
    char_pr(34, 1300, 8),              # ○ 항목·산문
    char_pr(35, 1300, 8),              # - 하위 항목
    char_pr(36, 1200, 8),              # · 3단계
    char_pr(37, 1100, 2, bold=True),   # 표·그림 제목 < 표 1. … >
]
AI_PARA = [
    para_pr(25, "CENTER", prev=600, next_=200, line=160),                 # 제목
    para_pr(26, "CENTER", prev=0, next_=800, line=160),                   # 메타 줄
    para_pr(27, "JUSTIFY", left=0, intent=0, prev=900, next_=200, line=170),  # 절 제목
    para_pr(28, "JUSTIFY", left=1300, intent=-1300, prev=400, line=175),  # ○
    para_pr(29, "JUSTIFY", left=2300, intent=-1000, prev=250, line=175),  # -
    para_pr(30, "JUSTIFY", left=3300, intent=-1000, prev=150, line=175),  # ·
    para_pr(31, "JUSTIFY", left=0, intent=1300, prev=400, line=175),      # 산문(첫 줄 들여쓰기)
    para_pr(32, "CENTER", prev=500, next_=100, line=140),                 # 표·그림 제목
]

TARGETS = {
    "official-letter": (OFFICIAL_CHAR, OFFICIAL_PARA, OFFICIAL_BORDER),
    "briefing": (BRIEF_CHAR, BRIEF_PARA, BRIEF_BORDER),
    "ai-report": (AI_CHAR, AI_PARA, []),
}


def derive(src: str, chars: list[str], paras: list[str], borders: list[str]) -> str:
    def bump(text: str, tag: str, add: int) -> str:
        m = re.search(rf'<hh:{tag} itemCnt="(\d+)">', text)
        assert m, tag
        return text.replace(m.group(0), f'<hh:{tag} itemCnt="{int(m.group(1)) + add}">', 1)

    out = src
    out = bump(out, "charProperties", len(chars)).replace("</hh:charProperties>", "".join(chars) + "</hh:charProperties>", 1)
    out = bump(out, "paraProperties", len(paras)).replace("</hh:paraProperties>", "".join(paras) + "</hh:paraProperties>", 1)
    out = bump(out, "borderFills", len(borders)).replace("</hh:borderFills>", "".join(borders) + "</hh:borderFills>", 1)
    return out


def main(argv: list[str]) -> int:
    check = "--check" in argv
    src = SRC.read_text(encoding="utf-8")
    for tid, (chars, paras, borders) in TARGETS.items():
        dst = BASE / tid / "header.xml"
        derived = derive(src, chars, paras, borders)
        if check:
            if not dst.exists() or dst.read_text(encoding="utf-8") != derived:
                print(f"DRIFT: {dst}", file=sys.stderr)
                return 1
            print(f"ok {tid}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(derived, encoding="utf-8")
        print(f"wrote {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
