"""Reading the API key from the person or the pipe, for ``login``.

The Stripe CLI's ``login --interactive`` reads the key with the terminal's echo off; this is
the same, through ``getpass``. When stdin is not a terminal (cron, CI, a pipe) the first line
of stdin is the key, so ``printf %s "$KEY" | python -m eninesites login`` works unattended.
Nothing here prints the key.
"""

from __future__ import annotations

import getpass
import sys

PROMPT = "Enter your API key: "


def read_api_key() -> str:
    """The key the caller typed (hidden) or piped; empty when nothing was given."""
    if sys.stdin is None:
        return ""
    if sys.stdin.isatty():
        try:
            return getpass.getpass(PROMPT).strip()
        except (EOFError, KeyboardInterrupt):
            return ""
    return sys.stdin.readline().strip()
