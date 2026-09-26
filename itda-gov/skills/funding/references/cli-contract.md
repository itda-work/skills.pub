# funding CLI 계약 (v1.0.0)

이 문서는 `funding` 스킬의 스크립트 표면을 **선고정**한다. SKILL.md·GUIDE·테스트·문서는
전부 이 파일을 단일 참조로 삼는다 — 여기 없는 인자·exit code·필드를 다른 문서가 주장하면
그쪽이 틀린 것이다.

- 대상 스크립트: `scripts/survey_crawl.py`(수집), `scripts/survey_diff.py`(회차 비교)
- 모든 진단·경고·요약은 **stderr**, prefix `[funding]`. stdout 은 산출물 전용(diff 의 보고서 등).
- 수집 산출물은 **파일**(jsonl · `run_manifest.json` · 상세 txt · 첨부)로 남고, stdout 으로 흘리지 않는다.

---

## 1. `survey_crawl.py list` — 목록 전수 수집

```
python3 "$SKILL_DIR/scripts/survey_crawl.py" list <source> [옵션]
```

| 인자 | 값 | 설명 |
|---|---|---|
| `source` | `kstartup` \| `bizinfo` \| `nipa` \| `kocca` \| `smtech` \| `all` | 수집 소스. `all` = 5종 전부 |
| `-o`, `--output` | 경로 (기본 `survey.jsonl`) | jsonl 산출 경로. `run_manifest.json` 은 **같은 폴더**에 쓰인다 |
| `--max-pages` | 정수 (기본 `40`) | 소스당 페이지 상한. 상한 도달 시 partial 판정(아래 exit 계약) |
| `--min-expected` | 정수 (기본 `50`, kstartup 만 적용) | 이 건수 미만이면 partial. `0` 이면 검사 해제 |
| `--smoke` | 플래그 | 저부하 스모크. **coverage 검증(page-cap·min-expected)만** 완화한다. 1페이지 파싱 0건·네트워크 오류·차단은 **그대로 실패** — 계약 회귀를 잡는 canary 라서 완화하지 않는다 |

- 요청 간 지연은 코드 상수(K-Startup 0.3s / 기타 0.4s)로 고정 — 옵션으로 낮출 수 없다.
- `all` 은 5종을 순차 수집해 **하나의 jsonl** 에 이어 쓰고, `run_manifest.json` 에 **소스당 1 run** 을 기록한다.
- 한 소스가 실패해도 나머지는 계속 수집한다. 실패 소스가 수집한 부분 데이터도 파일에 **보존**된다.
- **총 수집이 0건이면 jsonl 을 쓰지 않는다** — 파싱 실패·차단으로 빈 파일을 덮어쓰면 직전 회차
  데이터가 사라지고 다음 diff 가 전 공고를 GONE 으로 오판한다. 매니페스트는 그래도 기록된다.

### K-Startup API 우선 경로

`KO_DATA_API_KEY` 가 해석되면 K-Startup 은 공공데이터포털 오픈 API(데이터셋 15125364)를 먼저 쓰고,
실패하면 **공개 페이지 크롤로 폴백한다(stderr 에 사유를 명시 고지 — 조용한 폴백 아님)**.
크롤이 전수 커버리지의 보증 경로이고 API 는 최적화다.

- API 가 totalCount 로 소진을 **증명**하면 `stop_reason: "api"` + exit 0.
- 증명 없이 최신순 휴리스틱으로 멈추면 `stop_reason: "api-window"` + **exit 2(partial)** — 최근 구간
  커버리지일 뿐이므로 diff 가 이를 근거로 GONE 을 결론내지 못하게 한다.
- 키가 없으면 곧바로 크롤 경로(고지 없음 — 정상 기본 경로).

---

## 2. `survey_crawl.py detail` — 상세 본문·첨부 수집

```
python3 "$SKILL_DIR/scripts/survey_crawl.py" detail <source> <id|url> [<id|url> ...] [옵션]
```

| 인자 | 값 | 설명 |
|---|---|---|
| `source` | `kstartup` \| `bizinfo` \| `nipa` \| `kocca` \| `smtech` | 대상 소스 |
| `id\|url` | 1개 이상 | `kstartup` 은 공고번호(`pbancSn`, 숫자) 또는 상세 URL, 나머지는 **jsonl 의 `url` 을 그대로** 넘긴다(쿼리 파라미터가 빠지면 리다이렉트된다) |
| `-o`, `--output` | 폴더 (기본 `details`) | 상세 텍스트 저장 폴더 |
| `--download-dir` | 폴더 | 첨부 다운로드 폴더. 공고별 하위 폴더에 저장 |
| `--merge-into` | jsonl 경로 | 목록 jsonl 레코드에 `content_hash`·`hash_version`·`attachments`·`attachments_complete` 병합(원자적 교체) |

첨부 계약은 `references/sources.md` 의 소스별 robots 실측 표를 따른다. robots 불허 경로·계약
미확정 경로는 **다운로드하지 않고 링크만** 기록한다(우회 금지).

---

## 3. exit 계약 (fail-closed)

| code | 의미 | 발생 조건 |
|---|---|---|
| **0** | 전수 성공 | 요청한 모든 소스가 소진까지 수집(또는 detail 전건 성공). 첨부까지 전부 성공 |
| **2** | partial — 커버리지 불완전 | 아래 분기 중 하나 이상 |
| **3** | 차단 — 수동 전환 | 401/403 응답, 또는 200 위장 CAPTCHA·접근거부 본문 감지 |

**exit 2 의 분기** (`run_manifest.json` 의 `stop_reason`·`errors` 로 구분):

| 분기 | stop_reason | 설명 |
|---|---|---|
| 네트워크 오류 | `network-error`, `error` | 크롤 도중 전송 실패. 그때까지의 데이터는 저장됨 |
| HTTP 오류 | `http-<코드>` | 403/412 등 비-차단 실패 상태 |
| 페이지 캡 | `page-cap` | `--max-pages` 도달 시점에 마지막 페이지에 신규 항목이 남아 있었음 |
| 파싱 실패 | `parse-failure` | 1페이지가 0건 파싱 — 사이트 개편 의심 |
| 소스 일부 실패 | (소스별) | `all` 에서 일부 소스만 실패 — 성공 소스 데이터는 보존 |
| 최소 기대치 미달 | (그대로) | K-Startup 수집량이 `--min-expected` 미만 |
| API 최근구간 | `api-window` | API 가 소진을 증명하지 못하고 휴리스틱으로 정지 |
| 첨부 불완전 | — (detail) | 첨부 1건 이상이 실패·robots 생략·계약 미확정. 본문 v2 해시 유지 + `attachments_complete:false` |
| 소스 판별 불가 | — (detail) | URL 이 4개 소스(정확한 호스트)로 판별되지 않음. 적용할 robots·호스트 정책이 없으므로 **요청조차 하지 않고** FAIL — 전체 허용 fetcher 로 폴백하지 않는다 |
| 병합 id 추출 불가 | — (detail) | `--merge-into` 인데 URL 에서 공고 id 를 못 뽑아 병합 대상 레코드를 특정할 수 없음. 조용히 건너뛰지 않고 FAIL(요청된 기능 미수행 = 실패) |

**호출자 규율**: exit 2 를 성공으로 취급하지 않는다. 보고서에는 반드시 커버리지 한계를 고지한다.
exit 3 은 우회 시도 금지 — 사용자에게 수동 확인을 안내한다.

---

## 4. jsonl 레코드 스키마

한 줄 = 공고 1건(JSON). 소스에 따라 두 형태가 공존하며 `survey_diff.py` 가 양쪽을 정규화한다.

### 공통 (bizinfo · nipa · kocca · smtech)

| 필드 | 설명 |
|---|---|
| `source` | 소스 이름 |
| `id` | 소스 내 공고 식별자 (`PBLN_…`·숫자·`intcNo`·`ancmId`) |
| `title` | 공고명 |
| `field` | 지원분야·카테고리 |
| `org` | 소관부처/수행기관 |
| `apply_start`, `apply_end` | 신청 시작·마감 (`YYYY-MM-DD`, 파싱 불가 시 원문) |
| `reg_date` | 등록·공고일 |
| `url` | 상세 페이지 URL (detail 에 그대로 넘길 것) |

### K-Startup

| 필드 | 설명 |
|---|---|
| `pbancSn` | 공고번호 (원본 키) |
| `source`, `id` | `"kstartup"`, `pbancSn` 과 동일 값 (교차 소스 비교용 별칭) |
| `category`, `dday`, `title`, `program`, `org`, `agency_type` | 목록 표시 필드 |
| `start`, `deadline` | 신청 시작·마감 |
| `apply_start`, `apply_end` | `start`·`deadline` 의 별칭 (비교 필드 통일용) |
| `url` | 상세 페이지 URL |

### `detail --merge-into` 로 추가되는 필드

| 필드 | 설명 |
|---|---|
| `content_hash` | 본문(v2) 또는 본문+첨부(v3) sha256 |
| `hash_version` | `2` = 본문만, `3` = 본문 + 정렬된 첨부 sha256. **첨부 전건 성공일 때만 3** |
| `attachments` | `[{url, filename, download_status, download_reason?, sha256?, local_path?}]` |
| `attachments_complete` | 전 첨부 다운로드 성공 여부 |

`download_status` 값: `ok` · `failed` · `blocked_redirect` · `skipped_robots` · `skipped_unverified`.

---

## 5. `run_manifest.json` (schema v1)

목록 수집 시 jsonl 과 **같은 폴더**에 원자적으로 쓰인다. 커버리지 판정은 stderr 요약이 아니라
이 파일을 읽는다. 같은 소스의 기존 run 은 새 run 으로 교체된다. 다른 소스 run 은 **그 소스의
데이터가 방금 쓴 jsonl 에 실재할 때만** 보존된다 — `list` 는 jsonl 을 통째로 덮어쓰므로,
부분 재수집(`list bizinfo` 단독) 후에도 사라진 소스의 `status=ok` run 이 남으면 커버리지가
거짓이 된다. 잔존 run 은 제거하고 stderr 에 고지한다. **수집 0건이라 jsonl 을 쓰지 않은 런은
대조하지 않는다**(직전 파일이 그대로 살아 있으므로).

```json
{
  "manifest_schema_version": 1,
  "generated_at": "2026-07-28T14:03:00+09:00",
  "runs": [
    {
      "source": "kstartup",
      "status": "ok",
      "exit_code": 0,
      "pages_fetched": 18,
      "collected": 271,
      "reported_total": 271,
      "duplicates": 12,
      "stop_reason": "no-new-2pages",
      "cutoff": null,
      "errors": []
    }
  ]
}
```

- `status` ∈ `ok` · `partial` · `manual` · `inactive`. `status=ok` ⟺ `exit_code=0` (모순 시 작성 거부).
- **개인정보·검색어·공고 본문은 절대 들어가지 않는다** — 카운트·상태·사유만.
- 손상되거나 스키마 버전이 다른 매니페스트는 조용히 덮어쓰지 않고 `run_manifest.json.corrupt-<ts>`
  로 보존한 뒤 새로 시작하며, 새 매니페스트에 `recovered_from_corrupt` 를 남긴다.

---

## 6. `survey_diff.py` — 회차 비교 (T2 구현, 인자 계약 고정)

```
python3 "$SKILL_DIR/scripts/survey_diff.py" <old_dir> <new_dir> [옵션]
```

| 인자 | 설명 |
|---|---|
| `old_dir`, `new_dir` | 비교할 두 회차 폴더 (각각 `*.jsonl` + `run_manifest.json` 보유) |
| `--out` | 결과 JSON 산출 경로 (미지정 시 stdout 요약만) |
| `--old-profile`, `--new-profile` | 프로필 파일 경로. fingerprint 가 다르면 이전 회차의 판정 승계를 무효화한다 |
| `--assume-complete` | 현재 회차를 전수로 간주(매니페스트 없이 비교할 때) — 남용 시 GONE 오판 위험 |

GONE(소멸) 레코드는 `--out` 파일이 아니라 같은 폴더의 `gone_<out 파일명>`(예: `--out new_items.jsonl` → `gone_new_items.jsonl`)에 분리 기록된다.

분류: `new` · `changed` · `gone` · `needs_rehash` · `unchanged`. 비교 필드는
`title` · `apply_start` · `apply_end` · `status` · `content_hash`.
**GONE 은 현재 회차가 그 소스를 전수 커버(`status=ok`·`exit_code=0`)했을 때만** 판정한다 —
partial 회차에서 사라진 것처럼 보이는 항목은 억제된다.

---

## 7. 환경·의존

| 항목 | 계약 |
|---|---|
| API 키 | `KO_DATA_API_KEY` — `shared/env_loader.py` 규약으로 해석(CLI 인자 > `os.environ` > `~/.claude/settings.json` > `.env` 계열). **없어도 크롤 경로로 동작한다** |
| 키 노출 | 로그·에러·URL 어디에도 출력하지 않는다. 인코딩 변형(`quote`/`quote_plus`/`unquote`, 대소문자 `%XX`)까지 `<KEY>` 로 마스킹 |
| `curl_cffi` | 권장(`requirements.txt`, `>=0.15`). **미설치 시 urllib 경로로 동작하되 stderr 에 1회 명시 고지**한다 — 조용한 폴백이 아니다 |
| Python | 3.10+ |
