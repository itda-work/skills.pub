#!/usr/bin/env bash
# windows-parallels-lab 프리미티브 — macOS Parallels Desktop 의 자동화 전용 Win11 클론 제어.
# bash/zsh 양쪽 호환. `source scripts/pmlab.sh` 후 pmlab_* 함수를 쓴다.
#
# 전제: (1) 랩 클론(기본 win11-parlab)이 bootstrap 완료(공유 격리 + 골든 스냅샷),
#       (2) Parallels Desktop 26.x/27.x + GuestTools installed(호스트·게스트 버전 정합).
# vmrun(vmlab.sh)과 달리 게스트 자격증명·키체인·SSH 가 전부 불요하다 — prlctl exec 는
# 자격증명 없이 SYSTEM(IsAdmin=True) 권한으로 도는 게 2026-08-25 실측 계약이다.
# 상세·함정은 SKILL.md 와 references/pitfalls.md 참조.

# ── 경로·대상 (필요시 환경변수로 override) ──
PMLAB_VM="${PMLAB_VM:-win11-parlab}"                 # 랩 클론. 마스터 실사용 VM 을 절대 가리키지 않는다(가드 참조)
# 골든 스냅샷 세대명 — 스냅샷은 vCPU/RAM·GuestTools 버전까지 되돌리므로(#1550 실측),
# 할당 변경·호스트 Parallels 업데이트 시 골든을 재생성하고 이 기본값을 갱신한다.
PMLAB_SNAP="${PMLAB_SNAP:-clean-desktop-6c}"
# 파일 전송 표면은 전용 공유 하나로 단일화(스마트마운트 off + --shf-host-add 로 좁힘).
# 호스트 디렉터리 PMLAB_SHARE_DIR 를 게스트에서 \\Mac\<PMLAB_SHARE_NAME> 로 접근한다.
PMLAB_SHARE_NAME="${PMLAB_SHARE_NAME:-parlab}"
PMLAB_SHARE_DIR="${PMLAB_SHARE_DIR:-$HOME/parlab}"
PMLAB_BUNDLE="${PMLAB_BUNDLE:-$HOME/Parallels/${PMLAB_VM}.pvm}"
# 유계 예산(초) — 전체 상한 / exec 1회 상한 / wait_ready 전체 상한·스텝 상한
PMLAB_EXEC_TIMEOUT="${PMLAB_EXEC_TIMEOUT:-300}"
PMLAB_READY_TIMEOUT="${PMLAB_READY_TIMEOUT:-180}"
PMLAB_READY_STEP_TIMEOUT="${PMLAB_READY_STEP_TIMEOUT:-15}"

# 이 스킬이 배포하는 실행 래퍼(공유에 있어야 exec 명령줄에 따옴표가 0개가 된다 — 함정 1)
_PMLAB_SKILL_DIR="${BASH_SOURCE[0]:-$0}"; _PMLAB_SKILL_DIR="$(cd "$(dirname "$_PMLAB_SKILL_DIR")/.." && pwd)"

# ── 안전 가드: 마스터 실사용 VM 은 read-only ──
# exec/snapshot-switch/snapshot-delete/set 같은 게스트·상태 변경 op 는 랩 클론에만 허용한다.
# (마스터에 허용되는 것: list/snapshot 생성/capture — 관측성 유지)
_pmlab_is_master() {
  case "$PMLAB_VM" in
    "Windows 11"|"Windows 11 (강의용)") return 0 ;;
  esac
  return 1
}
_pmlab_guard_write() {
  if _pmlab_is_master; then
    printf 'pmlab: [%s] 은(는) 마스터 실사용 VM 입니다 — %s 은(는) 랩 클론(기본 %s)에서만 실행합니다\n' \
      "$PMLAB_VM" "$1" "win11-parlab" >&2
    return 9
  fi
}

# ── 내부 유틸 ──
# 유계 실행 — prlctl exec 는 자체 타임아웃이 없을 수 있다(인계 §5). 상한으로 방어한다.
# 유계 수단이 하나도 없으면 무제한 실행으로 넘어가지 않고 에러로 끝낸다(no-silent-fallback).
_pmlab_timeout() {
  local secs="$1"; shift
  if command -v gtimeout >/dev/null 2>&1; then gtimeout "$secs" "$@"
  elif command -v timeout >/dev/null 2>&1; then timeout "$secs" "$@"
  elif command -v perl >/dev/null 2>&1; then
    perl -e 'alarm shift; exec { $ARGV[0] } @ARGV; exit 127;' "$secs" "$@"
  else
    printf 'pmlab: gtimeout/timeout/perl 이 없어 유계 실행이 불가합니다 — 무제한 블록 위험으로 중단합니다\n' >&2
    return 125
  fi
}

# CRLF 제거(함정 4) — cmd /c 출력은 \r\n 이라 [ "$x" = "y" ] 판정이 항상 거짓이 된다.
# LC_ALL=C 필수: macOS tr 은 UTF-8 스트림에 존재하지 않는 바이트(UTF-16 출력 등)를 만나면
# 'Illegal byte sequence' 로 죽는다(2026-08-25 wsl.exe 출력 실측).
_pmlab_strip_cr() { LC_ALL=C tr -d '\r'; }

# 게스트 UNC 경로 조립: pmlab_guestpath run.ps1 → \\Mac\parlab\run.ps1
pmlab_guestpath() { printf '\\\\Mac\\%s\\%s' "$PMLAB_SHARE_NAME" "${1//\//\\}"; }

# .ps1 에 UTF-8 BOM 이 없으면 붙인다(PS 5.1 CP949 오독 방지). $1=파일. 없던 파일이면 생성.
_pmlab_ensure_bom() {
  local f="$1"
  [ -f "$f" ] || return 1
  if [ "$(head -c 3 "$f" | od -An -tx1 | tr -d ' \n')" != "efbbbf" ]; then
    local tmp; tmp="$(mktemp "${TMPDIR:-/tmp}/pmlab-bom.XXXXXXXX")" || return 1
    printf '\xEF\xBB\xBF' > "$tmp" && cat "$f" >> "$tmp" && mv "$tmp" "$f"
  fi
}

# 공유 래퍼 확인(부재 시 스킬 scripts/ 에서 설치)
_pmlab_ensure_wrapper() {
  mkdir -p "$PMLAB_SHARE_DIR" || return 1
  local w="$PMLAB_SHARE_DIR/pmlab-run.ps1"
  if [ ! -f "$w" ] || ! cmp -s "$w" "$_PMLAB_SKILL_DIR/scripts/pmlab-run.ps1" 2>/dev/null; then
    cp "$_PMLAB_SKILL_DIR/scripts/pmlab-run.ps1" "$w" || return 1
  fi
  _pmlab_ensure_bom "$w"
}

# ── 상태·관측 (마스터 VM 도 허용) ──
pmlab_vms()     { prlctl list -a; }
# 현재 상태(running/stopped/…) — 이름에 공백이 있는 VM(`Windows 11 (강의용)`)도 4번째 필드부터 조립해 잡는다.
pmlab_state()   { prlctl list -a | awk -v vm="$PMLAB_VM" 'NR > 1 { name = ""; for (i = 4; i <= NF; i++) name = (name == "" ? $i : name " " $i); if (name == vm) print $2 }'; }
pmlab_capture() { prlctl capture "$PMLAB_VM" --file "$1"; }   # $1=호스트 png 경로

# ── 스냅샷 ──
# 생성(메모리 포함, 실행 중 가능 — 마스터에도 허용되는 유일한 변경 op)
pmlab_snapshot() {  # $1=이름 [$2=설명]
  local d="${2:-pmlab $(date +%Y-%m-%d)}"
  prlctl snapshot "$PMLAB_VM" -n "$1" -d "$d"
}
pmlab_snapshots() { prlctl snapshot-list "$PMLAB_VM"; }
# 이름이 든 상세: snapshot-list 본체는 ID만 준다(2026-08-25 실측 — 부모/자식 ID 컬럼, 현재 스냅샷 '*'),
# 이름·설명은 'snapshot-list -i <id>' 상세조회에만 있다.
pmlab_snapinfo() { prlctl snapshot-list "$PMLAB_VM" -i "$1"; }   # $1=스냅샷 guid

# 이름 → 스냅샷 guid. ID 전수에 -i 상세를 대조해 찾는다(스냅샷 수가 적어 호출 비용 무시 가능).
# ⚠️ while 문에 파이프를 쓰면 서브셸이 돼 return 이 함수에 안 닿는다 — heredoc 공급이 정본.
pmlab_snapid() {  # $1=이름 → stdout: {guid}, 미발견 시 rc=1
  local want="$1" id found=""
  while read -r id; do
    [ -n "$id" ] || continue
    if [ "$(prlctl snapshot-list "$PMLAB_VM" -i "$id" 2>/dev/null | awk '/^Name:/ { sub(/^Name: /, ""); print; exit }')" = "$want" ]; then
      found="$id"; break
    fi
  done <<EOF
$(prlctl snapshot-list "$PMLAB_VM" | awk 'NR > 1 { gsub(/^[* ]+|[ ]+$/, "", $NF); print $NF }')
EOF
  if [ -n "$found" ]; then printf '%s\n' "$found"; return 0; fi
  return 1
}

# 스냅샷 복원(랩만). vmrun 9초 메모리 revert 의 대응물 — 전원 사이클 유무·복원 속도는 클론 실측값(§검증 상태) 참조.
pmlab_switch() {  # [$1=스냅샷 이름(기본 $PMLAB_SNAP)]
  _pmlab_guard_write 'snapshot-switch' || return 9
  local id
  id="$(pmlab_snapid "${1:-$PMLAB_SNAP}")" || { printf 'pmlab: 스냅샷 [%s] 미발견 — pmlab_snapshots 로 확인\n' "${1:-$PMLAB_SNAP}" >&2; return 1; }
  prlctl snapshot-switch "$PMLAB_VM" -i "$id"
}

# 스냅샷 삭제(랩만, 라이브 가능). 구버전 스냅샷의 .pvc 유실 시 자동 처방(함정 3) 후 1회 재시도.
pmlab_delete() {  # $1=스냅샷 이름
  _pmlab_guard_write 'snapshot-delete' || return 9
  local id
  id="$(pmlab_snapid "$1")" || { printf 'pmlab: 스냅샷 [%s] 미발견\n' "$1" >&2; return 1; }
  if prlctl snapshot-delete "$PMLAB_VM" -i "$id"; then return 0; fi
  printf 'pmlab: 삭제 1차 실패 — .pvc 유실(함정 3) 의심, 처방 시도\n' >&2
  if pmlab_pvc_fix "$id"; then
    prlctl snapshot-delete "$PMLAB_VM" -i "$id"
  else
    return 1
  fi
}

# 함정 3 처방: Snapshots/<guid>.pvc 부재 시 현재 config.pvs 를 복사해 넣는다(2026-08-25 실증: 즉시 삭제 성공, 복사본은 스냅샷과 함께 정리됨).
pmlab_pvc_fix() {  # $1=스냅샷 guid
  local snapdir="${PMLAB_BUNDLE}/Snapshots"
  if [ -f "${snapdir}/$1.pvc" ]; then
    printf 'pmlab: %s.pvc 이미 존재 — 복사 불요. 삭제 실패 원인은 다른 축\n' "$1" >&2
    return 1
  fi
  if [ ! -f "${PMLAB_BUNDLE}/config.pvs" ]; then
    printf 'pmlab: 번들 경로가 실제와 다릅니다(현재 %s) — PMLAB_BUNDLE 을 <vm>.pvm 절대경로로 지정하세요\n' "$PMLAB_BUNDLE" >&2
    return 1
  fi
  cp "${PMLAB_BUNDLE}/config.pvs" "${snapdir}/$1.pvc" || return 1
  printf 'pmlab: config.pvs → Snapshots/%s.pvc 복사 완료\n' "$1" >&2
}

# ── 게스트 실행 (prlctl exec — 자격증명 불요·SYSTEM) ──
# .ps1 실행의 정본: 공유의 pmlab-run.ps1 래퍼를 -File 로 부른다(명령줄에 따옴표 0개 — 함정 1,
# 래퍼가 OutputEncoding=UTF8 선행 — 함정 2). 한국어 .ps1 은 push 가 BOM 을 보장한다.
pmlab_runps() {  # $1=공유 내 .ps1 상대경로 [나머지=스크립트 인자]
  _pmlab_guard_write 'exec' || return 9
  _pmlab_ensure_wrapper || { printf 'pmlab: 실행 래퍼 설치 실패(%s)\n' "$PMLAB_SHARE_DIR" >&2; return 1; }
  local target; target="$(pmlab_guestpath "$1")"; shift
  local wrapper; wrapper="$(pmlab_guestpath pmlab-run.ps1)"
  _pmlab_timeout "$PMLAB_EXEC_TIMEOUT" \
    prlctl exec "$PMLAB_VM" powershell -NoProfile -ExecutionPolicy Bypass -File "$wrapper" "$target" ${1+"$@"}
}

# raw exec — 짧은 ASCII 명령용(출력은 CRLF. 판정에 쓸 땐 _pmlab_strip_cr 를 거친다).
pmlab_exec() {  # $@=게스트 명령(따옴표·한국어 없는 단순 인자만 안전)
  _pmlab_guard_write 'exec' || return 9
  _pmlab_timeout "$PMLAB_EXEC_TIMEOUT" prlctl exec "$PMLAB_VM" "$@"
}

# ── 파일 push/pull — 전용 공유가 곧 파일 시스템 ──
# 한국어 포함 .ps1 을 UTF-8 BOM 으로 저장(PS 5.1 CP949 오독 방지). $1=경로, stdin=본문.
pmlab_write_ps() { printf '\xEF\xBB\xBF' > "$1"; cat >> "$1"; }
# .ps1 은 BOM 을 보장해 복사한다(PS 5.1 CP949 오독 방지).
pmlab_push() {  # $1=호스트 파일 [$2=공유 내 이름(기본 basename)]
  mkdir -p "$PMLAB_SHARE_DIR" || return 1
  local base="${2:-$(basename "$1")}"
  case "$base" in
    *.ps1) cp "$1" "$PMLAB_SHARE_DIR/$base" && _pmlab_ensure_bom "$PMLAB_SHARE_DIR/$base" ;;
    *)     cp "$1" "$PMLAB_SHARE_DIR/$base" ;;
  esac
}
pmlab_pull() {  # $1=공유 내 이름 [$2=호스트 목적지(기본 ./<이름>)]
  cp "$PMLAB_SHARE_DIR/$1" "${2:-$(basename "$1")}"
}
# 한국어 포함 .ps1 을 공유에 쓸 때는 pmlab_push 가 BOM 을 보장한다.

# ── 준비 대기(유계) ──
# 준비 신호 = exec 로 마커 명령이 성공. CRLF(함정 4)를 제거한 뒤 비교한다.
# 전체 상한 PMLAB_READY_TIMEOUT, 호출별 상한 PMLAB_READY_STEP_TIMEOUT — 상한을 남은 예산으로
# clamp 해 총합이 실제로 유계다(인계 §5: prlctl exec 자체 타임아웃 부재 가능성).
pmlab_wait_ready() {
  local budget="${PMLAB_READY_TIMEOUT:-180}" step="${PMLAB_READY_STEP_TIMEOUT:-15}"
  local deadline=$(( $(date +%s) + budget )) now remain per out
  while :; do
    now=$(date +%s); remain=$(( deadline - now ))
    [ "$remain" -le 0 ] && break
    per="$step"; [ "$remain" -lt "$per" ] && per="$remain"
    out="$(_pmlab_timeout "$per" prlctl exec "$PMLAB_VM" cmd /c echo pmlab-ok 2>/dev/null | _pmlab_strip_cr)" \
      && [ "$out" = "pmlab-ok" ] && return 0
    remain=$(( deadline - $(date +%s) )); [ "$remain" -le 0 ] && break
    [ "$remain" -lt 2 ] && sleep "$remain" || sleep 2
  done
  printf 'pmlab: 게스트 준비 대기 %s초 초과 — VM 미기동 또는 GuestTools 미준비. prlctl list -a 로 상태 확인\n' "$budget" >&2
  return 1
}

# ── GUI 앱(사용자 세션) — Session 0 격리의 정공법 ──
# prlctl exec 는 SYSTEM 컨텍스트라 Start-Process 로 띄운 GUI 앱이 콘솔 데스크톱에 안 보인다
# (2026-08-25 실측: notepad 가 화면에 없음). schtasks /RU <사용자> /IT 가 사용자 세션 실행의
# 정본이다(같은 세션 실측: notepad 가 콘솔 데스크톱에 뜨고 한국어 렌더가 캡처로 판독됨).
# 콘솔 세션(로그온 사용자)이 없으면 실패한다 — 로그인 화면/잠금 상태에선 사람 개입이 필요하다.
pmlab_console_user() {  # → stdout: 콘솔 세션 사용자명
  _pmlab_timeout "$PMLAB_EXEC_TIMEOUT" prlctl exec "$PMLAB_VM" cmd /c qwinsta 2>/dev/null | _pmlab_strip_cr \
    | awk '$1 == "console" { print $2; exit }'
}
pmlab_open_app() {  # $1=게스트 exe 경로, [$2=파일 인자] — 비대기, 사용자 세션에서 실행
  _pmlab_guard_write 'exec' || return 9
  _pmlab_ensure_wrapper || return 1
  local user; user="$(pmlab_console_user)"
  if [ -z "$user" ]; then
    printf 'pmlab: 콘솔 세션(로그온 사용자)이 없어 GUI 앱을 못 띄웁니다 — 로그인 화면/잠금 상태입니다\n' >&2
    return 1
  fi
  # /tr 에 exe+인자를 직접 싣으면 schtasks→작업엔진 게이트에서 인용이 벗겨져 공백 경로가
  # 'C:\Program' 까지 잘린다(2026-08-25 실측: Hwp.exe → Last Result 0x80070002). /tr 은
  # 따옴표 0개인 "powershell -File <공유 launcher>" 로 두고 exe·인자는 launcher 안
  # Start-Process 의 PS 인용으로 전달한다 — 함정 1(PS 인용부호 소실)의 schtasks 판.
  local exe_p="${1//\'/\'\'}" arg_p="${2//\'/\'\'}" user_p="${user//\'/\'\'}" launcher
  launcher="$(pmlab_guestpath pmlab-launch.ps1)"
  pmlab_write_ps "$PMLAB_SHARE_DIR/pmlab-launch.ps1" <<PS1
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
if ('${arg_p}' -ne '') { Start-Process -FilePath '${exe_p}' -ArgumentList '${arg_p}' }
else { Start-Process -FilePath '${exe_p}' }
PS1
  pmlab_write_ps "$PMLAB_SHARE_DIR/pmlab-open-app.ps1" <<PS1
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
\$tr = 'powershell -NoProfile -ExecutionPolicy Bypass -File ${launcher}'
(& schtasks /create /tn parlab-open /tr \$tr /sc once /st 23:59 /RU ${user_p} /IT /F) | Out-Null
if (\$LASTEXITCODE -ne 0) { Write-Error 'pmlab-open-app: schtasks 생성 실패'; exit 4 }
(& schtasks /run /tn parlab-open) | Out-Null
if (\$LASTEXITCODE -ne 0) { Write-Error 'pmlab-open-app: schtasks 실행 실패'; exit 5 }
exit 0
PS1
  pmlab_runps pmlab-open-app.ps1
}

# ── 전원 ──
pmlab_start()  { _pmlab_guard_write 'start'  || return 9; prlctl start  "$PMLAB_VM"; }
pmlab_stop()   { _pmlab_guard_write 'stop'   || return 9; prlctl stop   "$PMLAB_VM"; }

# ── bootstrap (모드 C — 최초 1회, 무인) ──
# vmrun 판과 달리 사람 개입(UAC·로그인)이 필요 없다: exec 가 SYSTEM 이라 승격 경계가 없고,
# base 의 자동 로그인 상태가 클론에 그대로 이어진다(실측 2026-08-25: 강의용 Rename-Computer).
# 1) 클론 — 소스 VM 은 정지 필수(실행 중이면 "VM is busy"). APFS clonefile 로 고속·실소비 최소.
pmlab_clone() {  # $1=소스 VM 이름(마스터), $2=새 클론 이름
  prlctl clone "$1" --name "$2"
}
# 2) 공유 격리 — smart mount 가 홈 전체·외장·iCloud 까지 마운트하므로 끄고 전용 좁은 공유만 남긴다.
#    파일 전송 표면이 이 공유 하나로 단일화된다(검증 게이트 4).
#    ⚠️ 플래그는 --smart-mount(단수형, 2026-08-25 실측) — --smart-mounts 는 Unrecognized.
pmlab_isolate() {  # 인자 없음 — PMLAB_VM/PMLAB_SHARE_* 설정 사용
  _pmlab_guard_write 'set' || return 9
  prlctl set "$PMLAB_VM" --smart-mount off || return 1
  mkdir -p "$PMLAB_SHARE_DIR" || return 1
  prlctl set "$PMLAB_VM" --shf-host-add "$PMLAB_SHARE_NAME" --path "$PMLAB_SHARE_DIR" || return 1
  printf 'pmlab: 공유 격리 완료 — smart-mount off, 전용 공유 %s → 게스트 %s\n' \
    "$PMLAB_SHARE_DIR" "$(pmlab_guestpath .)" >&2
}
# 3) 게스트 호스트명 변경(선택) — Windows 신원 충돌(동시 구동) 방지. Rename-Computer.ps1 을
#    공유에 쓰고 래퍼로 실행한다(인용부호·한국어 회피). -Restart 로 재부팅까지 동반하므로
#    이어서 pmlab_wait_ready 로 재대기한 뒤 스냅샷을 뜬다(재부팅 전 스냅샷이면 revert 마다
#    옛 이름으로 돌아온다).
pmlab_rename_host() {  # $1=새 호스트명
  _pmlab_guard_write 'exec' || return 9
  _pmlab_ensure_wrapper || return 1
  local ps="$PMLAB_SHARE_DIR/pmlab-rename.ps1"
  printf '\xEF\xBB\xBF' > "$ps"
  printf 'Rename-Computer -NewName %s -Force -Restart\n' "$1" >> "$ps"
  _pmlab_timeout "$PMLAB_EXEC_TIMEOUT" \
    prlctl exec "$PMLAB_VM" powershell -NoProfile -ExecutionPolicy Bypass -File "$(pmlab_guestpath pmlab-rename.ps1)"
}

# ── 자동 로그인 구성 (모드 C 보조 — 콘솔 세션 무인화) ──
# base/클론이 부팅 시 콘솔 세션까지 자동 로그인되게 Winlogon 을 설정한다. 자동 로그인은
# `pmlab_open_app`(schtasks /IT — 콘솔 세션 필수)과 GUI 렌더(capture) 실측의 전제다.
#
# ⚠️ 계약 3요소(실측 2026-08-26): AutoAdminLogon=1 + DefaultUserName + **DefaultPassword
#    항목의 존재**. 마지막이 빠지면 재부팅 후에도 콘솔이 Conn(미로그인)에 머문다 — 값이
#    빈 문자열이어도 **항목 자체**가 있어야 Winlogon 이 자동 로그인을 시도한다. 암호 없는
#    계정은 추가로 LSA LimitBlankPasswordUse=0 이 필요하다(원격/자동 빈암호 로그인 허용).
#
# ⚠️ 이 함수는 exec(SYSTEM)로 레지스트리를 쓰므로 게스트에서 자격증명을 취급하지 않는다
#    (암호 인자를 받지 않는다 — 암호 없는 랩 계정 전용). 실제 암호가 있는 계정의 자동
#    로그인은 게스트에서 Sysinternals `Autologon.exe`(암호를 LSA 시크릿에 암호화 저장)를
#    한 번 실행하는 것이 정본이며, 이 함수 범위 밖이다.
pmlab_autologon() {  # $1=콘솔 로그인시킬 사용자명(암호 없는 계정)
  _pmlab_guard_write 'exec' || return 9
  _pmlab_ensure_wrapper || return 1
  local user="$1"
  if [ -z "$user" ]; then
    printf 'pmlab_autologon: 사용자명 인자가 필요합니다\n' >&2; return 1
  fi
  local ps="$PMLAB_SHARE_DIR/pmlab-autologon.ps1"
  printf '\xEF\xBB\xBF' > "$ps"
  cat >> "$ps" <<PS1
\$k = "HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon"
Set-ItemProperty \$k AutoAdminLogon "1" -Type String
Set-ItemProperty \$k DefaultUserName "${user}" -Type String
Set-ItemProperty \$k DefaultDomainName "." -Type String
Set-ItemProperty \$k DefaultPassword "" -Type String
Set-ItemProperty "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Lsa" LimitBlankPasswordUse 0 -Type DWord
Write-Output "autologon set for ${user}"
PS1
  _pmlab_timeout "$PMLAB_EXEC_TIMEOUT" \
    prlctl exec "$PMLAB_VM" powershell -NoProfile -ExecutionPolicy Bypass -File "$(pmlab_guestpath pmlab-autologon.ps1)"
  printf 'pmlab_autologon: 설정 완료 — 재부팅해야 적용됩니다(pmlab_switch 또는 prlctl restart)\n' >&2
}
