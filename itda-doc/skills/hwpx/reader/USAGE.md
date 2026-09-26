> 이 문서는 통합 hwpx 스킬의 reader 경로 상세 사용법이다 (구 hwpx-reader SKILL.md).
> 아래 `SKILL_DIR` 블록은 통합 스킬의 `reader/` 서브트리를 가리키도록 갱신되어 있다.
> `requirements.txt` 는 스킬 루트로 병합: `"${SKILL_DIR}/../requirements.txt"`.

# HWP/HWPX 문서 처리

HWP5(.hwp) 및 HWPX(.hwpx) 문서를 읽고 Markdown/HTML로 변환합니다.

이 스킬은 **읽기·변환 전용**입니다. HWP/HWPX 생성·편집·저장은 지원하지 않습니다.

## 설계 원칙

- **Python native**: 스킬 내부 `hwpx_native` 패키지가 HWP5/HWPX 파싱과 Markdown/HTML 렌더링을 담당합니다.
- **외부 바이너리 없음**: 별도 실행 파일 탐색, 번들 추출, PATH 의존이 없습니다.
- **결정적 출력**: `-o`로 지정한 경로에 그대로 쓰고, Markdown 이미지는 `<stem>/image_NNNN.ext`로 추출합니다.
- **읽기 최적화**: 기본은 Markdown 변환 후 표 평탄화이며, 원본 구조가 중요하면 HTML 또는 테이블 보존을 선택합니다.

## 요구 사항

먼저 스킬 디렉토리 경로를 `SKILL_DIR` 로 확정합니다 (이하 모든 명령이 이 변수를 사용):

```bash
# Claude Code(플러그인 설치) = $CLAUDE_PLUGIN_ROOT / Cowork = 세션 마운트 탐색
SKILL_DIR="${CLAUDE_PLUGIN_ROOT:+$CLAUDE_PLUGIN_ROOT/skills/hwpx}"
[ -n "$SKILL_DIR" ] || SKILL_DIR=$(find /sessions/*/mnt/.remote-plugins -type d -path '*/skills/hwpx' 2>/dev/null | head -1)
# 둘 다 아니면(저장소 체크아웃 등) 스킬 루트(SKILL.md 위치) 절대경로를 그대로 사용
SKILL_DIR="$SKILL_DIR/reader"
```

스킬 디렉토리에서 Python 의존성을 사용할 수 있어야 합니다.

```bash
python3 -m pip install -r "${SKILL_DIR}/../requirements.txt"
```

필수 의존성:

- `Pillow`: 이미지 포맷 확인 및 BMP 선언 이미지의 PNG 변환
- `olefile`: HWP5 OLE/CFB 컨테이너 읽기

## 변환 명령

항상 입력 파일을 쓰기 가능한 작업 디렉토리로 복사한 뒤 변환합니다. Cowork 업로드 경로는 read-only일 수 있습니다.

```bash
mkdir -p .itda-skills
cp <입력파일> .itda-skills/

PYTHONPATH="${SKILL_DIR}" \
python3 -m hwpx_native convert .itda-skills/<파일명> \
  -o .itda-skills/<파일명>.md --format md
```

본문만 필요하고 이미지 파일을 만들지 않으려면:

```bash
PYTHONPATH="${SKILL_DIR}" \
python3 -m hwpx_native convert .itda-skills/<파일명> \
  -o .itda-skills/<파일명>.md --format md --no-extract-images
```

HTML 변환:

```bash
PYTHONPATH="${SKILL_DIR}" \
python3 -m hwpx_native convert .itda-skills/<파일명> \
  -o .itda-skills/<파일명>.html --format html
```

## 워크플로

### 1. Markdown 읽기

1. 입력 파일을 `.itda-skills/`로 복사합니다.
2. `python3 -m hwpx_native convert ... --format md`를 실행합니다.
3. 생성된 `.md` 파일을 읽습니다.
4. 사용자가 원본 표 보존을 요청하지 않았다면 [Table 평탄화 지침](#table-평탄화-지침)을 적용합니다.
5. Cowork 환경에서는 `.md`와 이미지 디렉토리를 `mnt/outputs/`로 복사합니다.

### 2. 이미지 옵션

디폴트는 **이미지 추출 O / 캡션 X**입니다.

| 사용자 의도 | 트리거 키워드 | 변환 옵션 | 캡션 단계 |
|------------|-------------|----------|----------|
| 디폴트 | 없음 | `--format md` | 스킵 |
| 본문만 | "본문만", "텍스트만", "이미지 빼고", "이미지 없이" | `--no-extract-images` | 스킵 |
| 캡션 포함 | "이미지 설명도", "캡션 포함", "이미지 분석해줘", "이미지 설명 추가" | `--format md` | 실행 |
| 모순 | 본문만 + 캡션 포함 | 실행 보류 | 사용자에게 의도 재확인 |

이미지는 Markdown 출력 파일 stem 디렉토리에 저장됩니다.

```text
.itda-skills/보도자료.md
.itda-skills/보도자료/image_0001.png
.itda-skills/보도자료/image_0002.jpg
```

`--no-extract-images`를 쓰면 이미지 파일을 만들지 않고 Markdown 본문에 `#image-omitted` 참조를 남깁니다.

### 3. 이미지 캡션 생성

사용자가 명시적으로 이미지 설명을 원할 때만 실행합니다.

1. `scripts/find_images.py`로 `.itda-skills/<stem>/image_NNNN.*`를 찾습니다.
2. 이미지가 10개를 초과하면 전체/일부/건너뛰기를 사용자에게 확인합니다.
3. Pillow, `sips`, `ffmpeg` 중 가능한 도구로 512px JPEG 임시 이미지를 만듭니다.
4. 각 이미지마다 Sonnet 서브에이전트를 병렬 실행해 한국어 1-2문장 설명을 받습니다.
5. Markdown의 `![](<path>)` 또는 `<img src="...">` 참조에 alt/caption을 반영합니다.
6. `.itda-skills/images_resized/` 임시 디렉토리를 삭제합니다.

### 4. HTML 변환

HTML은 원본 구조 보존 목적입니다.

- 이미지 데이터는 Base64 data URI로 문서 안에 임베드됩니다.
- Table 평탄화와 이미지 캡션 삽입을 적용하지 않습니다.
- Cowork 환경에서는 HTML 파일을 `mnt/outputs/`에 저장합니다.

## 지원 변환

| 입력 → 출력 | 지원 |
|-------------|------|
| HWP5 → Markdown | O |
| HWP5 → HTML | O |
| HWPX → Markdown | O |
| HWPX → HTML | O |
| Markdown/HTML → HWP/HWPX | X |

## HWP5 제약 사항

| 제약 | 설명 |
|------|------|
| 하이퍼링크 | HWP5 바이너리 구조상 링크 추출을 지원하지 않습니다. |
| 수식/차트 | OLE 객체 기반 수식과 차트는 텍스트/이미지로 완전 복원하지 않습니다. |
| 특수 폰트 | Wingdings류 심볼은 원문과 다르게 보일 수 있습니다. |
| **배포용 보호 문서** | 본문이 `BodyText` 가 아니라 **`ViewText` 에 암호화**되어 있어 추출할 수 없습니다. 변환기가 **명시 에러**로 거부합니다(#1536) — 예전에는 빈 문서가 조용히 "성공" 으로 나왔습니다. |

## Table 평탄화 지침

한국 공공기관 문서는 레이아웃 목적으로 테이블을 과도하게 사용합니다.
Markdown 변환 결과의 테이블을 LLM 맥락 이해에 적합한 리스트/텍스트로 평탄화합니다.
HTML 변환에는 적용하지 않습니다.

### 원본 보존

사용자 요청에 아래 키워드가 포함되면 평탄화를 건너뜁니다.

- "원본 그대로"
- "테이블 유지"
- "표 형식으로 보여줘"

### 분류 기준

행-열 교차 맥락이 아주 중요한 경우만 보존합니다. 판단이 애매하면 평탄화를 선택합니다.

| 구분 | 예시 |
|------|------|
| 평탄화 대상 | 키-값 테이블, 레이아웃 테이블, 일반 데이터 테이블, 양식 테이블 |
| 보존 대상 | 비교표, 교차분석표, 수치 매트릭스, 시간표·스케줄 |

### 변환 규칙

키-값 테이블은 불릿 리스트로 바꿉니다.

```markdown
| 기관명 | 한국도로공사 |
| 담당부서 | 도로관리처 |

- **기관명**: 한국도로공사
- **담당부서**: 도로관리처
```

단일셀/레이아웃 테이블은 셀 텍스트를 자연문으로 꺼냅니다.

```markdown
| 제1조 (목적) 이 규정은 ... |

**제1조 (목적)** 이 규정은 ...
```

다열 데이터 테이블은 첫 번째 열 또는 가장 식별력 있는 열을 항목 제목으로 사용합니다.

```markdown
- **도로확장**
  - 예산: 5,000백만원
  - 집행률: 78%
  - 담당부서: 도로관리처
```

양식 테이블은 라벨:값 리스트로 바꾸고 빈 셀은 `(빈칸)` 처리하거나 생략합니다.

## 에러 처리

| 에러 상황 | 대응 |
|----------|------|
| Python 의존성 없음 | `python3 -m pip install -r "${SKILL_DIR}/../requirements.txt"` 실행 |
| 변환 실패 | traceback의 마지막 오류를 사용자에게 전달하고, HWP5 Markdown 실패 시 HTML 변환을 시도 |
| 파일을 찾을 수 없음 | 입력 파일 경로를 다시 확인 |
| 미지원 포맷 | HWP/HWPX → Markdown/HTML만 지원한다고 안내 |
| `distribution-protected HWP5 file` | 배포용 보호 문서입니다. 한/글에서 보호를 해제한 원본을 요청하세요 — 우회 추출 경로는 없습니다. |
| `encrypted HWP5 file` | 암호가 걸린 문서입니다. 암호를 푼 파일이 필요합니다. |

## 참고

구현 세부와 API 예시는 `references/hwpx-native-reference.md`를 참조하세요.
