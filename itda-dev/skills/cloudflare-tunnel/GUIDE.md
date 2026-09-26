# cloudflare-tunnel 사용 가이드

집이나 사무실 컴퓨터의 서비스(원격 데스크톱·SSH·내부 웹페이지)를 **공유기 포트포워딩 없이** 바깥에서 안전하게 접속하도록 Cloudflare Tunnel을 설정해 줍니다.
**Claude에게 말로 부탁하면 됩니다** — "집 윈도우에 RDP 터널 깔아줘", "cloudflare tunnel로 ssh 열어줘", "이 구성으로 터널 검증해줘"처럼요. 터미널 명령을 외워서 직접 입력할 필요는 없습니다.

> ⚠️ 이 스킬은 **설정(셋업) 도구**입니다. 실제로 트래픽을 계속 중계하는 상시 프로그램은 컴퓨터에 설치되는 `cloudflared`(OS 서비스)이고, 이 스킬은 "무엇을 열고 무엇을 보호할지" 계획을 만들고 안전한지 검증하는 역할을 합니다.
>
> ⚠️ **대상 독자**: 이 가이드는 Cloudflare 계정과 도메인을 다뤄본 분(또는 함께할 사내 IT 담당)을 전제로 합니다. 아래 "사전 준비"(도메인 연결·Zero Trust〔접속 전 신원 확인을 거치게 하는 보호〕·토큰 발급)를 갖춰야 시작할 수 있어요 — 생활 자동화 스킬과 달리 순수 비개발자 단독 진행은 어렵고, 사내 IT와 함께 진행하시길 권합니다.

---

## 무엇을 할 수 있나요

| 하고 싶은 것 | 이렇게 실행하세요 |
|--------------|-----------------|
| 원격 데스크톱(RDP) 열기 | `/cloudflare-tunnel 집 윈도우에 원격 데스크톱 터널 깔아줘` |
| SSH 접속 열기 | `/cloudflare-tunnel 내 서버에 ssh 터널 열어줘` |
| 내부 웹페이지 노출 | `/cloudflare-tunnel localhost:8080에서 도는 웹을 blog.example.com으로 열어줘` |
| 구성이 안전한지 검증 | `/cloudflare-tunnel 이 desired-state로 터널 구성 검증해줘` |
| 노출 위험 점검 | `/cloudflare-tunnel 지금 터널 구성에서 위험하게 열린 게 있는지 봐줘` |
| 라우트에 접근 통제 걸기 | `/cloudflare-tunnel 터널 라우트에 access 걸어줘` |

지원 OS는 **Windows · macOS · Linux** 모두입니다.

---

## 왜 포트포워딩이 필요 없나요

집/서버 컴퓨터가 Cloudflare 쪽으로 **나가는(아웃바운드)** 연결만 맺습니다. 바깥에서 집으로 들어오는 문(인바운드 포트)을 여는 게 아니라서:

- 공유기 포트포워딩 설정이 필요 없습니다.
- 공인 IP가 없어도(통신사 공유망·CGNAT 환경) 동작합니다.
- 집 실제 IP 주소가 외부에 노출되지 않습니다.

---

## 보안이 기본으로 켜져 있습니다 (꼭 읽어주세요)

이 스킬은 **안전한 쪽이 기본값**입니다. 별도로 말하지 않으면 모든 통로에 접근 통제(Cloudflare Zero Trust Access)가 자동으로 붙습니다.

- ⚠️ **기본은 "보호됨"입니다.** 어떤 주소를 열면, 따로 지정하지 않는 한 인증(예: 이메일 OTP)을 거쳐야만 접근할 수 있습니다.
- ⚠️ **공개로 열려면 직접 "공개"라고 말해야 합니다.** 누구나 봐도 되는 웹페이지처럼 인증 없이 열고 싶을 때만 "이 주소는 공개로 해줘"라고 명시하세요(구성 파일에서는 `"access": "public"`).
- ⚠️ **원격 데스크톱·SSH는 공개로 열 수 없습니다.** `rdp`·`ssh`·`tcp` 같은 서비스를 공개로 만들려고 하면 스킬이 **거부**합니다(보안 위반 안내, `정책 위반` / exit 2). 이런 서비스는 항상 인증으로 보호합니다.
- ⚠️ **공개로 열면 진짜로 공개됩니다.** 접근 통제를 떼면 그 주소는 원본 서비스 자체의 비밀번호·보안에만 의존합니다(Cloudflare의 인증·방화벽 보호가 사라집니다).

---

## 시작하기 전에 준비할 것 (Prerequisites)

이 스킬은 일부 사전 준비가 필요합니다. 한 번만 갖춰두면 됩니다.

### 1. 도메인이 Cloudflare에 등록되어 있어야 합니다

내가 쓸 도메인(예: `example.com`)이 Cloudflare DNS에 zone(도메인을 Cloudflare가 관리하는 단위)으로 등록되어 있어야 합니다. 아직이라면 Cloudflare 대시보드에서 도메인을 먼저 추가하세요.

### 2. Zero Trust(Access)를 켜세요

Cloudflare 대시보드에서 Zero Trust를 활성화합니다. **무료 플랜으로 충분**하며, 이메일 OTP 같은 간단한 인증을 쓸 수 있습니다.

### 3. cloudflared를 설치하세요

실제 터널을 연결할 컴퓨터에 `cloudflared` 프로그램을 설치합니다.

| OS | 설치 방법 |
|----|-----------|
| macOS | Homebrew로 `cloudflared` 설치 |
| Windows | winget으로 `Cloudflare.cloudflared` 설치, 또는 공식 릴리스의 `.msi` |
| Linux | 배포판 패키지, 또는 [공식 릴리스 페이지](https://github.com/cloudflare/cloudflared/releases) |

> 공식 다운로드: <https://github.com/cloudflare/cloudflared/releases>

### 4. Cloudflare API 토큰을 발급하세요

DNS와 Access를 구성하려면 API 토큰이 필요합니다.

- ⚠️ **Global API Key는 쓰지 마세요.** 권한이 너무 넓습니다. 아래처럼 **최소 권한**으로 발급하세요:
  - `Zone.DNS:Edit` (해당 도메인 zone)
  - Access 앱을 API로 만들 경우에만, 계정의 `Access: Apps and Policies:Edit`
- ⚠️ **토큰은 절대 코드 저장소(git)에 올리지 마세요.** OS 보안 저장소(macOS 키체인 · Windows 자격 증명 관리자 · Linux secret-service)에 보관하는 것을 권장합니다. 간편하게는 작업 폴더 루트의 `.env` 파일도 됩니다.

발급한 토큰은 아래 형태로 작업 폴더의 `.env`에 넣어두면 Claude가 읽습니다.

```dotenv
CLOUDFLARE_API_TOKEN=발급받은_토큰
# Access 앱을 API로 만들 때만 필요(대시보드로 만들면 불필요)
CLOUDFLARE_ACCOUNT_ID=계정_ID
```

---

## 구성을 한 파일로 선언합니다 (desired-state)

"무엇을 열고 무엇을 보호할지"를 JSON 파일 한 장으로 적습니다. 이 한 장이 단일 기준이 됩니다. Claude에게 "이렇게 구성해줘"라고 말하면 이 파일을 같이 만들어 줍니다.

```json
{
  "tunnel": "home-win",
  "default_policy": "email:you@example.com",
  "routes": [
    { "hostname": "rdp.example.com", "service": "rdp://localhost:3389" },
    { "hostname": "blog.example.com", "service": "http://localhost:8080", "access": "public" }
  ]
}
```

- `tunnel` — 터널 이름.
- `default_policy` — 보호되는 통로에 개별 정책을 안 적으면 적용될 기본 신원(예: 특정 이메일).
- `routes` — 열 주소 목록. 각 항목은 `hostname`(바깥에서 접속할 주소)과 `service`(내 컴퓨터의 실제 서비스).
- 통로마다 `access`를 생략하면 자동으로 **보호(required)** 됩니다. 위 예시에서 `rdp.example.com`은 보호되고, `blog.example.com`만 명시적으로 공개입니다.

---

## 어떻게 진행되나요

Claude가 다음 순서로 도와줍니다. 사용자는 자연어로 요청만 하면 됩니다.

### 1단계 — 구성 검증 + 계획 확인 (항상 먼저)

만든 구성이 보안 규칙을 어기지 않는지 먼저 검사하고, 무엇이 열리고 무엇이 보호되는지(통로·DNS·접근 통제) 계획을 보여줍니다. 보안 위반이 있으면 여기서 **중단**되므로 적용 전 안전장치가 됩니다.

이렇게 말하세요:

```
/cloudflare-tunnel 이 desired-state로 터널 구성 검증하고 계획 보여줘
```

```
/cloudflare-tunnel 지금 구성에서 위험하게 열린 게 있는지 점검만 해줘
```

공개로 열린 통로나, 보호하기로 해놓고 실제로는 보호가 빠진 곳이 있으면 경고로 알려줍니다. 만들어진 구성 파일은 cloudflared 자체 검증기로 교차 확인할 수도 있습니다(이때는 Cloudflare 계정도 필요 없습니다).

### 2단계 — 터널 생성·적용

검증을 통과하면 실제 터널을 만들고 적용합니다. Claude가 계획에 따라 단계를 진행합니다.

이렇게 말하세요:

```
/cloudflare-tunnel 검증 통과했으니 이 터널 실제로 만들고 적용해줘
```

이 단계에서 일어나는 일(요약): Cloudflare 로그인(최초 1회 브라우저 인증) → 터널 생성 → 구성 파일 만들기 → 각 주소를 터널에 연결(DNS) → 보호 대상 주소에 접근 통제 앱 생성 → 재부팅 후에도 자동 실행되도록 OS 서비스로 등록.

> ⚠️ 이 적용 단계는 Claude가 계획에 따라 안내·실행합니다(현재 버전의 자동화 범위는 말미 "지금 버전의 범위와 한계" 참고).

### 3단계 — 실제 접속

원격 데스크톱(RDP)은 별도 레시피가 준비되어 있습니다(아래 시나리오 참고).

---

## 활용 시나리오

### 집 윈도우에 원격 데스크톱(RDP) 터널 깔기

외출 중에 집 윈도우 PC에 포트포워딩 없이 접속하고 싶을 때.

```
/cloudflare-tunnel 집 윈도우에 RDP 터널 rdp.example.com으로 깔아줘. 내 이메일만 접근 가능하게.
```

RDP는 **항상 접근 통제로 보호**됩니다(공개 불가). 접속 시에는 클라이언트 컴퓨터에서 로컬 프록시를 띄우고 브라우저로 인증(이메일 OTP/SSO)을 거친 뒤, 윈도우 원격 데스크톱 앱으로 `localhost:3389`에 접속합니다. macOS에서는 Windows App(구 Microsoft Remote Desktop)으로 같은 방식으로 접속합니다. 자세한 단계는 스킬의 `references/rdp-recipe.md` 레시피를 Claude가 안내해 줍니다.

### SSH 터널 열기

서버에 SSH로 접속하되 공인 IP·방화벽 개방 없이.

```
/cloudflare-tunnel 내 서버 ssh.example.com에 ssh 터널 열어줘
```

SSH도 비-HTTP 서비스라 공개로 열 수 없고, 접근 통제로 보호됩니다.

### 공개 웹페이지 노출

블로그나 데모처럼 누구나 봐도 되는 웹을 외부에 열 때.

```
/cloudflare-tunnel localhost:8080에서 도는 블로그를 blog.example.com으로 공개로 열어줘
```

이 경우에만 "공개로"라고 명시해야 인증 없이 열립니다. 그 외에는 기본 보호가 적용됩니다.

### 구성만 미리 점검하기

아직 적용하지 않고 "이 구성이 안전한가"만 보고 싶을 때.

```
/cloudflare-tunnel 이 desired-state 적용하기 전에 노출 위험만 감사해줘
```

공개로 열린 통로, 알 수 없는 서비스 형식 등을 경고로 정리해 줍니다.

---

## 안 될 때

| 증상 | 원인 / 해결 |
|------|-------------|
| "정책 위반 … access: public …" 안내 (`exit 2`) | 원격 데스크톱·SSH 같은 비-HTTP 서비스를 공개로 열려고 함. 그 통로를 보호(`access: required`, 또는 생략)로 바꾸세요 |
| "입력 오류" 안내 (`exit 1`) | 구성 JSON의 형식이 틀렸거나 필드가 빠짐. `tunnel`, 그리고 각 통로의 `hostname`/`service`가 있는지 확인 |
| "cloudflared를 찾을 수 없다"는 안내 | `cloudflared` 미설치. 위 "시작하기 전에 준비할 것 3"으로 설치 |
| 터널은 연결되는데 접속이 안 됨 | DNS·접근 통제가 아직 적용 안 됐거나, 내 컴퓨터의 해당 서비스가 안 켜져 있음. 계획의 DNS·접근 항목 적용 여부와 로컬 서비스 포트를 확인 |
| (RDP) 인증 화면이 안 뜸 | 접속하는 컴퓨터에서 로컬 프록시가 실행 중인지, 주소 철자가 맞는지 확인 |
| (RDP) 재부팅 후 접속 불가 | 서버 쪽 `cloudflared`가 OS 서비스로 상시 실행 등록됐는지 확인 |

---

## 팁

- **항상 1단계(검증)부터.** 적용 전에 계획과 경고를 먼저 보면 의도치 않은 공개 노출을 막을 수 있습니다.
- **접근 정책은 좁게.** 특정 이메일이나 그룹만 허용하도록 좁혀두는 게 안전합니다. 접근 통제는 연결이 맺어지기 *전에* 신원을 확인합니다.
- **원격 데스크톱은 RDP 자체 보안도 챙기세요.** 강한 계정 암호 + 가능하면 NLA(윈도우 원격 접속의 추가 인증)를 유지하세요.
- **토큰·자격증명은 git에 올리지 마세요.** OS 보안 저장소 보관을 권장하고, 부득이하면 작업 폴더 `.env`에만 두세요.

---

## 지금 버전의 범위와 한계

- ⚠️ **버전 0.1.0**: 보안 검증·계획 산출은 자동화되어 있고, 실제 터널 생성·DNS·접근 통제·서비스 등록은 Claude가 계획에 따라 안내·실행합니다. 이 전 과정을 한 번에 자동 적용하고 변경분만 맞춰주는 기능은 다음 버전에서 추가됩니다.
- 공유기 포트포워딩·호스트 방화벽 설정은 다루지 않습니다(터널 방식이라 필요 없습니다).
- 터널 바깥에서 직접 들어오는(동적 DNS) 방식은 이 스킬 범위가 아닙니다(별도 스킬에서 다룰 예정).
- Windows 경로 동작은 별도 검증을 거칩니다.
- 이 스킬은 hyve 데몬이나 MCP에 의존하지 않습니다. 필요한 것은 `cloudflared`와 Cloudflare 계정뿐입니다.

---

## 더 알아보기

- Cloudflare Tunnel 공식 문서: <https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/>
- Zero Trust Access 공식 문서: <https://developers.cloudflare.com/cloudflare-one/policies/access/>
