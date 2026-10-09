# itda-web-reader

웹페이지를 깔끔한 Markdown·JSON, 또는 목록 페이지의 행 단위 레코드로 바꾸는 정적 페이지 전용 스킬. 한국 웹사이트(EUC-KR/CP949)에 최적화.

> **v8.0.0 안내** (2026-10-01): 요청은 itda-hyve(`http_request`)가 보내고 스크립트는 저장된 파일만 읽는다. `plan.py` 가 robots.txt → 페이지를
> 한 걸음씩(리다이렉트는 한 홉씩, 목적지 검사) 계획한다. curl_cffi 지문·WAF 격자·`--cookie`·`diagnose_url.py` 는 없어졌다.
> JS 렌더·로그인·봇 차단·robots 불허 페이지는 브라우저 경로(`itda-web:aside-browser-mcp`)를 쓴다.

## 문서

- **사용 안내** (사용자용): [GUIDE.md](GUIDE.md) — 사전 준비(itda-hyve), 자주 쓰는 요청, 안 될 때
- **실행 계약** (런타임용): [SKILL.md](SKILL.md) — 흐름(plan → itda-hyve → 추출), 멈춤·exit code, 보안
- **옛 판 전환**: [references/migration.md](references/migration.md) · **itda-hyve 규약**: [references/netbridge.md](references/netbridge.md)
- **변경 이력**: [CHANGELOG.md](CHANGELOG.md)

## 핵심 use case (v8.0.0)

1. **EUC-KR / CP949 한글 인코딩 페이지 디코딩** — Content-Type·meta·바이트로 코덱 판정
2. **기사·문서 본문 → Markdown/JSON** — 자동 본문 탐지 또는 `--selector`
3. **목록 페이지·RSS → 검증 가능한 행 레코드** — 출처 URL + 원문 발췌(부분문자열 검증)

## License

Apache-2.0
