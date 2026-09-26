# morning-brief — 개발자 노트

사용자용 실행 계약은 `SKILL.md` 다. 이 문서는 **차용 출처와 갈라진 지점**을
기록한다(`upstream-fork-evidence-sync`).

## 차용 출처

| 항목 | 값 |
|---|---|
| 상류 | Claude 기본 스킬 `morning` |
| 상류 판 | **2026-09 판** (2026-09-03 마스터 제공본) |
| 원문 보존 | GitHub Issue itda-skills/hyve **#1638 첫 코멘트** (SKILL.md 전문) |
| 차용 범위 | Gather → Sort → Write → Build → Verify 흐름, 두 목록 구조, 지형 한 획 + 세 마디, Voice, Ground rules, 버튼 정확 문구 게이트와 seed 규율 |
| 복제 여부 | **없음** — 계약을 우리 문장(한국어 존댓말)으로 다시 썼다 |

상류는 **디자인 스킬**이라 `empirical-validation` 류 반증 기록이 없다. 즉 상류
규칙의 판별력이 대조 코퍼스로 측정된 적이 없으므로, 우리는 상류 규칙을 옮길 때
"무조건" 을 그대로 받지 않고 **코드가 집행할 수 있는 축만** 게이트로 올렸다
(`verify.py`). 나머지는 SKILL.md 의 문서 규율로 남긴다.

## 의도적 divergence

| # | 상류 | 우리 | 왜 |
|---|---|---|---|
| D1 | LLM 이 HTML 을 직접 그린다 | **결정론 3종**(`gather.py`·`render.py`·`verify.py`), LLM 은 Sort·문장만 | 이스케이프 누락·링크 스킴·요일 오기·버튼 인코딩이 매 회차 흔들린다. 공통 뿌리를 코드로 닫는다 |
| D2 | 커넥터 카탈로그(Google Calendar·Gmail·Slack·M365) | itda-work `calendar`·`email` 형제 스킬 subprocess | 한국 사용자의 네이버·아이클라우드·다음·CalDAV 에는 커넥터가 없다. 상류는 연결 제안 카드만 띄우고 끝난다 |
| D3 | 역할 4종(calendar·email·chat·other) | **2종**(calendar·email) | chat·task 소스가 우리에게 없다. 없는 역할을 이름만 남기지 않는다 |
| D4 | 미연결 역할에 커넥터 제안 카드 | 카드 없음, 조용히 skip | 우리에겐 제안할 커넥터가 없고, 카드는 브리핑이 아니다 |
| D5 | 버튼 게이트를 LLM 이 판정 | `gather --include-buttons` 가 `controls.buttons` 에 **고정**, render·verify 는 그 값만 본다 | 제3자 데이터를 읽은 뒤의 LLM 판단은 권위가 아니다. 후보를 읽기 전에 확정한다 |
| D6 | Fraunces woff2 를 base64 로 임베드 | **폰트 임베드 폐기**, 시스템 스택만 | 한글 헤드라인에 Fraunces 는 Latin 전용이라 무효다. Cowork 샌드박스에 Noto CJK 15 패밀리가 있고(실측), HTML 은 사용자 OS 에서 열린다 |
| D7 | playwright 스크린샷으로 Verify | **정적 검증이 정본**, 시각 축은 `INCONCLUSIVE` | Cowork 에 playwright·chromium·`/opt/pw-browsers` 가 없다(Phase 0 실측 확정). 상류 Build 의 렌더 체크 절은 통째로 미채택 |
| D8 | 팔레트 wash `#F9F9F7` / clay `#C6613F` | 먹·한지 톤(`#FBF8F1`·`#22201C`) + 단청 주홍 accent `#B3492D` | 한국 감성 개정. 골격(두 밴드·지형 한 획·목록 둘·640px)은 유지 |
| D9 | "오늘 마감"·"사라진 겹침"·비주최자 prep·spare 검색 | 없음 | 소스가 없거나(마감·회차 간 상태) 앵커가 약하다. 지어내느니 뺀다 |
| D10 | Sections 는 연결된 아무 도구나, **요청한 것만** | allowlist **2종**(날씨·환율), argv 확정. **날씨는 기본 적용**(`Sections: none` 으로 제외) | 교차 플러그인 자유 호출은 계약이 없다. 날씨는 아침에 가장 먼저 궁금한 것이라 매번 요청하게 두지 않는다(마스터 결정 2026-09-03 — v4 "Sections 없음=0" 반전). 시드·수집 실패 시엔 다른 데서 끌어오지 않고 경고만 남긴다 |
| D11 | 인용 축자 요구가 문서 규율 | `verify.py` 가 앵커 1:1 + 인용 **바이트 대조**로 집행 | "축자로 쓰라"는 지킬 수 없다 — 지켰는지 재는 것이 답이다 |
| D12 | 예약 작업을 스킬이 만든다 | **템플릿 제공까지** | 예약 자동 생성은 이 판의 범위 밖. 무인 판별 신호가 없어 프롬프트 명시가 유일 |
| D13 | RTL 지원 | 없음 | 한국어 전용 |
| D14 | 페이지 하단에 아무것도 두지 않는다(footer 금지) | 접이식 **「출처」 절** — 수집 요약(역할·프로바이더·계정 주소)·원본 목록·항목↔원본 링크·미표시 후보 표기 | 상류는 브리핑의 여백을 지키려 footer 를 금지하지만, 우리 데이터는 **연결된 커넥터가 아니라 사용자 개인 계정**에서 온다 — 무엇을 어느 계정에서 읽었고 무엇을 안 보여줬는지 말할 수 있어야 신뢰가 선다. 기본 닫힘이라 여백은 지켜지고, 공유 시엔 `--no-sources` 로 뺀다. candidates.json 만으로 코드가 만들어 LLM 무접촉 |
| D15 | 소스가 없으면 커넥터 제안 카드 | **샘플 모드** — 명시 요청(`샘플 브리핑`)에만 지어낸 시나리오로 같은 페이지를 그리고, 최상단 상시 띠·출처 계정란 「샘플 · 에이전트 생성 시나리오」·앵커 `provider:"sample"` 로 샘플임을 못 지우게 박는다 | 상류는 미연결 역할에 연결 제안 카드를 띄우지만 우리에겐 제안할 커넥터가 없다(D4). 그래도 "이 스킬이 뭘 주는지" 는 보여줄 수 있어야 도입 판단이 선다 — 카드 대신 **완성된 형식 한 장**으로 답한다. 계정 부재 시 자동 대체는 금지(no-silent-fallback): 계정 0 페이지는 안내 한 줄만 두고, 전환은 사용자의 명시 요청으로만 |

## 상류 반증 대조

| 회차 | 상류 리비전·판 | 대조한 것 | 결과 |
|---|---|---|---|
| 2026-09-03 | 2026-09 판(#1638 첫 코멘트) | 최초 차용 — 전 절 대조 | 위 D1~D13 으로 갈랐다. 상류에 반증 기록(empirical validation) **없음** |

상류가 개정되면 이 표에 줄을 더한다. **상류 문구가 우리와 다르다는 이유만으로
되돌리지 않는다** — divergence 표의 사유가 무너졌는지를 먼저 본다.

## 정정 이력

- **2026-09-03 · T1 실계약 반영(#1638)** — 초판 `gather.py` 는 세 곳이 계약과 달랐다.
  ① 에러 봉투 키를 `code` 로 알고 `status:"error"` 본문을 통과시켰다(실제 키는 `error`).
  ② `--account` 를 `default` 가 아닐 때만 붙였다 — 다계정에서 그 호출은 **exit 2** 다.
  ③ `thread_status` 의 `warnings` 를 전부 `severity: "warning"` 으로 접어
  `sent_folder_not_found`(회신 판정 전건 실패 → 후보 0)가 **조용한 빈 목록**이 됐다.
  ③ 때문에 `severity` 에 `degraded` 를 신설하고 render·verify 가 그것도 한 줄로
  말하게 했다. 되돌리지 마라 — 후보 0 과 "판정을 못 해 0" 은 다르다.

규칙을 강등·조건부화·삭제할 때는 여기에 **무엇이 왜 틀렸는지**를 남긴다.
조용히 고치면 다음 사람이 상류 원문을 보고 되돌린다.

## 동기화 절차

1. 상류 `morning` SKILL.md 의 현재 판을 구해 #1638 첫 코멘트의 보존본과 diff 한다.
2. 바뀐 절이 위 divergence 표의 어느 줄에 걸리는지 본다.
   - 걸리지 않는 새 규칙 → 우리 문장으로 채택 검토.
   - 걸리는데 상류가 근거를 새로 댔다면(반증·실측) → 우리 D 항목의 사유가 아직
     성립하는지 재확인하고, 무너졌으면 **정정 이력**과 함께 바꾼다.
3. 상류 판 날짜와 대조 결과를 위 **상류 반증 대조** 표에 한 줄 추가한다.
4. `verify.py` 가 집행하는 축을 바꿨다면 뮤테이션으로 RED 를 실측한다.

## 구조

```
scripts/gather.py    형제 스킬 subprocess(argv 배열) → candidates.json
scripts/render.py    content.json + candidates.json → 단일 파일 HTML
scripts/verify.py    ①~⑦ 정적 검증. exit 0/1, 판정 JSON
tests/               가짜 형제 스크립트 픽스처로만 돈다(네트워크·실계정 0)
tests/fixtures/golden/   종단 골든 3종(candidates·content·brief.html)
```

외부 의존 없음(stdlib only) — `requirements.txt`·`deps.json` 을 두지 않는다.

### 형제 스킬에 대한 전제

| 형제 | 스크립트 | 우리가 기대하는 것 |
|---|---|---|
| `calendar` | `check_env.py` | `{"providers":[{"provider","status","accounts":[{"account_id","login","status"}]}]}` |
| `calendar` | `list_events.py --provider --from --to --expand` | 이벤트 배열. `organizer` 필드는 #1638 T2 가 추가한다 |
| `email` | `check_env.py` | 위와 같은 형태(`email` 키) |
| `email` | `thread_status.py --provider --account <id> --days 2 --with-body 500 --limit 8` | `{"status","candidates":[{"anchor","from","subject","date","verdict","reason_code","body"}],"excluded","warnings":[{"code","detail"}]}` — #1638 T1 신설. 실패는 `{"status":"error","error":"<코드>"}`(키가 `error` 다), 다계정 `--account` 미지정은 **exit 2** — 그래서 `--account` 를 언제나 명시한다. `sent_folder_not_found` 경고는 회신 판정 전건 `unknown`(후보 0)을 뜻해 `degraded` 로 접는다 |
| `weather-here` | `weather_here.py [지역]` | **평문**(JSON 아님) |
| `exchange-rate` | `exchange_rate.py --currency USD --date YYYY-MM-DD` | **평문**. `--date`/`--month` 중 하나가 필수라 gather 가 오늘 날짜를 넣는다 |

형제 계약이 바뀌면 `tests/fixtures/fake_skills/` 의 가짜 스크립트를 먼저 고쳐
RED 를 확인한 뒤 `gather.py` 를 고친다.
