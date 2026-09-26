"""fill_hwpx CLI — --dump / --list / --check / --residue / 채우기(--set·--map·--cell·--label·--tick)."""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.dom import minidom

from .check import (
    PLACEHOLDER_RE,
    check_mapping,
    find_residue,
    fix_collisions,
    fixed_mapping,
    format_verdict,
    is_guidance_like,
)
from .fill import (
    ControlInvariantError,
    FillError,
    FillReport,
    apply_edits,
    assert_control_invariant,
    fill_cell,
    fill_texts,
    find_cell,
    parse_cell_spec,
    resolve_label,
    show,
    strip_lineseg_edits,
    tick_items,
)
from .scan import SENTINEL, Para, Section, display_with_marks, scan_section, visible

SECTION_RE = re.compile(r"^Contents/section(\d+)\.xml$")
PREVIEW_ENTRY = "Preview/PrvText.txt"
PREVIEW_MAX_CHARS = 2000

Value = str | list[str]

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_CHECK = 2
EXIT_STRICT = 3


# ---- 입출력 ---------------------------------------------------------------------


def read_sections(path: Path) -> list[tuple[str, str]]:
    """(엔트리명, XML) 을 section 번호 순으로."""
    with zipfile.ZipFile(path) as zf:
        names = [(int(SECTION_RE.match(n).group(1)), n) for n in zf.namelist() if SECTION_RE.match(n)]
        names.sort()
        return [(n, zf.read(n).decode("utf-8")) for _, n in names]


def scan_document(sections: list[tuple[str, str]]) -> list[Section]:
    """섹션들을 문서 순서로 스캔하고 표·문단 일련번호를 문서 전체로 잇는다. 나열 번호(number)도 매긴다."""
    out: list[Section] = []
    table_base = 0
    para_base = 0
    for _, xml in sections:
        sec = scan_section(xml, table_base=table_base, para_base=para_base)
        table_base += len(sec.tables)
        para_base += len(sec.paras)
        out.append(sec)
    number_paras(out)
    return out


def number_paras(secs: list[Section]) -> None:
    n = 0
    for sec in secs:
        for p in sec.paras:
            if p.is_listed:
                n += 1
                p.number = n
            else:
                p.number = 0


def all_paras(secs: list[Section]) -> list[Para]:
    return [p for sec in secs for p in sec.paras]


def all_tables(secs: list[Section]) -> list:
    return [t for sec in secs for t in sec.tables]


def load_mapping(args: argparse.Namespace) -> dict[str, Value]:
    mapping: dict[str, Value] = {}
    if args.map:
        data = json.loads(Path(args.map).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            sys.exit(f"오류: --map 파일은 JSON 객체여야 합니다: {args.map}")
        for k, v in data.items():
            if isinstance(v, list):
                mapping[str(k)] = [str(x) for x in v]
            else:
                mapping[str(k)] = str(v)
    seen: dict[str, int] = {}
    for item in args.set or []:
        if "=" not in item:
            sys.exit(f"오류: --set 형식은 'placeholder=값' 입니다: {item!r}")
        key, _, value = item.partition("=")
        seen[key] = seen.get(key, 0) + 1
        if seen[key] == 1:
            mapping[key] = value
        else:
            prev = mapping[key]
            mapping[key] = (prev if isinstance(prev, list) else [prev]) + [value]
    return mapping


def parse_kv(items: list[str] | None, flag: str) -> list[tuple[str, str]]:
    out = []
    for item in items or []:
        if "=" not in item:
            sys.exit(f"오류: {flag} 형식은 '이름=값' 입니다: {item!r}")
        k, _, v = item.partition("=")
        out.append((k, v))
    return out


# ---- dump / list -------------------------------------------------------------------


def para_flag(p: Para) -> str:
    """OK | CTRL(보이는 텍스트를 나누는 컨트롤 보유) | EMPTY(보이는 텍스트 없음 — 빈 셀·표만 품은 셀)."""
    if p.has_ctrl:
        return "CTRL"
    if not visible(p.text):
        return "EMPTY"
    return "OK"


def cmd_dump(src: Path) -> int:
    secs = scan_document(read_sections(src))
    listed = [p for p in all_paras(secs) if p.is_listed]
    if not listed:
        print("본문 텍스트가 없습니다.")
        return EXIT_USAGE
    print(f"문단 {len(listed)}개 — 형식: 번호\t위치\t플래그\t텍스트 (마지막 탭 뒤 전체가 키)")
    print("  치환은 문단 텍스트의 부분문자열 매칭이라 조각난 자리(예: 머리글의 '부서명')도 짧은 키로 채울 수 있고,")
    print("  항목 기호(□ ○ ― ※)는 키에서 빼야 기호가 남는다. CTRL = 탭(⇥)·줄바꿈(⏎)·필드/그림/표(▯) 등 분절 요소 보유 — 키를 그 앞뒤로 나눈다.")
    print('  EMPTY = 빈 셀 문단 — --cell "표i r c=값" 또는 --label "라벨=값" 으로 채운다. 위치 "표i r c" 의 i 는 문서 등장 순서.')
    for p in listed:
        print(f"{p.number}\t{p.location}\t{para_flag(p)}\t{display_with_marks(p)}")
    return EXIT_OK


def cmd_list(src: Path, pattern: str | None) -> int:
    rx = re.compile(pattern) if pattern else PLACEHOLDER_RE
    found: dict[str, int] = {}
    for p in all_paras(scan_document(read_sections(src))):
        for m in rx.finditer(p.text):
            if SENTINEL in m.group():
                continue
            found[m.group()] = found.get(m.group(), 0) + 1
    if not found:
        print("placeholder 후보를 찾지 못했습니다. --pattern 으로 직접 지정해 보세요.")
        return EXIT_USAGE
    print(f"placeholder 후보 {len(found)}종:")
    for key, n in found.items():
        print(f"  {key}  (x{n})")
    return EXIT_OK


# ---- check / residue -------------------------------------------------------------------


def cmd_check(src: Path, mapping: dict[str, Value], fix_out: Path | None, as_json: bool) -> int:
    if not mapping:
        sys.exit("오류: --check 에는 --set 또는 --map 으로 검사할 키가 필요합니다.")
    paras = all_paras(scan_document(read_sections(src)))
    result = check_mapping(mapping, paras)
    human = sys.stderr if as_json else sys.stdout
    for v in result.verdicts:
        print(format_verdict(v), file=human)
    summary = result.to_json()
    # 교정 후 키가 겹치면 --fix 는 매핑 항목을 소실시킨다 — 쓰지 않고 collision 으로 보고한다(Codex R2 F9)
    collisions = fix_collisions(mapping, result)
    if collisions:
        summary["summary"]["collision"] = len(collisions)
        summary["collisions"] = [{"fix": t, "keys": ks} for t, ks in collisions.items()]
        for t, ks in collisions.items():
            print(f"collision\t{t}\t교정하면 키 {ks} 가 같은 자리로 겹칩니다 — 키를 서로 다른 자리로 나누세요", file=human)
    if fix_out is not None:
        if collisions:
            summary["fix_skipped"] = "collision"
            print(f"교정 매핑을 쓰지 않았습니다: 충돌 {len(collisions)}건 — {fix_out} 미생성", file=human)
        else:
            fixed = fixed_mapping(mapping, result)
            fix_out.write_text(json.dumps(fixed, ensure_ascii=False, indent=2), encoding="utf-8")
            summary["fix_written"] = str(fix_out)
            print(f"교정 매핑 저장: {fix_out} (fixable {summary['summary']['fixable']}건 교정)", file=human)
    if as_json:
        print(json.dumps(summary, ensure_ascii=False))
    if collisions and result.ok:
        print(f"검사 결과: 교정 충돌 {len(collisions)}건 — 채우기 전에 키를 고치세요", file=human)
        return EXIT_CHECK
    if not result.ok:
        s = summary["summary"]
        print(
            f"검사 결과: ok {s['ok']} / fixable {s['fixable']} / ctrl {s['ctrl']} / multi {s['multi']} / missing {s['missing']} — 채우기 전에 키를 고치세요",
            file=human,
        )
        return EXIT_CHECK
    print(f"검사 결과: 키 {len(result.verdicts)}개 전부 ok", file=human)
    return EXIT_OK


def cmd_residue(filled: Path, orig: Path, mapping: dict[str, Value], keep: list[str], as_json: bool) -> int:
    orig_paras = all_paras(scan_document(read_sections(orig)))
    result_paras = all_paras(scan_document(read_sections(filled)))
    items, coverage = find_residue(orig_paras, result_paras, mapping, keep)
    human = sys.stderr if as_json else sys.stdout
    checked = sum(1 for p in orig_paras if p.text.strip())
    candidates = sum(1 for p in orig_paras if p.text.strip() and is_guidance_like(p.text))
    for it in items:
        print(f"residue\t{it.kind}\t문단 {it.paragraph}\t{it.text}", file=human)
    summary = {
        "ok": not items,
        "residue": [it.to_json() for it in items],
        "checked_paragraphs": checked,
        "candidate_paragraphs": candidates,
        "coverage": coverage,
        "keep": keep,
    }
    if as_json:
        print(json.dumps(summary, ensure_ascii=False))
    if items:
        print(
            f"잔재 {len(items)}건 — 원본 안내문이 남았거나 치환값이 결과에 없습니다"
            f"(의도한 고정 문구면 --keep 으로 제외; 값 커버리지 {coverage['values_found']}/{coverage['keys_in_original']})",
            file=human,
        )
        return EXIT_CHECK
    print(
        f"잔재 없음 (원본 문단 {checked}개 대조, 안내문 후보 {candidates}개, 값 커버리지 {coverage['values_found']}/{coverage['keys_in_original']})",
        file=human,
    )
    return EXIT_OK


# ---- fill -------------------------------------------------------------------


def build_preview(secs: list[Section]) -> bytes:
    lines = []
    for p in all_paras(secs):
        t = p.text.replace(SENTINEL, " ").strip()
        if t:
            lines.append(t)
    text = "\r\n".join(lines)
    if len(text) > PREVIEW_MAX_CHARS:
        text = text[:PREVIEW_MAX_CHARS]
    return text.encode("utf-8")


def cmd_fill(args: argparse.Namespace, src: Path, out: Path, mapping: dict[str, Value]) -> int:
    cells = [parse_cell_spec(s) for s in (args.cell or [])]
    labels = parse_kv(args.label, "--label")
    ticks = list(args.tick or [])
    if not (mapping or cells or labels or ticks):
        sys.exit("오류: --set/--map/--cell/--label/--tick 으로 채울 값을 하나 이상 지정하세요.")
    if out.resolve() == src.resolve():
        sys.exit("오류: 출력 경로가 입력과 같습니다. 원본 보존을 위해 다른 경로를 지정하세요.")

    sections = read_sections(src)
    if not sections:
        sys.exit("오류: Contents/section*.xml 이 없습니다. HWPX 파일이 맞는지 확인하세요.")
    xmls: dict[str, str] = dict(sections)
    names = [n for n, _ in sections]
    report = FillReport()  # report.changed = 변경 문단 ordinal(문서 전체 일련번호 — 섹션 간 유일)
    strict_fail = False

    def current() -> list[Section]:
        return scan_document([(n, xmls[n]) for n in names])

    # 1) 텍스트 치환(문단 단위 매칭)
    if mapping:
        cursors: dict[str, int] = {}
        for n, sec in zip(names, current()):
            edits = fill_texts(sec, mapping, cursors, report)
            if not edits:
                continue
            assert_control_invariant(sec.xml, edits)
            xmls[n] = apply_edits(sec.xml, edits)
        for key, n_rep in report.counts.items():
            value = mapping[key]
            if isinstance(value, list):
                print(f"치환: {key!r} → {n_rep}회 (순차, 값 {len(value)}개)")
                if n_rep < len(value):
                    print(f"경고: {key!r} 순차 값 {len(value) - n_rep}개가 쓰이지 않았습니다(자리가 부족)", file=sys.stderr)
            else:
                print(f"치환: {key!r} → {n_rep}회")
        leftover = {
            k: report.occurrences[k] - report.counts[k]
            for k, v in mapping.items()
            if isinstance(v, list) and report.occurrences[k] > report.counts[k]
        }
        for key, n_left in leftover.items():
            print(f"경고: {key!r} 자리 {n_left}개가 값 없이 남았습니다(순차 값 부족)", file=sys.stderr)
        missed = [k for k, n_rep in report.counts.items() if n_rep == 0]
        if missed:
            print(f"경고: 문서에서 찾지 못한 placeholder {len(missed)}건: {missed}", file=sys.stderr)
            print("      (표기 차이·컨트롤 분절·문단 합침일 수 있습니다 — --check 로 사유와 교정안을 확인하세요)", file=sys.stderr)
        # --strict: 미발견 키뿐 아니라 **값 없이 남은 순차 자리**도 실패다 — 양식 안내문이 남은 채 "성공" 으로
        # 돌아오는 것이 채우기에서 가장 위험한 결과다 (#1652 D-3).
        if missed or leftover:
            strict_fail = True

    # 2) 셀·라벨 채움 (좌표 확정 → 편집)
    if cells or labels:
        secs = current()
        tables = all_tables(secs)
        sec_of_table = {t.index: i for i, sec in enumerate(secs) for t in sec.tables}
        planned: list[tuple[int, object, str, str]] = []  # (section idx, cell, value, how)
        used: set[str] = set()

        def plan(cell, value: str, how: str) -> None:
            if cell.coord in used:
                raise FillError(f"{cell.coord} 셀을 두 번 지정했습니다({how})")
            used.add(cell.coord)
            planned.append((sec_of_table[cell.table.index], cell, value, how))

        for ti, r, c, value in cells:
            plan(find_cell(tables, ti, r, c), value, f"--cell 표{ti} r{r} c{c}")
        for label, value in labels:
            tgt = resolve_label(tables, label)
            plan(tgt.target, value, f"--label {label!r} → {tgt.target.coord} ({tgt.direction})")
        per_sec: dict[int, list] = {}
        for si, cell, value, how in planned:
            edits, res = fill_cell(secs[si], cell, value, report)
            per_sec.setdefault(si, []).extend(edits)
            prev = f" (이전: {show(res.previous)!r})" if show(res.previous) else ""
            print(f"셀 채움: {how} ← {value!r}{prev} [{res.mode}]")
            if res.warning:
                print(f"경고: {res.warning}", file=sys.stderr)
        for si, edits in per_sec.items():
            xmls[names[si]] = apply_edits(secs[si].xml, edits)

    # 3) 체크박스
    if ticks:
        tick_counts: dict[str, int] = {}
        for n, sec in zip(names, current()):
            edits = tick_items(sec, ticks, report, tick_counts)
            if edits:
                xmls[n] = apply_edits(sec.xml, edits)
        for item in ticks:
            n_t = tick_counts.get(item, 0)
            print(f"체크: {item!r} → {n_t}곳")
            if n_t == 0:
                print(f"경고: 체크박스 {item!r}(□/☐ 뒤) 를 찾지 못했습니다", file=sys.stderr)
                strict_fail = True

    # 4) 위생: 변경 문단의 linesegarray 제거(옵트인)
    if args.strip_lineseg:
        removed = 0
        for n, sec in zip(names, current()):
            edits = strip_lineseg_edits(sec, report.changed)
            if edits:
                removed += len(edits)
                xmls[n] = apply_edits(sec.xml, edits)
        print(f"위생: linesegarray 제거 {removed}문단")

    # well-formedness
    for n in names:
        try:
            minidom.parseString(xmls[n].encode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            sys.exit(f"오류: 치환 후 {n} 이 유효한 XML이 아닙니다 — 중단: {exc}")

    preview: bytes | None = None
    if args.refresh_preview:
        preview = build_preview(current())

    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(out, "w") as zout:
        wrote_preview = False
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename in xmls:
                data = xmls[info.filename].encode("utf-8")
            elif info.filename == PREVIEW_ENTRY and preview is not None:
                data = preview
                wrote_preview = True
            compress = zipfile.ZIP_STORED if info.filename == "mimetype" else zipfile.ZIP_DEFLATED
            zout.writestr(info.filename, data, compress_type=compress)
    if args.refresh_preview:
        print("위생: PrvText 재생성" if wrote_preview else "위생: PrvText 엔트리가 없어 재생성하지 않음")
    print(f"완료: {out}")
    return EXIT_STRICT if (strict_fail and args.strict) else EXIT_OK


# ---- main -------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="HWPX 양식 placeholder 채우기(문단 단위 매칭·빈 셀·사전검증·잔재 대조)")
    parser.add_argument("input", type=Path, help="입력 .hwpx 양식(--residue 에서는 채운 결과)")
    parser.add_argument("-o", "--output", type=Path, help="출력 .hwpx 경로")
    parser.add_argument("--set", action="append", metavar="KEY=VALUE", help="치환 항목 (반복 가능, 같은 키 반복 = 순차 치환)")
    parser.add_argument("--map", metavar="JSON", help="치환 매핑 JSON 파일 {placeholder: 값 | [값…]}")
    parser.add_argument("--cell", action="append", metavar="'표i rN cM=값'", help="좌표 셀 채움 (반복 가능)")
    parser.add_argument("--label", action="append", metavar="'라벨=값'", help="라벨 셀의 오른쪽/아래 빈 셀 채움 (반복 가능)")
    parser.add_argument("--tick", action="append", metavar="항목", help="□항목/☐항목 → ☑항목 (반복 가능)")
    parser.add_argument("--list", action="store_true", help="placeholder 후보 나열")
    parser.add_argument("--dump", action="store_true", help="문단 전수 나열(번호·위치·플래그·텍스트)")
    parser.add_argument("--pattern", metavar="REGEX", help="--list 에서 쓸 후보 정규식")
    parser.add_argument("--check", action="store_true", help="매핑 키 사전검증(ok/fixable/ctrl/multi/missing) — 문제 있으면 exit 2")
    parser.add_argument("--fix", type=Path, metavar="OUT.json", help="--check 의 fixable 만 교정한 매핑 저장")
    parser.add_argument("--residue", type=Path, metavar="원본.hwpx", help="채운 결과(input)에 원본 안내문이 남았는지 + 치환값이 실제로 들어갔는지 대조 — 어긋나면 exit 2")
    parser.add_argument("--keep", action="append", metavar="문구", help="--residue 에서 의도적 고정 문구 제외 (반복 가능)")
    parser.add_argument("--json", action="store_true", help="--check/--residue 결과를 JSON 으로 stdout 에(사람용 줄은 stderr)")
    parser.add_argument("--strict", action="store_true", help="미발견 placeholder·값 없이 남은 순차 자리·미발견 체크박스 시 exit 3")
    parser.add_argument("--strip-lineseg", action="store_true", help="변경된 문단의 <hp:linesegarray> 제거(옵트인)")
    parser.add_argument("--refresh-preview", action="store_true", help="Preview/PrvText.txt 를 치환 후 본문으로 재생성(옵트인)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.input.is_file():
        sys.exit(f"오류: 입력 파일이 없습니다: {args.input}")
    try:
        if args.dump:
            return cmd_dump(args.input)
        if args.list:
            return cmd_list(args.input, args.pattern)
        if args.check:
            return cmd_check(args.input, load_mapping(args), args.fix, args.json)
        if args.residue is not None:
            if not args.residue.is_file():
                sys.exit(f"오류: --residue 원본 파일이 없습니다: {args.residue}")
            return cmd_residue(args.input, args.residue, load_mapping(args), list(args.keep or []), args.json)
        if not args.output:
            sys.exit("오류: 채우기 모드에는 -o/--output 이 필요합니다.")
        return cmd_fill(args, args.input, args.output, load_mapping(args))
    except FillError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return EXIT_CHECK
    except ControlInvariantError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return EXIT_USAGE
