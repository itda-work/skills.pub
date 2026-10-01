---
name: cloudflare-tunnel
description: >
  포트포워딩 없이 Cloudflare Tunnel로 내 서비스(원격 데스크톱·SSH·웹)를 안전하게 노출/접근하도록
  셋업하는 스킬입니다. "집 윈도우에 RDP 터널 깔아줘", "cloudflare tunnel로 ssh 열어줘",
  "터널 라우트에 access 걸어줘", "이 desired-state로 터널 구성 검증해줘"처럼 말하면 됩니다.
  라우트별 Zero Trust Access를 기본 적용하고, 선언형 desired-state로 ingress·DNS·Access 계획을
  멱등 산출하며, Windows/macOS/Linux를 모두 지원합니다.
license: Apache-2.0
compatibility: "Claude Code 등 로컬 실행 환경이 정본(cloudflared 설치·서비스 등록·브라우저 인증). Cowork 는 plan/audit/config 산출까지. Python 3.10+, cloudflared 필요."
allowed-tools: Bash, Read, Write, mcp__workspace__bash
user-invocable: true
argument-hint: "[plan | audit | config STATE.json] · 이후 cloudflared 런북"
metadata:
  author: "스킬.잇다 <dev@itda.work>"
  category: "ops"
  version: "0.2.0"
  created_at: "2026-06-21"
  updated_at: "2026-09-30"
  tags: "cloudflare, tunnel, cloudflared, zero-trust, access, rdp, ssh, remote-access, ops"
---

# cloudflare-tunnel

Cloudflare Tunnel(`cloudflared`)로 **포트포워딩·인바운드 개방 없이** 내 서비스를 외부에서 접근할 수 있게 셋업합니다. 터널은 집/서버에서 Cloudflare 엣지로 *아웃바운드* 연결만 맺으므로 공인 IP·방화벽 개방·CGNAT 여부와 무관하게 동작합니다.

> 이 스킬은 **세팅 도구**입니다. 상시 실행 데몬은 `cloudflared`(OS 서비스)이며, 트래픽 중계는 스킬이 하지 않습니다. hyve 데몬/MCP에 의존하지 않습니다.

## 보안 모델 (기본값 — 반드시 숙지)

- **라우트별 Access 기본 required.** desired-state 에서 `access` 를 생략하면 자동으로 Zero Trust Access 보호가 붙습니다.
- **public 은 명시적 opt-in 만.** 공개 웹페이지처럼 Access 가 없어야 하는 라우트는 `"access": "public"` 을 직접 적어야 합니다.
- **비-HTTP 서비스는 public 불가.** `rdp://`·`ssh://`·`tcp://` 등에 `public` 을 주면 정책 엔진이 **거부(exit 2)** 합니다. 이런 서비스는 항상 Access 로 보호하세요.
- **public = 진짜 공개.** Access 를 떼면 그 라우트는 원본 서비스 자체 인증·보안에만 의존합니다(Cloudflare Access/WAF 보호 없음).

## 사전 준비 (Prerequisites)

**먼저** 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 `SKILL_DIR` 에 넣고 아래 블록을 실행한다 — 블록은 그 값을 검증해 쓰고, 넣지 못했을 때만 설치 위치를 찾는다(후보가 여럿이면 멈춘다).

```bash
# SKILL_DIR 확정(skill-dir-resolution) — 스킬을 불러올 때 받은 base directory 를 먼저 SKILL_DIR="그 경로" 로 넣는다(항상)
# 블록은 그 값을 검증해 쓰고, 넣지 못했을 때만 설치 위치를 찾는다 — SKILL.md 가 있는 후보가 하나일 때만 받고 아니면 멈춘다
SKILL_DIR=$(sh -c '
S=$1 P=$2 H=${5:-$HOME/.claude}
ok() { d=${1%/}; [ "${d##*/}" = "$S" ] && [ -f "$d/SKILL.md" ] && (cd "$d" && pwd -P); }
[ -n "$3" ] && { ok "$3" && exit; d=${3%/}; [ "${d##*/}" = "$S" ] && echo "SKILL_DIR 무시: $3 에 SKILL.md 가 없다" >&2; }
[ -n "$4" ] && { ok "$4/skills/$S" && exit; echo "CLAUDE_PLUGIN_ROOT 무시: $4/skills/$S 에 SKILL.md 가 없다" >&2; }
c=$(for d in "$H"/plugins/synced/*/"$P"/skills/"$S" "$H"/plugins/synced/*/"$P"~*/skills/"$S" "$H"/plugins/cache/*/"$P"/*/skills/"$S" \
    /root/.claude/plugins/synced/*/"$P"/skills/"$S" /root/.claude/plugins/synced/*/"$P"~*/skills/"$S" \
    /sessions/*/mnt/.remote-plugins/*/skills/"$S" /sessions/*/mnt/.claude/skills/"$S"; do ok "$d"; done | sort -u)
[ "$(printf "%s\n" "$c" | grep -c .)" -gt 1 ] && { printf "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다:\n%s\n" "$c" >&2; exit 1; }
printf "%s\n" "$c"' _ cloudflare-tunnel itda-dev "${SKILL_DIR:-}" "${CLAUDE_PLUGIN_ROOT:-}" "${CLAUDE_CONFIG_DIR:-}")
: "${SKILL_DIR:?정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 SKILL_DIR 에 넣고 이 블록을 다시 실행하라}"
```

```powershell
# SKILL_DIR 확정(skill-dir-resolution) — bash 블록과 같은 계약. 스킬을 불러올 때 받은 base directory 를 먼저 $env:SKILL_DIR 에 넣는다(항상)
$S = 'cloudflare-tunnel'; $P = 'itda-dev'; $H = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$ok = { param($d) if ($d -and (Split-Path $d.TrimEnd('\', '/') -Leaf) -eq $S -and (Test-Path -LiteralPath (Join-Path $d 'SKILL.md'))) { (Resolve-Path -LiteralPath $d).Path.TrimEnd('\', '/') } }
$c = @(& $ok $env:SKILL_DIR) + @(if ($env:CLAUDE_PLUGIN_ROOT) { & $ok (Join-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT 'skills') $S) })
if (-not $c) { $c = @(@(Get-Item -Path (Join-Path $H "plugins/synced/*/*/skills/$S") -ErrorAction SilentlyContinue | Where-Object { $_.Parent.Parent.Name -eq $P -or $_.Parent.Parent.Name -like "$P~*" }) + @(Get-Item -Path (Join-Path $H "plugins/cache/*/$P/*/skills/$S") -ErrorAction SilentlyContinue) | Where-Object { $_.PSIsContainer } | ForEach-Object { & $ok $_.FullName } | Sort-Object -Unique) }
if ($c.Count -gt 1) { Write-Warning "SKILL_DIR 후보가 여럿이다 — 어느 설치본이 쓰이는지 모른다: $($c -join ', ')"; $c = @() }
if (-not $c) { throw 'SKILL_DIR 을 정하지 못했다 — 스킬을 불러올 때 받은 base directory(이 SKILL.md 가 있는 절대경로)를 $env:SKILL_DIR 에 넣고 이 블록을 다시 실행하라' }
$env:SKILL_DIR = $c[0]
```

1. **도메인이 Cloudflare DNS** 에 있어야 합니다(zone 등록).
2. **Zero Trust(Access)** 활성화 — 무료 플랜으로 충분(이메일 OTP 등).
3. **`cloudflared` 설치**
   - macOS: `brew install cloudflared`
   - Linux: 패키지 또는 https://github.com/cloudflare/cloudflared/releases
   - Windows: `winget install --id Cloudflare.cloudflared` 또는 위 릴리즈의 `.msi`
4. **Cloudflare API 토큰** — DNS/Access 구성용. **Global API Key 금지**, 최소 스코프로 발급:
   - `Zone.DNS:Edit` (해당 zone)
   - (Access 앱을 API로 만들 경우) Account 의 `Access: Apps and Policies:Edit`
   - 보관: OS 보안 저장소(Keychain / Windows 자격 증명 관리자 / secret-service) 권장. 폴백은 **셸 환경변수** `CLOUDFLARE_API_TOKEN`(Claude Code 는 `claude config set env.CLOUDFLARE_API_TOKEN "토큰"` 도 가능, 등록 뒤 세션 재시작). 토큰을 `.env` 파일에 두라고 안내하지 않는다(itda-work/skills#45). **토큰·자격증명은 절대 저장소에 커밋하지 않습니다.**

## desired-state (선언형 구성)

라우트와 보안 자세를 한 파일(JSON)로 선언합니다. 이 한 장이 "무엇을 노출하고 무엇을 보호하는가"의 단일 진실입니다.

```json
{
  "tunnel": "home-win",
  "default_policy": "email:you@example.com",
  "routes": [
    { "hostname": "rdp.example.com", "service": "rdp://localhost:3389" },
    { "hostname": "blog.example.com", "service": "http://localhost:8080", "access": "public" }
  ]
}
```

- `tunnel`: 터널 이름. `default_policy`: Access 라우트에 개별 `policy` 미지정 시 기본 신원.
- 라우트 `access` 생략 → `required`(보호). `policy` 로 라우트별 신원 재정의 가능.

## 사용법

### 1) 정책 검증 + 계획 산출 (먼저 실행)

desired-state 가 보안 정책을 지키는지 검사하고, cloudflared ingress·DNS·Access 계획을 출력합니다. **위반 시 exit 2 로 중단**되므로 적용 전 게이트로 씁니다.

```bash
# macOS/Linux
python3 "$SKILL_DIR/scripts/tunnel_policy.py" plan state.json --tunnel-id <TUNNEL_UUID>
python3 "$SKILL_DIR/scripts/tunnel_policy.py" audit state.json        # 노출 경고만
python3 "$SKILL_DIR/scripts/tunnel_policy.py" config state.json --tunnel-id <UUID> \
  --credentials-file <CREDS.json> > config.yml           # cloudflared config.yml 생성

# Windows
py -3 "$env:SKILL_DIR\scripts\tunnel_policy.py" plan state.json --tunnel-id <TUNNEL_UUID>
```

`--format json` 으로 기계가독 출력도 가능합니다. PUBLIC 라우트·drift 는 경고로 표면화됩니다.
생성한 config.yml 은 cloudflared 자체 검증기로 교차검증할 수 있습니다(계정 불필요):
`cloudflared tunnel --config config.yml ingress validate` → `OK`.

### 2) 터널 생성·적용 (cloudflared 런북)

> v0.1.0 은 정책 검증·계획 산출을 자동화하고, 아래 cloudflared 단계는 에이전트가 계획에 따라 실행합니다(완전 apply 자동화는 미도입 — #613 NOT_PLANNED).

```bash
# (a) 최초 1회 로그인 — 브라우저로 zone 인증, cert.pem 생성
cloudflared tunnel login

# (b) 터널 생성 (자격증명 JSON 생성) — 이름은 desired-state 의 tunnel
cloudflared tunnel create home-win
cloudflared tunnel list          # UUID 확인 → 위 plan 의 --tunnel-id 로 사용

# (c) config.yml 생성 + 사전 검증 (정책 엔진이 desired-state 에서 직접 생성)
python3 "$SKILL_DIR/scripts/tunnel_policy.py" config state.json --tunnel-id <UUID> --credentials-file <CREDS> > config.yml
cloudflared tunnel --config config.yml ingress validate   # → OK

# (d) DNS 라우트 — 각 hostname → 터널 CNAME (plan 의 dns 항목)
cloudflared tunnel route dns home-win rdp.example.com
cloudflared tunnel route dns home-win blog.example.com

# (e) required 라우트에 Access 애플리케이션 생성 (Zero Trust 대시보드 또는 API)
#     plan 의 access 항목 = 보호 대상 hostname + policy. blog(public)은 제외.

# (f) 서비스로 상시 실행 등록 (3 OS 공통 — cloudflared 가 OS 서비스 매니저 위임)
cloudflared service install     # Windows=서비스, macOS=launchd, Linux=systemd
```

### 3) 원격 데스크톱(RDP) 접속

서버측 ingress(`rdp://localhost:3389`) + Access 보호 후, 클라이언트에서 로컬 프록시로 접속합니다. 자세한 단계는 [references/rdp-recipe.md](references/rdp-recipe.md) 참고.

## 환경 변수

| 변수 | 용도 | 비고 |
|------|------|------|
| `CLOUDFLARE_API_TOKEN` | DNS/Access 구성 | OS 보안 저장소 권장, 폴백은 셸 환경변수. `.env` 파일 안내 금지. 커밋 금지 |
| `CLOUDFLARE_ACCOUNT_ID` | Access 앱 API 생성 시 | Zero Trust 대시보드로 만들면 불필요 |

## 트리거 키워드

cloudflare tunnel, 클라우드플레어 터널, cloudflared, zero trust, access, 원격 데스크톱, RDP, 원격접속,
포트포워딩 없이, 터널, ingress, ssh 터널, 내부망 노출, remote desktop, tunnel route

## 파일 구조

```
cloudflare-tunnel/
  SKILL.md
  scripts/
    tunnel_policy.py          # desired-state 검증·정책 강제·계획 산출 (순수 로직)
    tests/
      conftest.py
      test_tunnel_policy.py
  references/
    rdp-recipe.md             # RDP over Tunnel 단계별 레시피
```

## 오류 처리

| 증상 | 원인 | 해결 |
|------|------|------|
| `정책 위반: ... access: public ...` (exit 2) | 비-HTTP 서비스에 public | 해당 라우트를 `access: required` 로 (또는 생략) |
| `입력 오류` (exit 1) | JSON 형식·필드 누락 | desired-state 스키마 확인(`tunnel`, `routes[].hostname/service`) |
| `cloudflared: command not found` | 미설치 | 위 사전 준비 (b) 설치 |
| 터널 연결되나 접속 불가 | DNS/Access 미구성 또는 origin 미기동 | plan 의 dns·access 항목 적용 여부, 로컬 서비스 포트 확인 |

## 한계 / 로드맵

- v0.1.0: 정책 검증·계획 산출 자동화 + cloudflared 수동 런북 — 이 스킬의 의도된 종착점. **완전 apply 자동화**(config.yml 생성·DNS·Access·service install 일괄, reconcile)는 도입하지 않습니다(SPEC-OPS-TUNNEL-002 #613 NOT_PLANNED — RDP는 별도 터널 경로로 운영).
- 라우터 포트포워딩·호스트 방화벽은 다루지 않습니다(터널은 불필요).
- 직접 inbound(터널 밖) 동적 DNS(`cloudflare-ddns`, #546)는 다루지 않습니다(NOT_PLANNED).
- Windows 경로는 CI(Windows 러너) + 로컬 실측으로 검증합니다.

## 참고

- Cloudflare Tunnel: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/
- Zero Trust Access: https://developers.cloudflare.com/cloudflare-one/policies/access/
