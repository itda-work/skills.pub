# itda-dev

개발 환경 지원 스킬팩 — Cloudflare Tunnel 노출(cloudflare-tunnel), 에이전트·스킬 하네스 설계(harness), 개발도구 릴리즈 요약(changelog), Orca 활용 코칭(orca-coach), Parallels Windows 랩 제어(windows-parallels-lab), Windows 실기 SSH 랩(windows-remote-lab).

> 개발자 대상 지원 스킬만 둡니다.

## 포함 스킬

| 스킬 | 기능 |
|---|---|
| [`changelog`](skills/changelog/SKILL.md) | Orca(onorca.dev)·Claude Code·Codex CLI·herdr 의 최근 릴리즈를 모아 버전별 한국어 요약으로 만들고 Orca 내장 브라우저 탭으로 연다. |
| [`cloudflare-tunnel`](skills/cloudflare-tunnel/SKILL.md) | 포트포워딩 없이 Cloudflare Tunnel로 내 서비스(원격 데스크톱·SSH·웹)를 안전하게 노출/접근하도록 셋업하는 스킬입니다. |
| [`harness`](skills/harness/SKILL.md) | 하네스를 구성합니다. |
| [`orca-coach`](skills/orca-coach/SKILL.md) | Orca(온오르카) 기능 활용 코치. 사용자가 "orca로 뭘 할 수 있어?", "이 작업에 orca 기능 뭐 쓰면 좋을까?", "orca 활용 아이디어 줘", "지금 워크플로우 개선해줘 (orca 관점)"처럼 상황에 맞는 기능 추천을 원할 때 사용한다. |
| [`windows-parallels-lab`](skills/windows-parallels-lab/SKILL.md) | macOS Parallels Desktop 안의 자동화 전용 Windows 11 클론(win11-parlab)을 `prlctl exec` 로 제어해 Windows 실런타임 검증과 문서 렌더링 그라운드 트루스를 얻는다. macOS + Parallels Desktop 전용 로컬 운영 스킬. |
| [`windows-remote-lab`](skills/windows-remote-lab/SKILL.md) | 로컬 네트워크의 Windows 실머신을 SSH 로 원격 조작해 Windows 실런타임 검증·헤드리스 Office COM 자동화·파일 push/pull 을 세션 안에서 완결한다. 복원 수단이 없는 실사용 머신이라 안전 규율이 하드 제약인 로컬 운영 스킬. |

`link-skills.sh` 는 이 팩 스킬을 `~/.claude/skills/` 에 심볼릭 링크로 거는 개발 편의 스크립트입니다.

## 설치

```
/plugin marketplace add itda-work/skills.pub
/plugin install itda-dev@itda-skills-pub
```

스킬별 사전 준비(API 키·환경변수·Python 패키지)는 각 `SKILL.md` 의 Prerequisites 절에 있습니다.

## 개발

```bash
just test itda-dev          # 저장소 루트
just -f itda-dev/justfile test
```
