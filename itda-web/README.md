# itda-web

웹 수집 스킬팩 — 다중 엔진 검색 → 브라우저(Aside) 순 사다리로, 가장 싼 경로부터 웹 정보를 가져온다. 정적 페이지 추출(EUC-KR, robots 준수 — web-reader)은 v14.1 에 다시 싣는다.

> 2026-09-05 재정비(#1648)로 구 `itda-work` 의 web-search·web-reader·web-scout·blog-reader 가 이 팩으로 왔습니다(2026-10-01 web-scout 제외 — 여러 사이트를 훑는 정찰이 사이트별 robots 판정·호출 최소화 원칙과 부딪친다. blog-reader 제거 — 네이버 블로그 robots 가 목록·댓글·전체 검색을 막는다, 네이버 블로그는 Aside 브라우저 `itda-web:aside-browser-mcp` 로 연다). `itda-research`(ground-check·market-scan)가 이 팩의 web-search 를 수집 엔진으로(v14.1 부터는 web-reader 를 폴백으로도) 쓰므로 함께 설치하는 것을 권합니다.
>
> 로그인·JS 렌더가 필요한 페이지는 `aside-browser-mcp`(Aside 브라우저)로 가져옵니다. hyve 앱 전제였던 브라우저 자동화 규율 스킬은 2026-09-25 저장소 이관 때 빠졌습니다.

## 포함 스킬

| 스킬 | 기능 |
|---|---|
| [`web-reader`](skills/web-reader/SKILL.md) | **배포 보류 — v14.0.0 공개 배포본에는 없고 v14.1 에 다시 싣는다**(itda-hyve 가 사설·내부망 주소를 기본으로 막는 기능이 들어온 뒤). WebFetch가 못 다루는 한국 웹페이지(EUC-KR/CP949 등 정적 페이지)를 마크다운·JSON·목록 레코드로 가져오는 폴백 스킬입니다. |
| [`web-search`](skills/web-search/SKILL.md) | 여러 검색엔진으로 웹을 한 번에 검색해 정규화된 결과 목록(제목·URL·발췌)을 돌려주는 스킬입니다. |

## 설치

```
/plugin marketplace add itda-work/skills.pub
/plugin install itda-web@itda-skills-pub
```

## 사전 준비

스킬별 API 키·환경변수·계정 설정·Python 패키지는 각 스킬의 `SKILL.md` Prerequisites 절과 `GUIDE.md` 에 있습니다. 여러 스킬이 같은 키를 쓰면 환경변수 하나로 함께 쓰입니다 — 스킬은 `.env` 같은 파일을 읽지 않습니다(itda-work/skills#45).

## 개발

```bash
just test itda-web          # 저장소 루트
just -f itda-web/justfile test
```
