"""robots.py — robots.txt 판독(RFC 9309). 네트워크 없음.

web-reader 8.0.0(itda-work/skills#46, 사용자 결정 D1-A): 호스트마다 robots.txt 를 먼저 받아
``User-agent: *`` 규칙으로 불허면 멈춘다. 우리는 User-Agent 에 신원을 싣지 않으므로(규칙
``outbound-identity-leak``) 사이트가 우리에게 적용하는 규칙은 ``*`` 무리다.

``urllib.robotparser`` 를 쓰지 않는다 — 모듈 안에서 ``urllib.request`` 를 import 한다(스크립트는
네트워크 모듈을 싣지 않는다, 가드 ``scripts/tests/test_no_direct_network.py``).

판정:
- ``User-agent: *`` 를 가진 무리를 모두 합친다. 그런 무리가 없으면 전부 허용.
- 가장 긴 일치가 이긴다(패턴 길이, 퍼센트 정규화 뒤 옥텟 수). 길이가 같으면 Allow 가 이긴다.
- ``*``(아무 문자열)·``$``(끝) 지원. 빈 ``Disallow:`` 는 규칙이 아니다. ``/robots.txt`` 는 늘 허용.
- 경로는 ``path?query`` 로 비교한다. ``..``·``.`` 세그먼트를 푼 형태와 원형 **둘 다** 검사해 어느 쪽이든
  불허면 불허다(``/a/../api/`` 로 ``/api/`` 불허를 비껴가지 못하게).
- 규칙의 ``*``·끝 ``$`` 는 문법이고, 규칙의 ``%2A``·``%24`` 는 리터럴 글자다. 요청 URI 의 리터럴 ``*``·``$`` 는
  ``%2A``·``%24`` 로 바꿔 견준다 — 그래야 ``Disallow: /path/foo-%24`` 가 ``/path/foo-$`` 를 막는다(RFC 9309 §2.2.3
  Figure 6, 리뷰 W-4). 규칙 가운데의 ``$``(끝이 아닌 것)는 앵커가 아니므로 리터럴 ``%24`` 로 읽는다.
- 쿼리 안의 ``:`` ``/`` ``?`` ``@`` 는 데이터일 뿐 구분자 역할이 없어(RFC 3986 §3.4) 글자 그대로와 ``%XX`` 가 같은 값이다.
  RFC 9309 §2.2.2 Figure 4 는 ``?baz=https://foo.bar`` 를 ``?baz=https%3A%2F%2Ffoo.bar`` 로 견준다. 이 꼴은 **추가 관점**으로
  견준다 — 규칙·요청 양쪽 쿼리의 그 글자를 ``%XX`` 로 맞춘 판에서도 판정하고, 어느 관점이든 불허면 불허다(원래 판정을 좁히지 않는다).
"""
from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass, field

_UNRESERVED = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
_RESERVED = set(":/?#[]@!$&'()*+,;=")  # RFC 3986 gen-delims + sub-delims — 인코딩된 채와 글자 그대로를 다른 것으로 둔다


@dataclass(frozen=True)
class Rule:
    allow: bool
    pattern: str   # 퍼센트 정규화한 패턴
    raw: str       # 파일에 적힌 그대로(사유 줄에 싣는다)
    line: int


@dataclass
class Robots:
    rules: list[Rule] = field(default_factory=list)
    has_star_group: bool = False

    def decide(self, url_or_path: str) -> tuple[bool, Rule | None]:
        """``(허용 여부, 이긴 규칙)``. 일치 규칙이 없으면 ``(True, None)``."""
        target = _target(url_or_path)
        if target == "/robots.txt":
            return True, None
        verdicts = [_best(self.rules, t, view) for t in _candidates(target) for view in (_plain, _query_data_encoded)]
        for allowed, rule in verdicts:
            if not allowed:
                return False, rule
        return verdicts[0]


def normalize(s: str) -> str:
    """퍼센트 정규화(RFC 9309 §2.2.2) — 예약되지 않은 문자의 ``%XX`` 는 풀고, 나머지는 대문자 16진으로.
    비ASCII·공백·URI 에 쓸 수 없는 ASCII(``|`` ``"`` ``{`` 등 — 예약도 비예약도 아닌 글자)는 ``%XX`` 로 인코딩한다.
    그래야 규칙 ``/a|b`` 와 요청 ``/a%7Cb``(Go 는 ``|`` 를 늘 ``%7C`` 로 보낸다)가 같은 것으로 견주어진다(리뷰 W-3 동반)."""
    out: list[str] = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "%" and re.fullmatch(r"[0-9A-Fa-f]{2}", s[i + 1:i + 3]):
            byte = int(s[i + 1:i + 3], 16)
            c = chr(byte)
            out.append(c if byte < 0x80 and c in _UNRESERVED else "%" + s[i + 1:i + 3].upper())
            i += 3
            continue
        if ord(ch) >= 0x80 or (ch not in _UNRESERVED and ch not in _RESERVED and ch != "%"):
            out.append(urllib.parse.quote(ch, safe=""))
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def _target(url_or_path: str) -> str:
    if "://" in url_or_path:
        parts = urllib.parse.urlsplit(url_or_path)
        path, query = parts.path, parts.query
    else:
        path, _, query = url_or_path.partition("?")
    path = path or "/"
    # 요청의 리터럴 `*`·`$` 는 규칙 문법이 아니라 글자다 — 규칙의 `%2A`·`%24` 와 견주도록 인코딩한다(RFC 9309 Figure 6)
    return normalize(path + ("?" + query if query else "")).replace("*", "%2A").replace("$", "%24")


def _pattern_literal(pattern: str) -> str:
    """규칙 패턴의 끝이 아닌 ``$`` 는 앵커가 아니다 — 요청 쪽과 같이 ``%24`` 로. ``*`` 는 늘 와일드카드."""
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    return body.replace("$", "%24") + ("$" if anchored else "")


_QUERY_DATA = {":": "%3A", "/": "%2F", "?": "%3F", "@": "%40"}


def _plain(s: str) -> str:
    return s


def _query_data_encoded(s: str) -> str:
    """첫 ``?`` 뒤(쿼리)의 ``:`` ``/`` ``?`` ``@`` 를 ``%XX`` 로 — RFC 9309 Figure 4 의 비교 꼴. 규칙·요청에 똑같이 쓴다."""
    head, sep, query = s.partition("?")
    if not sep:
        return s
    return head + sep + "".join(_QUERY_DATA.get(ch, ch) for ch in query)


def _remove_dot_segments(path: str) -> str:
    """RFC 3986 5.2.4 — 쿼리는 건드리지 않는다."""
    p, sep, q = path.partition("?")
    segs: list[str] = []
    for seg in p.split("/"):
        if seg == "..":
            if len(segs) > 1:
                segs.pop()
        elif seg != ".":
            segs.append(seg)
    out = "/".join(segs)
    if p.endswith(("/.", "/..")):
        out += "/"
    if not out.startswith("/"):
        out = "/" + out
    return out + sep + q


def _candidates(target: str) -> list[str]:
    cands = [target]
    dotless = _remove_dot_segments(target)
    if dotless != target:
        cands.append(dotless)
    return cands


def _match(pattern: str, target: str) -> bool:
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    if "*" not in body and not anchored:
        return target.startswith(body)
    regex = "".join(".*" if ch == "*" else re.escape(ch) for ch in body)
    return re.match(regex + ("$" if anchored else ""), target, re.DOTALL) is not None


def _best(rules: list[Rule], target: str, view=_plain) -> tuple[bool, Rule | None]:
    best: Rule | None = None
    best_len = -1
    target = view(target)
    for rule in rules:
        pattern = view(_pattern_literal(rule.pattern))
        if not _match(pattern, target):
            continue
        if best is None or len(pattern) > best_len or (len(pattern) == best_len and rule.allow and not best.allow):
            best, best_len = rule, len(pattern)
    if best is None:
        return True, None
    return best.allow, best


def parse(text: str) -> Robots:
    """robots.txt 본문을 읽어 ``*`` 무리의 규칙을 모은다."""
    robots = Robots()
    text = text.lstrip("\ufeff")  # UTF-8 BOM — 첫 줄 키에 붙으면 `User-agent: *` 무리가 열리지 않는다(W14 리뷰 M2)
    agents: list[str] = []
    in_rules = False  # 규칙 줄을 만난 뒤의 user-agent 는 새 무리를 연다
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower().replace("_", "-")
        value = value.strip()
        if key in ("user-agent", "useragent"):
            if in_rules:
                agents = []
                in_rules = False
            agents.append(value.lower())
            continue
        if key not in ("allow", "disallow"):
            continue  # sitemap·crawl-delay 등 — 무리를 끝내지 않는다
        in_rules = True
        if "*" not in agents:
            continue
        robots.has_star_group = True
        if not value:
            continue  # 빈 Disallow = 규칙 없음
        robots.rules.append(Rule(allow=(key == "allow"), pattern=normalize(value), raw=f"{key.capitalize()}: {value}", line=lineno))
    if not robots.has_star_group and any(a == "*" for a in agents):
        robots.has_star_group = True
    return robots
