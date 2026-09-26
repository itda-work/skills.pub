"""Build cache script for pre-fetching exchange rate data from SMBS.

Pre-fetches and caches exchange rate data for a specified set of currencies,
years, and query types. Adds random delays between requests to be respectful
of the SMBS API.

Usage:
    python3 build_cache.py
    python3 build_cache.py --currencies USD JPY EUR --years 2023 2024 2025
    python3 build_cache.py --dry-run
"""
from __future__ import annotations

import argparse
import datetime
import random
import sys
import time
from pathlib import Path

# Allow running directly or importing
_SCRIPT_DIR = Path(__file__).parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import exchange_rate as er


# Default currencies to pre-fetch (major currencies for tax purposes)
DEFAULT_CURRENCIES = ["USD", "JPY", "EUR", "CNY"]

# Default years to pre-fetch (current year and 2 prior years)
_THIS_YEAR = datetime.date.today().year
DEFAULT_YEARS = [_THIS_YEAR - 2, _THIS_YEAR - 1, _THIS_YEAR]

# Default query types
DEFAULT_QUERY_TYPES = ["daily", "monthly"]

# Delay range in seconds between API requests (min, max)
REQUEST_DELAY_MIN = 0.5
REQUEST_DELAY_MAX = 1.5


def get_cache_combinations(
    currencies: list[str],
    years: list[int],
    query_types: list[str],
) -> list[tuple[str, int, str]]:
    """Generate all (currency, year, type) combinations for cache building.

    Args:
        currencies: List of currency codes to include.
        years: List of years to include.
        query_types: List of query types ("daily", "monthly").

    Returns:
        List of (currency_code, year, query_type) tuples.
    """
    combinations = []
    for currency in currencies:
        for year in years:
            for query_type in query_types:
                combinations.append((currency, year, query_type))
    return combinations


def build_cache_entry(
    currency_code: str,
    year: int,
    query_type: str,
    cache_dir: Path,
    skip_existing: bool = True,
    verbose: bool = True,
) -> bool | None:
    """Fetch and cache a single (currency, year, type) combination.

    Args:
        currency_code: ISO 4217 currency code.
        year: Year to fetch.
        query_type: "daily" or "monthly".
        cache_dir: Cache directory path.
        skip_existing: If True, skip if cache already exists.
        verbose: Print progress messages if True.

    Returns:
        True if data was fetched, False if skipped (cache exists), None on error.
    """
    cache_path = er.get_cache_path(cache_dir, currency_code, year, query_type)

    if skip_existing and cache_path.exists():
        if verbose:
            print(f"  SKIP {currency_code} {year} {query_type} (cached)")
        return False

    if verbose:
        print(f"  FETCH {currency_code} {year} {query_type}...", end=" ", flush=True)

    try:
        er.fetch_rates(currency_code, year, query_type, cache_dir, skip_cache=True)
        if verbose:
            print("OK")
        return True
    except Exception as exc:  # noqa: BLE001
        if verbose:
            print(f"ERROR: {exc}")
        return None


def run_build_cache(
    currencies: list[str] | None = None,
    years: list[int] | None = None,
    query_types: list[str] | None = None,
    cache_dir: Path | None = None,
    skip_existing: bool = True,
    dry_run: bool = False,
    verbose: bool = True,
) -> dict[str, int]:
    """Run the full cache build process.

    Args:
        currencies: Currency codes to fetch (defaults to DEFAULT_CURRENCIES).
        years: Years to fetch (defaults to DEFAULT_YEARS).
        query_types: Query types to fetch (defaults to DEFAULT_QUERY_TYPES).
        cache_dir: Cache directory (defaults to skill data/cache directory).
        skip_existing: Skip combinations where cache already exists.
        dry_run: Print what would be done without actually fetching.
        verbose: Print progress messages.

    Returns:
        Dict with counts: {"fetched": N, "skipped": N, "errors": N}.
    """
    if currencies is None:
        currencies = DEFAULT_CURRENCIES
    if years is None:
        years = DEFAULT_YEARS
    if query_types is None:
        query_types = DEFAULT_QUERY_TYPES
    if cache_dir is None:
        cache_dir = er._get_default_cache_dir()

    combinations = get_cache_combinations(currencies, years, query_types)
    counts = {"fetched": 0, "skipped": 0, "errors": 0}

    if verbose:
        print(f"Building cache: {len(combinations)} combinations")
        print(f"  Currencies: {currencies}")
        print(f"  Years: {years}")
        print(f"  Types: {query_types}")
        print(f"  Cache dir: {cache_dir}")
        print()

    for i, (currency_code, year, query_type) in enumerate(combinations):
        if dry_run:
            print(f"  [DRY] {currency_code} {year} {query_type}")
            continue

        success = build_cache_entry(
            currency_code=currency_code,
            year=year,
            query_type=query_type,
            cache_dir=cache_dir,
            skip_existing=skip_existing,
            verbose=verbose,
        )

        if success is True:
            counts["fetched"] += 1
            # Add random delay between API requests to be respectful
            if i < len(combinations) - 1:
                delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
                time.sleep(delay)
        elif success is False:
            counts["skipped"] += 1
        else:  # None = fetch error
            counts["errors"] += 1

    if verbose and not dry_run:
        print()
        print(
            f"Done: {counts['fetched']} fetched, "
            f"{counts['skipped']} skipped, "
            f"{counts['errors']} errors"
        )

    return counts


def main() -> None:
    """CLI entry point for cache building."""
    parser = argparse.ArgumentParser(
        description="Pre-fetch and cache SMBS exchange rate data"
    )
    parser.add_argument(
        "--currencies",
        nargs="+",
        default=DEFAULT_CURRENCIES,
        help=f"Currency codes to fetch (default: {DEFAULT_CURRENCIES})",
    )
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=DEFAULT_YEARS,
        help=f"Years to fetch (default: {DEFAULT_YEARS})",
    )
    parser.add_argument(
        "--types",
        nargs="+",
        default=DEFAULT_QUERY_TYPES,
        choices=["daily", "monthly"],
        help="Query types to fetch (default: daily monthly)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Cache directory path (default: skill data/cache directory)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch even if cache already exists",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be fetched without actually fetching",
    )

    args = parser.parse_args()

    run_build_cache(
        currencies=args.currencies,
        years=args.years,
        query_types=args.types,
        cache_dir=args.cache_dir,
        skip_existing=not args.force,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
