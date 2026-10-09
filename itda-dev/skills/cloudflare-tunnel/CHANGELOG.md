# Changelog — itda-dev/cloudflare-tunnel

이 스킬의 변경 이력입니다. [Keep a Changelog](https://keepachangelog.com) 포맷을 따릅니다. 0.2.0 까지의 이력은 팩 CHANGELOG(`itda-dev/CHANGELOG.md`)에 있습니다.

## [0.3.0] — 2026-10-03 (itda-work/skills#46 W17)

### Removed

- **Cloudflare API 토큰의 환경변수 폴백 안내를 없앴다** (사용자 결정 2026-10-03 — 키를 프로세스 환경변수로 받는 경로를 모두 없앤다). 셸 환경변수 `CLOUDFLARE_API_TOKEN`·Claude Code 설정의 `env`(GUIDE 의 json 블록 포함) 안내를 지우고, 보관처를 OS 보안 저장소 한 곳으로 적었다. 스크립트 `tunnel_policy.py` 는 원래 토큰을 읽지 않으므로 동작은 그대로다 — DNS 라우트는 `cloudflared tunnel login`, Access 앱은 Zero Trust 대시보드가 기본 경로이고 토큰은 Access 앱을 API 로 만들 때만 쓴다.

### Changed

- SKILL.md 「환경 변수」 표를 「자격증명」 표로 바꿨다(계정 ID 는 비밀이 아님을 적었다). GUIDE.md 의 토큰 발급 단계를 "필요할 때만" 으로 고쳤다.
