# Changelog — markdown-doc

## [0.1.0] — 2026-10-14 (itda-work/skills#53)

### Added

- 첫 판. itda-hyve 문서 창의 md 문서를 쓰고 고친다 — 문법은 지금 설치된 앱에서 받고(`md_syntax`·`itda-hyve md --syntax`), 쓴 뒤 같은 렌더러로 검사해(`md_check`·`--check`) 경고 0, 새 문서는 처음 한 번 `md_preview`. "Claude 에게 고쳐 달라기" 요청 글은 대상 줄 범위만 고친다(itda-work/itda-hyve#135).
- 동봉 사본: 앱이 없을 때만 쓰는 문법 사본 `references/syntax-fallback.md`(itda-hyve 0.17.2, syntax_hash `daec08f11fe4`), 문서 꼴 서식 `references/doc-forms.md`(문서 창 "새 문서" 서식 6종), 공용 규약 `references/netbridge.md`. 사본은 저장소의 `scripts/update_markdown_doc_refs.py` 로만 다시 만든다(배포본에 싣지 않는다).
