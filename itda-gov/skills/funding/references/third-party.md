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
| `scripts/kstartup_crawl.py` | `scripts/kstartup_crawl.py` | 3.0.0: 네트워크·수집 루프·병합을 걷어내고 판독기(목록 파서·본문 추출·첨부 링크·robots 상수)만 남김. 레코드에 `source`/`id`/`apply_start`/`apply_end` 별칭 |
| `scripts/sources_crawl.py` | `scripts/sources_crawl.py` | 3.0.0: 네트워크·수집 루프·상세 명령을 걷어내고 상세 판독기(본문·첨부 링크)와 소스별 호스트·robots 상수만 남김. bizinfo 첨부 이름을 링크 title 에서 읽고, KOCCA 팝업을 `kocca_popup_refs`·`parse_kocca_popup` 으로 나눔 |
| `scripts/listing.py` | `scripts/sources_crawl.py`(`page_*`·`crawl`) | 3.0.0 신설: 목록 행 파서를 행 번호·현재 쪽·마지막 쪽까지 읽게 개작하고, 수집 루프를 분모 기반 전량 대조·다음 계획으로 바꿈. SMTECH 식별자 `ancmId-dtlAncmSn`·IRIS 행 |
| `scripts/detailing.py` | `scripts/sources_crawl.py`·`kstartup_crawl.py`(`cmd_detail`·`collect_detail`·`merge_detail`) | 3.0.0 신설: 상세·첨부를 계획/판정 두 단계로 나누고 첨부를 바이트로 검사. hash v2/v3·병합 계약 승계 |
| `scripts/attach_download.py` | `scripts/attach_download.py` | 3.0.0: 다운로드·리다이렉트 추종·파일명 복구를 걷어내고 robots·호스트 검사, 해시 산식, 받은 첨부 검사(`verify_attachment`)만 남김 |
| `scripts/run_manifest.py` | `scripts/run_manifest.py` | 로그 태그 교체. 3.0.0: `inactive` 는 exit 0, run 에 `coverage`·`last_page`·`counted`·`dropped` |
| `scripts/survey_diff.py` | `scripts/diff_surveys.py` | (T2 소유) 프로필 fingerprint·해시 버전 전환·GONE 억제 계약 개작. 3.0.0: `coverage=window` 억제·SMTECH 옛 id 이행 |
| `references/sources.md` | `references/sources.md` | 소스 레지스트리 승계 + robots 실측 표에 재확인 일자 병기(2026-09-30 itda-hyve 실측) |
| `references/diff_record_schema.json` | 동명 파일 | (T2 소유) |

2.x 의 `scripts/kstartup_api.py`(공공데이터포털 API 클라이언트, 원본 동명 파일)는 3.0.0 에서 지웠다.

전 파일 공통: 로그 태그 `[ir-search]` → `[funding]`.

**약화하지 않은 것** — 호스트 화이트리스트(정확 호스트 `=` 접두), robots 불허 경로 사전 차단(인코딩 위장 방어 포함),
sha256·hash v2/v3, fail-closed 종료코드(0/2/3) 계약. 3.0.0 에서 요청이 itda-hyve 로 옮겨 가며 바뀐 것: 리다이렉트는
홉 검사 대신 **따라가지 않는다**(`follow_redirects:false` — 3xx 는 실패), 첨부 상한은 itda-hyve 저장 상한 50MiB,
경로 탈출·심볼릭 링크 방어는 itda-hyve `save_as` 규칙(상대 경로·숨김 이름 거부)이 맡는다. API 키 경로는 없어졌다.

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
