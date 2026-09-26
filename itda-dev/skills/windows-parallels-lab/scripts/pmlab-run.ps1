# pmlab-run.ps1 — prlctl exec 게이트의 인용부호 소실(함정 1)·출력 인코딩(함정 2)을
# 우회하는 실행 래퍼. zsh→prlctl 경로에서 따옴표가 깨지므로, exec 명령줄에는
# 따옴표가 하나도 없는 단순 인자만 남긴다:
#   prlctl exec <vm> powershell -NoProfile -ExecutionPolicy Bypass -File <이 파일> <대상.ps1> [인자...]
# 대상 스크립트의 exit code 는 그대로 전파된다(exit N → 프로세스 N).
param(
  [string]$Script,
  [Parameter(ValueFromRemainingArguments = $true)]$Rest
)
if (-not $Script) {
  Write-Error 'pmlab-run: 대상 스크립트 경로가 비어 있습니다'
  exit 3
}
# 출력 인코딩 계약 — 이걸 안 하면 한글이 CP949 로 깨져 호스트 판독이 무너진다.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
& $Script @Rest
exit $LASTEXITCODE
