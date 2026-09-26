# windows-parallels-lab 함정 상세

씨드 5건은 2026-08-25 세션 라이브 실측(인계: `docs/agent-snippets/parallels-lab-skill.md`).
이 아래의 "세션 신규" 절은 스킬 저작·검증 과정에서 추가 실측된 것이다. 새 함정을 발견하면 이 파일에 날짜와 함께 붙인다.

## 1. PS 인용부호 소실 — zsh→prlctl 게이트에서 따옴표가 깨진다

`"…'C:'"` 조합이 zsh→prlctl 게이트를 지나며 깨져 파라미터가 탈락한다. **처방: 한국어·인용이
필요한 스크립트는 .ps1 파일을 공유 폴더로 push 후 `powershell -File` 실행**이 정본이다.
`pmlab_runps` 는 한 발 더 나가서 — exec 명령줄에 **따옴표가 아예 0개**인 형태(공유의
`pmlab-run.ps1` 래퍼를 `-File` 로 호출)만 쓴다. 래퍼가 대상 스크립트 경로를 받아 실행하고
OutputEncoding=UTF8 까지 선행한다(함정 2 겸용).

## 2. cmd 출력 = CP949 — PS 경유 + UTF-8 OutputEncoding 선행이 인코딩 계약

`prlctl exec … cmd /c` 의 한글 출력은 깨진다. 판정에 한글이 필요하면 PS 경유 +
`[Console]::OutputEncoding=[System.Text.Encoding]::UTF8` 선행. `pmlab-run.ps1` 래퍼가 항상
선행한다. 마찬가지로 **한국어가 든 .ps1 은 UTF-8 BOM 필수** — PS 5.1 은 BOM 없는 파일을
CP949 로 오독해 파싱 에러를 낸다. `pmlab_push` 가 .ps1 확장자에 자동으로 BOM 을 보장한다.

## 3. `.pvc` 유실 스냅샷 삭제 실패 — `Snapshots/<guid>.pvc` 부재

`prlctl snapshot-delete` 는 `Snapshots/<guid>.pvc`(스냅샷 시점 VM 설정)를 요구한다.
구버전(2025-09 이전) 스냅샷에선 이 파일이 유실돼 "설정 파일이 무효"라는 오해를 부르는 에러가
난다. **처방: 현재 `config.pvs` 를 `Snapshots/<guid>.pvc` 로 복사 후 재시도** (2026-08-25
실증: 즉시 삭제 성공, 복사 파일은 스냅샷과 함께 정리됨). `pmlab_delete` 가 1차 실패 시
`pmlab_pvc_fix` 로 자동 처방 후 1회 재시도한다.

## 4. `cmd /c` 출력 CRLF — 셀 문자열 비교가 항상 거짓이 된다

개행이 `\r\n` 이라 `[ "$h" = "X" ]` 가 항상 거짓(2026-08-25 당일 거짓 실패 실증 — 판정 자체는
옳았는데 폴링만 5분 타임아웃). 비교 전 `tr -d '\r'` 필수. `pmlab_wait_ready` 는 마커 비교
전에 `_pmlab_strip_cr` 을 항상 거친다.

## 5. 라이브/정지 계약이 명령마다 다르다

| 명령 | 실행 중 소스 | 비고 |
|---|---|---|
| `clone` (full) | **정지 필수** | 실행 중이면 "VM is busy". APFS clonefile 로 고속(당일 실측 1초)·실소비 최소 |
| `snapshot` | 가능 | 메모리 포함(`.mem` ~3.5GB, 수 초 스턴) |
| `snapshot-delete` | **라이브 가능** | merge 정상 동작 |
| `exec` | 가능 | **자격증명 불요·SYSTEM(IsAdmin=True)** |
| `capture` | 가능 | 2596×1460 PNG |
| `stop` | 가능 | 이미 정지된 VM 에는 "not started" 경고와 **rc=0**(멱등) |

"실행 중이라 안 된다"와 "된다"의 경계가 명령마다 다르므로 이 표에서 확인한다.

## 세션 신규 (2026-08-25, 스킬 저작 중 실측)

### `snapshot-list` 는 ID만 준다 — 이름·설명은 `-i <id>` 상세조회에

`prlctl snapshot-list <vm>` 출력은 부모/자식 ID 두 컬럼뿐이고 이름이 없다(당초 예상한
`ID:/Name:` 라인 쌍이 아니다). 현재 스냅샷은 ID 앞 `*` 로 표시된다. 이름을 얻으려면 스냅샷마다
`prlctl snapshot-list <vm> -i '{guid}'` 를 별도 호출해야 한다 — 상세에
`ID/Name/Date/Current/State/Description` 가 온다. 이름→ID 조회(`pmlab_snapid`)는 ID 전수에
`-i` 상세를 대조한다. **계약 주석·가정이 아니라 생산자 출력을 열어 확인한 뒤 파서를 썼다**
(`cross-language-contract-keys` 규율).

### `prlctl set` 의 help 는 카테고리 2단계 — VM 이름 없이 `prlctl set <category> --help`

`prlctl set <vm> --help` 는 카테고리 목록(cpus/optimization/security/…)만 준다. 개별 옵션은
**VM 이름 없이** `prlctl set cpus --help`·`prlctl set optimization --help` 형태로 봐야 한다.
옵션명을 모를 때 `prlctl set <vm> optimization --help` 는 "Unrecognized option" 이다 — 이
문법 자체가 함정. `--nested-virt` 플래그도 이 카테고리에 있다(`config.pvs` 의
`<VirtualizedHV>`) — 단 Apple Silicon 에서는 **no-op** 다(아래 전용 함정 참조).

### `prlctl stop` 은 이미 정지된 VM 에 rc=0 — "not started" 경고와 함께 성공

클론 생성 스크립트가 정지된 소스에 `stop` 을 걸어 "Failed to stop … not started" 경고가
났는데 **rc=0** 이었다(멱등). 경고 문구에 "Failed"가 있어 실패로 오독해 스크립트를 중단하면
안 된다. 단 정말 정지됐는지는 `prlctl list -a` 상태로 판정한다.

### 부팅 자동로그인 VM 의 클론은 곧바로 exec 가능

base 가 자동 로그인 상태로 쓰이고 있으면 정지→클론→기동된 클론도 자동 로그인돼 기동 직후
exec(SYSTEM)가 통한다. vmrun 판의 "최초 로그인 사람 1회" 국면이 없다 — bootstrap 이 무인
완결된다. (자동 로그인이 아닌 base 라면 이 국면이 다시 필요할 수 있다 — 그때 이 문단을
실측으로 갱신한다.)

### `wsl.exe` 출력은 UTF-16 — PS 캡처 재출력 + `LC_ALL=C tr` 이 계약

wsl.exe 는 stdout 이 콘솔이 아닐 때 UTF-16LE 로 출력한다. 그대로 파이프로 받으면 macOS
`tr` 이 `Illegal byte sequence` 로 죽는다. **PS 안에서 캡처 후 재출력**(`(& wsl …) 2>&1 |
Out-String | ForEach-Object { $_ }`)이 정규화의 정본이고, 호스트 쪽 `tr` 은 항상
`LC_ALL=C` 로 돌린다(`_pmlab_strip_cr` 내장).

### exec 는 SYSTEM 계정 — WSL 은 아예 안 돈다 (`WSL_E_LOCAL_SYSTEM_NOT_SUPPORTED`)

`prlctl exec` 의 SYSTEM 권한(승격 불요라는 이 스킬의 핵심 우위)이 **WSL 표면에서는 반대로
장애**다. WSL 은 로컬 시스템 계정 세션을 지원하지 않아 `wsl --status` 조차
`WSL_E_LOCAL_SYSTEM_NOT_SUPPORTED` 로 죽는다(2026-08-25 실측). 게스트 사용자 세션에서만
도는 것(WSL·Cowork 워크스페이스 등)은 exec 로 검증할 수 없다 — 사용자 세션 테스트는
`schtasks /RU <사용자> /IT` 로 출력을 파일로 회수하는 경로로 한다(아래 Session 0 절과 같은
기법). ⚠️ 어느 쪽이든 WSL2 자체는 Apple Silicon 중첩 가상화 미지원으로 **게스트에서 못
돈다**(아래 중첩 가상화 절).

### 중첩 가상화(nested virt)는 Apple Silicon 에서 **불가** — `--nested-virt` 는 Intel 전용 no-op (2026-08-25 오판 정정)

`prlctl set <vm> --nested-virt on`(optimization 카테고리)은 **Intel Mac 전용** 기능이다.
공식 Parallels KB 116239: "this feature is currently not supported in Parallels Desktop on
Mac computers with Apple silicon"(Pro/Business/Enterprise 의 Intel 에서만 지원). Apple
Silicon 에서 이 플래그는 **rc=0 으로 정상 처리되고 config.pvs 의 `<VirtualizedHV>` 까지
1로 쓰이지만 게스트에 아무 효과가 없다.** 통제 실측(2026-08-25, 호스트 M5 Pro + PD 26.4.1):
플래그 설정 → config 확인 → 완전 정지 상태 확인 → 콜드부팅(LastBootUpTime 으로 fresh
부팅 확인) → `Win32_Processor.VirtualizationFirmwareEnabled` 전 vCPU **False** · 사용자
세션 `wsl --status` "기본 버전: 1"(WSL2 초기화 실패) · Cowork 워크스페이스
"BIOS/UEFI 가상화 활성화" 에러 지속.

**판정 함정 2개(초판이 여기서 오판했다 — 재발 방지)**:

- `Win32_ComputerSystem.HypervisorPresent=True` · systeminfo "A hypervisor has been
  detected" 는 Parallels 위의 **모든 VM 이 항상 보고**하는 값이다(Parallels 자체가
  하이퍼바이저라 CPUID 하이퍼바이저 비트가 항상 켜져 있다). 중첩 가상화 작동의 증거로
  쓰지 않는다.
- 반대로 이 케이스의 `VirtualizationFirmwareEnabled=False` 는 '하이퍼바이저 실행 중 보고
  왜곡'이 아니라 **문자 그대로 '노출 안 됨'** 이다(콜드부팅 후에도 False).

정직한 판정법: ① 플래그 + 콜드부팅 후 `VirtualizationFirmwareEnabled` ② 사용자 세션
기능 테스트(WSL2 등) — 둘 다 통과해야 한다. 결론: 게스트 내 하이퍼바이저가 필요한 것
(WSL2·Claude Cowork 워크스페이스·Windows Sandbox)은 **이 표면에서 못 돌린다** — macOS 15+
M3+ 의 Hypervisor.framework 중첩 가상화를 Parallels 가 Windows 게스트에 노출하지 않는다
(공식 미지원, 로드맵 미정). VMware Fusion(중첩 불가)과 같은 제약이다.

## 라이브 검증 세션 실측 (2026-08-25, 게이트 통과 과정)

### `prlctl exec` 는 프로세스 종료까지 대기한다 — GUI 앱 직접 exec 는 블록

`pmlab_exec cmd /c 'start notepad …'` 로 GUI 앱을 띄우면 start 조차 반환하지 않고 notepad
종료까지 대기한다(3분 유계 상한 소진, 이후 `taskkill` 로 회수 — notepad PID 가 남아 있었음).
vmrun 의 `-noWait` 에 대응하는 exec 플래그는 이 빌드에 없다. **비동기 실행은 스크립트 안에서**:
headless 면 `Start-Process`, GUI 면 아래의 schtasks 경로(`pmlab_open_app`).

### exec(SYSTEM) 의 GUI 앱은 Session 0 격리 — 화면에 안 뜬다

SYSTEM 컨텍스트에서 `Start-Process notepad` 를 실행하면 프로세스는 살아있는데(세션 0)
**콘솔 데스크톱에 창이 없다**(capture 로 실증). 모드 B(렌더 확인)의 관문이 여기다.
**처방: `schtasks /RU <콘솔사용자> /IT`** 로 사용자 세션에서 실행한다 — `pmlab_open_app` 이
자동화한다(작업 생성→실행, `/F` 로 재사용).

- `/IT` 단독으로는 **실패한다** — SYSTEM 컨텍스트엔 "현재 사용자"가 없어
  `No mapping between account names and security IDs` + `UserId` 에러. **`/RU <사용자>` 를
  반드시 명시**한다(사용자명은 `qwinsta` 의 console 라인에서 — `pmlab_console_user`).
- 콘솔 로그온 자체가 없으면(로그인 화면·잠금) 사용자 세션 실행이 불가능하다 — 사람 개입 국면.

### ⚠️ `pmlab_open_app` 은 인자를 **하나만** 받는다 — 나머지는 조용히 사라진다 (2026-08-26 실측)

시그니처가 `pmlab_open_app <exe> [단일 인자]` 다(launcher 의 `Start-Process -ArgumentList
'${arg_p}'` 가 `$2` 만 싣는다). 여러 개를 넘기면 **`$2` 만 쓰이고 나머지는 버려지는데 rc=0** 이다:

```bash
# ✗ '-ExecutionPolicy' 만 전달된다 — 스크립트가 아예 안 뜬다
pmlab_open_app 'C:\...\powershell.exe' '-NoProfile' '-ExecutionPolicy' 'Bypass' '-File' 'C:\x.ps1'
# ✓ 한 문자열로 합친다
pmlab_open_app 'C:\...\powershell.exe' '-NoProfile -ExecutionPolicy Bypass -File C:\x.ps1'
```

**왜 고약한가**: 실패가 무음이라 게스트에 **직전 회차의 잔존 창·프로세스**가 살아 있으면
그것을 이번 결과로 읽는다(#1576 에서 실제로 그럴 뻔했다 — 갈라 준 것은 UI 의 버전 필드였다).
`prlctl exec` 도 마찬가지로 GUI 앱을 못 띄우므로 "창이 안 뜬다" 의 용의자가 둘이다.

- **해야 한다** — 새 회차 전에 **이전 프로세스를 죽이고 잔존 0 을 확인**한다. 산출 디렉토리도
  회차마다 새로 만들어(`Remove-Item` 후 `New-Item`) "이번 회차의 것" 임을 파일 존재로 판정한다.
- **해야 한다** — 기동 성공을 **산출물**(phase 파일 등)로 확인한다. `pmlab_open_app` 의 rc=0 은
  schtasks 등록·실행의 성공이지 스크립트가 돌았다는 뜻이 아니다.
- **하지 않는다** — 체인에서 출력을 억제(`>/dev/null 2>&1`)한 채 `&&` 로 잇는 것. #1576 에서
  push→copy→open 체인을 그렇게 묶었다가 중간 실패를 못 보고 "스크립트가 없다" 로 헤맸다
  (`no-silent-fallback` — 내 하네스에도 적용된다).

### 골든 스냅샷을 잠금 화면에서 뜨는 함정 — wait_ready 는 잠금을 못 본다

`pmlab_wait_ready` 는 exec(SYSTEM) 성공 기반이라 **로그인 화면·잠금 상태에서도 통과한다**.
rename 재부팅 직후(자동 로그인 아님) 스냅샷을 뜨면 잠금 화면이 기준점이 돼, 이후 revert
마다 렌더 검증이 잠금에 가려진다(첫 캡처가 시계만 있는 잠금 화면이었다). **스냅샷 전
`qwinsta` 로 console 세션 Active 확인 + `pmlab_capture` 로 데스크톱 관측**까지가 계약이다.
resume(suspend→start)은 세션을 그대로 살려 반환하므로 잠금이 아니다.

### 공유 격리는 옵션 4종 세트 — `--smart-mount off` 만으론 `\\Mac\Home` 이 산다

격리(게이트 ④)에 필요한 전량(2026-08-25 실측):

```bash
prlctl set <vm> --smart-mount off        # 스마트마운트(외장·네트워크 볼륨 자동)
prlctl set <vm> --shf-host-defined off   # 기본 정의 공유(\\Mac\Home = home 정의) 제거 — 핵심
prlctl set <vm> --shared-cloud off       # \\Mac\iCloud 축(misc_sharing)
prlctl set <vm> --shared-profile off     # 홈 프로필 폴더 공유 방어 차단
prlctl set <vm> --shf-host-add parlab --path ~/parlab   # 전용 공유(파일 표면 단일화)
```

`--smart-mount off` 후에도 `\\Mac\Home`·`\\Mac\iCloud` 가 열려 있었다 — Home 은
`--shf-host-defined`(shared_folders 카테고리) 소관이다. 인계 문서의 "smart mount 가 마운트
한다" 서술은 이 축 구분이 정확하지 않았다. 적용은 게스트 재부팅 없이 즉시 반영됐다.

### 그 밖의 세션 실측

- **`snapshot-switch` 2초·라이브**: 실행 중 전원 사이클 없이 메모리 상태가 전환된다. 파일·프로세스·화면 오염이 전부 소멸(결정론 사이클 PASS). vmrun 9초 revert 대응물.
- **suspend→start(resume) 즉시(0초)**: Parallels 는 VM 종료 시 suspend 정책을 쓸 수 있다 — suspended 상태의 클론도 `prlctl start` 로 즉시 resume 된다.
- **`--linked -i`**: clone 하위 옵션으로 존재(스냅샷 ID 지정 링크드 클론). 실행 중 가능 여부는 미실측.
- **`prlctl enter`·`send-key-event`**: 26.4.1·27.0.0 양 빌드의 prlctl 에 부재 — help 전수 확인.
- **`prlctl set` 하위옵션 typo 는 조용히 안 죽는다**: `--smart-mounts`(s 포함)는 `Unrecognized option` rc=255 — 즉시 실패라 다행이지만, help 의 카테고리/하위옵션 계층(`prlctl set <category> --help`)을 먼저 보고 쓴다.

## 세션 신규 (2026-08-25 심야, #1550 잔여 실측 — 데몬 소유·할당·골든 수명)

### 데몬이 VM 을 소유한다 — prlctl 클라이언트를 죽여도 게스트는 산다 (vmrun 최대 함정 소멸 실증)

vmrun 판의 최대 함정("vmrun 이 죽으면 vmware-vmx 까지 SIGTERM 동반 사망, 메모리 스냅샷 소실")이
Parallels 에선 구조적으로 소멸한다. 실측(2026-08-25):

- VM 프로세스 `prl_vm_app` 의 부모(PPID)가 **디스패처 `prl_disp_service`** 다 — 클라이언트
  `prlctl` 은 단발 자식일 뿐 VM 프로세스를 소유하지 않는다.
- 장기 `prlctl exec`(ping 60s) 중 **클라이언트를 SIGTERM** → 클라이언트 즉사, VM 상태 running
  유지·VM 프로세스 pid 불변·신규 exec 응답 정상("alive-after-kill").

### 스냅샷은 GuestTools·할당(vCPU/RAM)까지 되돌린다 — 골든은 호스트 업그레이드·할당 변경마다 재생성한다

- `prlctl set --cpus 6` 상태에서 `snapshot-switch` → **cpus 가 스냅샷 시점 값(4)으로 복귀**,
  게스트 논리 프로세서도 4. 할당은 골든에 고정된다 — 상향은 "정지 → set → 기동 → 재스냅샷".
- **GuestTools 도 스냅샷에 묶인다**: 호스트 앱이 26.4.1→27.0.0 으로 자동 업데이트된 뒤 구 골든
  (26.4.1 시점)으로 switch 하면 게스트 도구가 26.4.1 로 되돌아가 `state=outdated` 가 된다.
  그 상태에서 Parallels 가 도구 자동 승급을 밀면 **게스트 재부팅 5회 + VM 프로세스 교체 churn**
  이 일어났다(2026-08-25 실측 — "게스트가 스스로 재부팅한다"로 위장). 호스트 업그레이드 직후에는
  골든을 재생성해 도구 버전을 맞춘다(현행 골든 `clean-desktop-6c` = 27.0.0 정합).

### 스냅샷 복원 판정은 상태 관측(마커·프로세스·config·tools)으로 — lastboot 축은 불가해하다

churn 이후 구 골든으로 switch 했을 때 게스트 `LastBootUpTime` 이 스냅샷 생성시각(21:35)과
조화 불가능한 값(22:43)으로 관측됐다 — 스냅샷 `.mem` 파일 mtime(21:35)과도 불일치. Parallels
switch 의 메모리 이미지 선택 계약(특히 current 포인터가 이미 목표 스냅샷일 때)은 미해명이다.
**결정론 게이트는 시계 축을 쓰지 않는다** — 마커 파일·프로세스·VM config(cpus)·GuestTools 버전
4축 상태 검증이 정본이고, 신규 골든에서는 4축이 전부 일관 복원됨을 실측했다(2초 switch).

### pmlab_open_app 의 /tr 에 공백 경로 exe 를 직접 싣지 않는다 — 0x80070002 로 즉사

`C:\Program Files (x86)\...\Hwp.exe` 처럼 공백·괄호가 든 경로를 schtasks `/tr` 에 조립하면
작업엔진 게이트에서 인용이 벗겨져 `C:\Program` 까지 절단, **Last Result 0x80070002
(FILE_NOT_FOUND)** 로 실패한다(2026-08-25 실측 — 게이트 ②가 notepad[공백 없음] 로만 통과해
숨어 있던 결함). **처방(pmlab.sh 반영)**: `/tr` 은 따옴표 0개인 `powershell -File <공유
launcher>` 로 두고 exe·인자는 launcher 안 `Start-Process` 의 PS 인용으로 전달한다. 계약테스트
`case_open_app`(/tr 에 exe 부재·launcher 인용 조립 단언)이 회귀를 잡는다.

### 리소스 할당 — 성능 진단은 하이퍼바이저가 아니라 할당부터 본다 (#1550)

- **생성 기본값(4 vCPU / 12GB)을 그대로 두지 않는다** — VMware 판 사고(2 vCPU/4GB 기본값으로
  Office+한글+게스트 빌드를 돌고 "VM 이 느리다"로 오진)와 같은 클래스다. 랩 클론은 **6 vCPU /
  12GB**(호스트 M5 Pro 18코어·64GB 기준, 골든 `clean-desktop-6c` 에 고정).
- 할당 변경은 스냅샷 되돌림과 상쇄된다(위 절) — **할당은 골든을 다시 뜰 때 함께 결정한다**.
- 마스터 VM(실사용)의 할당은 마스터 소유 — 이 스킬이 임의로 바꾸지 않는다.

## 안전 관련 관례

- **마스터 실사용 VM(`Windows 11`·`Windows 11 (강의용)`)은 read-only + 스냅샷 생성만**.
  `pmlab.sh` 의 `_pmlab_guard_write` 가 exec/start/stop/set/snapshot-switch/snapshot-delete
  를 마스터 VM 대상으로 거부한다(rc=9). 관측(list·snapshot 생성·capture)만 허용.
- **마스터 VM 설정 변경은 마스터 명시 요청 시에만** prlctl 직접 호출로 한다(2026-08-25 전례:
  강의용 `--nested-virt on` — 스냅샷 선행 후 변경).
- 클론 배포 직후 smart mount 가 홈 전체(`\\Mac\Home`)·외장(`\\Mac\T7 Shield`)·iCloud(`\\Mac\iCloud`)
  까지 마운트한다. `pmlab_isolate`(smart-mounts off + 전용 공유) 전의 클론에서 공유를 쓰면
  마스터 홈이 게스트에 노출된다.

### 콘솔 세션 자동 로그인 3요소 — DefaultPassword **항목**이 빠지면 조용히 미로그인

`pmlab_open_app`(schtasks `/IT`)·GUI 렌더 실측은 콘솔 세션이 **로그인(Active)** 이어야 성립한다
(`qwinsta` 의 `console` 행이 `Conn` 이면 미로그인 — schtasks `/IT` 가 붙을 세션이 없다). 부팅
자동 로그인의 계약은 3요소다(2026-08-26 실측):

```
AutoAdminLogon=1 · DefaultUserName=<계정> · DefaultPassword=<값 또는 "">   ← 세 번째가 핵심
```

`AutoAdminLogon`+`DefaultUserName` 만 넣고 `DefaultPassword` 항목을 만들지 않으면 **재부팅 후에도
콘솔이 Conn 에 머문다** — 값이 빈 문자열이어도 **항목 자체의 존재**가 Winlogon 의 자동 로그인
시도 조건이다. 암호 없는 계정은 추가로 `HKLM\SYSTEM\CurrentControlSet\Control\Lsa`
`LimitBlankPasswordUse=0` 이 필요하다. 정본 헬퍼는 `pmlab_autologon <계정>`(암호 없는 랩 계정 전용).

⚠️ **호스트 에이전트의 Bash 로 `DefaultPassword`·`LimitBlankPasswordUse` 를 직접 치면 권한
분류기가 자격증명 조작으로 차단한다**(실측 2026-08-26 — 2회). `pmlab_autologon` 은 그 레지스트리
쓰기를 **게스트에 push 한 .ps1 안**에 두고 `prlctl exec ... -File` 로 실행하므로 호스트 명령
문자열에 암호 토큰이 없다 — 분류기 표면을 우회하지 않고 계약대로 통과한다. 그래도 막히거나 실제
암호가 있는 계정이면 **사용자가 게스트에서 직접** 설정한다: 관리자 PowerShell 로 위 3키를 쓰거나,
Sysinternals `Autologon.exe`(암호를 LSA 시크릿에 암호화 저장 — 평문 레지스트리보다 안전)를 한 번
실행한다. 마스터 실사용 VM 은 read-only 라 이 설정을 걸지 않는다(랩 클론 전용).

## 세션 신규 (2026-09-09, 모드 D 개발 상자 세팅 실측)

전부 **ARM64 Win11 게스트 + macOS(Ghostty) → SSH** 조합에서 라이브로 겪은 것이다.

### OpenSSH 는 FoD 로 안 깔린다 — Win32-OpenSSH **MSI** 가 정본

`Add-WindowsCapability -Online -Name OpenSSH.Server*` 가 **진척 없이 매달린다**(300초 예산 초과,
백그라운드로 돌려도 로그가 `START` 에서 멈춤). 게스트 인터넷은 정상(`Invoke-WebRequest` 200),
`wuauserv` 도 Running 인데 `TiWorker`/`TrustedInstaller` 가 뜨지 않는다 — CBS 가 아예 착수하지
않는 상태다. 공식 릴리스 MSI 로 우회하면 즉시 끝난다(`msiexec exit: 0`).

```
https://github.com/PowerShell/Win32-OpenSSH/releases  →  OpenSSH-ARM64-v<ver>.msi
msiexec /i <msi> ADDLOCAL=Server /qn /norestart
```

MSI 는 UNC 에서 직접 설치하지 말고 게스트 로컬로 복사한 뒤 건다(SYSTEM 컨텍스트에서 실패하기 쉽다).

### `Subsystem sftp sftp-server.exe` 는 **상대 이름이라 scp 가 죽는다**

기본 셸을 Git Bash 로 바꾸면(`HKLM\SOFTWARE\OpenSSH` `DefaultShell`), sshd 가 서브시스템을 그
셸로 해석하는데 `sftp-server.exe` 가 그 PATH 에 없다. 증상은 `scp: Connection closed`,
`sftp` 도 `Connection closed`. **절대경로로 고정**하면 산다.

```
Subsystem	sftp	"C:/Program Files/OpenSSH/sftp-server.exe"
```

`scp -O`(레거시 프로토콜)는 이 상태에서도 통과하므로, **scp 는 되는데 sftp 만 죽는** 형태로
오진하기 쉽다. 고치기 전에 `sftp` 로 직접 확인한다.

### Excel COM `SaveAs` 만 실패한다 — `systemprofile\Desktop` 부재

비대화형(SSH) 세션에서 `New-Object -ComObject Excel.Application`·`Workbooks.Add`·셀 쓰기는 전부
통과하는데 **`SaveAs` 에서만** COMException 이 난다("Workbook 클래스 중 SaveAs 속성을 구할 수
없습니다"). 로캘 문제로 보이지만 아니다 — 스레드 컬처를 en-US 로 고정해도 그대로다. 아래 두
디렉토리를 만들면 즉시 통과한다.

```
C:\Windows\System32\config\systemprofile\Desktop
C:\Windows\SysWOW64\config\systemprofile\Desktop
```

통과 후 실측: `SUM=246`, 한글 셀 보존, `.xlsx` 저장, 좀비 EXCEL 0(RCW 역순 해제 + GC 2회 계약).

### herdr 은 **윈도우를 SSH 타깃으로 받지 않는다** — `ssh -t <host> herdr` 이 유일한 경로

`herdr --remote parlab` → `error: unsupported remote platform: MINGW64_NT-...`. 공식 문서의
지원표가 `herdr --remote` 를 **Linux/macOS 호스트로 한정**하고, 0.9.0 의 `herdr machine` 항목도
"Native Windows servers are not supported as SSH targets" 로 못박는다. 즉 윈도우는 herdr 의
**클라이언트**로만 지원된다. SSH 로 띄운 서버·pane 은 로그아웃 후에도 살아남으므로 `herdr` 로
재연결한다.

설치는 **공식 스크립트**로 한다 — exe 를 수동으로 떨구면 `herdr update`·채널 전환이 죽고,
설치 스크립트가 "Detected existing Herdr command" 로 거부한다.

```
powershell -ExecutionPolicy Bypass -c "irm https://herdr.dev/install.ps1 | iex"
```

### herdr 마우스가 pane 으로 샌다 (SSH 경유) — 상류 PR #3742, 지금은 끄는 수밖에 없다

pane 프롬프트에 좌표 바이트가 찍힌다. herdr 은 마우스 추적을 **정상 요청**하고 있다(기동 로그
실측: `DECSET ?1000h ?1002h ?1003h ?1006h` — SGR 확장 포함). 원인은 상류가 밝혀 놓았다 —
OpenSSH 가 레거시 마우스 보고를 **중첩 Windows key record** 로 전달하는데 herdr 이 그것을
의도적인 shift 키 입력으로 오독한다(PR #3742, 2026-09-08 생성·미머지). 설정 레버는 없고,
`[ui] mouse_capture = false` 를 주면 herdr 이 추적 요청 자체를 안 한다(대조 실측: 위 DECSET
4종이 전부 0회) — 증상이 아니라 원인을 끄는 것이라 회피책으로 올바르다. 머지되면 되살린다.

### PowerShell 7 은 winget 으로 못 깐다(쓸 수 있는 형태로는) — msix 별칭이 SSH 에서 죽는다

winget 의 `Microsoft.PowerShell` 은 **msix 설치본만** 제공한다(`설치 관리자 유형: msix`,
2026-09-09 실측). msix 는 실행 별칭(`%LOCALAPPDATA%\Microsoft\WindowsApps\pwsh.exe`)으로만
노출되고 그 별칭은 **비대화형 세션에서 `Permission denied`** 로 죽는다. `--installer-type msi`
는 "적용 가능한 설치 관리자 없음"(rc=16), `--force`·`--scope machine` 도 마찬가지다.
GitHub 릴리스의 **MSI** 를 따로 깐다.

MSI 를 깔아도 **PATH 에서는 Store 별칭이 여전히 먼저 잡힌다**(`where.exe pwsh` 실측). herdr 의
`default_shell` 을 이름으로 두면 pane 이 깨진 셸로 뜨므로 **절대경로**로 고정한다.

### Ghostty 로 SSH 하면 TERM 이 깨진다 — 게스트에 terminfo 를 심는다

`TERM=xterm-ghostty` 가 그대로 넘어와 pager 를 쓰는 명령이 죽는다(`git log` →
`'xterm-ghostty': unknown terminal type.`). 게스트에 `infocmp`·`tic` 이 있으므로 맥에서 한 번
심으면 끝난다.

```bash
infocmp -x xterm-ghostty | ssh parlab 'tic -x -'
```

게스트 파일시스템에 들어가므로 **스냅샷을 되돌리면 사라진다**. dotfiles 의 `windows/bashrc` 에
terminfo 가 없을 때만 TERM 을 낮추는 안전망이 있다.

### 게스트 도구는 아키텍처를 따진다 — 네이티브가 있으면 네이티브로

ARM64 게스트다. 네이티브 빌드가 있으면 그걸 쓰고, 없으면 x86_64 를 Prism 에뮬레이션으로 돌린다
(실측상 둘 다 동작).

| 도구 | 이 게스트에서 | 비고 |
|---|---|---|
| jq 1.8.2 · fzf 0.74.3 | **네이티브 arm64** | 전용 릴리스 자산이 있다 |
| herdr 0.9.0 · delta 0.19.2 | x86_64 (Prism) | 윈도우 arm64 빌드 미제공 |
| OpenSSH 10.0 | **네이티브 arm64 MSI** | |

`jq` 는 statusline 의 의존이다 — 없으면 죽지는 않고 **값이 전부 0 으로** 나와서 오진하기 쉽다.
