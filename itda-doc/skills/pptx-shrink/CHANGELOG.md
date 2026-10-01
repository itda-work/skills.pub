# Changelog — itda-work/pptx-shrink

## [0.2.3] — 2026-09-30 (itda-work/skills#47)

### Fixed

- **SKILL_DIR 확정 블록이 새 Cowork 배치에서 빈 값을 내던 것** — Cowork 가 플러그인을 `/root/.claude/plugins/synced/` 에 두고
  `CLAUDE_PLUGIN_ROOT` 를 주지 않자 옛 블록의 1·2순위가 둘 다 비었다. 새 블록(규칙 `skill-dir-resolution` 정본)은 스킬을 불러올 때 받은
  base directory 를 먼저 넣게 하고 그 값을 검증해 쓴다. 넣지 못했을 때만 설정 홈(`CLAUDE_CONFIG_DIR`)의 동기화본·Code 캐시와
  Cowork 배치를 찾으며, 후보마다 `SKILL.md` 를 확인하고 없거나 여럿이면 빈 값으로 진행하지 않고 멈춘다. PowerShell 블록도 같은 계약으로 바꿨다.

## [0.2.2] — 2026-09-27

### Changed

- 제거된 덱 생성 스킬 지목을 `[책임 경계]`·"쓰지 않을 때" 표에서 뺐다(2026-09-27) — 발표자료 신규 생성은 비지원으로 안내.

## [0.2.1] — 2026-09-25 (itda-work/itda-hyve#6)

### Changed

- `[책임 경계]`·“쓰지 않을 때” 표에서 빠진 스킬(구 itda-hyve 팩의 pptx-diff)과 hyve PowerPoint COM 안내를 지웠다. 버전 비교·슬라이드 편집은 비지원으로 적는다.

## [0.2.0] — 2026-09-05 (이슈 #1646 — 마스터 제안)

### Added

- `report` 가 **품질 90/80/70 × 해상도 원본/220/150ppi** 를 전부 실측해 조합별 결과 크기 표(`tiers_after_mb`)를 낸다.
  "예상" 표기를 "실측" 으로 정정(원래도 실제 인코딩이었다).
- 표시 크기 파서 `display_sizes`: 슬라이드·레이아웃·마스터 `<p:pic>` 의 `a:ext`(그룹 ext/chExt 스케일 반영) → 미디어별 최대
  표시 인치. `downsample_candidates`·`downsample_gain_pct`·`downsample_recommended`(5% 이상) 로 축소 이득을 보고.
- `shrink --downsample-ppi {220|150}`(기본 꺼짐): 표시 크기보다 픽셀이 큰 이미지만 LANCZOS 축소 후 JPEG. 슬라이드 XML 무접촉.
- SKILL.md 관문 2 가 **품질 · 해상도 축소 · 저장 방식** 셋을 한 번에 확인. GUIDE 에 "품질은 어떻게 고르나" 절 신설,
  "PowerPoint 그림 압축" 절을 실측 표(A/L/H: JPEG 뒤 축소 이득 0.2MB 수준)로 교체.
- 테스트 +7(그룹 스케일·미상·다중 사용, target_px, 조합 단조성, 축소 픽셀·verify, 확대 배치 제외, CLI, 실물 픽스처).

## [0.1.1] — 2026-09-05 (이슈 #1645 2차 — 테스트 보강)

### Added

- **실물 구조 픽스처** `tests/fixtures/deck-real.pptx`(0.67MB) + 생성기 `make_fixture.py`: hyve-training E 덱에서 구조(레이아웃 13·
  마스터·노트마스터·테마·webextension·노트 4)는 그대로 두고 텍스트·도형 이름·외부 링크·revision·픽셀을 전부 합성으로 치환.
  공유 참조(D 덱)·마스터 그림(세라젬 덱)·외부 URL 잔여 이름 미디어(L 덱)를 이식. PNG 는 변환 대상 2 + 투명 1 + 단색 10 으로 최소화
  (마스터 지시) — 테스트는 `min_bytes=50_000` 으로 잰다.
- `tests/test_fixture_real.py` 7종: 구조·원문 잔존 0 · report · 왕복(마스터·공유 rels 전파, 미디어·rels·Content_Types 외 바이트 동일) ·
  verify 3축(마스터 그림 소실·노트/슬라이드 수·미선언 확장자) · 기존 고아 참조 제외 · LibreOffice 렌더 스모크(soffice 없으면 skip).
- 가장자리 분기 7종: 이름 충돌 `_1.jpeg` · 깨진 PNG skipped · `BACKUP_EXISTS`/`--force` · `--in-place`+`-o` · 출력=입력 · quality 범위 ·
  Content_Types 에 Default 부재.

### Fixed

- `report` 가 확장자에 URL 잔여물이 붙은 미디어(`image8.xx&_nc_gid=…` — L 덱 실물)를 미디어 합계에서 빠뜨리던 것.
- `verify` 가 슬라이드 그림만 세던 것 → 레이아웃·마스터·노트마스터·노트의 그림 수도 대조(뮤테이션 RED 실측).

## [0.1.0] — 2026-09-05 (이슈 #1645)

### Added

- 스킬 신설. hyve-training 의 `pptx_shrink.py`(IGM 12덱 212→57MB 실측, 텍스트·노트·그림 수 무손실)를 승격.
  - `report`: 미디어 분해(확장자별·상위 이미지·해상도·알파)·예상 절감. 파일을 쓰지 않는다.
  - `shrink`: `ppt/media/*.png` 를 해상도 유지 JPEG 로 재인코딩(품질 80 · 300KB 미만 유지 · 투명 PNG 유지 ·
    커지면 유지), rels Target·[Content_Types] 정합. zip 직접 조작 — python-pptx 라운드트립 없음.
  - **원본 보호 게이트**(마스터 지시): 기본은 `<이름>-shrunk.pptx` 새 파일. `--in-place` 는 `--backup [경로]`
    또는 `--no-backup` 명시 없이는 거부(exit 2 `BACKUP_DECISION_REQUIRED`). SKILL.md 관문 2 가 사용자 확인을 요구.
  - `verify.py`: 슬라이드 수·슬라이드별 텍스트·노트·그림 수·rels 참조 실재·Content_Types 확장자 대조. shrink 가
    자동 호출하고 실패 시 산출 폐기(exit 3).
  - 테스트 16종(합성 pptx 픽스처) + 뮤테이션 4종(알파 판정·rels 치환·백업 게이트·verify 폐기) RED 실측.
