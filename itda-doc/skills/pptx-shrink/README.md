# pptx-shrink — 개발 노트

사용자 안내는 `GUIDE.md`, 에이전트 절차는 `SKILL.md`. 이 파일은 왜 이렇게 만들었는지만 적는다.

## 출처

hyve-training 저장소 `scripts/pptx_shrink.py` + `scripts/hooks/pre-commit`(2026-09-05, IGM 9기 덱 12종 212→57MB).
훅은 저장소 운영 자산이라 여기 가져오지 않았고(SKILL.md 부록에 선례로만), 스크립트는 다음을 바꿔 이식했다:

- PEP 723 `uv run` 셔뱅 제거 → `install_skill_deps.py` + `requirements.txt`(Pillow). Cowork 에는 uv 가 없다.
- `report` 서브커맨드 신설(원본은 변환만).
- **원본 보호 게이트** 신설 — 원본 훅은 in-place 가 기본이었다(git 이 백업이므로). 스킬은 사용자 파일을 다루므로
  기본을 새 파일로 뒤집고, in-place 는 백업 결정을 명시해야 통과한다.
- `verify.py` 를 분리해 shrink 종단에 배선. 원본 세션은 텍스트·노트를 python-pptx 로 손 대조했다.

## 0.2.0 — 실측 표와 선택 (#1646)

마스터 제안: "적용 전에 얼마나 줄지 실측해서 보여 주고 확인받자 · PowerPoint 그림 압축까지 얹으면 얼마나 더 주는지도 · JPEG 품질도
고르게". report 가 품질 3단 × 해상도 3단을 전부 인코딩해 잰다(변환 대상 30장 기준 수 초). 해상도 축소는 A/L/H 실덱에서 JPEG 뒤
0.2MB 수준이라(슬라이드 26.67in, 스크린샷이 표시보다 작게 놓임) 기본 꺼짐 + 5% 이상일 때만 권한다. 크롭 적용(srcRect 편집)은 슬라이드
XML 을 건드려야 해 제외.

## 왜 zip 직접 조작인가

python-pptx 로 열어 저장하면 애니메이션·일부 확장 요소가 유실될 수 있다. 이미지만 바꾸는 데 문서 모델이
필요 없으므로 zip 항목을 그대로 복사하고 `ppt/media/*.png` 만 갈아 끼운다. 바뀌는 것은 미디어 파일명·rels
Target·Content_Types 세 곳뿐이라 verify 가 그 세 곳을 전부 본다.

## 테스트

```bash
cd skills/itda-work && just test-skill pptx-shrink
```

두 겹이다.

- `test_pptx_shrink.py` — 합성 pptx(zip 직접 조립)로 분류·게이트·가장자리 분기 23종.
- `test_fixture_real.py` — **실물 구조 픽스처** `fixtures/deck-real.pptx` 7종. hyve-training E 덱을 `fixtures/make_fixture.py` 로
  치환한 것이라 레이아웃·마스터·테마·노트의 실제 얽힘을 갖되 원문·픽셀은 없다(재생성: `python3 make_fixture.py <원본> <출력>`,
  원본은 hyve-training git 이력 `0ef907b^`). PNG 를 늘리지 않는다 — 변환 대상 2·투명 1 이면 충분하다.

뮤테이션(알파 판정 · rels 치환 · 백업 게이트 · verify 폐기 · 마스터 그림 판정)은 각각 RED 를 실측했다(#1645).
LibreOffice 렌더 스모크는 soffice 가 있는 환경에서만 돈다(개발 머신엔 없어 skip — 실측 공백으로 기록).
