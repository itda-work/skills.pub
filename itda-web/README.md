# itda-web

웹 수집 스킬팩 — 다중 엔진 검색 → 정적 fetch(EUC-KR·WAF 폴백) → 정보원 정찰 → 브라우저 자동화 순 사다리로, 가장 싼 경로부터 웹 정보를 가져온다.

> 2026-09-05 재정비(#1648)로 구 `itda-work` 의 web-search·web-reader·web-scout·blog-reader 가 이 팩으로 왔습니다. `itda-research`(ground-check·market-scan)가 이 팩의 web-reader·web-search 를 폴백·수집 엔진으로 쓰므로 함께 설치하는 것을 권합니다.
>
> 로그인·JS 렌더가 필요한 페이지는 `aside-browser-mcp`(Aside 브라우저)로 가져옵니다. hyve 앱 전제였던 `web-automation` 은 2026-09-25 저장소 이관 때 빠졌습니다.

## 포함 스킬

| 스킬 | 기능 |
|---|---|
| [`blog-reader`](skills/blog-reader/SKILL.md) | 네이버 블로그의 글 목록·본문·댓글 트리·블로그 내 검색·전역 키워드 검색을 로그인 없이 읽는 스킬입니다. |
| [`web-reader`](skills/web-reader/SKILL.md) | WebFetch가 못 다루는 한국 웹페이지(EUC-KR/CP949·쿠키 인증·WAF 차단 정적 페이지)를 마크다운·JSON으로 가져오는 폴백 스킬입니다. |
| [`web-scout`](skills/web-scout/SKILL.md) | 정보원 정찰 스킬 — "이 정보가 어느 사이트 어디에 있고 어떻게 꺼내야 싸게 되는가"를 실측해 기억합니다. |
| [`web-search`](skills/web-search/SKILL.md) | 여러 검색엔진으로 웹을 한 번에 검색해 정규화된 결과 목록(제목·URL·발췌)을 돌려주는 스킬입니다. |

## 설치

```
/plugin marketplace add itda-work/skills.pub
/plugin install itda-web@itda-skills-pub
```

## 사전 준비

스킬별 API 키·환경변수·계정 설정·Python 패키지는 각 스킬의 `SKILL.md` Prerequisites 절과 `GUIDE.md` 에 있습니다. 여러 스킬이 같은 키를 쓰면 작업 폴더 `.env` 한 곳에 두면 됩니다.

## 개발

```bash
just test itda-web          # 저장소 루트
just -f itda-web/justfile test
```
