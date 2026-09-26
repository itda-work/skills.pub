# itda-web-reader

웹페이지와 YouTube 자막을 가져와 깔끔한 Markdown 또는 JSON으로 변환하는 정적 페치 전용 스킬. 한국 웹사이트(EUC-KR/CP949)에 최적화.

> **v3.0.0 안내** (2026-05-11): 동적 fetch(Playwright/Chromium)와 SPA 어댑터(naver-land 등)는 제거되었습니다. JS 렌더·SPA(네이버 부동산 등)는 브라우저 경로(`itda-web:aside-browser-mcp`)를 씁니다. v2.x 호출 패턴은 exit code 4 + stderr에 마이그레이션 안내 메시지를 출력합니다.

## 문서

- **사용 안내** (사용자용): [GUIDE.md](GUIDE.md) — 빠른 시작, 활용 시나리오, 출력 옵션, JS 페이지 처리, **v2 → v3 마이그레이션 안내**
- **CLI 레퍼런스** (개발자용): [SKILL.md](SKILL.md) — frontmatter, Prerequisites, Script Reference, Troubleshooting, 보안 정책
- **변경 이력**: [CHANGELOG.md](CHANGELOG.md)
- **구현 기준**: `SKILL.md`, `GUIDE.md`, `scripts/`, `tests/`, `CHANGELOG.md`

## 핵심 use case (v3.0.0)

이 스킬은 다음 3가지 정적 페치 use case 전용입니다:

1. **EUC-KR / CP949 한글 인코딩 페이지 디코딩** — `fetch_html.py --url URL`
2. **YouTube 자막(transcript/caption) 추출** — `fetch_youtube.py --url URL`
3. **쿠키 인증이 필요한 정적 페이지** — `fetch_html.py --url URL --cookie "..."`

JavaScript 렌더링이 필요한 SPA / 안티봇 사이트 / 멀티스텝 자동화 / 네이버 부동산은 모두 브라우저 경로(`itda-web:aside-browser-mcp`)로 위임됩니다. 자세한 마이그레이션 경로는 [GUIDE.md](GUIDE.md)의 "마이그레이션 안내 (v2 → v3)" 섹션을 참조하세요.

## License

Apache-2.0
