---
name: windows-remote-lab
description: >-
  macOS 에서 로컬 네트워크의 Windows 11 실머신(Surface Book 2)을 `ssh surface` 로 원격 조작해
  Windows 실런타임 검증·헤드리스 Office COM 자동화·파일 push/pull 을 세션 안에서 완결한다.
  "윈도우 실기에서 돌려봐줘", "실제 Excel COM 으로 계산해줘", "이 파일 윈도우로 보내줘",
  "윈도우 좀비 프로세스 정리해줘" 같은 요청에 사용한다. SSH 는 비대화형(Services) 세션이라
  Visible=true 창이 안 뜬다(대화형은 부록 schtasks 우회). macOS + 로컬 네트워크 실기 전용.
  [책임 경계] SSH 실머신 전담 — itda-dev:windows-parallels-lab 은 Parallels 클론.
metadata:
  version: "0.2.0"
  updated_at: "2026-10-01"
---

# windows-remote-lab

macOS 에서 **실제 Windows 11 머신**(Surface Book 2)에 SSH 로 붙어, macOS 에서 원천적으로 불가능한 검증·자동화를 원격으로 완결한다. `windows-parallels-lab` 이 Parallels 클론(결정론 스냅샷·렌더링 그라운드 트루스) 판이라면, 이쪽은 **실머신 + SSH** 판이다.

| | windows-parallels-lab | **windows-remote-lab** |
|---|---|---|
| 대상 | Parallels 클론(win11-parlab) | **실머신(Surface Book 2)** |
| 제어 | `prlctl exec`(자격증명 불요·SYSTEM) | **SSH(`ssh surface`)** |
| 복원 | 스냅샷 switch(~2초) | **없음 — 되돌릴 수 없다** |
| 화면 | 캡처·GUI 앱 열기 가능 | 비대화형(창 안 뜸, 부록으로 우회) |

**복원 수단이 없다.** 스냅샷도 revert 도 없는 마스터 실사용 머신이므로, 아래 안전 규율이 하드 제약이다.

## 언제 쓰나 (트리거)

- "윈도우 실기에서 돌려봐줘", "surface 에서 이 코드 되는지 확인", "원격 윈도우에서 dotnet 테스트"
- "실제 Excel/Word COM 으로 계산·생성해줘"(헤드리스), "이 파일 윈도우로 보내고 결과 가져와줘"
- "윈도우 프로세스 상태 봐줘", "좀비 EXCEL 정리해줘"
- Windows 전용 실런타임 공백(`ci-runner-policy` — Windows 러너 미채택)을 **온디맨드 세션 보조**로 메울 때. CI 게이트가 아니다.
- 대화형 세션(사용자 화면의 창·트레이 앱)·원격 로컬 서버 터널·사용자 세션 GUI 자동화가 필요하면 → **부록**

**쓰지 않을 때**: 결정론 리셋이 필요한 파괴적 실험(→ `windows-parallels-lab`) / 문서 렌더링 스크린샷 판독(→ `windows-parallels-lab`, 이쪽은 화면이 없다) / GUI 좌표 조작 / 순수 macOS 작업.

## 절대 안전 규율 (하드)

1. **실사용 머신이다 — 파괴적 조작 금지.** 시스템 디렉토리·레지스트리·사용자 문서에 대한 삭제·포맷·대량 이동을 하지 않는다. 쓰기는 **작업 디렉토리 `~/remote-lab/`(= `C:\Users\<user>\remote-lab`) 안으로만** 한다.
2. **되돌릴 수 없다.** 기존 파일을 덮어쓰기 전 존재 여부를 확인하고, 지우기 전 내용을 본다. `rm -rf`·`Remove-Item -Recurse -Force` 를 홈·시스템 경로에 쓰지 않는다.
3. **자격증명은 스킬·로그·커밋에 쓰지 않는다.** 접속은 **호스트 별칭 `surface`** 하나로만 하며(키 인증), 비밀번호·키 내용·IP 를 문서·출력에 남기지 않는다(`금지선`).
4. **마스터가 그 머신을 쓰고 있을 수 있다.** 로그인 사용자의 대화형 세션에 창을 띄우거나(부록) 사용자 프로세스를 죽이는 조작은 **사전 승인 후**에만 한다. 우리가 띄운 프로세스만 우리가 정리한다.
5. **실패는 에러로 표면화**(`no-silent-fallback`). 원격 실행 실패를 로컬 대체 경로로 조용히 우회하지 않는다.
6. **작업 후 잔존 확인이 계약이다.** COM 을 쓴 세션은 반드시 §좀비 가드를 거친다.

---

## 1층 — SSH 단독 (기본)

### 접속

```bash
ssh surface 'echo HELLO; uname -a'
# → MINGW64_NT-10.0-26200 SURFACE-BOOK2 ... Msys      (기본 셸 = Git Bash)
```

원격 셸은 **Git Bash(MINGW64)** 다. `pwd` 는 `/c/Users/<user>`, POSIX 명령(`ls`·`cat`·`grep`·`rm`)이 그대로 돈다. PowerShell 은 **명시 호출**한다:

```bash
ssh surface 'powershell.exe -NoProfile -Command "$PSVersionTable.PSVersion.ToString()"'
# → 5.1.26100.8875     (Windows PowerShell 5.1 — PS7 아님)
```

### 파일 push / pull

```bash
ssh surface 'mkdir -p ~/remote-lab'
scp ./run.ps1        surface:remote-lab/run.ps1          # push
scp surface:remote-lab/result.xlsx ./result.xlsx         # pull
```

경로는 **Git Bash 쪽은 POSIX**(`~/remote-lab/x`), **PowerShell·COM 에 넘길 때는 Windows 절대경로**(`C:\Users\<user>\remote-lab\x`)로 쓴다. COM 은 POSIX 경로를 이해하지 못한다.

**이 문서의 `<user>` 는 계정명 플레이스홀더다 — 지어내지 말고 원격에서 받아온다.** 변환은 `cygpath` 가 정본이다(실측):

```bash
WINLAB=$(ssh surface 'cygpath -w ~/remote-lab')
printf '%s\n' "$WINLAB"                            # → C:\Users\<user>\remote-lab  (echo 는 깨진다 — §함정 ⑩)
ssh surface "powershell.exe -NoProfile -Command \"Test-Path '$WINLAB'\""   # → True
```

이후 스크립트·COM 인자에는 `$WINLAB\out.xlsx` 처럼 조립해 쓴다 — 계정명을 스킬·스크립트·커밋에 하드코딩하지 않는다(§안전 규율 3). `$HOME`(`/c/Users/<user>`)·`$USERPROFILE`(`C:\Users\<user>`)도 같은 값을 준다.

### 스크립트 실행 (정본 패턴)

인라인 `-Command` 는 3중 인용(local bash → ssh → Git Bash → PowerShell)에서 깨지기 쉽다. **스크립트를 push 해 `-File` 로 실행**하는 것이 정본이다.

```bash
# 1) 로컬에서 .ps1 작성 — 한국어가 들어가면 UTF-8 BOM 필수
printf '\xEF\xBB\xBF' > run.ps1 && cat >> run.ps1 <<'PS1'
... PowerShell ...
PS1

# 2) push → 실행 → 결과 회수
scp ./run.ps1 surface:remote-lab/run.ps1
ssh surface 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\<user>\remote-lab\run.ps1"; echo "rc=$?"'
scp surface:remote-lab/result.txt ./result.txt
```

### 헤드리스 Office COM 자동화

**SSH 비대화형 세션에서 Office COM 이 직접 돈다**(실측: 값 입력 → 수식 계산 `SUM=246` → `.xlsx` 저장 → 한글 셀 보존). `Visible = $false` 로 두고, **RCW 를 역순 해제 + GC 2회**로 끝낸다 — 이것이 좀비를 막는 유일한 수단이다.

```powershell
$ErrorActionPreference = 'Stop'
$xl = $null; $wb = $null; $ws = $null
try {
  $xl = New-Object -ComObject Excel.Application
  $xl.Visible = $false          # SSH 세션에선 true 여도 화면에 안 뜬다
  $xl.DisplayAlerts = $false
  $wb = $xl.Workbooks.Add()
  $ws = $wb.Worksheets.Item(1)
  $ws.Cells.Item(1,1).Value2 = 123
  $ws.Cells.Item(3,1).Formula = '=SUM(A1:A2)'
  $wb.SaveAs('C:\Users\<user>\remote-lab\out.xlsx', 51)   # 51 = xlOpenXMLWorkbook
  "SUM=$($ws.Cells.Item(3,1).Value2)" | Out-File 'C:\Users\<user>\remote-lab\result.txt' -Encoding utf8
} finally {                     # ← 예외가 나도 반드시 지난다
  if ($wb) { $wb.Close($false) }
  if ($xl) { $xl.Quit() }
  foreach ($o in @($ws,$wb,$xl)) { if ($o) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($o) } }
  $ws=$null; $wb=$null; $xl=$null
  [GC]::Collect(); [GC]::WaitForPendingFinalizers()
  [GC]::Collect(); [GC]::WaitForPendingFinalizers()
}
```

Word=`Word.Application`, PowerPoint=`PowerPoint.Application` 도 같은 골격이다(RCW 를 만든 역순으로 해제하는 것이 계약이다).

### 좀비 가드 (COM 작업의 종결 조건)

COM 을 쓴 세션은 **반드시** 잔존을 세고 0 을 확인한다.

```bash
# 세기 — 판정은 tasklist 가 아니라 Get-Process 로 (§함정 ③)
ssh surface 'powershell.exe -NoProfile -Command "@(Get-Process EXCEL -ErrorAction SilentlyContinue).Count"'

# 0 이 아니면 — 우리가 띄운 것만 정리 (마스터가 Excel 을 쓰고 있으면 먼저 확인·승인)
ssh surface 'powershell.exe -NoProfile -Command "Get-Process EXCEL -ErrorAction SilentlyContinue | Stop-Process -Force"'
ssh surface 'powershell.exe -NoProfile -Command "@(Get-Process EXCEL -ErrorAction SilentlyContinue).Count"'   # → 0
```

실측: RCW 해제 + GC 를 갖춘 스크립트는 **잔존 0**, 그것을 뺀 스크립트는 회차마다 `EXCEL.EXE` 1개씩 누적(3회 중 2회), `Quit()` 에 도달하지 못한 예외 경로도 1개 잔존. 즉 **좀비는 예외가 아니라 기본값**이며, `finally` + RCW 해제가 그것을 막는다.

### dotnet / Go 실런타임 검증 위임

macOS 에서 빌드·타입까지는 검증되지만 실런타임은 안 되는 것들(`ci-runner-policy` 의 "빌드·로직 macOS ↔ 실런타임 Windows" 분리)을 여기서 돌린다.

```bash
scp -r ./MyProject surface:remote-lab/MyProject
ssh surface 'cd ~/remote-lab/MyProject && "/c/Program Files/dotnet/dotnet.exe" test -c Release 2>&1 | tail -40'
```

보고할 때는 **macOS 에서 검증된 것 / 이 실머신에서 검증된 것 / 여전히 공백인 것**을 분리해 적는다.

---

## 반드시 지킬 함정 (전부 라이브 실측)

① **기본 셸이 Git Bash 다.** `dir`·`type` 같은 cmd 내장 명령은 없고 `ls`·`cat` 이 돈다. PowerShell 이 필요하면 `powershell.exe -NoProfile -Command "..."` 를 명시 호출한다.

② **인용이 4겹이다** — local bash → ssh → Git Bash → PowerShell. `|`·`>`·`$` 는 **Git Bash 가 먼저 먹는다**. 실측 사고 2건:
  - `powershell.exe -Command "..." | Select-String boom` → `Select-String: command not found`(Git Bash 가 파이프를 해석). PowerShell 파이프라인은 **따옴표 안**에 둔다.
  - `ForEach-Object { "pid=" + $_.Id }` → **원격 Git Bash 가 `$_` 를 `/usr/bin/bash` 로 확장**해 PowerShell 파서 에러. 로컬을 작은따옴표로 감싸도 **원격 bash 의 확장은 안 막힌다** — PowerShell 변수는 `\$_`·`\$xl` 처럼 **역슬래시로 이스케이프**한다.

  둘 다 스크립트를 push 해 `-File` 로 돌리면 애초에 생기지 않는다 — 인라인이 두 줄을 넘으면 §스크립트 실행 패턴으로 간다.

③ **`tasklist` 는 못 찾아도 rc=0** 이고, 없다는 메시지가 **CP949 로 깨져** 나온다. 존재 판정을 종료코드·출력 문자열로 하지 말고 `@(Get-Process X -ErrorAction SilentlyContinue).Count` 로 **숫자**를 받는다. (`//FI`·`//NH` 처럼 슬래시를 두 번 쓰는 것은 MSYS 경로 변환 회피 관례다.)

④ **한글 출력이 CP949 로 깨진다.** 원격 콘솔 기본 인코딩은 `ks_c_5601-1987`. PowerShell 출력에 한글이 있으면 첫 줄에 `[Console]::OutputEncoding=[Text.Encoding]::UTF8` 를 넣는다(실측: 넣으면 `한글 테스트` 정상, 빼면 깨짐). Git Bash 자체 경로(`cat`·`echo`)는 UTF-8 로 정상이다.

⑤ **한국어가 든 `.ps1` 은 UTF-8 BOM 필수.** PS 5.1 은 BOM 없는 UTF-8 을 CP949 로 오독해 파싱 에러·문자 깨짐을 낸다. 작성은 `printf '\xEF\xBB\xBF' > x.ps1` 로 시작한다. 반대로 **`Out-File -Encoding utf8` 은 BOM 을 붙이므로**, 회수한 결과 파일을 파싱할 때 선행 `\xEF\xBB\xBF` 를 벗긴다.

⑥ **SSH 세션은 비대화형(Services 세션 0)이다.** `query session` 실측: SSH 는 `services`(ID 0), 로그인 사용자는 `console`(ID 1). 그래서 `Visible=$true` 로 띄운 창도 **화면에 뜨지 않고**, 사람에게 보여야 하는 시연·GUI 는 이 경로로 불가능하다 → 부록.

⑦ **hyve.exe(폐기된 hyve 데스크톱 앱 — 2026-08 실측)는 GUI 서브시스템 바이너리**라 SSH 에서 실행해도 **stdout 이 오지 않았다**(무응답처럼 보인다). `rc=0` 인데 출력만 비는 것이 이 증상이다 — "명령이 실패했다"가 아니라 **콘솔이 훔쳤다**로 읽는다(`-H=windowsgui` + `attachParentConsole()` 이 `os.Stdout` 을 `CONOUT$` 로 교체해 **리다이렉트로도 안 잡힌다**). 상태는 로그 파일·프로세스·포트로 확인한다. 캡처 우회는 콘솔 없는 부모로 띄우는 것이다(정본 기록: 보관된 `itda-skills/hyve` 저장소 규칙 `shell-platform-contract-drift` §축 3, hyve #1483). 기동 자체에 대화형 세션이 필요하면 부록으로 간다.

  **이것은 hyve.exe 의 성질이지 GUI 서브시스템 바이너리 일반의 성질이 아니다**(2026-10-01 실측). 같은 GUI 서브시스템인 itda-hyve.exe(Wails 앱)는 SSH 에서 `version` stdout 이 정상으로 왔다 — 리다이렉트(`> out.txt`)·직접 실행 모두. 콘솔을 붙잡는 방식이 바이너리마다 다르므로, 새 바이너리는 **출력이 오는지부터 한 번 재고** 판정 경로를 정한다.

  ⚠️ **원격 로컬 서버의 HTTP 응답은 상태코드로 판정하지 않는다.** hyve 앱 실측(2026-08)에서 같은 서버라도 라우트에 따라 TCP 조회가 **200 + SPA HTML**(catch-all 위조)을 주기도, 정상 JSON 을 주기도 했다 — **라우트마다 다르다**. 결론은 하나다: **Content-Type + 계약 필드로 판정**한다(`no-silent-fallback` §HTTP 200 위조). 헬스 체크처럼 계약이 분명한 엔드포인트를 쓴다.

⑧ **좀비는 기본값이다** — §좀비 가드.

⑨ **로컬 셸은 zsh** — `read -ra` 금지, `arr=(...)` 사용. 원격 명령은 작은따옴표로 감싸 로컬 확장을 막는다.

⑩ **회수한 Windows 경로를 `echo` 로 찍으면 깨져 보인다.** zsh 의 `echo` 는 백슬래시 이스케이프를 해석해 `C:\Users\<user>\remote-lab` 을 `C: sers\<user>emote-lab` 으로 출력한다(`\U`·`\r` 해석 — `Users` 의 `U`, `remote` 의 `r` 이 먹힌다). **값은 멀쩡하다** — 같은 변수로 `Test-Path` 가 `True` 를 반환했고 `${#VAR}` 도 정확했다. 표시는 `printf '%s\n' "$VAR"` 로 한다. `echo` 결과만 보고 "경로 회수가 깨졌다"고 판단해 하드코딩으로 우회하지 않는다 — **깨진 것은 관측이지 값이 아니다**.


⑪ **`Subsystem sftp` 가 상대 이름이면 sftp 가 죽는다** (2026-09-09 실측). 기본 셸이 Git Bash 라 sshd 가 `sftp-server.exe` 를 그 PATH 에서 못 푼다 — `sftp` 는 `Connection closed`, 그런데 **`scp -O`(레거시)는 통과**해서 "scp 는 되는데" 로 오진하기 쉽다. `C:\ProgramData\ssh\sshd_config` 를 절대경로로 고친다: `Subsystem	sftp	"C:/Program Files/OpenSSH/sftp-server.exe"`.

⑫ **scoop shim 은 SSH 세션에서 실행에 실패한다** (2026-09-09 실측). `jq` 가 scoop shim 이면
`Shim: Could not create process with command ...` 로 죽는다. statusline 처럼 `jq` 에 의존하는
것은 **죽지 않고 값이 전부 0** 으로 나와 더 헷갈린다. 네이티브 단일 실행파일을 `~/.local/bin`
에 둔다(`jq-windows-amd64.exe`).

⑬ **Store(msix) 판 PowerShell 7 은 SSH 에서 못 쓴다** (2026-09-09 실측). 실행 별칭
(`%LOCALAPPDATA%\Microsoft\WindowsApps\pwsh.exe`)이 `Permission denied` 로 죽는다. winget 의
`Microsoft.PowerShell` 은 **msix 만 제공**하므로(`--installer-type msi` 는 rc=16) GitHub 릴리스의
**MSI** 를 깔아 `C:\Program Files\PowerShell\7` 에 실체를 만든다. MSI 를 깔아도 PATH 에서는
**별칭이 여전히 먼저 잡히므로**, 이름이 아니라 절대경로로 호출한다.

⑭ **`$PROFILE` 경로를 Git Bash 로 다루지 않는다** (2026-09-09 실측). Documents 가 OneDrive 로
리디렉션되고 폴더명이 한글("문서")이면, cygpath 로 만든 POSIX 경로에 쓴 파일이 pwsh 쪽에
나타나지 않는다(`Test-Path` → False, 인코딩이 갈려 별도 디렉토리가 생김). ASCII 임시 경로로만
전송하고 최종 배치는 pwsh 가 `$PROFILE.CurrentUserAllHosts` 로 직접 하게 한다.

⑮ **Ghostty 로 접속하면 `TERM=xterm-ghostty` 가 그대로 넘어온다** — 원격에 그 terminfo 가 없으면
`git log` 등이 `'xterm-ghostty': unknown terminal type.` 로 죽는다. 맥에서 한 번 심는다:
`infocmp -x xterm-ghostty | ssh surface 'tic -x -'`.

⑯ **herdr 은 이 머신을 SSH 타깃으로 받지 않는다.** `herdr --remote` 도 0.9.0 의 `herdr machine`
도 Linux/macOS 서버만 지원한다(공식 문서: "Native Windows servers are not supported as SSH
targets"). `ssh -t surface herdr` 로 들어가 그쪽 herdr 을 띄우는 것이 유일한 경로다. SSH 로 띄운
서버·pane 은 로그아웃 후에도 살아남는다. 마우스는 pane 으로 새므로(상류 PR #3742 미머지)
`[ui] mouse_capture = false` 로 둔다.

⑰ **SSH 기본 셸이 PowerShell 7(pwsh)일 수 있다** (2026-10-01 실측 — 로컬 네트워크의 다른 Windows 10 실기, Boot Camp·amd64). ①의 Git Bash 는 이 머신의 설정이지 기본값이 아니다 — sshd 는 `HKLM\SOFTWARE\OpenSSH\DefaultShell` 을 따른다. 그래서 같은 명령이 머신마다 다른 셸에서 돈다. 셸에 기대지 말고 **5.1 을 명시**하고, 긴 스크립트는 push 없이 **stdin 으로** 넘긴다(인용 겹이 사라진다):

```bash
ssh <host> 'powershell -NoProfile -ExecutionPolicy Bypass -Command -' < script.ps1
```

  한글 출력이 있으면 스크립트 첫 줄에 `[Console]::OutputEncoding=[Text.Encoding]::UTF8` 를 둔다(④와 같은 결).

⑱ **쓰지 않는 노트북은 절전으로 거의 잠들어 있다** (2026-10-01 실측). 약 40분 간격으로 몇 분씩만 깨어나므로, 그 사이에는 SSH 가 시간 초과로 죽고 네트워크 VPN 에서도 offline 으로 보인다 — 접속 실패를 설정 결함으로 읽지 않는다. **깨어난 순간** 사용자 세션에 잠들지 못하게 붙잡는 PowerShell 을 띄워 실측 동안 유지하고, 끝나면 그 프로세스만 끝낸다. **전원 설정(`powercfg /change`)은 바꾸지 않는다** — 실사용 머신의 설정이다.

```powershell
# keepawake.ps1 — 부록 ⓐ 의 schtasks /IT 로 사용자 세션에 띄운다(세션 0 에서는 효과가 없다)
Add-Type -Namespace W -Name P -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[void][W.P]::SetThreadExecutionState([uint32]2147483651)   # 0x80000003 = ES_CONTINUOUS|ES_SYSTEM_REQUIRED|ES_DISPLAY_REQUIRED (5.1 에서 0x8… 리터럴은 음수 Int32 라 십진수로 쓴다)
while ($true) { Start-Sleep -Seconds 60 }
```

  유지 여부는 `powercfg /requests` 의 SYSTEM·DISPLAY 항목에 그 프로세스가 보이는지로 확인한다. 실측이 끝나면 그 PID 를 끝내고 작업을 지운다(§부록 ⓐ4 와 같은 정리 순서).
---

## 부록: 대화형 세션 + MCP 터널 (선택)

이 절은 **대화형 세션이 반드시 필요할 때만** 적용한다(사용자에게 보이는 창, 트레이 앱, 사용자 세션에서 떠야 하는 로컬 서버). 1층으로 되는 일을 여기로 가져오지 않는다. 마스터가 그 머신을 쓰고 있을 수 있으므로 **사전 승인 후** 실행한다.

### ⓐ schtasks 로 로그인 사용자의 대화형 세션에 기동

SSH(세션 0)에서 띄운 프로세스는 콘솔 세션에 나타나지 않는다. 작업 스케줄러는 **로그인 사용자 컨텍스트**로 실행하므로 이 경계를 넘는다.

아래 `<app>`(프로세스 이름)·`<app-path>`(실행 파일 절대경로)·`<args>`·`<PORT>` 는 자리표시다 — 원격에서 확인한 값으로 채우고 스킬·커밋에 박지 않는다. 작업 이름은 우리 것임이 드러나게(`lab-probe` 처럼) 짓는다.

**착수 전 상태 확인**(마스터가 이미 쓰고 있으면 건드리지 않는다):

```bash
ssh surface 'powershell.exe -NoProfile -Command "@(Get-Process <app> -ErrorAction SilentlyContinue).Count";
             netstat -ano | grep <PORT> | grep -i listening;
             schtasks //Query //TN lab-probe >/dev/null 2>&1 && echo TASK_EXISTS || echo TASK_NONE'
```

```bash
# 1) 등록 — /IT(대화형 전용)라 비밀번호가 필요 없다. 자격증명을 명령줄에 넣지 않는다.
#    경로는 해석된 절대경로로(공백이 든 경로는 따옴표째 넘긴다).
ssh surface 'schtasks //Create //TN lab-probe //TR "<app-path> <args>" //SC ONLOGON //RU <user> //IT //F'

# 2) 즉시 기동 (지금 로그인돼 있는 콘솔 세션에서 뜬다)
ssh surface 'schtasks //Run //TN lab-probe'

# 3) 상태 확인 — GUI 바이너리는 stdout 이 없을 수 있으므로(§함정 ⑦) 프로세스/세션/포트로 본다
ssh surface 'powershell.exe -NoProfile -Command "Get-Process <app> | ForEach-Object { \"pid=\" + \$_.Id + \" sess=\" + \$_.SessionId }"'
#   → pid=… sess=1   ← 세션 1 = 콘솔(대화형). 세션 0 이면 경계를 못 넘은 것이다.
ssh surface 'netstat -ano | grep <PORT> | grep -i listening'      # 서버라면

# 4) 정리 — 우리가 만든 것만. End → 프로세스 0 확인 → Delete → 작업 소멸 확인
ssh surface 'schtasks //End //TN lab-probe; sleep 2;
             powershell.exe -NoProfile -Command "@(Get-Process <app> -ErrorAction SilentlyContinue).Count"'
ssh surface 'schtasks //Delete //TN lab-probe //F;
             schtasks //Query //TN lab-probe >/dev/null 2>&1 && echo STILL_EXISTS || echo GONE'
```

⚠️ **`schtasks //Run` 의 rc=0 은 "요청했다"이지 "떴다"가 아니다**(메시지 원문도 "실행하도록 시도했습니다"). 판정은 반드시 3)의 프로세스·포트로 한다. `schtasks` 의 한국어 메시지는 CP949 로 깨지므로 **rc 와 `//Query` 결과로 읽는다**(§함정 ③④와 같은 결).

### ⓑ SSH 포트포워딩으로 원격 로컬 서버 접속

원격 머신의 `127.0.0.1` 에만 바인딩된 서버(HTTP·MCP 등)를 맥으로 끌어온다. **원격에서 포트를 외부에 열지 않는다**(터널만).

```bash
lsof -nP -iTCP:<PORT> -sTCP:LISTEN            # 맥 쪽 로컬 포트 선점 확인(비어야 함)
ssh -f -N -o ExitOnForwardFailure=yes -L <PORT>:127.0.0.1:<PORT> surface
#   ExitOnForwardFailure — 포워딩 실패를 조용히 넘기지 않는다(no-silent-fallback)
#   맥에서 같은 포트를 이미 쓰고 있으면 왼쪽만 바꾼다: -L <다른 포트>:127.0.0.1:<PORT>

curl -s -w '\nHTTP=%{http_code} CT=%{content_type}\n' http://127.0.0.1:<PORT>/<health 경로>
#   → 계약 JSON / HTTP=200 CT=application/json 이어야 한다
```

**판정은 상태코드가 아니라 Content-Type + 계약 필드로 한다**(`no-silent-fallback` — SPA catch-all 이 200/text/html 을 돌려준다).

인증 토큰이 필요한 서버면 **토큰 값을 출력·로그·커밋에 남기지 않는다** — 원격 파일에서 변수로만 흘리고 쓰고 나면 `unset` 한다. MCP 서버면 `initialize` 요청 한 번(`Accept: application/json, text/event-stream`)으로 종단을 확인한다 — 토큰 없이 401 이 오면 "라우트는 있고 게이트가 산다"는 뜻이다.

**정리는 터널 → 작업 순서로**: 로컬 `ssh -f` 프로세스를 kill 하고 `lsof` 로 해제를 확인한 뒤 ⓐ4 를 수행한다. 원격 `netstat` 에 남는 `TIME_WAIT` 줄은 커널이 자동 만료시키므로 잔재가 아니다 — **`LISTENING` 이 0 인지**로 판정한다.

### ⓒ 사용자 세션 GUI 자동화 — 트레이·작업 표시줄·팝업 메뉴

ⓐ 로 사용자 세션(콘솔)에 띄운 PowerShell 5.1 에서 창을 찾고 누르고 찍는다. 마스터가 그 화면을 쓰고 있을 수 있으므로 **사전 승인 후, 자리 비움 확인 후**에만 한다(입력이 사용자 앱으로 샌다 — 사람이 쓰는 데스크톱을 교란하지 않는다). 전부 2026-10-01 실측(로컬 네트워크의 다른 Windows 10 실기)이다.

- **Win32 껍데기 UI 는 관리 UIA 로 자식이 안 보인다.** Windows 10 의 알림 영역·넘침 창(`NotifyIconOverflowWindow`)·작업 표시줄 단추·팝업 메뉴는 PowerShell 5.1 의 `System.Windows.Automation` 으로 열거하면 자식이 비어 나온다. **MSAA**(`oleacc!AccessibleObjectFromWindow` → `IAccessible` 자식 순회)로 열거한다. 반대로 XAML 쪽(Alt+Tab 전환기·웹뷰 내용)은 UIA 로 보인다 — 대상마다 API 를 고른다.
- **PowerShell 은 P/Invoke 의 string 인자에 `$null` 을 넘기면 `""` 로 바꾼다.** `FindWindowEx($parent, 0, 'ClassName', $null)` 은 "제목 무관"이 아니라 **제목이 빈 창만** 찾는다 — 못 찾아도 에러가 없어 조용히 틀린다. NULL 이 필요하면 `[NullString]::Value` 를 넘긴다.
- **작업 표시줄 "뉴스 및 관심사" 위젯은 마우스를 올리면 열려 넘침 창을 덮는다.** 넘침 단추에는 마우스를 **오른쪽에서** 다가가게 한다(위젯 위를 지나지 않게). 덮인 채 누르면 위젯 카드가 눌려 **사용자 브라우저에 탭이 열린다**(실제로 일어났다).
- **캡처는 같은 세션에서 GDI BitBlt(`CAPTUREBLT`)** 로 한다. 세션 0(SSH)에서 찍으면 사용자 화면이 아니다.
- **실측 대조 팁 — 트레이 아이콘 정리.** Windows 10 은 강제 종료(`taskkill /F`)된 프로세스의 알림 영역 아이콘을 **마우스를 올릴 때까지 남긴다**(Windows 11 은 곧바로 치운다). 그래서 "정상 종료 → 아이콘 소멸 / 강제 종료 → 아이콘 잔존"의 차이로, 앱이 정상 종료 때 `Shell_NotifyIcon(NIM_DELETE)` 로 아이콘을 지우는지 가를 수 있다. 판정 전에 마우스를 트레이 위로 지나가게 하지 않는다(유령 아이콘이 치워져 대조가 사라진다).

---

## 검증 상태

2026-10-01 회차(로컬 네트워크의 다른 Windows 10 실기 — 트레이 앱 로그오프·종료 실측)의 교훈은 §함정 ⑦⑰⑱·§부록 ⓒ 에 넣었다.

아래는 2026-08-12 회차(hyve #1486) 기록이다. 부록 대상 앱이 **지금은 폐기된 hyve 데스크톱 앱**이었다 — 부록 ⓐⓑ 의 절차는 앱과 무관하게 같고, 표의 값은 그 회차의 기록으로 남긴다.

macOS → `ssh surface` 라이브 실측 전건 PASS:

| 항목 | 결과 |
|---|---|
| SSH 접속·셸 판별 | PASS — MINGW64(Git Bash), `/c/Users/<user>` |
| PowerShell 명시 호출 | PASS — 5.1.26100.8875 |
| UTF-8 출력 스위치 | PASS — 미적용 시 CP949 깨짐 재현 |
| scp push/pull | PASS — `.ps1` push, `.xlsx` pull(로컬 `file` 판정 = Microsoft Excel 2007+) |
| Excel COM 헤드리스 | PASS — 수식 `SUM=246`, 한글 셀 보존, `.xlsx` 저장 |
| 좀비 재현·가드·정리 | PASS — 미해제 스크립트 3회 중 2회 잔존 + 예외 경로 1회 잔존 → RCW 해제판은 잔존 0, `Stop-Process` 정리 후 0 확인 |
| 세션 경계 | PASS — `query session`: SSH=services(0), 사용자=console(1) |
| dotnet·hyve 존재 | PASS — `C:\Program Files\dotnet\dotnet.exe`, `%LOCALAPPDATA%\hyve\hyve.exe` |

**부록도 같은 회차에 라이브 실측**(마스터 승인 후, 착수 전 상태 확인 → 사후 전량 정리):

| 항목 | 결과 |
|---|---|
| schtasks 등록·기동 | PASS — `/RU <user> /IT` 로 비밀번호 없이 등록, `//Run` rc=0 |
| **세션 경계 돌파** | PASS — `hyve.exe pid=13752 **sess=1**`(tasklist 교차확인 `"Console","1"`). SSH 는 세션 0 인데 프로세스는 콘솔 세션에 떴다 |
| 포트 리스닝 | PASS — 원격 `127.0.0.1:18520 LISTENING` |
| SSH 터널 | PASS — `-f -N -L 18520:127.0.0.1:18520`, 맥 로컬 LISTEN 확인 |
| healthz | PASS — `{"status":"ok"}` / HTTP 200 / `application/json`(CT+계약 필드 동시 판정) |
| `/api/version` | PASS — `"v1.1.0-1160-g809135b4"` |
| **MCP 프리셋 종단** | PASS — `/mcp/office` 무토큰 401 → Bearer 인증 `initialize` **200**, `serverInfo.name=hyve`(토큰 값 미출력) |
| 정리 | PASS — 터널 해제·`//End` 후 hyve 0·`//Delete` 후 `GONE`·포트 LISTENING 0·EXCEL 0·`~/remote-lab` 비움 |

부작용 없음: 마스터 머신에 남긴 작업·프로세스·파일 0. hyve serve 가 마스터 실앱디렉토리에 로그·`discovery.json` 을 갱신하는 것은 정상 기동의 결과다(격리 인스턴스를 쓰지 않았다 — 실머신 검증이므로 의도된 선택).
