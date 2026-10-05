"""The page views as terminal text.

Every line this noun's cli prints is written here. Each ``print_<verb>`` takes that verb's
result and writes it; it reads no store and decides nothing, and it reads the same types
the api returns, so what it prints cannot drift from them.
"""

from __future__ import annotations

import sys

from ..results import CrawlPage


def print_crawl(result: CrawlPage) -> None:
    """``page crawl`` as text, one ``key: value`` line per field."""
    for key, value in result.items():
        print(f"{key}: {value}")


def error(message: str) -> None:
    """A refusal the api raised, on stderr, so stdout stays empty."""
    print(message, file=sys.stderr)
