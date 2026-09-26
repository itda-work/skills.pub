#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""uictl.py — macOS 호스트에서 Parallels 게스트(win11-parlab)의 GUI 를 좌표로 조작한다.

전제
  * 게스트 제어 프리미티브는 windows-parallels-lab 스킬의 pmlab.sh 셸 함수다.
  * prlctl exec(= pmlab_exec)는 SYSTEM · Session 0 이라 입력/GUI 가 콘솔 데스크톱에 닿지
    않는다. 따라서 마우스·키보드·클립보드·창목록은 전부 pmlab_open_app(schtasks /RU <콘솔
    사용자> /IT) 경로로 **사용자 세션**에서 실행한다.
  * pmlab_open_app 은 실패가 무음이므로, 매 실행마다 게스트가 공유 폴더에 ack 파일을 쓰게
    하고 호스트가 그 갱신을 확인한다. 확인 못 하면 비영 종료한다.

절대 하지 않는 것: pmlab_switch / 스냅샷 revert / VM 정지 / 게스트 파일 삭제 / Esc 기본 동작.

사용법
  uictl.py ping
  uictl.py shot [경로.png]
  uictl.py move <x> <y>
  uictl.py click <x> <y>
  uictl.py type "<글>"
  uictl.py key "{ENTER}"        # SendKeys 표기 (^v, %{TAB} ...)
  uictl.py paste <텍스트파일>    # 파일 내용을 게스트 클립보드로 (여러 줄은 반드시 이 경로)
  uictl.py clipget              # 게스트 클립보드를 되읽어 출력 (검증용)
  uictl.py winlist
"""

import argparse
import datetime as _dt
import os
import pathlib
import shlex
import subprocess
import sys
import time
import uuid

# 같은 scripts/ 안의 pmlab.sh 가 정본이다 — 스킬을 어디에 두든 따라간다.
PMLAB_SH = os.environ.get(
    "PMLAB_SH", str(pathlib.Path(__file__).resolve().parent / "pmlab.sh")
)
VM = os.environ.get("PMLAB_VM", "win11-parlab")
SHARE_DIR = pathlib.Path(os.environ.get("PMLAB_SHARE_DIR", os.path.expanduser("~/parlab")))
SHARE_NAME = os.environ.get("PMLAB_SHARE_NAME", "parlab")
SCRATCH = pathlib.Path(__file__).resolve().parent

ACT_PS1 = "uictl-act.ps1"      # 사용자 세션에서 돌 스크립트
ACK_TXT = "uictl-ack.txt"      # 게스트가 쓰는 결과 파일
ARG_TXT = "uictl-arg.txt"      # 호스트 → 게스트 문자열 페이로드(UTF-8)

GUEST_ACK = r"\\Mac\{}\{}".format(SHARE_NAME, ACK_TXT)
GUEST_ARG = r"\\Mac\{}\{}".format(SHARE_NAME, ARG_TXT)
GUEST_ACT = r"\\Mac\{}\{}".format(SHARE_NAME, ACT_PS1)

ACK_TIMEOUT = float(os.environ.get("UICTL_ACK_TIMEOUT", "45"))
POWERSHELL = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"


# ─────────────────────────── 호스트 쪽 유틸 ───────────────────────────

def _guard():
    if VM in ("Windows 11", "Windows 11 (강의용)"):
        sys.exit("uictl: 마스터 실사용 VM({}) 은 대상이 아닙니다 — win11-parlab 만 조작합니다".format(VM))


def pmlab(snippet, timeout=180):
    """pmlab.sh 를 source 한 bash 에서 셸 코드를 실행하고 (rc, stdout_bytes, stderr_text) 반환."""
    script = "source {} && export PMLAB_VM={} && {}".format(
        shlex.quote(PMLAB_SH), shlex.quote(VM), snippet
    )
    p = subprocess.run(["bash", "-c", script], capture_output=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr.decode("utf-8", "replace")


def decode_guest(data):
    """게스트 출력은 CP949 + CRLF 일 수 있다 — UTF-8 우선, 실패 시 CP949 로 정리."""
    if isinstance(data, str):
        text = data
    else:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("cp949", "replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def write_bom(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"\xef\xbb\xbf")
        f.write(text.encode("utf-8"))


def write_utf8(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(text.encode("utf-8"))


# ─────────────────────────── 게스트 스크립트 조립 ───────────────────────────

CSHARP = r"""
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;

public class UICtl {
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
  [DllImport("user32.dll")] public static extern bool GetCursorPos(out POINT p);
  [DllImport("user32.dll")] public static extern int GetSystemMetrics(int n);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern IntPtr WindowFromPoint(POINT p);

  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X; public int Y; }
  [StructLayout(LayoutKind.Sequential)] public struct MOUSEINPUT {
    public int dx; public int dy; public uint mouseData; public uint dwFlags;
    public uint time; public IntPtr dwExtraInfo; }
  [StructLayout(LayoutKind.Sequential)] public struct KEYBDINPUT {
    public ushort wVk; public ushort wScan; public uint dwFlags;
    public uint time; public IntPtr dwExtraInfo; }
  [StructLayout(LayoutKind.Explicit)] public struct INPUTUNION {
    [FieldOffset(0)] public MOUSEINPUT mi; [FieldOffset(0)] public KEYBDINPUT ki; }
  [StructLayout(LayoutKind.Sequential)] public struct INPUT { public uint type; public INPUTUNION u; }

  [DllImport("user32.dll", SetLastError = true)]
  public static extern uint SendInput(uint n, INPUT[] p, int cb);

  const uint INPUT_MOUSE = 0, INPUT_KEYBOARD = 1;
  const uint MOUSEEVENTF_MOVE_ABS = 0x8001;      // MOVE | ABSOLUTE
  const uint MOUSEEVENTF_LEFTDOWN = 0x0002, MOUSEEVENTF_LEFTUP = 0x0004;
  const uint KEYEVENTF_KEYUP = 0x0002, KEYEVENTF_UNICODE = 0x0004;

  public static string Move(int x, int y) {
    SetCursorPos(x, y);
    POINT p; GetCursorPos(out p);
    return p.X + "," + p.Y;
  }

  public static string Click(int x, int y) {
    SetCursorPos(x, y);
    System.Threading.Thread.Sleep(80);
    POINT p; GetCursorPos(out p);
    INPUT[] inp = new INPUT[2];
    inp[0].type = INPUT_MOUSE; inp[0].u.mi.dwFlags = MOUSEEVENTF_LEFTDOWN;
    inp[1].type = INPUT_MOUSE; inp[1].u.mi.dwFlags = MOUSEEVENTF_LEFTUP;
    uint sent = SendInput(2, inp, Marshal.SizeOf(typeof(INPUT)));
    return p.X + "," + p.Y + " sent=" + sent;
  }

  static void SendChar(ushort scan, ushort vk, bool unicode) {
    INPUT[] inp = new INPUT[2];
    inp[0].type = INPUT_KEYBOARD;
    inp[1].type = INPUT_KEYBOARD;
    if (unicode) {
      inp[0].u.ki.wScan = scan; inp[0].u.ki.dwFlags = KEYEVENTF_UNICODE;
      inp[1].u.ki.wScan = scan; inp[1].u.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP;
    } else {
      inp[0].u.ki.wVk = vk;
      inp[1].u.ki.wVk = vk; inp[1].u.ki.dwFlags = KEYEVENTF_KEYUP;
    }
    SendInput(2, inp, Marshal.SizeOf(typeof(INPUT)));
  }

  // 임의 유니코드(한글 포함)를 IME 없이 그대로 주입한다.
  public static string TypeUnicode(string s, int delayMs) {
    int n = 0;
    foreach (char c in s) {
      if (c == '\r') continue;
      if (c == '\n') SendChar(0, 0x0D, false);   // VK_RETURN
      else if (c == '\t') SendChar(0, 0x09, false);
      else SendChar((ushort)c, 0, true);
      n++;
      if (delayMs > 0) System.Threading.Thread.Sleep(delayMs);
    }
    return n.ToString();
  }

  public static string Screen() {
    POINT p; GetCursorPos(out p);
    return "screen=" + GetSystemMetrics(0) + "x" + GetSystemMetrics(1)
         + " virtual=" + GetSystemMetrics(78) + "x" + GetSystemMetrics(79)
         + " cursor=" + p.X + "," + p.Y;
  }

  // ── 창 목록 ──
  delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowTextLength(IntPtr h);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }

  public static string WinList() {
    IntPtr fg = GetForegroundWindow();
    List<string> rows = new List<string>();
    EnumWindows(delegate(IntPtr h, IntPtr l) {
      if (!IsWindowVisible(h)) return true;
      int len = GetWindowTextLength(h);
      if (len <= 0) return true;
      StringBuilder sb = new StringBuilder(len + 2);
      GetWindowText(h, sb, sb.Capacity);
      RECT r; GetWindowRect(h, out r);
      rows.Add((h == fg ? "*" : " ") + " 0x" + h.ToInt64().ToString("X")
               + "\t" + r.L + "," + r.T + "," + (r.R - r.L) + "x" + (r.B - r.T)
               + "\t" + sb.ToString());
      return true;
    }, IntPtr.Zero);
    return string.Join("\n", rows.ToArray());
  }
}
"""


def build_action_ps1(token, body):
    """사용자 세션에서 돌 .ps1 본문. 결과는 무조건 ack 파일에 쓴다(성공/실패 모두)."""
    return "\n".join([
        "$ErrorActionPreference = 'Stop'",
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8",
        "$ack = '{}'".format(GUEST_ACK),
        "$argfile = '{}'".format(GUEST_ARG),
        "$token = '{}'".format(token),
        "$status = 'FAIL'",
        "$payload = ''",
        "try {",
        "  Add-Type -TypeDefinition @'",
        CSHARP,
        "'@",
        "  [void][UICtl]::SetProcessDPIAware()",
        "  $utf8r = New-Object System.Text.UTF8Encoding($false)",
        "  function Get-Arg { [IO.File]::ReadAllText($argfile, [System.Text.Encoding]::UTF8) }",
        body,
        "  $status = 'OK'",
        "} catch {",
        "  $payload = 'ERR: ' + $_.Exception.Message",
        "}",
        "$enc = New-Object System.Text.UTF8Encoding($false)",
        "[IO.File]::WriteAllText($ack, $token + \"`n\" + $status + \"`n\" + $payload, $enc)",
        "",
    ])


def run_in_user_session(body, timeout=ACK_TIMEOUT, note=""):
    """.ps1 을 공유에 쓰고 pmlab_open_app 으로 사용자 세션에서 실행 → ack 확인.

    반환 (status, payload). ack 미확인 시 SystemExit(비영).
    """
    _guard()
    token = uuid.uuid4().hex
    ack_path = SHARE_DIR / ACK_TXT
    try:
        ack_path.unlink()
    except FileNotFoundError:
        pass

    write_bom(SHARE_DIR / ACT_PS1, build_action_ps1(token, body))

    arg = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File {}".format(GUEST_ACT)
    rc, out, err = pmlab(
        "pmlab_open_app {} {}".format(shlex.quote(POWERSHELL), shlex.quote(arg))
    )
    if rc != 0:
        sys.exit("uictl: pmlab_open_app rc={} — {}".format(rc, (decode_guest(out) + err).strip()))

    deadline = time.time() + timeout
    while time.time() < deadline:
        if ack_path.exists():
            raw = ack_path.read_bytes()
            text = decode_guest(raw).lstrip("\ufeff")
            lines = text.split("\n")
            if lines and lines[0].strip() == token:
                status = lines[1].strip() if len(lines) > 1 else "FAIL"
                payload = "\n".join(lines[2:]).rstrip("\n")
                if status != "OK":
                    sys.exit("uictl: 게스트 실행 실패{} — {}".format(note, payload))
                return status, payload
        time.sleep(0.25)

    sys.exit(
        "uictl: ack 미확인({:.0f}초 초과){} — pmlab_open_app 이 조용히 실패했거나 "
        "콘솔 세션이 잠겼습니다. `uictl.py ping` 으로 확인하세요.".format(timeout, note)
    )


# ─────────────────────────── 명령 ───────────────────────────

def cmd_ping(args):
    _guard()
    rc, out, _ = pmlab("pmlab_state")
    state = decode_guest(out).strip()
    print("VM        : {} ({})".format(VM, state or "unknown"))
    if state != "running":
        sys.exit("uictl: VM 이 running 이 아닙니다 — 중단")

    rc, out, err = pmlab("pmlab_exec cmd /c qwinsta")
    if rc != 0:
        sys.exit("uictl: qwinsta 실패 — {}".format(err.strip()))
    console_line, active = None, False
    for line in decode_guest(out).split("\n"):
        t = line.replace(">", " ").split()
        if t and t[0] == "console":
            console_line = line.strip()
            active = any(x in ("활성", "Active") for x in t)
    print("qwinsta   : {}".format(console_line or "(console 세션 없음)"))
    print("콘솔 세션 : {}".format("Active" if active else "NOT Active"))
    if not active:
        sys.exit("uictl: 콘솔 세션이 Active 가 아닙니다 — 입력 명령이 닿지 않습니다")

    _, payload = run_in_user_session("  $payload = [UICtl]::Screen()", note="(ping 왕복)")
    print("사용자세션: OK — {}".format(payload))
    return 0


def cmd_shot(args):
    _guard()
    if args.path:
        dest = pathlib.Path(args.path).expanduser().resolve()
    else:
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = SCRATCH / "shot-{}.png".format(stamp)
    dest.parent.mkdir(parents=True, exist_ok=True)
    rc, out, err = pmlab("pmlab_capture {}".format(shlex.quote(str(dest))))
    if rc != 0 or not dest.exists():
        sys.exit("uictl: 캡처 실패 rc={} — {}".format(rc, err.strip()))
    size = ""
    try:
        with open(dest, "rb") as f:
            head = f.read(33)
        if head[:8] == b"\x89PNG\r\n\x1a\n":
            w = int.from_bytes(head[16:20], "big")
            h = int.from_bytes(head[20:24], "big")
            size = " {}x{}".format(w, h)
    except OSError:
        pass
    nbytes = dest.stat().st_size
    print("{} ({} bytes{})".format(dest, nbytes, size))
    if nbytes < 30000:
        sys.stderr.write(
            "uictl: 경고 — 캡처가 비정상적으로 작습니다({} bytes). 게스트 화면이 절전으로 "
            "꺼졌을 수 있습니다. `uictl.py move <x> <y>` 로 깨운 뒤 다시 찍으세요.\n".format(nbytes)
        )
    return 0


def cmd_move(args):
    _, payload = run_in_user_session(
        "  $payload = [UICtl]::Move({}, {}) + ' | ' + [UICtl]::Screen()".format(args.x, args.y),
        note="(move)",
    )
    print("move -> {}".format(payload))
    return 0


def cmd_click(args):
    _, payload = run_in_user_session(
        "  $payload = [UICtl]::Click({}, {})".format(args.x, args.y), note="(click)"
    )
    print("click -> {}".format(payload))
    return 0


def cmd_type(args):
    write_utf8(SHARE_DIR / ARG_TXT, args.text)
    _, payload = run_in_user_session(
        "  $s = Get-Arg\n  $payload = 'chars=' + [UICtl]::TypeUnicode($s, {})".format(args.delay),
        note="(type)",
    )
    print("type -> {}".format(payload))
    return 0


def cmd_key(args):
    write_utf8(SHARE_DIR / ARG_TXT, args.keys)
    body = "\n".join([
        "  Add-Type -AssemblyName System.Windows.Forms",
        "  $s = Get-Arg",
        "  [System.Windows.Forms.SendKeys]::SendWait($s)",
        "  Start-Sleep -Milliseconds 120",
        "  $payload = 'keys=' + $s",
    ])
    _, payload = run_in_user_session(body, note="(key)")
    print("key -> {}".format(payload))
    return 0


def cmd_paste(args):
    src = pathlib.Path(args.file).expanduser()
    if not src.is_file():
        sys.exit("uictl: 파일 없음 — {}".format(src))
    text = src.read_bytes().decode("utf-8", "replace")
    write_utf8(SHARE_DIR / ARG_TXT, text)
    body = "\n".join([
        "  $s = Get-Arg",
        "  Set-Clipboard -Value $s",
        "  Start-Sleep -Milliseconds 150",
        "  $back = Get-Clipboard -Raw",
        "  if ($null -eq $back) { throw '클립보드 설정 후 되읽기 실패' }",
        "  $payload = 'chars=' + $s.Length + ' lines=' + ($s -split \"`n\").Count +"
        " ' clipchars=' + $back.Length",
    ])
    _, payload = run_in_user_session(body, note="(paste)")
    print("paste -> {}".format(payload))
    return 0


def cmd_clipget(args):
    body = "\n".join([
        "  $c = Get-Clipboard -Raw",
        "  if ($null -eq $c) { $c = '' }",
        "  $payload = $c",
    ])
    _, payload = run_in_user_session(body, note="(clipget)")
    sys.stdout.write(payload + ("\n" if not payload.endswith("\n") else ""))
    return 0


def cmd_winlist(args):
    _, payload = run_in_user_session("  $payload = [UICtl]::WinList()", note="(winlist)")
    print(payload)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="uictl.py", description="Parallels 게스트(win11-parlab) GUI 좌표 조작"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ping", help="게스트·콘솔 세션·사용자 세션 왕복 확인").set_defaults(fn=cmd_ping)

    p = sub.add_parser("shot", help="화면 캡처")
    p.add_argument("path", nargs="?", help="저장할 png 경로(생략 시 스크래치패드)")
    p.set_defaults(fn=cmd_shot)

    p = sub.add_parser("move", help="커서 이동(클릭 없음)")
    p.add_argument("x", type=int); p.add_argument("y", type=int)
    p.set_defaults(fn=cmd_move)

    p = sub.add_parser("click", help="좌표 좌클릭")
    p.add_argument("x", type=int); p.add_argument("y", type=int)
    p.set_defaults(fn=cmd_click)

    p = sub.add_parser("type", help="문자열 입력(한글 포함, SendInput 유니코드)")
    p.add_argument("text")
    p.add_argument("--delay", type=int, default=8, help="글자 간 지연 ms (기본 8)")
    p.set_defaults(fn=cmd_type)

    p = sub.add_parser("key", help="SendKeys 표기 키 입력 ({ENTER}, ^v, %%{TAB} …)")
    p.add_argument("keys")
    p.set_defaults(fn=cmd_key)

    p = sub.add_parser("paste", help="텍스트 파일 내용을 게스트 클립보드에 넣는다")
    p.add_argument("file")
    p.set_defaults(fn=cmd_paste)

    sub.add_parser("clipget", help="게스트 클립보드를 되읽어 출력").set_defaults(fn=cmd_clipget)
    sub.add_parser("winlist", help="보이는 창 목록(핸들·위치·제목)").set_defaults(fn=cmd_winlist)

    args = ap.parse_args(argv)
    return args.fn(args) or 0


if __name__ == "__main__":
    sys.exit(main())
