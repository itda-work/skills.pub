# itda-web-reader

웹페이지 본문을 출처가 붙은 Markdown 으로, 목록 페이지·RSS 는 항목 레코드로 가져오는 정적 페이지 전용 스킬. 한국 웹사이트(EUC-KR/CP949)에 맞췄다.

> **v9.0.0 안내** (2026-10-11): 받기·리다이렉트·문자셋·본문 추출은 itda-hyve `web_read` 가 한다(itda-work/itda-hyve#72). 스킬에는 스크립트가 없다 —
> `plan.py`·`extract_content.py`·`extract_records.py`·`clean_html.py` 가 없어졌다. robots.txt 는 보지 않는다.
> JS 렌더·로그인·봇 차단 페이지는 브라우저 경로(`itda-web:aside-browser-mcp`)를 쓴다.

## 문서

- **사용 안내** (사용자용): [GUIDE.md](GUIDE.md) — 사전 준비(itda-hyve), 자주 쓰는 요청, 안 될 때
- **실행 계약** (런타임용): [SKILL.md](SKILL.md) — 판 확인(`server_features`), `web_read` 호출, 실패 코드, 보안
- **옛 판 전환**: [references/migration.md](references/migration.md) · **itda-hyve 규약**: [references/netbridge.md](references/netbridge.md)
- **변경 이력**: [CHANGELOG.md](CHANGELOG.md)

## 핵심 use case (v9.0.0)

1. **EUC-KR / CP949 한글 인코딩 페이지** — itda-hyve 가 Content-Type·meta·바이트로 판정해 UTF-8 로 푼다
2. **기사·문서 본문 → Markdown** — 자동 본문 탐지 또는 `selector`, 출처(최종 URL·홉·받은 시각·원문 해시)
3. **목록 페이지·RSS → 검증 가능한 항목 레코드** — `web_read` 의 `records: true`(itda-hyve#72 2단계, 기능 이름 `web_read_records`)

## License

Apache-2.0
