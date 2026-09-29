# itda-skills

[스킬.잇다](https://itda.work) 공식 스킬팩 저장소입니다.

Claude Code · Claude Cowork에서 대한민국 직장인·공공업무·투자자를 위한 스킬을 추가합니다.

## 설치

```
/plugin marketplace add itda-work/skills.pub
/plugin install itda-doc@itda-skills-pub   # 예시 — 팩 목록은 아래(마켓플레이스 이름은 itda-skills-pub)
```

예전 주소 `itda-skills/skills.pub` 로 등록해 두었다면 마켓플레이스 이름(`itda-skills-pub`)이 같으므로,
`/plugin marketplace remove itda-skills-pub` 로 먼저 지운 뒤 위 명령으로 새 주소를 등록하세요.

메일·일정 스킬(email·calendar)과 공공 데이터 스킬 dart·realty-deals 는 PC 에서 도는 **itda-hyve 0.9.0 이상**을 거쳐 네트워크에 나갑니다
(ecos 는 Cowork 처럼 네트워크가 막힌 환경에서만). 계정·API 키도 itda-hyve 에 등록합니다.
[내려받기·설치 안내](https://itda.work/hyve/)

공개 팩 9종(2026-09 재편 #1703 — 팩을 대상 명사 한 단어로 갈랐다): itda-doc · itda-data · itda-gov · itda-work · itda-research · itda-dev · itda-web · itda-travel · itda-org-mmaa. 정본은 `release-skills.yml` 의 `PLUGINS`(워크플로 파일이 진실 소스). 구 두 토막 이름(itda-content-create·itda-gov-collect·itda-work-coach 등)은 폐기됐고 별칭이 없다 — 스킬.잇다 웹은 구 팩 URL 을 301 로 넘긴다(website #199).

## 개발 저장소

본 저장소는 **published artifact**이며 소스/이슈/PR은 개발 저장소에서 관리합니다.

- Source: itda-work/skills (비공개 개발 저장소)
- Issues / PRs: 개발 저장소에서만 받습니다.

## 문의

- dev@itda.work

## 라이선스

각 플러그인 디렉토리의 `LICENSE` 또는 `CHANGELOG.md`를 참조하세요. (대부분 Apache-2.0)

Last Updated: 2026-09-26 (첫 공개 11.0.0 — 공개 저장소 `itda-work/skills.pub` 확정, itda-hyve 0.9.0 요구)
