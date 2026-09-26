---
name: windows-parallels-lab
description: >-
  macOS Parallels Desktop 의 자동화 전용 Windows 11 클론(win11-parlab)을 제어해 Windows
  실런타임(COM/Office/.NET)을 검증하고, 생성 문서(hwpx·pptx·docx)를 실제 한글/Office 로 열어
  렌더를 판독하며, SSH 개발 상자로도 쓴다. "윈도우에서 실행해서 확인해줘", "hwpx 가 한글에서
  안 깨지는지 봐줘", "게스트 화면 캡처해줘", "parlab 에서 개발할래" 처럼 말하면 된다. 원본 VM 은
  건드리지 않고 클론 + 스냅샷으로 복원한다. Parallels 26/27 + ARM Win11 전용.
  [책임 경계] 되돌릴 수 있는 클론 전담 — 되돌릴 수 없는 실머신 조작은 다루지 않는다.
metadata:
  version: "0.1.1"
  updated_at: "2026-09-25"
---

# windows-parallels-lab

macOS 호스트에서 Claude Code 가 **Parallels Desktop 안의 Windows 11 클론**을 제어해, macOS 에서 원천적으로 불가능한 두 가지를 세션 안에서 완결한다:

- **UC1 — Windows 실런타임 검증**: COM/Office/Outlook/.NET 경로처럼 Windows 에서만 도는 코드를 게스트에 배포·실행하고 결과를 회수한다. `ci-runner-policy`(Windows 러너 미채택)를 위반하지 않는 **온디맨드 세션 보조**다 — CI 게이트가 아니다.
- **UC2 — 문서 렌더링 그라운드 트루스**: `hwpx`·`pptx-design` 등이 생성한 문서를 **실제 한글/Office** 로 열어 `prlctl capture`(2596×1460 PNG) → 에이전트 비전으로 깨짐·폰트·레이아웃을 판독한다. 파서 자기검증이 못 주는 유일한 검증축이다.

`windows-vm-lab`(VMware Fusion, 폐기)의 대체다 — 2026-08-25 폐기 결정(#1572). vmrun 판의 게스트 계정·키체인·SSH·UAC 경계가 **전부 사라진다**: `prlctl exec` 는 자격증명 없이 SYSTEM(IsAdmin=True) 권한으로 돈다(실측).

## 언제 쓰나 (트리거)

- "이 COM/Office/.NET 코드 윈도우에서 실제로 되나 확인", "게스트에서 dotnet/PowerShell 돌려줘"
- "생성한 hwpx/pptx/docx 가 실제 한글/파워포인트에서 안 깨지는지 봐줘", "렌더링 그라운드 트루스"
- "랩 클론 스냅샷 떠줘", "clean 으로 되돌려줘", "게스트 화면 캡처해줘"
- Windows 실런타임 검증 공백을 "VM 실측 PASS/FAIL"로 메우고 싶을 때

**쓰지 않을 때**: 게스트 **사용자 세션**에서만 도는 것(WSL2·Claude Cowork — exec 는 SYSTEM 계정이라 `WSL_E_LOCAL_SYSTEM_NOT_SUPPORTED`) / 게스트 내 하이퍼바이저가 필요한 것(WSL2·Cowork 워크스페이스·Sandbox — Apple Silicon 중첩 가상화 미지원, `references/pitfalls.md`) / Windows GUI 를 좌표로 조작하는 풀 컴퓨트-유즈 / 순수 macOS 작업.

## 절대 안전 규율 (하드)

1. **마스터 실사용 VM(`Windows 11`·`Windows 11 (강의용)`)은 read-only + 스냅샷 생성만**. 전원·revert·게스트 쓰기·설정 변경은 **랩 클론(`win11-parlab`)에서만**. `pmlab.sh` 의 `_pmlab_guard_write` 가 exec/start/stop/set/switch/delete 를 마스터 대상으로 거부한다(rc=9) — 우회하지 않는다. 마스터 VM 설정 변경은 마스터 명시 요청 시에만 prlctl 직접 호출(전례: 강의용 `--nested-virt on`, 스냅샷 선행).
2. **파괴 작업 전 스냅샷, revert 전 산출물 회수**. 게스트를 바꾸기 전 골든(`clean-desktop-6c`) 상태를 확인하고, switch 로 지울 산출물은 먼저 공유로 회수한다.
3. **클론 배포 직후 공유 격리 필수**. smart mount 는 홈 전체(`\\Mac\Home`)·외장·iCloud 까지 마운트한다. `pmlab_isolate`(smart-mounts off + 전용 공유 `parlab` 하나) 전의 클론에서 공유를 쓰지 않는다.
4. **게스트 자격증명은 취급하지 않는다** — exec 무자격증이 계약이라 키체인·.env·암호 축이 아예 없다(VMware 판과의 가장 큰 차이).
5. **두 VM 동시 구동은 신원 충돌 위험** — 랩 클론은 호스트명을 바꾸고(`pmlab_rename_host`), base/강의용이 running 이면 클론 기동 전 사용자에게 확인한다.

## 프리미티브

```bash
source skills/itda-dev/skills/windows-parallels-lab/scripts/pmlab.sh
```

| 동작 | 함수 | 대응 vmrun 판 |
|---|---|---|
| 결정론 리셋 | `pmlab_switch [스냅샷]` + `pmlab_wait_ready` | `vmlab_revert` |
| 게스트 .ps1 실행 | `pmlab_push x.ps1` → `pmlab_runps x.ps1` | `vmlab_runps` |
| 결과 회수 | `pmlab_pull <공유내이름>` | `vmlab_pull` |
| GUI 앱(사용자 세션) | `pmlab_open_app <exe> [인자]` | `vmlab_open_app` |
| 콘솔 자동 로그인 | `pmlab_autologon <계정>` (암호 없는 랩 계정 전용, 재부팅 후 적용) | — |
| 화면 캡처 | `pmlab_capture out.png` | `vmlab_capture` |
| 스냅샷 생성/조회 | `pmlab_snapshot` / `pmlab_snapshots` / `pmlab_snapid <이름>` | `vmlab_snapshots` |
| 유계 준비 대기 | `pmlab_wait_ready` | `vmlab_wait_ready` |

파일 push/pull 은 **전용 공유 폴더가 곧 파일 시스템**이다(호스트 `~/parlab` ↔ 게스트 `\\Mac\parlab`) — vmrun CopyFile 대응. 대기 예산은 `PMLAB_READY_TIMEOUT`(기본 180초)·`PMLAB_READY_STEP_TIMEOUT`(15초)·`PMLAB_EXEC_TIMEOUT`(300초)으로 전부 유계다.

## 모드

### 모드 A — `verify` (UC1: Windows 실런타임 검증)

```bash
pmlab_start && pmlab_wait_ready            # 클론 기동(중지 상태면) — 기동은 사용자 확인 후
pmlab_switch && pmlab_wait_ready           # 골든(clean-desktop-6c)으로 결정론 리셋
pmlab_write_ps ./run.ps1 <<'PS1'           # 한국어 .ps1 — BOM 자동 보장
... COM/Office/.NET 검증, 결과를 run/result.txt 로 Out-File ...
PS1
pmlab_push ./run.ps1
pmlab_runps run.ps1                        # 공유의 래퍼 경유 -File 실행(따옴표 0개)
pmlab_pull result.txt ./result.txt         # 결정론 결과 회수
```

- `pmlab_write_ps` 로 stdin 을 BOM 붙여 저장한다(`pmlab_push` 도 .ps1 에 BOM 보장).
- 스크립트 인자는 `pmlab_runps run.ps1 arg1 arg2` 로 전달된다.
- **점(`.`)이 든 플래그(네이티브 명령)는 스크립트 안에서 `cmd /c 'prog -test.run X > out.txt 2>&1'` 로** — PS 5.1 이 `-test.run` 을 절단한다(`references/pitfalls.md`, VMware 판과 동일한 Windows 함정).
- 관측용 짧은 ASCII 명령은 `pmlab_exec cmd /c dir C:\\` — 출력은 CRLF 라 판정 전 `_pmlab_strip_cr`.

### 모드 B — `render-check` (UC2: 문서 렌더링 그라운드 트루스)

```bash
pmlab_push ./report.hwpx report.hwpx
# GUI 앱은 반드시 pmlab_open_app — exec(SYSTEM) 로 띄우면 Session 0 에 갇혀 화면에 안 뜬다(실측).
pmlab_open_app 'C:\Program Files (x86)\HNC\Office 2024\HOffice130\Bin\Hwp.exe' '\\Mac\parlab\report.hwpx'
sleep 8                                    # 렌더 대기(앱별 실측값으로 조정)
pmlab_capture /tmp/render.png              # 그 뒤 Read 로 비전 판독(깨짐/폰트/레이아웃/표)
```

- `pmlab_open_app` 은 `schtasks /RU <콘솔사용자> /IT` 로 **사용자 세션**에서 실행한다(2026-08-25 실측: notepad 한국어 렌더 판독). 콘솔 로그온이 없으면(잠금·로그인 화면) 실패한다 — 그 상태에선 사람 개입이 필요하다.
- 판독은 **비전으로** — "제목 잘림·한글 폰트 대체·표 붕괴·이미지 누락"을 구체적으로 보고한다("보인다"≠"정확하다").
- 앱 종료는 `pmlab_exec cmd /c 'taskkill /IM Hwp.exe /F'` 류(렌더 검증 뒤 정리).

### 모드 B-2 — `ui-drive` (GUI 좌표 조작: 클릭·입력·클립보드, 2026-09-12 신설)

모드 B 가 "띄우고 찍는" 것이라면, 이쪽은 **띄운 화면을 실제로 조작한다** — 브라우저 탭을 고르고,
입력칸을 눌러 데이터를 붙여넣고, 그 결과 화면을 캡처한다. 교안용 화면 캡처처럼 **사람이 손으로
해야 나오는 상태**를 세션 안에서 만들 때 쓴다.

```bash
UI=skills/itda-dev/skills/windows-parallels-lab/scripts/uictl.py
python3 $UI ping                     # VM running + 콘솔 세션 Active + 해상도(좌표계) 확인
python3 $UI shot /tmp/now.png        # 캡처 → Read 로 판독해 좌표를 읽는다
python3 $UI click 521 38             # 그 좌표를 좌클릭
python3 $UI paste ./rows.tsv         # 여러 줄은 반드시 클립보드 경유
python3 $UI key '^v'                 # SendKeys 표기
python3 $UI winlist                  # 창 목록(포그라운드 `*`·핸들·위치)
```

- **좌표 = 캡처 픽셀**이다(실측 2480×1894, 1:1). 캡처를 읽고 좌표를 정한 뒤 누른다.
- 입력·클립보드·창목록은 전부 `pmlab_open_app` 경유 **사용자 세션**이다 — `pmlab_exec`(SYSTEM ·
  Session 0)의 클립보드는 **다른 공간**이라 `Get-Clipboard` 가 빈 값을 준다(2026-09-12 실측).
- `pmlab_open_app` 은 실패가 무음이라, 매 실행이 공유 폴더에 **ack 토큰**을 쓰고 호스트가 그 갱신을
  확인한다. 확인 못 하면 **비영 종료**한다(`no-silent-fallback`).
- **`type` 은 줄바꿈을 잃는다** — 여러 줄은 `paste`(클립보드) → `^v`.
- **`Esc` 를 함부로 쓰지 않는다.** 게스트 앱에서 승인창의 「거부」로 동작해 작업을 날린 전례가 있다.
- 도구는 `pmlab_switch`·스냅샷·전원 조작을 **아예 갖고 있지 않고**, 마스터 VM 이름이면 즉시 멈춘다.

### 모드 C — `bootstrap` (랩 클론 준비 — 최초 1회, 무인)

vmrun 판과 달리 **사람 개입이 없다**(exec 가 SYSTEM 이라 UAC 경계가 없고 base 의 자동 로그인이 클론에 이어진다).

```bash
# 0) 소스(base)를 정지한다 — full clone 은 소스 정지 필수("VM is busy"). 마스터 승인 하에.
# 1) 클론 생성(APFS clonefile 고속·실소비 최소)
pmlab_clone "Windows 11" win11-parlab
# 2) 공유 격리 — smart mount 끄고 전용 공유만(이 스킬의 유일한 파일 표면)
PMLAB_VM=win11-parlab pmlab_isolate
# 3) base 재기동(마스터 복귀) 후 클론 기동·대기
prlctl start "Windows 11"; pmlab_start && pmlab_wait_ready
# 4) 호스트명 변경(Windows 신원 충돌 방지) — 재부팅 동반
pmlab_rename_host WIN11-PARLAB && pmlab_wait_ready
# 5) ⚠️ 골든 스냅샷은 반드시 "로그인 데스크톱" 상태에서 뜬다 — wait_ready 는 exec(SYSTEM)
#    성공 기반이라 로그인 화면/잠금 상태에서도 통과한다(2026-08-25 실측: 잠금 화면 스냅샷을
#    떠서 첫 렌더 검증이 잠금에 가려졌다). qwinsta 로 console 세션 Active 를 확인한 뒤 뜨고,
#    스냅샷 직후 pmlab_capture 로 데스크톱이 맞는지 관측까지 한다.
pmlab_snapshot clean-desktop-6c "logged-in desktop baseline — 6 vCPU + tools matched"
```

> 골든은 **할당(vCPU/RAM)·GuestTools 버전까지 스냅샷에 고정**된다(#1550 실측) — 할당 변경이나
> 호스트 Parallels 업데이트 직후에는 이 단계를 다시 돌아 골든을 재생성한다(현행 세대:
> `clean-desktop-6c` = 6 vCPU + GuestTools 27.0.0 정합).

### 모드 D — `devbox` (개발 상자: SSH + herdr + Claude Code, 2026-09-09 신설)

맥에서 SSH 로 붙어 **게스트 안에서 개발을 완결**하는 자리다. 모드 A·B 가 "산출물을 넣고 결과를
빼는" 왕복이라면, 이쪽은 에이전트(Claude Code)를 게스트에 두고 Office COM 을 반복 시행착오하며
개발한다 — 왕복 지연이 사라지고, 실패한 COM 호출을 그 자리에서 고쳐 다시 돌릴 수 있다.

```bash
ssh -t parlab herdr        # 맥 → 게스트 herdr (이것이 유일한 접속 경로)
# herdr pane(pwsh) 안에서:  cc     ← Claude Code
```

**결정론 계열과 갈라 둔다.** 개발 상자는 상태가 쌓여야 하고(설치·인증·클론), 검증 랩은
`pmlab_switch` 로 지워져야 한다 — 한 VM 에서 공존하지 않는다. 그래서 골든에서 **별도 갈래**를
낸다. 이 갈래에서는 switch 를 쓰지 않는다(쓰면 개발 상태가 날아간다).

```
clean-desktop-6c
├── (검증 랩 계열 — 모드 A·B 가 쓰는 결정론 라인)
└── devbox-*             ← 개발 상자 갈래. switch 금지, 갱신은 새 스냅샷 추가로.
```

구성 요소(전부 게스트 안):

| | 무엇 | 비고 |
|---|---|---|
| 접속 | Win32-OpenSSH **MSI** + 키 인증, 기본 셸 Git Bash | FoD 로는 안 깔린다 — §함정 |
| 다중화 | herdr(공식 install.ps1) | 윈도우는 herdr 의 **클라이언트로만** 지원 — §함정 |
| 에이전트 | Claude Code + `cc`/`cc-glm` | Git Bash·pwsh 양쪽에 정의(dotfiles `windows/`) |
| 도구 | jq·fzf(네이티브 arm64) · delta(x86_64, Prism) | statusline·git 설정이 요구 |

호스트 맥의 배포 경로는 dotfiles 의 `herdr/sync-windows.sh parlab` 하나다(herdr 설정 + 셸 설정).

## 반드시 지킬 함정 (요약 — 상세 `references/pitfalls.md`)

- **개발 상자(모드 D) 함정 4종**(2026-09-09 실측, 상세 pitfalls §2026-09-09):
  OpenSSH 는 **FoD 가 아니라 MSI** 로 깐다(Add-WindowsCapability 가 진척 없이 매달린다) ·
  `Subsystem sftp` 는 **절대경로**여야 scp 가 산다(기본 셸이 Git Bash 라 상대 이름이 안 풀린다) ·
  Excel `SaveAs` 는 `systemprofile\Desktop` 두 개를 만들어야 통과한다(비대화형 세션) ·
  **herdr 은 윈도우를 SSH 타깃으로 받지 않는다**(`--remote`·`machine` 둘 다) — `ssh -t <host> herdr` 이 유일.
- **PS 인용부호 소실**: zsh→prlctl 게이트에서 따옴표가 깨진다 — `.ps1 push 후 -File 실행`이 정본, `pmlab_runps` 는 명령줄에 따옴표 0개인 래퍼 경로만 쓴다.
- **exec 는 프로세스 종료까지 대기(블록)**: GUI 앱을 직접 exec 하면 앱을 닫을 때까지 유계 상한을 다 태운다 — 비동기는 스크립트 안 `Start-Process`(headless) 또는 `pmlab_open_app`(GUI).
- **GUI 앱은 Session 0 격리**: exec(SYSTEM)로 띄운 창은 콘솔 데스크톱에 안 보인다 — `pmlab_open_app`(schtasks `/RU <사용자> /IT`)이 정공법.
- **`prlctl capture` 는 마우스 커서를 그리지 않는다**(2026-09-12 실측) — 커서 이동 검증은 커서가
  아니라 **호버 반응**(탭 미리보기·버튼 하이라이트)의 픽셀 변화로 한다. 시작 단추 호버는 Win11 에서
  거의 변화가 없어 표적으로 부적합하다.
- **캡처가 새까만 작은 PNG(13~20KB)로 나오는 진짜 원인은 절전이 아니다**(2026-09-13 실측). 게스트
  Windows 의 디스플레이 절전을 `powercfg /change monitor-timeout-ac 0`(DC 도)로 꺼도, Parallels 의
  `Pause idle` 이 off 여도 계속 검게 나온다. **macOS 에서 Parallels 창이 뒤에 있으면 게스트 렌더링이
  멈추는 것**이라, 캡처 직전에 창을 앞으로 부르면 곧바로 살아난다:

  ```bash
  osascript -e 'tell application "Parallels Desktop" to activate'
  ```

  `uictl.py shot` 이 30KB 미만이면 경고하니, 그때 이 한 줄을 넣고 다시 찍는다. 마우스 `move` 로
  깨어나는 경우도 있지만 확실하지 않다 — activate 가 정본이다.
- **`pmlab_open_app` 은 인자를 하나만 받는다**(`$2`): 여러 개를 넘기면 나머지가 **rc=0 인 채 조용히 사라져** 스크립트가 안 뜬다 — `'-NoProfile -ExecutionPolicy Bypass -File C:\x.ps1'` 처럼 **한 문자열로 합친다**. 실패가 무음이라 직전 회차의 **잔존 창을 이번 결과로 오독**하기 쉽다(#1576 실측) — 회차마다 산출 디렉토리를 새로 만들고 그 존재로 판정한다.
- **cmd 출력 CP949 + CRLF**: PS 경유 UTF-8 선행(래퍼 내장), 판정 전 `tr -d '\r'`(LC_ALL=C).
- **한국어 .ps1 은 UTF-8 BOM 필수** — `pmlab_push` 가 보장.
- **스냅샷은 로그인 데스크톱에서만 뜬다**: wait_ready 는 잠금 상태에서도 통과한다(SYSTEM 기반) — qwinsta console Active + capture 관측 후 스냅샷.
- **골든은 호스트 업그레이드·할당 변경마다 재생성**: switch 는 GuestTools·vCPU/RAM 을 스냅샷 시점으로 되돌린다 — 구 골든 revert 후 도구 자동 승급이 게스트 재부팅 churn 을 일으켰다(#1550 실측).
- **공백 경로 exe 는 schtasks /tr 직접 조립 금지**: `C:\Program` 까지 절단돼 0x80070002 로 즉사 — `pmlab_open_app` 은 공유 launcher `-File` 경유로 해결(계약테스트 case_open_app 가드).
- **`.pvc` 유실 스냅샷 삭제 실패**: `pmlab_delete` 가 `config.pvs` 복사 처방을 자동 1회 재시도.
- **라이브/정지 계약이 명령마다 다르다**: clone=정지 필수, snapshot/snapshot-delete=라이브 가능, exec=SYSTEM. pitfalls §5 표 참조.
- **WSL 은 exec 로 안 돈다**(SYSTEM 계정) — 게스트 사용자 세션 축은 이 스킬 밖.
- **스냅샷 이름은 `-i <guid>` 상세조회로만** — snapshot-list 본체는 ID만 준다.
- **셸은 zsh 호환** — 배열 확장 가드(`${arr[@]+"${arr[@]}"}`), `for x in $LIST` 금지.
- 실패는 에러로 표면화(`no-silent-fallback`) — 게스트 조작 실패를 조용히 우회하지 않는다.

## 우위 표면 (VMware 판 대비, 2026-08-25 실측)

- **자격증명 0**: 게스트 계정·키체인·SSH·.env·expect 전부 불요 — exec 무자격증·SYSTEM.
- **공유 폴더 = 파일 I/O**: push/pull 이 cp 다(vmrun CopyFile 왕복 불요).
- **디스크 관리**: `prl_disk_tool` compact/merge/resize/validate — VMware 판에 부재.
- **APFS clonefile 클론**: full clone 이 초 단위(당일 실측 1초).

중첩 가상화는 **양쪽 다 불가**다(VMware와 동일) — `--nested-virt` 는 Intel 전용 no-op,
`HypervisorPresent=True` 는 Parallels 위의 모든 VM 이 항상 보고하는 값이라 증거 못 됨
(2026-08-25 통제 실측 정정, `references/pitfalls.md` §중첩 가상화).

## 검증 상태 (2026-08-25, #1572 저작 + #1550 잔여 실측 — 전 게이트 라이브 PASS)

| 게이트 | 결과 |
|---|---|
| ① 모드 A 왕복 | PASS — 한국어 .ps1(BOM 자동) push → runps → pull, UTF-8 무결(`안녕하세요 … 그라운드 트루스`), exit code 전파(7), `isadmin=True` |
| ② 모드 B 렌더 | PASS — `pmlab_open_app`(schtasks /IT) 으로 notepad 한국어 렌더 → capture 2596×1460 PNG 비전 판독 |
| ③ 결정론 사이클 | PASS — 오염(파일+프로세스+화면) → `snapshot-switch` **2초·라이브(전원 사이클 없음)** → 마커·notepad 소멸·깨끗한 데스크톱 복원. vmrun 9초 revert 대응물 |
| ④ 공유 격리 | PASS — `--smart-mount off` + `--shf-host-defined off` + `--shared-cloud off` + `--shared-profile off` 후 `\\Mac\Home`·`\\Mac\iCloud` 접근 거부, `\\Mac\parlab` 생존 |
| ⑤ 셸 계약 | PASS — `scripts/pmlab-contract-test.sh` bash·zsh 양쪽 + guard 무력화 뮤테이션 RED 실측 (2026-08-25 #1550: open_app `/tr` 인용 케이스 추가 — 공백 경로 0x80070002 회귀 가드) |
| ⑥ 데몬 소유 | PASS — VM 프로세스(`prl_vm_app`)의 소유자는 디스패처(`prl_disp_service`); 클라이언트 prlctl 을 exec 중 SIGTERM 해도 게스트 생존·응답(vmrun 판 최대 함정 소멸 실증, #1550 판정기준 4-①) |
| ⑦ Hwp 실렌더 | PASS — hwpx(수사 3기 모의고사 문서) → Hwp.exe 사용자 세션 기동 → 문서 렌더 ≤10초 → capture 비전 판독(한국어·①~④ 선택지 선명, 폰트 대체·레이아웃 붕괴 없음) |

운영 상수: switch ~2초 / suspend→resume 즉시(0초) / 클론 생성 APFS ~1초(소스 정지) / 렌더 대기 notepad 5초·**Hwp 첫 실행 ≤10초**. 골든 스냅샷: **`clean-desktop-6c`**(6 vCPU + GuestTools 27.0.0 정합) — 스냅샷은 할당·도구 버전까지 되돌리므로 호스트 업그레이드·할당 변경 시 재생성한다(#1550 실측, `references/pitfalls.md` §골든 수명). 미실측 남음: `clone --linked -i` 실행 중 가능 여부, `exec --use-advanced-terminal` 유용성 — 필요 시 이 절에 갱신. (`prlctl enter`·`send-key-event` 는 26.4.1·27.0.0 양 빌드에 부재.)
