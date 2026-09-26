#!/bin/bash
# pmlab.sh 셸 계약 테스트 — 스텁 prlctl 로 게스트 VM 없이 검증(bash·zsh 양쪽).
# 실행: bash scripts/pmlab-contract-test.sh ; zsh scripts/pmlab-contract-test.sh
#
# 커버(검증 게이트 ⑤):
#   1. 마스터 VM 가드(exec/runps rc=9, 스텁 미호출)
#   2. runps argv 도달 — exec 명령줄에 따옴표 0개(함정 1), 래퍼·대상 UNC 정확 전달
#   3. wait_ready — CRLF 출력 판정 성공(함정 4) / 유계 타임아웃 실패(무한 루프 방어)
#   4. push — .ps1 에 BOM 자동 부착(함정 2), pull 왕복
#   5. snapid — snapshot-list(ID 컬럼) + -i 상세(이름) 2단 계약
#   6. open_app /tr 인용 — exe·인자는 launcher Start-PS 인용으로, /tr 은 powershell -File
#      (2026-08-25 실측: 공백 경로 exe 를 /tr 에 직접 싣으면 0x80070002 로 즉사 — 회귀 가드)
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
FAILS=0
PASS() { printf 'ok   - %s\n' "$1"; }
FAIL() { printf 'FAIL - %s\n' "$1"; FAILS=$((FAILS + 1)); }

# 스텁 prlctl — argv 를 한 줄씩 기록하고 STUB_MODE 로 응답. 자식 프로세스로 도므로
# STUB_MODE·PMLAB_STUB_LOG 는 반드시 export 로 전달한다.
setup_stub() {
  STUB_DIR="$(mktemp -d "${TMPDIR:-/tmp}/pmlab-ct.XXXXXXXX")"
  PMLAB_STUB_LOG="$STUB_DIR/prlctl.log"
  : > "$PMLAB_STUB_LOG"          # wc -l 리다이렉션 에러 방지(가드 케이스가 로그 생성 전에 읽는다)
  export PMLAB_STUB_LOG
  cat > "$STUB_DIR/prlctl" <<EOF
#!/bin/bash
# pmlab-contract-test stub
printf '%s\n' "\$@" >> "\$PMLAB_STUB_LOG"
# prlctl exec <vm> cmd /c echo pmlab-ok — \$1=exec \$2=<vm> \$3=cmd
if [ "\$1" = exec ] && [ "\$3" = cmd ] && [ "\$5" = qwinsta ]; then
  printf 'console             allieus      Active\r\n'
  exit 0
fi
if [ "\$1" = exec ] && [ "\$3" = cmd ]; then
  if [ "\$STUB_MODE" = ready ]; then printf 'pmlab-ok\r\n'; exit 0
  else printf 'exec: VM is not running\n' >&2; exit 1; fi
fi
if [ "\$1" = snapshot-list ]; then
  if [ "\$3" = '-i' ]; then
    case "\$4" in
      '{aaaa-1}') printf 'ID: {aaaa-1}\nName: clean-desktop\nDate: 2026-08-25\nCurrent: yes\n' ;;
      '{bbbb-2}') printf 'ID: {bbbb-2}\nName: older\nDate: 2026-08-01\nCurrent: no\n' ;;
    esac
    exit 0
  fi
  printf 'PARENT_SNAPSHOT_ID                      SNAPSHOT_ID\n'
  printf '                                        {aaaa-1}\n'
  printf '{aaaa-1} *{bbbb-2}\n'
  exit 0
fi
exit 0
EOF
  chmod +x "$STUB_DIR/prlctl"
  PATH="$STUB_DIR:$PATH"; export PATH
}

# 각 케이스는 스텁 재설치 후 source 로 초기화(함수·변수 리셋).
fresh() {
  setup_stub
  # shellcheck disable=SC1090
  . "$HERE/pmlab.sh"
}

# ── 1. 마스터 VM 가드 ──
case_guard_master() {
  fresh
  PMLAB_VM="Windows 11"
  pmlab_exec cmd /c echo x >/dev/null 2>&1
  [ $? -eq 9 ] && PASS 'guard: base VM exec 거부 rc=9' || FAIL 'guard: base VM exec 거부(rc=9 기대)'
  PMLAB_VM="Windows 11 (강의용)"
  PmlabLogLines="$(wc -l < "$PMLAB_STUB_LOG" 2>/dev/null || printf 0)"
  pmlab_runps run.ps1 >/dev/null 2>&1
  rc2=$?
  nowLines="$(wc -l < "$PMLAB_STUB_LOG" 2>/dev/null || printf 0)"
  [ "$rc2" -eq 9 ] && [ "$nowLines" = "$PmlabLogLines" ] \
    && PASS 'guard: 강의용 VM runps 거부 rc=9 + 스텁 미호출' \
    || FAIL "guard: 강의용 VM runps(rc=9 기대, 스텁 호출 없음 기대 — rc=$rc2 lines=$nowLines/$PmlabLogLines)"
}

# ── 2. runps argv 도달(따옴표 0개) ──
case_runps_argv() {
  fresh
  PMLAB_VM=win11-parlab
  PMLAB_SHARE_NAME=parlab
  PMLAB_SHARE_DIR="$STUB_DIR/share"
  mkdir -p "$PMLAB_SHARE_DIR"
  cp "$HERE/pmlab-run.ps1" "$PMLAB_SHARE_DIR/"
  : > "$PMLAB_STUB_LOG"
  pmlab_runps sub/run.ps1 arg1 arg2 >/dev/null 2>&1
  # 기대: 인자가 한 줄씩 — exec, VM, powershell, -NoProfile, -ExecutionPolicy, Bypass,
  #       -File, \\Mac\parlab\pmlab-run.ps1, \\Mac\parlab\sub\run.ps1, arg1, arg2
  want='exec
win11-parlab
powershell
-NoProfile
-ExecutionPolicy
Bypass
-File
\\Mac\parlab\pmlab-run.ps1
\\Mac\parlab\sub\run.ps1
arg1
arg2'
  got="$(cat "$PMLAB_STUB_LOG")"
  [ "$got" = "$want" ] && PASS 'runps: argv 정확 도달(따옴표 0개, UNC 조립)' \
    || FAIL "runps: argv 불일치 — got: $(printf '%s' "$got" | tr '\n' '|')"
}

# ── 3. wait_ready ──
case_wait_ready() {
  fresh
  PMLAB_VM=win11-parlab
  out="$(STUB_MODE=ready PMLAB_READY_TIMEOUT=5 pmlab_wait_ready 2>/dev/null)"; rc=$?
  [ $rc -eq 0 ] && PASS 'wait_ready: CRLF 출력 판정 성공(함정 4)' \
    || FAIL "wait_ready: CRLF 판정 실패 rc=$rc"
  start=$(date +%s)
  STUB_MODE=notready PMLAB_READY_TIMEOUT=3 PMLAB_READY_STEP_TIMEOUT=1 pmlab_wait_ready >/dev/null 2>&1
  rc=$?; elapsed=$(( $(date +%s) - start ))
  [ $rc -eq 1 ] && [ $elapsed -le 8 ] \
    && PASS "wait_ready: 유계 타임아웃 rc=1 (${elapsed}s)" \
    || FAIL "wait_ready: 유계 실패(rc=$rc elapsed=${elapsed}s)"
}

# ── 4. push BOM / pull 왕복 ──
case_push_bom() {
  fresh
  PMLAB_VM=win11-parlab
  PMLAB_SHARE_DIR="$STUB_DIR/share"; mkdir -p "$PMLAB_SHARE_DIR"
  src="$STUB_DIR/plain.ps1"
  printf 'Write-Output %s\n' '테스트-한국어' > "$src"   # BOM 없는 한국어 .ps1
  pmlab_push "$src" plain.ps1
  head3="$(head -c 3 "$PMLAB_SHARE_DIR/plain.ps1" | od -An -tx1 | tr -d ' \n')"
  [ "$head3" = "efbbbf" ] && PASS 'push: .ps1 BOM 자동 부착(함정 2)' \
    || FAIL "push: BOM 미부착(head=$head3)"
  pmlab_pull plain.ps1 "$STUB_DIR/back.ps1"
  cmp -s <(tail -c +4 "$PMLAB_SHARE_DIR/plain.ps1") "$src" \
    && PASS 'pull: 공유→호스트 cp 왕복 무결' || FAIL 'pull: 내용 불일치'
  # .ps1 외 파일은 BOM 을 붙이지 않는다(훼손 방지)
  printf 'hello\n' > "$STUB_DIR/data.bin"
  pmlab_push "$STUB_DIR/data.bin" data.bin
  cmp -s "$STUB_DIR/data.bin" "$PMLAB_SHARE_DIR/data.bin" \
    && PASS 'push: 비-PS 파일 무변경 복사' || FAIL 'push: 비-PS 파일 변형'
}

# ── 5. snapid 2단 계약 ──
case_snapid() {
  fresh
  PMLAB_VM=win11-parlab
  id="$(pmlab_snapid clean-desktop)"
  [ "$id" = "{aaaa-1}" ] && PASS 'snapid: 이름→guid 조회(list + -i 2단)' \
    || FAIL "snapid: 불일치 got=$id"
  pmlab_snapid missing >/dev/null 2>&1
  [ $? -eq 1 ] && PASS 'snapid: 미발견 rc=1' || FAIL 'snapid: 미발견 판정 실패'
  id2="$(pmlab_snapid older)"
  [ "$id2" = "{bbbb-2}" ] && PASS 'snapid: 두 번째 스냅샷(컬럼 파싱)' || FAIL "snapid: 두번째 got=$id2"
}

# ── 6. open_app /tr 인용 게이트 (2026-08-25 Hwp 0x80070002 회귀 가드) ──
case_open_app() {
  fresh
  PMLAB_VM=win11-parlab
  PMLAB_SHARE_NAME=parlab
  PMLAB_SHARE_DIR="$STUB_DIR/share"
  mkdir -p "$PMLAB_SHARE_DIR"
  cp "$HERE/pmlab-run.ps1" "$PMLAB_SHARE_DIR/"
  pmlab_open_app 'C:\Program Files (x86)\HNC\Office 2024\HOffice130\Bin\Hwp.exe' '\\Mac\parlab\render-test.hwpx' >/dev/null 2>&1
  launch="$PMLAB_SHARE_DIR/pmlab-launch.ps1"
  opener="$PMLAB_SHARE_DIR/pmlab-open-app.ps1"
  grep -qF 'Start-Process -FilePath '\''C:\Program Files (x86)\HNC\Office 2024\HOffice130\Bin\Hwp.exe'\'' -ArgumentList '\''\\Mac\parlab\render-test.hwpx'\''' "$launch" \
    && PASS 'open_app: exe·인자가 launcher Start-Process 인용으로 전달' \
    || FAIL 'open_app: launcher 본문 불일치'
  grep -qF -- '-File \\Mac\parlab\pmlab-launch.ps1' "$opener" \
    && PASS 'open_app: /tr = powershell -File launcher (따옴표 0개)' \
    || FAIL 'open_app: /tr 조립 불일치'
  if grep -q 'Hwp.exe' "$opener"; then
    FAIL 'open_app: /tr 에 exe 경로 잔존(공백 경로 0x80070002 회귀)'
  else
    PASS 'open_app: /tr 에 exe 경로 부재'
  fi
  pmlab_open_app 'C:\Windows\notepad.exe' '' >/dev/null 2>&1
  # 무인자 호출은 런타임 else 분기로 빠진다 — if-분기 원문에 -ArgumentList 문자열이
  # 남는 것은 무해하므로, else 분기 조립 자체를 단언한다.
  grep -qF 'else { Start-Process -FilePath '\''C:\Windows\notepad.exe'\'' }' "$launch" \
    && PASS 'open_app: 무인자는 else 분기(Start-Process 단독)로 조립' \
    || FAIL 'open_app: 무인자 launcher 조립 불일치'
}

case_guard_master
case_runps_argv
case_wait_ready
case_push_bom
case_snapid
case_open_app
rm -rf "$STUB_DIR"

if [ "$FAILS" -eq 0 ]; then printf 'ALL PASS (%s)\n' "${0##*/}"; exit 0; fi
printf '%d FAIL (%s)\n' "$FAILS" "${0##*/}"
exit 1
