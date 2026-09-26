# 제3자 코드 고지 (Third-party notices)

`funding` 스킬 자체의 라이선스는 SKILL.md frontmatter 의 `license: Apache-2.0` 이다.
아래 파일들은 **ir-search 프로젝트(MIT)에서 차용해 개작**한 것이며, 그 부분에 한해
MIT 라이선스가 함께 적용된다(NOTICE 방식 병기). 각 파일 상단에도 동일한 출처
고지 주석이 있다.

---

## 출처

- 프로젝트: **ir-search**
- 저장소: https://github.com/djfksjd/ir-search
- 라이선스: MIT
- 차용 시점: 2026-07-28 (#1320)

## 차용 파일과 개작 요지

| 파일 | 원본 | 개작 요지 |
|---|---|---|
| `scripts/kstartup_crawl.py` | `scripts/kstartup_crawl.py` | 모듈화 — `cmd_list` 을 `collect_list()` 로 분해해 `sys.exit` 대신 `(records, run, code)` 반환(`list all` 통합용). 레코드에 `source`/`id`/`apply_start`/`apply_end` 별칭 추가. `cmd_detail`→`collect_detail()`(코드 반환, URL 입력 허용). `main()` 제거 — 진입점은 `survey_crawl.py` |
| `scripts/sources_crawl.py` | `scripts/sources_crawl.py` | 모듈화 — `main()` 의 소스 루프를 `collect_sources()` 로 분해(파일 기록·종료코드는 호출자 소유). `cmd_detail` 이 `sys.exit` 대신 코드 반환. `main()` 제거 |
| `scripts/kstartup_api.py` | `scripts/kstartup_api.py` | 서비스 키 탐색을 `DATA_GO_KR_KEY` + `~/.config/*` 자체 체계에서 **`KO_DATA_API_KEY` + `shared/env_loader.py`** 규약으로 교체(`load_key()` 전면 재작성, 지역 import·미가용 시 stderr 고지) |
| `scripts/attach_download.py` | `scripts/attach_download.py` | `notify_backend()` 추가 — curl_cffi 미설치 폴백을 stderr 로 1회 명시 고지(no-silent-fallback). 그 외 보안 계약 무변경 |
| `scripts/run_manifest.py` | `scripts/run_manifest.py` | 로그 태그만 교체 (schema v1 계약 무변경) |
| `scripts/survey_diff.py` | `scripts/diff_surveys.py` | (T2 소유) 프로필 fingerprint·해시 버전 전환·GONE 억제 계약 개작 |
| `references/sources.md` | `references/sources.md` | 소스 레지스트리 승계 + robots 실측 표에 재확인 일자(2026-07-28) 병기 |
| `references/diff_record_schema.json` | 동명 파일 | (T2 소유) |

전 파일 공통: 로그 태그 `[ir-search]` → `[funding]`.

**약화하지 않은 것** — 리다이렉트 홉별 사전 검증, 호스트 화이트리스트(정확 호스트
`=` 접두), robots 불허 경로 사전 차단(인코딩 위장 방어 포함), 첨부 50MB 스트리밍
상한, sha256, 공고별 하위 폴더, 경로 탈출·심볼릭 링크 차단, API 키 마스킹,
fail-closed 종료코드(0/2/3) 계약.

---

## MIT License (ir-search)

```
MIT License

Copyright (c) 2026 ir-search contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
