# itda-org-mmaa

군인공제회 전용 스킬팩 — 복지포털 스냅샷 Q&A(mmaa-welfare): 복지부조·회원콘도·유익한 정보를 출처 URL·수집일과 함께 답한다. 조직 전용 팩(itda-org-*) 첫 사례.

> 군인공제회 구성원 전용 팩(`itda-org-*` 첫 사례, #1648). 복지포털 스냅샷은 스킬 안에 동봉돼 로그인·키 없이 답합니다.

## 포함 스킬

| 스킬 | 기능 |
|---|---|
| [`mmaa-welfare`](skills/mmaa-welfare/SKILL.md) | 군인공제회 복지포털 스냅샷 Q&A — 복지부조(신규가입·출산 축하금, 재해위로금, 축하기념품)· 회원콘도 이용안내·유익한 정보(취업·창업·시니어)를 출처 URL·수집일과 함께 답합니다. |

## 설치

```
/plugin marketplace add itda-work/skills.pub
/plugin install itda-org-mmaa@itda-skills-pub
```

## 사전 준비

스킬별 API 키·환경변수·계정 설정·Python 패키지는 각 스킬의 `SKILL.md` Prerequisites 절과 `GUIDE.md` 에 있습니다. 여러 스킬이 같은 키를 쓰면 환경변수 하나로 함께 쓰입니다 — 스킬은 `.env` 같은 파일을 읽지 않습니다(itda-work/skills#45).

## 개발

```bash
just test itda-org-mmaa          # 저장소 루트
just -f itda-org-mmaa/justfile test
```
