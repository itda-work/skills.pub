# itda-gov: 공공 정보 수집 스킬팩

> 2026-09-05 재정비(#1648): 구 `itda-gov` 를 개명하고 공공기관 게시판·통계(구 itda-class-igm 의 bai-notice·customs-notice·fss-docs·airport-airline-stats)와 국세법령정보 `taxlaw`(구 itda-tax) 를 편입했습니다.

한국 정부 공공데이터 API를 활용한 Claude Cowork 스킬 모음입니다.
전자공시, 국가통계, 경제지표, 부동산 실거래가, 정부 지원사업, 나라장터 입찰공고를 조회합니다.

> **공지 (v3.0.0)**: `law-korean` 스킬은 v3.0.0에서 제거되었습니다. 한국 법령 조회는 [korean-law MCP](https://github.com/lhandal/korean-law-mcp)를 사용해 주세요.

## 시작 전: API 키/OC 먼저 발급하세요

itda-gov 의 API 계열 스킬은 **사전 API 키(또는 OC) 발급이 필요**합니다. 먼저 아래 발급처에서 키를 받습니다. 스킬은 `.env` 같은 파일을 읽지 않습니다(itda-work/skills#45). `dart`·`ecos`·`g2b`·`kosis`·`realty-deals`·`realty-jeonse-gap`·`realty-price-stats`·`realty-supply`·`fuel-price` 는 itda-hyve 시크릿 탭에 등록한 키만 씁니다(스크립트는 네트워크를 쓰지 않고 `--input` 가공만 — itda-work/skills#46). `funding` 은 키가 필요 없습니다(3.0.0 — 공개 공고 페이지를 itda-hyve 로 받습니다).

| 환경변수 | 발급처 | 용도 |
|---------|-------|------|
| `DART_API_KEY` | https://opendart.fss.or.kr | 기업 재무/직원(dart — itda-hyve 시크릿 탭) |
| `KOSIS_API_KEY` | https://kosis.kr/openapi/ | 국가 통계(kosis·realty-supply — itda-hyve 시크릿 탭) |
| `ECOS_API_KEY` | https://ecos.bok.or.kr/api/ | 경제 지표(ecos — itda-hyve 시크릿 탭) |
| `RONE_API_KEY` | https://www.reb.or.kr/r-one/ (Open API → 인증키 발급) | 부동산 가격지수(realty-price-stats — itda-hyve 시크릿 탭) |
| `KO_DATA_API_KEY` | https://www.data.go.kr | 실거래가, 나라장터, 청약 분양정보(realty-supply — 15098547 별도 활용신청, itda-hyve 0.10.4 전에 등록한 키는 허용 호스트에 `api.odcloud.kr` 추가), **주식시세(15094808 별도 활용신청 필요)** |
| `OPINET_API_KEY` (선택) | https://www.opinet.co.kr/user/custapi/custApiInfo.do 「일반 API 이용 신청」 | 유가 — **기본 경로는 키 불요**(fuel-price — 선택 API 경로만 itda-hyve 시크릿 탭) |

| 키를 넣는 곳 | 쓰는 스킬 |
|---|---|
| itda-hyve GUI 시크릿 탭(Cowork 등 — `http_request` 의 `{{secret:NAME}}`) | `dart`(`DART_API_KEY`)·`ecos`(`ECOS_API_KEY`)·`g2b`·`realty-deals`·`realty-jeonse-gap`(`KO_DATA_API_KEY`)·`kosis`(`KOSIS_API_KEY`)·`realty-supply`(`KOSIS_API_KEY`·`KO_DATA_API_KEY`)·`realty-price-stats`(`RONE_API_KEY`·`KO_DATA_API_KEY`)·`fuel-price`(`OPINET_API_KEY`, 선택) — 이 경로만, 스크립트는 `--input` 가공만 |

> **주의**
> - `KO_DATA_API_KEY`는 공공데이터포털(data.go.kr) 키 하나로 `g2b`·`realty-*`(itda-hyve 시크릿 탭)에서 함께 사용합니다. `funding` 은 3.0.0 부터 이 키를 쓰지 않습니다.
> - `KOSIS_API_KEY`는 Base64 형태일 수 있으므로 끝 `=` 패딩이 잘리지 않도록 전체를 복사하세요.

## 포함 스킬

| 스킬 | 데이터 소스 | 핵심 데이터 |
|------|-----------|----------|
| [`dart`](skills/dart/SKILL.md) | DART 전자공시 | 기업개황, 재무제표, 직원현황 |
| [`kosis`](skills/kosis/SKILL.md) | KOSIS 국가통계 | 인구, 산업, 시장 통계 |
| [`ecos`](skills/ecos/SKILL.md) | ECOS 한국은행 | GDP, 금리, 환율, 물가 |
| [`funding`](skills/funding/SKILL.md) | K-Startup·기업마당·NIPA·SMTECH (KOCCA 는 상세만) | 정부 지원사업 공고 전수조사·증분 재조사·적합성 판정 (키 불요, itda-hyve) |
| [`g2b`](skills/g2b/SKILL.md) | 나라장터 (G2B) | 입찰공고 검색·상세 |
| [`customs-notice`](skills/customs-notice/SKILL.md) | 관세청 공지사항 | 게시판 수집 → 마크다운 표 (구 itda-class-igm) |
| [`fss-docs`](skills/fss-docs/SKILL.md) | 금융감독원 공통업무자료 | 게시판 수집 → 마크다운 표 (구 itda-class-igm) |
| [`taxlaw`](skills/taxlaw/SKILL.md) | 국세법령정보시스템 | 세법 법령·해석례·판례·상담사례 검색·전문 (키 불요, 구 itda-tax) |
| [`fuel-price`](skills/fuel-price/SKILL.md) | 오피넷 (한국석유공사) | 주유소 평균 유가 조회 — 전국·시도 16 × 일/주/월, 전기 대비·과거 시점. **키 불요** |

> **정본 문서 가이드 (SPEC-ITDAGOV-DOCS-001, 2026-04-28 정비 완료)**: 6개 스킬 모두 발급처 정본 명세를 `skills/{스킬}/references/`에 보존하고, 각 SKILL.md 하단 "상세 API 가이드" 섹션에서 정본 파일을 직접 링크합니다. 활용신청 안내, 정본 에러 코드 매핑(한글 hint + 자동 활용신청 URL 부착), HTTP 403 처리, 라이브 응답 필드 매핑이 통일되어 있습니다.

## 크로스-스킬 워크플로우 가이드

### 입찰 제안서 경쟁사 분석

```
1. 경쟁사 목록 확정 (사용자 제공 또는 업종으로 추정)
2. 각 경쟁사 프로필 수집
   → dart: collect_company.py profile --name "{경쟁사}" --year 2024
3. 재무 비교 테이블 작성 (매출, 영업이익, 직원수)
4. 보충 검색 (WebSearch로 최신 뉴스/사업 동향)
5. 경쟁사 분석 보고서 종합
```

### 사업계획서 시장 분석

```
1. 시장 통계 수집
   → kosis: collect_stats.py plan search --keyword "{산업 키워드}" → itda-hyve http_request → search --input …
   → kosis: collect_stats.py plan data --org-id {orgId} --tbl-id {tblId} --recent 5 → itda-hyve → data … --input …
2. 주요 기업 재무 데이터 수집
   → dart: collect_company.py finance --corp-code {코드} --year 2024
3. 거시경제 환경
   → ecos: itda-hyve 로 KeyStatisticList 받기 → collect_econ.py key --input ecos/key-r1.json (100대 지표로 경제 개요)
4. 보충: WebSearch로 시장 전망/트렌드
5. 시장 분석 보고서 종합
```

### 정책 보고서 경제 분석

```
1. 경제 지표 수집
   → ecos: itda-hyve 로 StatisticSearch/{통계표코드}/A/2020/2024 받기 → collect_econ.py search --input ecos/search-…-r1.json
2. 관련 통계 수집
   → kosis: collect_stats.py plan data --org-id {orgId} --tbl-id {tblId} --recent 5 → itda-hyve → data … --input …
3. 용어 정의 확인
   → ecos: itda-hyve 로 StatisticWord/{경제 용어} 받기 → collect_econ.py word --input ecos/word-1-r1.json
4. 법적 근거
   → korean-law MCP: 관련 법령 조회
5. 보고서 종합
```

### 부동산 시장 분석

부동산 실거래가 조회는 `itda-gov` 플러그인의 `realty-deals`(구 `realestate` 상위호환 대체, v7.0.0 이전 완료 → #1272 제거)를 사용합니다. 통계·거시 맥락이 필요하면 본 플러그인의 `kosis`(인구·주택 통계)·`ecos`(금리)와 조합하세요.

### 입찰 제안서 종합 분석 (G2B 통합)

```
1. 입찰공고 확인
   → g2b: collect_g2b.py plan --from 2026-03-01 --to 2026-03-28 --write … → itda-hyve batch
          → collect_g2b.py collect --input g2b/bids-*.json --keyword "소프트웨어 개발"

2. 경쟁사 재무 분석
   → dart: collect_company.py profile --name "경쟁사A" --year 2025

3. 거시경제 환경
   → ecos: itda-hyve 로 KeyStatisticList 받기 → collect_econ.py key --input ecos/key-r1.json

4. 정부 지원사업 연계
   → funding: survey_crawl.py plan list all → itda-hyve batch → collect list --next-plan (반복)
     (전수 수집 후 전건 검토로 소프트웨어 연계 사업 선별)

5. 종합: 입찰 제안서 초안 작성
```

### 자금 조달 계획

```
1. 프로필 확정 + 저장 경로 합의 (funding SKILL.md 0·0.5단계)
2. 모집중 공고 전수 수집 (예상 호출 수를 알리고 확인)
   → funding: survey_crawl.py plan list all --run-dir <회차> --save-dir <호스트 경로>
     → itda-hyve batch → survey_crawl.py collect list --run-dir <회차> --next-plan (incomplete 면 반복)
3. run_manifest.json 으로 커버리지 판정 (partial·window 면 보고서에 한계 고지)
4. 전체 목록 직접 검토 → 후보 선별 → 상세·첨부 검증 (사용자 옵트인 후)
   → funding: survey_crawl.py plan detail <source>:<id>… → itda-hyve batch → collect detail --next-plan (반복)
5. A/B/C 분류 + 우선순위 액션으로 자금 조달 계획서 작성
6. 2~4주 뒤 증분 재조사
   → funding: survey_diff.py <직전 회차> <새 회차> --out new_items.jsonl
```

## 신규 Collector 추가 시 패턴 가이드

신규 collector 스크립트(`itda-gov/skills/{name}/scripts/collect_{name}.py`)는 기존 3개(`dart`/`kosis`/`ecos`)와 동일한 CLI 인자 구조를 따릅니다 (SPEC-COLLECTOR-CLI-001).

> **예외 — `funding`(v1.0.0~)**: funding 은 이 규약의 **적용 대상이 아닙니다.** 표면이 단발 조회기
> (`collect_*.py <서브커맨드> --keyword`)가 아니라 **수집·diff 파이프라인**(`survey_crawl.py plan|collect list|detail`,
> `survey_diff.py <old> <new>`)이기 때문입니다 — 결과는 jsonl·`run_manifest.json` 파일로 남기고, stdout JSON 과
> exit code 로 진행(1 = 더 받을 것)·커버리지(0/2/3)를 계약합니다.
> 규약 개정이 아니라 예외 등재입니다. funding 의 표면 정본은
> [`skills/funding/references/cli-contract.md`](skills/funding/references/cli-contract.md) 입니다.

### `--format` 등 공용 옵션은 서브커맨드 앞/뒤 양쪽에서 동작해야 함

`argparse` `parents=[...]` 패턴은 **사용 금지**. 메인 파서와 서브파서 양쪽에 등록하면 서브파서 default가 메인 파싱 결과를 덮어쓰는 충돌이 발생합니다.

대신 `_add_common()` 헬퍼 + `default=argparse.SUPPRESS` + `parser.set_defaults()` 조합 사용:

```python
def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--api-key", default=argparse.SUPPRESS, help="...")
    p.add_argument("--format", choices=["json", "table"], default=argparse.SUPPRESS, help="...")

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="...")
    parser.set_defaults(api_key=None, format="json")
    _add_common(parser)                    # 메인 — 앞쪽 위치 호환
    sub = parser.add_subparsers(dest="command", required=True)

    p_search = sub.add_parser("search", help="...")
    _add_common(p_search)                  # 서브 — 뒤쪽 위치 허용
    p_search.add_argument("--keyword", required=True)
    # ... 모든 서브커맨드에 _add_common(p_xxx) 빠짐없이 부착
```

### 회귀 테스트는 `parametrize`로 일괄 검증

서브커맨드가 여러 개일 때 양방향 위치를 한 번에 검증:

```python
@pytest.mark.parametrize("subcmd_args", [
    ["search", "--keyword", "x"],
    ["info", "--corp-code", "y"],
    # ... 전체 서브커맨드 enumerate
])
class TestFormatArgPosition:
    def test_format_after(self, subcmd_args):
        args = build_parser().parse_args([*subcmd_args, "--format", "table"])
        assert args.format == "table"
    def test_format_before(self, subcmd_args):
        args = build_parser().parse_args(["--format", "table", *subcmd_args])
        assert args.format == "table"
```

### `sys.modules` 글로벌 stub 금지

테스트에서 `env_loader` 등 빌드 시 주입되는 모듈을 stub할 때, top-level `sys.modules.setdefault(...)` 사용 금지 — 다른 테스트 모듈을 오염시켜 회귀 발생.
대신 `monkeypatch.setitem(sys.modules, ...)` 또는 fixture scope 격리 사용.

### SKILL.md Troubleshooting 섹션

Cowork sandbox 등에서 한글 경로가 인식 안 되는 케이스를 SKILL.md에 명시. 규약 대상 3개 collector + `funding` 모두 동일 가이드 보유 (SPEC-COLLECTOR-CLI-001 REQ-2 — funding 은 규약 비대상이나 이 가이드는 공통 적용).

> 규약 대상 collector 가 5개에 도달하는 시점에 `shared/cli_builder.py` 공통 헬퍼화를 재평가합니다. 현재 3개는 코드 중복이 단순(`_add_common` 8~15줄)하므로 헬퍼화 ROI가 낮습니다.

## 개발

```bash
# 전체 테스트
just test

# 의존성 설치
just install-deps
```

## 라이선스

Apache-2.0
