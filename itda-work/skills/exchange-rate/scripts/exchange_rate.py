"""Exchange rate lookup script for the exchange-rate skill.

Fetches Korean won (KRW) exchange rates from Seoul Money Brokerage Services
(서울외국환중개, SMBS) and provides daily and monthly average rates for 53
supported currencies.

Usage:
    python3 exchange_rate.py --date 2025-01-05 --currency USD
    python3 exchange_rate.py --date 2025.01.05 --currency JPY
    python3 exchange_rate.py --month 2025-01 --currency EUR
    python3 exchange_rate.py --month 2025-01
    python3 exchange_rate.py --date 2025-01-05
"""
from __future__ import annotations

import argparse
import datetime
import json
import logging
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

# Default paths relative to this script
_SCRIPT_DIR = Path(__file__).parent
_SKILL_DIR = _SCRIPT_DIR.parent
_DATA_DIR = _SKILL_DIR / "data"
_CURRENCIES_FILE = _DATA_DIR / "currencies.json"
_DEFAULT_CACHE_DIR = Path(tempfile.mkdtemp(prefix="skill-"))

# SMBS API endpoints
_DAILY_URL = "http://www.smbs.biz/ExRate/StdExRate_xml.jsp?arr_value={currency}_{start}_{end}"
_MONTHLY_USD_URL = "http://www.smbs.biz/ExRate/MonAvgStdExRateUSD_xml.jsp?arr_value=USD_{start}_{end}"
_MONTHLY_OTHER_URL = "http://www.smbs.biz/ExRate/MonAvgStdExRate_xml.jsp?arr_value={currency}_{start}_{end}"

# Cache for loaded currencies (module-level singleton)
_currencies_cache: list[dict[str, Any]] | None = None

_logger = logging.getLogger(__name__)


def _get_default_cache_dir() -> Path:
    """Return the default cache directory path.

    This function is a seam for testing: tests can patch it to use a tmp_path.
    """
    return _DEFAULT_CACHE_DIR


def load_currencies() -> list[dict[str, Any]]:
    """Load and cache the currencies.json data.

    Returns:
        List of currency dicts with code, name_ko, name_en, unit, aliases_ko.
    """
    global _currencies_cache
    if _currencies_cache is None:
        with open(_CURRENCIES_FILE, encoding="utf-8") as f:
            data = json.load(f)
        # Support both top-level list and dict with 'currencies' key
        if isinstance(data, dict):
            _currencies_cache = data.get("currencies", []) or []
        else:
            _currencies_cache = data or []
    assert _currencies_cache is not None
    return _currencies_cache


def find_currency(query: str) -> dict[str, Any] | None:
    """Find a currency entry by code or Korean alias.

    Args:
        query: Currency code (e.g., "USD") or Korean alias (e.g., "달러").
               Lookup is case-insensitive for codes.

    Returns:
        Currency dict or None if not found.
    """
    currencies = load_currencies()
    query_upper = query.upper()
    query_stripped = query.strip()

    for currency in currencies:
        # Match by currency code (case-insensitive)
        if currency["code"].upper() == query_upper:
            return currency
        # Match by Korean alias
        aliases = currency.get("aliases_ko", [])
        if query_stripped in aliases:
            return currency

    return None


def parse_input(value: str) -> tuple[str, datetime.date | tuple[int, int]]:
    """Parse a date or month string into (mode, parsed_value).

    Supported formats:
        - YYYY-MM-DD or YYYY.MM.DD  -> ("daily", date(YYYY, MM, DD))
        - YYYY-MM                   -> ("monthly", (YYYY, MM))

    Args:
        value: Date or month string to parse.

    Returns:
        Tuple of (mode, parsed_value) where mode is "daily" or "monthly".

    Raises:
        ValueError: If the input format is not recognized or invalid.
    """
    value = value.strip()

    # Normalize dot separator to hyphen
    normalized = value.replace(".", "-")

    parts = normalized.split("-")

    if len(parts) == 3:
        # Daily format: YYYY-MM-DD
        try:
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
            return "daily", datetime.date(year, month, day)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"올바르지 않은 날짜 형식입니다: '{value}'. YYYY-MM-DD 또는 YYYY.MM.DD 형식을 사용하세요."
            ) from exc

    elif len(parts) == 2:
        # Monthly format: YYYY-MM
        try:
            year, month = int(parts[0]), int(parts[1])
            if not (1 <= month <= 12):
                raise ValueError(f"올바르지 않은 월: {month}")
            return "monthly", (year, month)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"올바르지 않은 월 형식입니다: '{value}'. YYYY-MM 형식을 사용하세요."
            ) from exc

    else:
        raise ValueError(
            f"올바르지 않은 입력 형식입니다: '{value}'. "
            "YYYY-MM-DD, YYYY.MM.DD, 또는 YYYY-MM 형식을 사용하세요."
        )


def build_url(currency_code: str, year: int, query_type: str) -> str:
    """Build the SMBS API URL for fetching exchange rate data.

    Args:
        currency_code: ISO 4217 currency code (e.g., "USD", "JPY").
        year: The year to fetch data for (full year Jan 1 - Dec 31).
        query_type: "daily" for daily rates, "monthly" for monthly averages.

    Returns:
        Full URL string for the SMBS API request.
    """
    start_year = f"{year}-01"
    end_year = f"{year}-12"

    if query_type == "daily":
        start = f"{year}-01-01"
        end = f"{year}-12-31"
        return _DAILY_URL.format(currency=currency_code, start=start, end=end)
    elif query_type == "monthly":
        if currency_code == "USD":
            return _MONTHLY_USD_URL.format(start=start_year, end=end_year)
        else:
            return _MONTHLY_OTHER_URL.format(
                currency=currency_code, start=start_year, end=end_year
            )
    else:
        raise ValueError(f"올바르지 않은 쿼리 타입: '{query_type}'")


def parse_xml_response(xml_bytes: bytes, query_type: str) -> dict[str, str]:
    """Parse the SMBS FusionCharts XML response into a rates dictionary.

    The SMBS API returns EUC-KR encoded XML with FusionCharts format:
        - Daily: <set label='YY.MM.DD' value='1470' />  (2-digit year)
        - Monthly: <set label='YYYY.MM' value='1455.79' />

    Args:
        xml_bytes: Raw bytes from the HTTP response (EUC-KR encoded).
        query_type: "daily" or "monthly" to select label parsing mode.

    Returns:
        Dict mapping date/month string to rate string.
        Daily: {"2025-01-02": "1470", ...}
        Monthly: {"2025-01": "1455.79", ...}
    """
    # Decode EUC-KR response
    xml_str = xml_bytes.decode("euc-kr", errors="replace").strip()

    # Parse XML
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return {}

    rates: dict[str, str] = {}

    for elem in root.iter("set"):
        label = elem.get("label", "")
        value = elem.get("value", "")

        if not label or not value:
            continue

        # Convert label to standard key format
        if query_type == "daily":
            # Label is "YY.MM.DD" -> convert to "20YY-MM-DD"
            parts = label.split(".")
            if len(parts) == 3:
                yy, mm, dd = parts
                full_year = f"20{yy}"
                key = f"{full_year}-{mm}-{dd}"
                rates[key] = value
        elif query_type == "monthly":
            # Label is "YYYY.MM" -> convert to "YYYY-MM"
            parts = label.split(".")
            if len(parts) == 2:
                yyyy, mm = parts
                key = f"{yyyy}-{mm}"
                rates[key] = value

    return rates


def get_cache_path(cache_dir: Path, currency_code: str, year: int, query_type: str) -> Path:
    """Build the cache file path for a given currency/year/type combination.

    Args:
        cache_dir: Base cache directory.
        currency_code: ISO 4217 currency code.
        year: Year for the data.
        query_type: "daily" or "monthly".

    Returns:
        Path object for the cache file (e.g., cache_dir/USD_2025_daily.json).
    """
    filename = f"{currency_code}_{year}_{query_type}.json"
    return cache_dir / filename


def save_cache(
    path: Path,
    currency_code: str,
    year: int,
    query_type: str,
    rates: dict[str, str],
) -> None:
    """Save exchange rate data to a JSON cache file.

    Cache format:
        {
          "metadata": {
            "currency": "USD",
            "year": 2025,
            "type": "daily",
            "fetched_at": "2026-03-11T09:30:00+09:00"
          },
          "rates": {
            "2025-01-02": "1470"
          }
        }

    Args:
        path: Destination file path.
        currency_code: ISO 4217 currency code.
        year: Year for the data.
        query_type: "daily" or "monthly".
        rates: Dict mapping date/month key to rate string.
    """
    now = datetime.datetime.now().astimezone()
    fetched_at = now.isoformat(timespec="seconds")

    cache_data = {
        "metadata": {
            "currency": currency_code,
            "year": year,
            "type": query_type,
            "fetched_at": fetched_at,
        },
        "rates": {str(k): str(v) for k, v in rates.items()},
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, indent=2, ensure_ascii=False)


def load_cache(path: Path) -> dict[str, Any] | None:
    """Load cache data from a JSON file.

    Args:
        path: Path to the cache file.

    Returns:
        Dict with "metadata" and "rates" keys, or None if file does not exist.
    """
    if not path.exists():
        return None

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        return None

    # Ensure rate keys and values are strings
    if "rates" in data and isinstance(data["rates"], dict):
        data["rates"] = {str(k): str(v) for k, v in data["rates"].items()}

    return data


# @MX:ANCHOR: [AUTO] Central cache-first fetch coordinator — called by get_daily_rate, get_monthly_rate, build_cache_entry (fan_in=3)
# @MX:REASON: All rate retrieval paths must flow through this function to ensure cache consistency
# @MX:SPEC: SPEC-EXRATE-001 FR-004
def fetch_rates(
    currency_code: str,
    year: int,
    query_type: str,
    cache_dir: Path,
    skip_cache: bool = False,
) -> dict[str, str]:
    """Fetch exchange rates with cache-first strategy.

    Checks for a local cache file first. On cache miss, fetches from SMBS API
    and saves the result to cache. Always fetches a full year of data.

    Args:
        currency_code: ISO 4217 currency code.
        year: Year to fetch data for.
        query_type: "daily" or "monthly".
        cache_dir: Directory for cache files.
        skip_cache: If True, bypass cache and always fetch from API.

    Returns:
        Dict mapping date/month string to rate string.
    """
    cache_path = get_cache_path(cache_dir, currency_code, year, query_type)

    # Return cached data if available and not skipping
    if not skip_cache:
        cached = load_cache(cache_path)
        if cached is not None:
            _logger.debug("[cache:hit] %s %s %s ← %s", currency_code, year, query_type, cache_path)
            return cached["rates"]

    # Fetch from SMBS API
    url = build_url(currency_code, year, query_type)
    _logger.debug("[http:fetch] %s %s %s → %s", currency_code, year, query_type, url)
    with urllib.request.urlopen(url) as response:  # noqa: S310
        xml_bytes = response.read()

    rates = parse_xml_response(xml_bytes, query_type)

    # Save to cache for future use
    save_cache(cache_path, currency_code, year, query_type, rates)
    _logger.debug("[cache:save] %s %s %s → %s (%d entries)", currency_code, year, query_type, cache_path, len(rates))

    return rates


def get_daily_rate(
    requested_date: datetime.date,
    currency: dict[str, Any],
    cache_dir: Path,
) -> tuple[datetime.date, str, bool]:
    """Get the daily exchange rate with business day fallback.

    Fetches the full year cache and looks up the rate for the requested date.
    If the date has no data (weekend/holiday), iterates backwards to find
    the most recent available rate. If Jan 1 and no prior date found in
    current year, loads previous year's cache.

    Args:
        requested_date: The date to look up the rate for.
        currency: Currency dict from find_currency().
        cache_dir: Cache directory path.

    Returns:
        Tuple of (result_date, rate_string, is_fallback) where is_fallback
        indicates the result date differs from requested_date.

    Raises:
        ValueError: If no rate can be found after exhaustive search.
    """
    currency_code = currency["code"]
    year = requested_date.year

    rates = fetch_rates(currency_code, year, "daily", cache_dir)

    # Try to find the rate by iterating backwards from requested_date
    current = requested_date
    while current.year == year:
        key = current.strftime("%Y-%m-%d")
        if key in rates:
            is_fallback = current != requested_date
            return current, rates[key], is_fallback
        current -= datetime.timedelta(days=1)

    # No rate found in current year, try previous year
    prev_year = year - 1
    prev_rates = fetch_rates(currency_code, prev_year, "daily", cache_dir)

    # Find the last available date in previous year
    prev_date = datetime.date(prev_year, 12, 31)
    while prev_date.year == prev_year:
        key = prev_date.strftime("%Y-%m-%d")
        if key in prev_rates:
            return prev_date, prev_rates[key], True
        prev_date -= datetime.timedelta(days=1)

    raise ValueError(
        f"{requested_date} 이전의 환율 데이터를 찾을 수 없습니다. ({currency_code})"
    )


def get_monthly_rate(
    year: int,
    month: int,
    currency: dict[str, Any],
    cache_dir: Path,
) -> tuple[str, str]:
    """Get the monthly average exchange rate.

    Args:
        year: Year for the monthly rate.
        month: Month number (1-12).
        currency: Currency dict from find_currency().
        cache_dir: Cache directory path.

    Returns:
        Tuple of (month_key, rate_string) where month_key is "YYYY-MM".

    Raises:
        ValueError: If no rate is found for the requested month.
    """
    currency_code = currency["code"]
    rates = fetch_rates(currency_code, year, "monthly", cache_dir)

    month_key = f"{year}-{month:02d}"
    if month_key not in rates:
        raise ValueError(
            f"{year}년 {month}월의 월평균 환율 데이터를 찾을 수 없습니다. ({currency_code})"
        )

    return month_key, rates[month_key]


def _format_rate_display(rate_str: str) -> str:
    """Format rate value for display with thousands separator.

    Args:
        rate_str: Raw rate value string.

    Returns:
        Formatted rate string (e.g., "1,468.3").
    """
    try:
        value = float(rate_str)
        formatted = f"{value:,.2f}"
        # Remove unnecessary trailing zeros after decimal
        if "." in formatted:
            formatted = formatted.rstrip("0").rstrip(".")
        return formatted
    except ValueError:
        return rate_str


def _weekday_ko(date: datetime.date) -> str:
    """Return Korean weekday abbreviation for a date.

    Args:
        date: Date to get weekday for.

    Returns:
        Korean weekday string (e.g., "월", "화", ..., "일").
    """
    weekdays = ["월", "화", "수", "목", "금", "토", "일"]
    return weekdays[date.weekday()]


def format_daily_output(
    requested_date: datetime.date,
    result_date: datetime.date,
    rate: str,
    currency: dict[str, Any],
    is_fallback: bool,
) -> str:
    """Format the daily rate lookup result for display.

    Args:
        requested_date: The originally requested date.
        result_date: The actual date the rate is for (may differ on fallback).
        rate: Raw rate string from cache.
        currency: Currency dict from find_currency().
        is_fallback: True if result_date differs from requested_date.

    Returns:
        Formatted markdown string for display.
    """
    code = currency["code"]
    name_ko = currency["name_ko"]
    unit = currency["unit"]
    formatted_rate = _format_rate_display(rate)
    result_weekday = _weekday_ko(result_date)

    if unit == 100:
        rate_label = f"{formatted_rate} KRW / 100 {code}"
    else:
        rate_label = f"{formatted_rate} KRW/{code}"

    lines = ["# 매매기준율 조회 결과", ""]

    if is_fallback:
        req_weekday = _weekday_ko(requested_date)
        lines.extend([
            f"📅 요청일: {requested_date} ({req_weekday})",
            f"💱 통화: {name_ko} ({code})",
            "",
            f"⚠️ {requested_date}는 휴일로 환율 데이터가 없습니다.",
            f"→ 직전 영업일 {result_date} ({result_weekday}) 환율을 적용합니다.",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| 매매기준율 | {rate_label} |",
            f"| 기준일 | {result_date} ({result_weekday}) |",
        ])
    else:
        lines.extend([
            f"📅 조회일: {result_date} ({result_weekday})",
            f"💱 통화: {name_ko} ({code})",
            "",
            "| 항목 | 값 |",
            "|------|-----|",
            f"| 매매기준율 | {rate_label} |",
            f"| 기준일 | {result_date} |",
        ])

    lines.extend([
        "",
        "---",
        "*출처: 서울외국환중개 (www.smbs.biz)*",
    ])

    return "\n".join(lines)


def format_monthly_output(
    year: int,
    month: int,
    rate: str,
    currency: dict[str, Any],
) -> str:
    """Format the monthly average rate lookup result for display.

    Args:
        year: Year for the monthly rate.
        month: Month number (1-12).
        rate: Raw rate string from cache.
        currency: Currency dict from find_currency().

    Returns:
        Formatted markdown string for display.
    """
    code = currency["code"]
    name_ko = currency["name_ko"]
    unit = currency["unit"]
    formatted_rate = _format_rate_display(rate)

    if unit == 100:
        rate_label = f"{formatted_rate} KRW / 100 {code}"
    else:
        rate_label = f"{formatted_rate} KRW/{code}"

    lines = [
        "# 월평균 매매기준율 조회 결과",
        "",
        f"📅 조회월: {year}년 {month}월",
        f"💱 통화: {name_ko} ({code})",
        "",
        "| 항목 | 값 |",
        "|------|-----|",
        f"| 월평균 매매기준율 | {rate_label} |",
        f"| 기준월 | {year}년 {month}월 |",
        "",
        "---",
        "*출처: 서울외국환중개 (www.smbs.biz)*",
    ]

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for exchange rate lookup.

    Args:
        argv: Argument list (defaults to sys.argv[1:] if None).
    """
    parser = argparse.ArgumentParser(
        description="Korean Won exchange rate lookup (매매기준율 조회)"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--date",
        help="Date in YYYY-MM-DD or YYYY.MM.DD format",
    )
    group.add_argument(
        "--month",
        help="Month in YYYY-MM format for monthly average",
    )
    parser.add_argument(
        "--currency",
        default="USD",
        help="Currency code or Korean alias (default: USD)",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG, stream=sys.stderr, format="%(message)s")

    # Resolve currency
    currency = find_currency(args.currency)
    if currency is None:
        print(
            f"오류: 지원하지 않는 통화입니다: '{args.currency}'\n"
            "currencies.json에서 지원하는 통화 목록을 확인하세요.",
            file=sys.stderr,
        )
        sys.exit(1)

    cache_dir = _get_default_cache_dir()

    try:
        if args.date:
            # Daily rate mode
            mode, parsed = parse_input(args.date)
            if mode != "daily":
                print("오류: --date 인자는 날짜 형식(YYYY-MM-DD)이어야 합니다.", file=sys.stderr)
                sys.exit(1)
            assert isinstance(parsed, datetime.date)

            result_date, rate, is_fallback = get_daily_rate(parsed, currency, cache_dir)
            output = format_daily_output(
                requested_date=parsed,
                result_date=result_date,
                rate=rate,
                currency=currency,
                is_fallback=is_fallback,
            )
            print(output)

        elif args.month:
            # Monthly average mode
            mode, parsed = parse_input(args.month)
            if mode != "monthly":
                print("오류: --month 인자는 월 형식(YYYY-MM)이어야 합니다.", file=sys.stderr)
                sys.exit(1)
            assert isinstance(parsed, tuple)
            year, month = parsed

            _, rate = get_monthly_rate(year, month, currency, cache_dir)
            output = format_monthly_output(year=year, month=month, rate=rate, currency=currency)
            print(output)

    except ValueError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        print(f"오류: 환율 조회 중 오류가 발생했습니다: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
