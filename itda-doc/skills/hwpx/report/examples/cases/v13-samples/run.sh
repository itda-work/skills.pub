#!/usr/bin/env bash
# v1.3 샘플 일괄 생성 — 사용법: bash run.sh <출력디렉토리>
# SKILL_DIR 은 이 스크립트 위치에서 역산한다. 결과·경고 요약은 <출력>/SUMMARY.md.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
SKILL="$(cd "${HERE}/../../../.." && pwd)"
OUT="${1:?출력 디렉토리를 주세요}"
PY="${PYTHON:-python3}"
FX="${SKILL}/tests/reader/fixtures/inputs/multi_section_with_image.hwpx"
mkdir -p "${OUT}"
SUM="${OUT}/SUMMARY.md"
: > "${SUM}"
log() { printf '%s\n' "$*" | tee -a "${SUM}"; }
gen() { # gen <이름> <소스.md> <layout> <template|--template-dir DIR>
  local name="$1" src="$2" layout="$3"; shift 3
  local spec="${OUT}/${name}.spec.json" hw="${OUT}/${name}.hwpx" w="${OUT}/${name}.warnings.txt"
  "${PY}" "${SKILL}/report/scripts/md_to_docspec.py" "${src}" -o "${spec}" --layout "${layout}" 2>"${w}"
  local rc1=$?
  PYTHONPATH="${SKILL}/report${PYTHONPATH:+:$PYTHONPATH}" "${PY}" -m hwpx_report convert "${spec}" -o "${hw}" "$@" 2>>"${w}"
  local rc2=$?
  PYTHONPATH="${SKILL}/reader" "${PY}" -m hwpx_native convert "${hw}" -o "${OUT}/${name}.md" --format md --no-extract-images >/dev/null 2>&1
  local rc3=$?
  log "| ${name} | ${layout} / $* | mapper rc=${rc1} · convert rc=${rc2} · reader rc=${rc3} | $(grep -c . "${w}") 경고 |"
}
log "# v1.3 샘플 생성 결과 ($(date '+%Y-%m-%d %H:%M'))"
log ""
log "| 샘플 | layout / template | 결과 | 경고 줄 |"
log "|---|---|---|---|"
gen 01-ai-outline-roman   "${HERE}/01-ai-outline-roman.md"   ai-report --template ai-report
gen 02-ai-brief-memo      "${HERE}/02-ai-brief-memo.md"      ai-report --template ai-report
gen 03-ai-inspection      "${HERE}/03-ai-inspection-tables.md" ai-report --template ai-report
gen 04-letter-external    "${HERE}/04-letter-external-full.md" official-letter --template official-letter
gen 05-letter-internal    "${HERE}/05-letter-internal-approval.md" official-letter --template official-letter
gen 06-press-release      "${HERE}/06-press-release-table.md" press-release --template press-release
gen 07-briefing           "${HERE}/07-briefing-attachments.md" briefing --template briefing
gen 08-gov-report         "${HERE}/08-gov-report-legacy.md"  report --template gov-report
gen 11-form-application   "${HERE}/11-form-application.md"   report --template gov-report
gen 12-form-guided        "${HERE}/12-form-guided.md"        ai-report --template ai-report

# 09 참고 서식 프로파일 — 실 한컴 저장본(표지 섹션 + 본문 섹션)을 참고로 01 을 그 서식으로
rm -rf "${OUT}/profile-real"
"${PY}" "${SKILL}/report/scripts/derive_profile.py" analyze "${FX}" -o "${OUT}/profile-real" --layout ai-report >"${OUT}/09-profile-real.analyze.json" 2>"${OUT}/09-profile-real.warnings.txt"
log "| 09-profile-real (analyze) | derive_profile analyze ← multi_section_with_image | rc=$? | $(grep -c . "${OUT}/09-profile-real.warnings.txt") 경고 |"
gen 09-ai-in-real-profile "${HERE}/01-ai-outline-roman.md" ai-report --template-dir "${OUT}/profile-real"
"${PY}" "${SKILL}/report/scripts/derive_profile.py" compare "${OUT}/profile-real" "${OUT}/09-ai-in-real-profile.hwpx" --ref "${FX}" >"${OUT}/09-compare.json" 2>&1
log "| 09-compare | compare --ref | rc=$? · ok=$(grep -o '"ok": [a-z]*' "${OUT}/09-compare.json" | head -1) |  |"

# 10 참고 서식 프로파일 — 우리 구 개조식 산출(08)을 참고로 02 를 report 조판으로
rm -rf "${OUT}/profile-gov"
"${PY}" "${SKILL}/report/scripts/derive_profile.py" analyze "${OUT}/08-gov-report.hwpx" -o "${OUT}/profile-gov" --layout report >"${OUT}/10-profile-gov.analyze.json" 2>"${OUT}/10-profile-gov.warnings.txt"
log "| 10-profile-gov (analyze) | derive_profile analyze ← 08-gov-report.hwpx | rc=$? | $(grep -c . "${OUT}/10-profile-gov.warnings.txt") 경고 |"
gen 10-memo-in-gov-profile "${HERE}/02-ai-brief-memo.md" report --template-dir "${OUT}/profile-gov"
"${PY}" "${SKILL}/report/scripts/derive_profile.py" compare "${OUT}/profile-gov" "${OUT}/10-memo-in-gov-profile.hwpx" --ref "${OUT}/08-gov-report.hwpx" >"${OUT}/10-compare.json" 2>&1
log "| 10-compare | compare --ref | rc=$? · ok=$(grep -o '"ok": [a-z]*' "${OUT}/10-compare.json" | head -1) |  |"

# 11 채우기(신청서형): --dump → --label/--cell/--tick → --residue
F="${SKILL}/scripts/fill_hwpx.py"; A="${OUT}/11-form-application.hwpx"
"${PY}" "${F}" "${A}" --dump >"${OUT}/11-dump.txt" 2>&1
"${PY}" "${F}" "${A}" -o "${OUT}/11-form-filled.hwpx" --strict \
  --label "성명=김서준" --label "생년월일=1998. 3. 14." --label "연락처=010-1234-5678" --label "전자우편=seojun@example.com" \
  --label "창업 아이템=지역 특산물 온라인 구독 서비스" --label "창업 예정일=2027. 3. 2." --label "소요 자금(천 원)=45,000" \
  --cell "표0 r2 c1=잇다광역시 중구 시청로 1, 302호" \
  --tick "개인정보" --tick "신청 내용이 사실과" >"${OUT}/11-fill.log" 2>&1
log "| 11-form-filled | fill_hwpx --label×7 --cell --tick×2 --strict | rc=$? | $(grep -c '채움\|치환\|체크' "${OUT}/11-fill.log") 건 |"
"${PY}" "${F}" "${OUT}/11-form-filled.hwpx" --residue "${A}" --json >"${OUT}/11-residue.json" 2>"${OUT}/11-residue.txt"
log "| 11-residue | --residue 원본 | rc=$? |  |"
PYTHONPATH="${SKILL}/reader" "${PY}" -m hwpx_native convert "${OUT}/11-form-filled.hwpx" -o "${OUT}/11-form-filled.md" --format md --no-extract-images >/dev/null 2>&1

# 12 채우기(안내문형): --check --fix → 채움 --strict → --residue --keep
G="${OUT}/12-form-guided.hwpx"
"${PY}" "${F}" "${G}" --dump >"${OUT}/12-dump.txt" 2>&1
"${PY}" "${F}" "${G}" --check --map "${HERE}/12-form-guided-map.json" --fix "${OUT}/12-map.fixed.json" --json >"${OUT}/12-check.json" 2>"${OUT}/12-check.txt"
log "| 12-check | --check --fix (혼동문자 ‧ 포함 키) | rc=$? · $(grep -o '"summary": {[^}]*}' "${OUT}/12-check.json") |  |"
"${PY}" "${F}" "${G}" -o "${OUT}/12-form-filled.hwpx" --strict --map "${OUT}/12-map.fixed.json" >"${OUT}/12-fill.log" 2>&1
log "| 12-form-filled | fill --strict --map fixed | rc=$? |  |"
"${PY}" "${F}" "${OUT}/12-form-filled.hwpx" --residue "${G}" --map "${OUT}/12-map.fixed.json" --keep "임의로 삭제하지 마십시오" --json >"${OUT}/12-residue.json" 2>"${OUT}/12-residue.txt"
log "| 12-residue | --residue --keep | rc=$? |  |"
PYTHONPATH="${SKILL}/reader" "${PY}" -m hwpx_native convert "${OUT}/12-form-filled.hwpx" -o "${OUT}/12-form-filled.md" --format md --no-extract-images >/dev/null 2>&1

# 13 읽기 — HTML 왕복(표 정렬·이미지)
PYTHONPATH="${SKILL}/reader" "${PY}" -m hwpx_native convert "${OUT}/01-ai-outline-roman.hwpx" -o "${OUT}/13-read-01.html" --format html >/dev/null 2>&1
log "| 13-read-html | reader --format html ← 01 | rc=$? |  |"
log ""
log "생성물: ${OUT}"
