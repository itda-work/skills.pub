# RDP over Cloudflare Tunnel — 레시피

포트포워딩 없이 Windows 원격 데스크톱(RDP)에 Zero Trust로 접속하는 절차. RDP는 **항상 Access로 보호**합니다(public 불가).

## 개요

```
[클라이언트 mstsc] → localhost:3389
        │ (cloudflared access rdp 로컬 프록시)
        ▼
   Cloudflare 엣지  ── Access 인증(이메일 OTP/SSO) ──
        ▲
        │ (아웃바운드 터널)
[서버 cloudflared] → rdp://localhost:3389 (Windows RDP)
```

## 서버측 (접속 당할 Windows 머신)

1. 원격 데스크톱 활성화: 설정 → 시스템 → 원격 데스크톱 ON.
2. desired-state 에 RDP 라우트 추가(Access 기본 보호):
   ```json
   { "hostname": "rdp.example.com", "service": "rdp://localhost:3389" }
   ```
3. SKILL.md "터널 생성·적용" 런북 수행: `cloudflared tunnel create` → `config.yml`(ingress에 위 라우트) → `cloudflared tunnel route dns` → `cloudflared service install`.
4. Zero Trust 대시보드에서 `rdp.example.com` 에 **Access 애플리케이션(self-hosted)** 생성 + 정책(예: 이메일 `you@example.com` 허용).

## 클라이언트측 (접속하는 머신)

```bash
# cloudflared 설치 후, 로컬 프록시 실행 — 브라우저로 Access 인증
cloudflared access rdp --hostname rdp.example.com --url rdp://localhost:3389
```

그 다음 RDP 클라이언트로 `localhost:3389` 접속:
- Windows: `mstsc /v:localhost:3389`
- macOS: Windows App(구 Microsoft Remote Desktop)에서 PC `localhost:3389`

## 보안 메모

- Access 정책이 연결 *수립 전* 신원을 강제합니다. 정책을 좁게(특정 이메일/그룹) 유지하세요.
- RDP 자체도 강한 계정 암호 + 가능하면 NLA 유지.
- `rdp.example.com` DNS는 터널 CNAME(프록시)이며 실제 집 IP를 노출하지 않습니다.

## 트러블슈팅

| 증상 | 점검 |
|------|------|
| Access 화면 안 뜸 | 클라이언트 `cloudflared access rdp` 실행 여부, hostname 철자 |
| 인증 후 검은 화면/끊김 | 서버 RDP 활성, `config.yml` 의 `rdp://localhost:3389`, 방화벽이 로컬 3389 허용 |
| 재부팅 후 접속 불가 | 서버 `cloudflared service install` 로 상시 실행 등록되었는지 |
| 느린 반응 | 터널 경유 RTT 증가는 정상. 대역폭 큰 작업은 체감 지연 가능 |
