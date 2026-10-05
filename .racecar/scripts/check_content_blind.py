#!/usr/bin/env python3
"""Content-blindness guard: no tracked file's prose may embed a real figure.

The reusable, frontmatter-parameterized generalization of a confidential-data adopter's
``scripts/tests/macro/test_check_content_blind.py`` (see
``docs-orchestrator/CONTENT_BLINDNESS.md`` for the one-home rule definition).
It implements the tier of that guard that GENERALIZES — the always-runs
STRUCTURAL rule that needs no private corpus:

    Formulae, worked examples and illustrations in PROSE must be written in
    VARIABLES, not numbers. A number that looks like a rate, price, notional,
    balance, threshold, share or capacity is a leak, even one the author
    believes they invented. Only content-blind structural constants (from the
    calendar or from arithmetic) may appear as literals.

The blocklist tier of a confidential-data adopter's guard (diff the private corpus against the
published tree) is inherently repo-specific — it needs the gitignored data —
and stays in the consuming repo. This checker is the tier every governed repo
can run identically, so it lives once in racecar.

TWO ARMS, ONE FILE, DIFFERENT DEFAULTS. The FIGURE arm above is opt-in. The
IDENTIFIER arm reads structured identifiers — a payment card, an IBAN, an SSN, a
GSTIN — and the checksum-anchored half of it runs unless the repo declines,
because its error rate is a property of a published format rather than of a
threshold someone picked. The argument for the split is at the IDENTIFIERS
section below; the short version is that a leak is wider than an amount, and the
wider part is the part that is cheap to detect.

Policy is read from the repo-root ``README.md`` YAML frontmatter, never
hardcoded here (CONTENT_BLINDNESS.md, "Declaration"):

    content_blind: true                    # opt IN to the FIGURE rule
                                           # absent  => figure rule off, anchored
                                           #            identifier rule on
                                           # false   => both off (declined)
    content_blind_exempt:                  # paths exempt from the prose rule
      - scripts/tests/macro/test_check_content_blind.py
    content_blind_placeholders: [4111111111111111]  # documented synthetic VALUES
    content_blind_identifiers_off: [card]  # identifier TYPES this domain carries
    content_blind_structural: [7.0]        # extra structural constants (opt)

The FIGURE arm is off by default, and that is a deliberate per-repo opt-in: the
discipline over-fires on the legitimate figures many domains carry (dates, ports,
versions, documented constants), and a checker that cries wolf gets switched off.

Absence and ``false`` therefore mean different things to the IDENTIFIER arm.
Absent, the repo has declared nothing and the checksum-anchored types run. An
explicit ``content_blind: false`` is the owner answering, and racecar advises
rather than overrules (``shared/OWNERSHIP.md``), so both arms go quiet.

A key that is PRESENT but unreadable (``ture``) reads as ENABLED and reports the
bad value. The two mistakes are not symmetric: a mistyped ``true`` taken as false
hides exactly the leak this guard exists for, while a mistyped ``false`` taken as
true costs some findings and a correction (``architecture/R10-trust/README.md``).

Prose scanned:
  - Python: every comment and docstring line (never code — a test asserting
    ``approx(625.0)`` is doing its job; prose is where a formula gets
    "helpfully" illustrated with a real number).
  - Markdown: every line OUTSIDE a fenced code block (a fence is a config
    example, i.e. data).

Files scanned: what git would publish (tracked + new-and-not-ignored); on a
non-git tree, every text file under the root minus hidden dirs.

Output:
  - One line per finding: ``check_content_blind: <severity>: <message>``.
  - Summary: ``check_content_blind: OK`` (exit 0) or
    ``check_content_blind: N errors`` (exit 1).

Usage:
    python3 <path-to>/check_content_blind.py [--root <path>]

Complexity: O(enabled patterns x lines); content_blind_identifiers_off excludes a
disabled type's pattern from the scan itself, not just from the result.
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import re
import sys
import tokenize
from collections.abc import Callable, Iterator
from pathlib import Path

from check_docs import ignore_patterns
from check_red import is_test
from identifiers import BY_NAME
from identifiers import scan as identifier_scan
from lib.shared import _frontmatter, _markdown
from lib.shared._constants import DELIVERED_RECORDS
from lib.shared._files import git_ls, repo_files
from lib.shared._report import Findings, emit
from lib.shared._root import find_repo_root

TEXT_SUFFIXES = frozenset(
    {".py", ".md", ".yaml", ".yml", ".toml", ".json", ".cfg", ".ini", ".txt"}
)

# Content-blind STRUCTURAL constants: from the calendar or from arithmetic,
# carrying no information about any deal. Everything else that LOOKS like a deal
# term is out. Mirrors a confidential-data adopter's STRUCTURAL set; a repo may extend it via
# `content_blind_structural` in frontmatter.
STRUCTURAL = frozenset({0.0, 1.0, 2.0, 12.0, 100.0, 360.0, 365.0, 1000.0})

# THE THREE SHAPED PATTERNS. Each fires on how a human WROTE the number -- grouped by
# commas, grouped by underscores, carried to four decimal places -- and that writing is the
# evidence. Nobody groups a port or an id; a person groups a number because they meant it
# to be read as an amount. Shape survives quoting, so these are read everywhere.
COMMA_GROUPED = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?")  # comma-grouped thousands
UNDERSCORE_GROUPED = re.compile(
    r"\b\d+_\d{3}(?:_\d{3})*\b"
)  # underscore-grouped thousands
PRECISE_DECIMAL = re.compile(r"(?<![\d.])\d*\.\d{4,}(?![\d])")  # a many-place decimal

# THE UNSHAPED ARM, and the one that has to be handled carefully, because it fires on a
# run of digits and nothing else. Every exemption below hangs off it -- a year, a YYYYMM
# key, a YYYYMMDD key are all runs of digits that are not quantities. Left unbounded it
# is a rule against writing numbers, and this file's own docstring admits as much
# ("over-fires on the legitimate figures many domains carry"). Making the guard opt-in
# does not make it right: a checker that cries wolf gets switched off, and then the leak
# it exists for ships.
#
# BOUNDED ABOVE. Past nine digits an unseparated run is not something a person wrote to be
# read as an amount; it is a token -- a hash, an id, an epoch (ten digits in seconds,
# thirteen in milliseconds), an account or invoice number. racecar's own `repo_id` is twelve
# hex characters, so about one repo in a thousand hashes to twelve digits, and this guard
# would then refuse every document naming it, permanently, for a reason connected to no
# deal at all.
#
# WHAT THAT GIVES UP, stated because a guard that quietly stops guarding is worse than
# one that was never there: an unseparated integer of ten digits or more is not read as
# a figure, so `12000000000` written bare in prose passes. Grouped and decimal forms are
# caught at any magnitude, so the whole of the loss is "a very large number written
# without separators" -- which is also the form nobody uses when they mean an amount.
LARGE_INTEGER = re.compile(r"(?<![\d.\w$§])\d{4,9}(?:\.\d+)?(?![\d\w])")

# THE PRIMARY SIGNAL. The four patterns above read the SHAPE OF THE DIGITS, and shape is
# not evidence: English writes any large number with separators, so "a corpus of 9,999
# records" and "a $9,999 fee" are indistinguishable to them. Shape firing on counts is
# noise, and noise in a guard teaches the author to reshape the number until the gate
# stops complaining. Shape alone misses the dangerous half -- `$12.3m`, `£4.5bn`, `$30k
# per month`, `20% carry` -- and those are precisely the material this guard exists to
# stop. A false positive costs one edit; a false negative is silent.
#
# A currency symbol, a magnitude suffix and a currency code are the clearest evidence a
# figure is an amount.
# A CURRENCY SYMBOL OR CODE IS UNAMBIGUOUS, and is read on its own. `$12.3m`, `£4.5bn`,
# `$48`, `30000 USD` -- there is no reading of those that is not an amount, so no exemption
# below applies to them either: `$2,028` is money even though 2028 is a year.
CURRENCY_MARKED = re.compile(
    r"[$£€¥₹]\s?\d[\d,_]*(?:\.\d+)?\s*(?:bn|mm|k|m|b)?"
    r"|\d[\d,_]*(?:\.\d+)?\s?(?:USD|GBP|EUR|JPY|INR|CHF|CAD|AUD)\b",
    re.IGNORECASE,
)

# A BARE MAGNITUDE SUFFIX IS NOT. `53k paths` and `1.2k paths` are counts, and reading
# `k` as money on its own is the same over-fire the money markers exist to remove,
# arriving from the other side. So a suffix needs the sentence to say money too; a
# currency symbol never does.
SUFFIX_FIGURE = re.compile(r"\d[\d,_]*(?:\.\d+)?\s*(?:bn|mm|k|m)\b", re.IGNORECASE)

# "A figure with none of those is a count UNTIL SOMETHING SAYS OTHERWISE". This is the
# something. Without the shape patterns `The monthly fee is 37500` would pass -- a
# silent false negative, which is the harm this guard exists to prevent. So an unmarked
# figure still reads, but only where the sentence itself says money: `fee`, `notional`,
# `carry`, `per month`. A count sentence ("1200 lines", "9999 records", "port 8080")
# carries none of these and is quiet.
MONEY_CONTEXT = re.compile(
    r"\b(?:fees?|notional|balances?|amounts?|principal|interest|yields?"
    r"|pric(?:e|ed|ing)|costs?|revenue|salar(?:y|ies)|valuation"
    r"|royalt(?:y|ies)|commitments?|facilit(?:y|ies)|carry|premiums?|spreads?|margins?"
    r"|discounts?|invoices?|budgets?|fundings?|payments?|rates?|cap|floor|arr|mrr"
    r"|usd|gbp|eur)\b"
    r"|\bper\s+(?:month|year|annum|unit)\b"
    r"|/mo\b|[$£€¥₹]",
    re.IGNORECASE,
)

# A percentage is a deal term only in a money sentence: `20% carry` is one, `95% of tuition`
# and `improved by 15%` are not. The marker alone is far too common in ordinary prose.
PERCENT_FIGURE = re.compile(r"\d[\d,_]*(?:\.\d+)?\s?%")

# A MONEY MARKER MARKS A UNIT AND A FORMAT TOO, NOT ONLY AN AMOUNT: a `unit: $000s`
# header, a `$0.00` placeholder, a README's `$1,234.00` format sample. Money markers
# alone cannot tell a unit from an amount. Two shapes are dropped from every arm, argued
# in full in CONTENT_BLINDNESS.md.
#
# EVERY DIGIT ZERO states no quantity. Zero is in `STRUCTURAL`, so the shape arm passes
# a bare `0.00`; the currency arm, which bypasses every exemption by design, agrees with
# it here.
#
# A COUNTING RUN CARRIED BY A SEPARATOR is showing you the separator. `$1,234.00` ascends
# because its job is to mark where the grouping and the decimal places fall, and nobody
# choosing an amount chooses 1, 2, 3, 4 in order. Both halves are required, which is what
# keeps it narrow -- `$12.3m`, `$1.23` and `$123.45` carry no separator.
#
# WHERE THE LINE IS: a round amount still fires. `$20`, `$100`, `$1,000` and `$25,000` state
# a quantity, and tidiness is not evidence of anything.
DIGIT_RUN = "123456789"

# A magnitude suffix is a claim about size, and a format sample makes none, so `$1,234k` is
# an amount however its digits fall.
MAGNITUDE_SUFFIX = re.compile(r"(?:bn|mm|[kmb])\s*$", re.IGNORECASE)

# An inline code span. Markdown's own way of saying "this is a literal, not narration",
# and the guard already honours the block form of exactly that (fenced code is not
# prose). In Python it honours the language's boundary too, reading only comments and
# docstrings. This is the markdown half: a port, a size, a flag default and an id are
# written in backticks, and a fee is not.
CODE_SPAN = re.compile(r"`[^`\n]*`")


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------
_BOOL_TRUE = frozenset({"true", "yes", "on"})
_BOOL_FALSE = frozenset({"false", "no", "off"})


def parse_policy(frontmatter: str) -> dict[str, object]:
    """Parse the flat content-blind keys from a frontmatter block, stdlib-only.

    Handles exactly the shapes CONTENT_BLINDNESS.md declares: a boolean scalar
    (`content_blind: true`), an inline list (`key: [a, b]`), and a block list
    (`key:` then `  - item` lines). No general YAML dependency — this checker
    stays stdlib-only like its doc-coherence peers.
    """
    policy: dict[str, object] = {}
    keys = {
        "content_blind",
        "content_blind_exempt",
        "content_blind_placeholders",
        "content_blind_structural",
        "content_blind_identifiers_off",
    }
    lines = frontmatter.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not m or m.group(1) not in keys:
            i += 1
            continue
        key, rest = m.group(1), m.group(2).strip()
        if key == "content_blind":
            # PRESENT AND NOT EXPLICITLY FALSE MEANS TRUE. Reading anything-but-true as
            # false would let `content_blind: ture` disable the whole scan and exit 0 —
            # fail-open on the key whose entire job is closed-by-default. The two ways
            # to be wrong are not symmetric: a mistyped `true` read as false hides a
            # leak, a mistyped `false` read as true costs the author some findings and a
            # correction. TRUST.md decides it — the behaviour when a check cannot run IS
            # the policy.
            #
            # Absent still means off. Opt-in is deliberate and argued above; this
            # governs only a key the author took the trouble to write.
            # Strip a trailing comment first: without it `false  # why` reads as
            # unreadable and turns the scan on.
            literal = re.split(r"\s+#", rest, maxsplit=1)[0].strip().lower()
            if literal not in _BOOL_TRUE | _BOOL_FALSE:
                policy["content_blind_malformed"] = rest
            policy[key] = literal not in _BOOL_FALSE
        elif rest.startswith("["):
            policy[key] = _parse_inline_list(rest)
        elif not rest:
            items, i = _consume_block_list(lines, i + 1)
            policy[key] = items
            continue
        else:
            policy[key] = [rest]
        i += 1
    return policy


def _parse_inline_list(rest: str) -> list[str]:
    """Parse a `[a, b, c]` inline YAML list into a list of stripped strings."""
    inner = rest.strip().lstrip("[").rstrip("]")
    return [item.strip().strip("'\"") for item in inner.split(",") if item.strip()]


def _consume_block_list(lines: list[str], start: int) -> tuple[list[str], int]:
    """Consume `  - item` lines starting at `start`; return (items, next_index)."""
    items: list[str] = []
    i = start
    while i < len(lines):
        item = re.match(r"^\s*-\s+(.*)$", lines[i])
        if not item:
            break
        items.append(item.group(1).strip().strip("'\""))
        i += 1
    return items, i


def _declared_out_of_scope(root: Path) -> Callable[[str], bool]:
    """A predicate over repo-relative paths, from the repo's own `ignore-paths`.

    Reads the declaration through `check_docs.ignore_patterns()` rather than growing a
    third reader of the same key -- that function exists to be the one home, and
    `check_file_placement` already imports it for exactly this.

    This is narrower than `content_blind_exempt`, which names a path the repo
    DOES grade but content-blindness should not. A path the repo has already declared out
    of scope for every other checker should not have to be named twice, in two
    vocabularies, to mean the same thing.
    """
    patterns = ignore_patterns(root)
    return lambda rel: any(p.search(rel) for p in patterns)


def published_files(root: Path) -> list[Path]:
    """Every text file git would publish; fall back to an rglob on a non-git tree."""
    out = git_ls(root, "--cached", "--others", "--exclude-standard")
    if out is None:
        return _rglob_text(root)
    out_of_scope = _declared_out_of_scope(root)
    files = []
    for name in out.splitlines():
        if not name or out_of_scope(name):
            continue
        path = root / name
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            files.append(path)
    return files


def _rglob_text(root: Path) -> list[Path]:
    """Every text file under `root`, from the ONE shared walk.

    The no-git fallback, and the only path that reaches here: `published_files` asks git
    first and gets a better answer. The shared walk keeps hidden files and prunes only
    hidden directories: `.pre-commit-config.yaml` is committed content a secrets checker
    should read.
    """
    out_of_scope = _declared_out_of_scope(root)
    return [
        path
        for path in repo_files(
            root, *(f"*{suffix}" for suffix in sorted(TEXT_SUFFIXES))
        )
        if path.is_file() and not out_of_scope(path.relative_to(root).as_posix())
    ]


# ---------------------------------------------------------------------------
# Prose extraction
# ---------------------------------------------------------------------------


def py_prose(path: Path) -> Iterator[tuple[int, str]]:
    """Yield (lineno, text) for every comment and docstring line in a python file."""
    source = path.read_text(encoding="utf-8", errors="ignore")
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT:
                yield token.start[0], token.string
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            doc = ast.get_docstring(node, clean=False)
            if doc and node.body:
                start = node.body[0].lineno
                for offset, line in enumerate(doc.splitlines()):
                    yield start + offset, line


def md_prose(path: Path) -> Iterator[tuple[int, str]]:
    """Yield (lineno, text) for every markdown line OUTSIDE a fenced code block."""
    yield from _markdown.prose(
        path.read_text(encoding="utf-8", errors="ignore").splitlines()
    )


def unquoted(line: str) -> str:
    """The line with inline code spans blanked out, positions preserved.

    Applied to EVERY figure arm. Where the author put a figure is a signal
    markdown already has a word for, and reading it is not an exemption for convenience --
    refusing to read it is treating a marked-up document as a flat stream of characters.

    What it gives up: a figure someone quoted, `37500`, is not read. That is a real
    hole and it is narrow -- an author narrating a fee does not put it in backticks, and one
    who does has quoted it as a literal, which is what the markup means. `is_test` below
    says the same thing about a whole file rather than one span.
    """
    return CODE_SPAN.sub(lambda m: " " * len(m.group(0)), line)


def unit_or_format(raw: str) -> bool:
    """True when a money-marked literal states a unit or a format rather than an amount.

    Two shapes, argued at `DIGIT_RUN` above. Every digit zero: `$000s`, `$0.00`. A counting
    run carried by a separator: `$1,234.00`, `$12,345.67`. Everything else is an amount,
    including a round one.
    """
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return False
    if set(digits) == {"0"}:
        return True
    if MAGNITUDE_SUFFIX.search(raw) or not any(sep in raw for sep in (",", "_")):
        return False
    whole, _, frac = re.sub(r"[^\d.]", "", raw).partition(".")
    if len(whole) < 3 or whole != DIGIT_RUN[: len(whole)]:
        return False
    return set(frac) <= {"0"} or frac == DIGIT_RUN[len(whole) : len(whole) + len(frac)]


def deal_figures_in(line: str, structural: frozenset[float]) -> list[str]:
    """Return the literals in `line` that look like a deal term, not a constant.

    Two signals, in the order they carry weight:

    1. A MONEY MARKER on the figure itself -- a currency symbol, a magnitude suffix, a
       currency code. Read always, and the exemptions below do not apply to it: `$2,028`
       is an amount even though 2028 is a year, and that is the point of the marker.
    2. The SHAPE of the digits, but only where the sentence itself says money
       (`MONEY_CONTEXT`). Shape alone would call `a corpus of 9,999 records` a deal
       term, which is how an author learns to reshape a number until the gate goes
       quiet.

    Backticks are read the same way in both arms.

    Neither signal is enough on its own, and `unit_or_format` is why: a currency symbol
    marks a unit header and a format sample as readily as an amount, so a marked literal
    that states no quantity is dropped from both arms before either reports it.
    """
    found: list[str] = []
    subject = unquoted(line)

    def take(pattern: re.Pattern[str]) -> None:
        for match in pattern.finditer(subject):
            raw = match.group(0).strip()
            if raw and not unit_or_format(raw) and raw not in found:
                found.append(raw)

    take(CURRENCY_MARKED)
    if not MONEY_CONTEXT.search(line):
        return found
    take(SUFFIX_FIGURE)
    take(PERCENT_FIGURE)
    for pattern in (COMMA_GROUPED, UNDERSCORE_GROUPED, PRECISE_DECIMAL, LARGE_INTEGER):
        subject = unquoted(line)
        for match in pattern.finditer(subject):
            raw = match.group(0)
            try:
                value = float(raw.replace(",", "").replace("_", ""))
            except ValueError:
                continue
            if value in structural or unit_or_format(raw):
                continue
            # A year or an ISO month key: 1899 (Excel's serial epoch) to 2100.
            if value.is_integer() and 1899 <= value <= 2100:
                continue
            # A compact date key — YYYYMM (paper ids, ISO month keys) or YYYYMMDD —
            # is a calendar value, not a deal term, by the same reasoning as the year
            # exemption above. These three cover the 4-to-9-digit band, which is the only
            # band the unshaped arm reads at all.
            #
            # Domain magic constants (ports, byte sizes, TTLs) are not guessable here, and
            # `content_blind_structural` is where a repo may list one. It is rarely
            # needed: those are written in backticks in every codebase
            # racecar has seen, and `unquoted` reads them as the literals they are rather
            # than sending the author to maintain an allowlist of their own port numbers.
            if value.is_integer():
                iv = int(value)
                is_yyyymm = 189901 <= iv <= 210012 and 1 <= iv % 100 <= 12
                is_yyyymmdd = (
                    18990101 <= iv <= 21001231
                    and 1 <= (iv // 100) % 100 <= 12
                    and 1 <= iv % 100 <= 31
                )
                if is_yyyymm or is_yyyymmdd:
                    continue
            # A residual or a tolerance (1e-3 and below) is a measure of error.
            if abs(value) <= 1e-3:
                continue
            if raw not in found:
                found.append(raw)
    return found


# ---------------------------------------------------------------------------
# THE SECOND ARM: structured identifiers
#
# The figure arm above reads a number and guesses whether a human meant it as an amount.
# That guess is unavoidable -- ANY number could be an amount -- and its imprecision is
# why the figure arm is opt-in. The imprecision is not evenly distributed, though, and
# bundling both arms behind one switch would run the precise half only in the repos that
# are already careful.
#
# A national identity number, a taxpayer id, a bank routing number, an account number, a
# payment card, a company registration number: each is a disclosure with consequences an
# amount does not have, and none of them is a rate, a price, a notional or a balance.
#
# THE RULES THEMSELVES LIVE IN DATA, not here. `scripts/identifiers.json` declares every
# type -- its shape, the algorithm that confirms it, the issuing authority whose rule it is
# and where that rule is published -- and `scripts/identifiers.py` implements the algorithms
# that file names. This module is a CONSUMER. Adding a jurisdiction is a row in that file,
# not a patch to this one, and every row can be audited against its own authority without
# reading any code.
#
# TWO TIERS, AND THE LINE IS EVIDENCE, NOT SEVERITY. An `anchored` type carries a structural
# signal besides the checksum -- a letter alphabet, a required separator, a closed
# enumeration -- so a false positive needs the structure AND the check to coincide. Those
# run whether or not a repo opted in. A `bare` type has no such signal: a naked run of
# digits, or a body so unrestricted that an ordinary token satisfies everything but the
# check digit. What is left is arithmetic a coincidence clears about one time in ten, which
# is a threshold rather than evidence, so those wait for `content_blind: true`. Neither
# claim is taken on trust -- identifiers.json records both measured rates per row, and
# scripts/tests/slow/test_identifiers.py refuses a table whose two tiers overlap.
#
# NOT IMPLEMENTED, AND SAID OUT LOUD: DUNS, bare SSN, bare EIN, Indian MICR, UK UTR and
# sort code. The reasons are recorded per type under `excluded` in identifiers.json, and
# they are all the same reason: a shape with no check and no enumeration accepts every
# string of that shape, which is a rule against writing numbers rather than a detector.
# ---------------------------------------------------------------------------


def identifiers_in(
    line: str,
    anchored_only: bool,
    disabled: frozenset[str],
    placeholders: frozenset[str],
) -> list[tuple[str, str]]:
    """Return (type, value) for every structured identifier the line carries.

    Read everywhere, including inside backticks, and the asymmetry with the bare-figure
    arm is the same one that arm already makes: a value that satisfies a published
    checksum carries its own evidence and is a disclosure wherever it sits. `unquoted`
    exists because a naked run of digits has no evidence and its POSITION is the only
    signal; that reasoning does not reach a value which has proved what it is.
    """
    found: list[tuple[str, str]] = []
    for name, raw in identifier_scan(
        line, anchored_only=anchored_only, disabled=disabled
    ):
        if re.sub(r"[ .\-/]", "", raw) in placeholders:
            continue
        found.append((name, raw))
    return found


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


# Where a repo records the files racecar put in it. Two kinds of file, because the answer
# differs by which repo this is running in and how recently it was synced.
#
# Path lists — one repo-relative path per line, `#` comments allowed:
#   - `scripts/.racecar-delivered.txt` — what a sync writes.
#   - `scripts/racecar-manifest.txt` — the same record, under the name some ADOPTERS
#     carry. (In racecar itself the canonical manifest is the JSONL below.)
# Every location a delivered record can have, from the one home that knows them
# (`lib.shared._constants`). A second spelling here would let the writer move without
# this list, and the lookup would then miss and conclude racecar delivered nothing.
_DELIVERED_RECORDS = DELIVERED_RECORDS

# The canonical delivery manifest, present in RACECAR ITSELF: one JSON object per line,
# whose `source` is the file in this repo. A separate constant from the path lists because
# it is a separate format, read by key — not a shape the line-splitting rule can absorb.
_DELIVERY_MANIFEST = "scripts/racecar-manifest.jsonl"


def delivered_received(root: Path) -> frozenset[str]:
    """Repo-relative paths a SYNC WROTE INTO this repo -- copies, never sources.

    The narrower half of `delivered_exempt` below, and separate because two consumers ask
    two different questions of one record. The content-blind guard asks *did racecar write
    this prose*, which is as true of a file racecar SHIPS as of a copy it delivered, so it
    wants both halves. `make fmt` asks *would the next sync overwrite my edit*, which is
    true only of the copies: in racecar itself every `source` in the canonical manifest is
    a file racecar AUTHORS, so answering the formatter with the wider set would stop
    racecar formatting its own `scripts/` while `fmt-check` stayed green.

    One parser, two answers.
    """
    paths: set[str] = set()
    for rel in _DELIVERED_RECORDS:
        record = root / rel
        if not record.is_file():
            continue
        try:
            text = record.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            print(
                f"check_content_blind: {rel} is not valid UTF-8 ({exc}); skipping it",
                file=sys.stderr,
            )
            continue
        paths |= {
            line.split()[0]
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
    return frozenset(paths)


def filter_delivered(root: Path, raw: bytes, *, keep_delivered: bool = False) -> bytes:
    """NUL-separated paths in; either the delivered ones or everything else, out.

    Lives beside the record's parser because that is the one home for its format; a
    filter that re-read the record in Make would be a second reader of it. NUL in and
    NUL out for the same reason the file list uses `-z` and `xargs -0`: a path with a
    space in it must survive the round trip whole.

    Both directions, because the gates need both populations and neither may be derived by
    re-reading the record somewhere else. `make fmt` takes the complement (never rewrite a
    file the next sync overwrites); the checking gates take the delivered set and grade it
    under canon's own configuration.
    """
    received = delivered_received(root)
    kept = [
        path
        for path in raw.split(b"\0")
        if path
        and (path.decode("utf-8", "surrogateescape") in received) is keep_delivered
    ]
    return b"\0".join(kept) + b"\0" if kept else b""


def drop_missing(root: Path, raw: bytes) -> bytes:
    """NUL-separated paths in; only those present on disk, out.

    A DIFFERENT question from `filter_delivered`'s, and kept separate because that
    function is a pure partition of a path set by the delivery record, and conflating
    them would make it disk-aware.

    `git ls-files --cached` reports what is TRACKED, which includes a file deleted from the
    worktree whose deletion is not yet staged. Handed to black that is a usage error --
    `Invalid value for 'SRC ...': Path 'x.py' does not exist` -- so `fmt-check` dies on the
    first one and reports a formatter argument problem, naming neither the index nor the
    repair. It is the ordinary state of a repo part-way through a rename, which is every
    adopter mid-migration.

    Dropping is right rather than lenient: a file not on disk has no content to format. The
    count goes to stderr with the repair, because a gate that silently grades less than it
    was asked to is the failure racecar treats as worse than a loud one.
    """
    kept, missing = [], 0
    for path in raw.split(b"\0"):
        if not path:
            continue
        if (root / path.decode("utf-8", "surrogateescape")).exists():
            kept.append(path)
        else:
            missing += 1
    if missing:
        print(
            f"check_content_blind: skipped {missing} tracked path(s) not on disk — "
            "deletions not yet staged. `git add -A` records them.",
            file=sys.stderr,
        )
    return b"\0".join(kept) + b"\0" if kept else b""


def delivered_ignore_regex(root: Path) -> str:
    """An anchored alternation of the delivered paths, for `--ignore-paths` and mypy.

    pylint and mypy take a scope as DIRECTORIES and subtract by regex, where the formatters
    take an explicit file list. Same fact, the shape each tool can consume -- and computed
    here rather than assembled in Make, so there is still exactly one thing that knows how a
    delivery record is read. Empty when nothing was delivered, which every caller must treat
    as "add no exclusion" rather than as an empty pattern matching everything.
    """
    paths = sorted(delivered_received(root))
    return "|".join("^" + re.escape(p) + "$" for p in paths)


def delivered_exempt(root: Path) -> frozenset[str]:
    """Repo-relative paths racecar delivered here, read from the delivery records.

    racecar-delivered files (the synced check scripts, `racecar.mk`) are tooling the
    repo owns no prose in and cannot edit without the next sync clobbering it, so the
    guard never scans them — a stray figure-shaped comment in canon must never turn a
    downstream repo's gate red. racecar does not edit the repo's owned README to record
    this (that would break the no-clobber contract); instead `racecar sync` writes
    the record of what it delivered, and the guard exempts exactly that set. The
    record is rewritten on every sync, so the exemption is always current.

    Two formats, each read as what it is. A path list gives its first whitespace-separated
    token; the canonical manifest gives its `source` field, read with `.get` so a field
    added later changes nothing. Reading a manifest line whole would turn every exempt
    path into `"<path> <dest> <digest>"`, match no file, and drop racecar's own
    self-exemption without a symptom.
    """
    paths: set[str] = set(delivered_received(root))
    manifest = root / _DELIVERY_MANIFEST
    if manifest.is_file():
        try:
            manifest_text = manifest.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            print(
                f"check_content_blind: {_DELIVERY_MANIFEST} is not valid UTF-8 "
                f"({exc}); skipping it",
                file=sys.stderr,
            )
            manifest_text = ""
        for line in manifest_text.splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            source = obj.get("source") if isinstance(obj, dict) else None
            if isinstance(source, str) and source:
                paths.add(source)
    return frozenset(paths)


def load_policy(root: Path) -> dict[str, object]:
    """Read the content-blind policy from the repo-root README.md frontmatter."""
    readme = root / "README.md"
    if not readme.is_file():
        return {}
    block = _frontmatter.block(readme.read_text(encoding="utf-8"))
    return parse_policy(block) if block else {}


def structural_set(policy: dict[str, object]) -> frozenset[float]:
    """Return STRUCTURAL extended by any `content_blind_structural` frontmatter."""
    extra = policy.get("content_blind_structural", [])
    values: set[float] = set(STRUCTURAL)
    if isinstance(extra, list):
        for item in extra:
            try:
                values.add(float(item))
            except (TypeError, ValueError):
                continue
    return frozenset(values)


def scan(
    root: Path,
    exempt: frozenset[str],
    structural: frozenset[float] | None,
    identifiers: tuple[bool, frozenset[str], frozenset[str]] | None = None,
) -> list[str]:
    """Return one `rel:lineno: value | line` line per finding, over both arms.

    `structural` is None when the figure arm is off (the repo did not opt in) and
    `identifiers` is None when the identifier arm is off (the repo opted OUT). The two
    are independent because their evidence is: see the IDENTIFIERS section above.
    """
    offenders: list[str] = []
    # This guard necessarily quotes the very shapes it forbids to explain them,
    # so it always exempts its own file (a confidential-data adopter's PROSE_EXEMPT_FILES pattern) —
    # otherwise it would flag itself once synced into a content-blind adopter.
    self_path = Path(__file__).resolve()
    for path in published_files(root):
        if path.resolve() == self_path:
            continue
        rel = path.relative_to(root).as_posix()
        if rel in exempt:
            continue
        if path.suffix == ".py":
            prose = py_prose(path)
        elif path.suffix == ".md":
            prose = md_prose(path)
        else:
            continue
        # A FIGURE IN A TEST FILE IS A LITERAL, NOT A NARRATION -- the class `unquoted`
        # already exists for. The guard refuses to read a test's CODE, because
        # `approx(625.0)` is the test doing its job, so what is left to read in one is
        # the comment and the docstring describing that fixture, which would be reading
        # the description of a value it deliberately declines to read. Pytest's own
        # filename rule decides, taken from `check_red.py` rather than spelled twice
        # (P-02). The IDENTIFIER arm still reads them -- a value that satisfies a
        # published checksum has proved what it is, and a real national id in a fixture
        # is exactly the disclosure.
        test_file = is_test(rel)
        for lineno, line in prose:
            if structural is not None and not test_file:
                for figure in deal_figures_in(line, structural):
                    offenders.append(
                        f"deal-shaped figure in prose — {rel}:{lineno}: {figure}"
                        f"  |  {line.strip()[:80]}"
                    )
            if identifiers is not None:
                for name, value in identifiers_in(line, *identifiers):
                    offenders.append(
                        f"structured identifier in prose — {rel}:{lineno}: {value} "
                        f"reads as {_note_for(name)}  |  {line.strip()[:80]}"
                    )
    return offenders


def _note_for(name: str) -> str:
    """The human sentence for an identifier type; the type id alone helps nobody."""
    return BY_NAME[name].note


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments for the content-blind check."""
    parser = argparse.ArgumentParser(
        description="Assert no tracked file's prose embeds a real figure "
        "(content-blindness Tier 2)."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repo root to scan. Default: discovered via .git walk-up from CWD.",
    )
    parser.add_argument(
        "--exclude-delivered",
        action="store_true",
        help="Filter mode: read NUL-separated paths on stdin and write through those no "
        "sync delivered here. racecar.mk pipes its file list through it so no formatter "
        "is ever handed a file the next sync overwrites.",
    )
    parser.add_argument(
        "--only-delivered",
        action="store_true",
        help="The complement of --exclude-delivered: write through only what a sync "
        "delivered here, which the checking gates grade under canon's own config.",
    )
    parser.add_argument(
        "--delivered-regex",
        action="store_true",
        help="Print an anchored alternation of the delivered paths, for pylint's "
        "--ignore-paths and mypy's exclude. Empty output means nothing was delivered.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the content-blind prose scan when opted in; return an exit code."""
    args = parse_args(argv if argv is not None else sys.argv[1:])
    root = args.root.resolve() if args.root else find_repo_root()

    # Before the policy read, because this verb answers from the delivery record alone and
    # must work in a repo that has opted out of the scan -- the formatter needs the answer
    # either way.
    if args.delivered_regex:
        print(delivered_ignore_regex(root))
        return 0
    if args.exclude_delivered or args.only_delivered:
        sys.stdout.buffer.write(
            filter_delivered(
                root,
                drop_missing(root, sys.stdin.buffer.read()),
                keep_delivered=args.only_delivered,
            )
        )
        sys.stdout.buffer.flush()
        return 0

    f = Findings()

    policy = load_policy(root)
    malformed = policy.get("content_blind_malformed")
    if malformed is not None:
        # Reported AND enabled. Erroring and returning would have been the same
        # fail-open in a louder voice: the author learns the value is wrong, and the
        # scan they asked for still does not run while they get around to it.
        f.error(
            f"README.md frontmatter: content_blind is {malformed!r}, which is neither "
            f"true nor false. Read as ENABLED, because a value nobody can read must "
            f"not silently disable the guard. Write `true` or `false` "
            f"(CONTENT_BLINDNESS.md)."
        )
    exempt_raw = policy.get("content_blind_exempt", [])
    exempt = frozenset(exempt_raw if isinstance(exempt_raw, list) else [])
    exempt = exempt | delivered_exempt(root)

    opted_in = bool(policy.get("content_blind"))
    declined = "content_blind" in policy and not opted_in

    # THE IDENTIFIER ARM'S DEFAULT, and the one asymmetry in it. Absent means the repo
    # has declared nothing, so the anchored types run: their error rate is a property of
    # the format, and a guard that only runs where someone already opted in never
    # protects the repo that needed it. An explicit `content_blind: false` is not
    # silence — it is the owner declining, and racecar advises rather than overrules
    # (shared/OWNERSHIP.md), so that answer is honoured for both arms.
    identifiers = (
        None
        if declined
        else (not opted_in, disabled_identifiers(policy), placeholder_set(policy))
    )

    if not opted_in:
        f.info(
            "content_blind not enabled in README.md frontmatter; the figure rule is off"
            + (
                " and so is the identifier rule (declined explicitly)"
                if declined
                else "; the checksum-anchored identifier rule still runs"
            )
            + " (see CONTENT_BLINDNESS.md)"
        )

    offenders = scan(
        root, exempt, structural_set(policy) if opted_in else None, identifiers
    )
    for offender in offenders:
        f.error(offender)
    return emit(
        f,
        "check_content_blind",
        ". A formula or worked example in prose must be written in VARIABLES, not "
        "numbers; a value that satisfies a published checksum belongs in no tracked "
        "prose at all (CONTENT_BLINDNESS.md).",
    )


def disabled_identifiers(policy: dict[str, object]) -> frozenset[str]:
    """Identifier type ids this repo has turned off, from `content_blind_identifiers_off`.

    Per TYPE rather than per repo, because a domain legitimately carrying one carries one:
    a payments library will quote test cards forever and has no reason to stop reading
    IBANs. `content_blind_placeholders` is the other half — a documented synthetic VALUE,
    for the case where the exception is one string rather than a whole class.
    """
    raw = policy.get("content_blind_identifiers_off", [])
    return (
        frozenset(str(x).strip().lower() for x in raw)
        if isinstance(raw, list)
        else frozenset()
    )


def placeholder_set(policy: dict[str, object]) -> frozenset[str]:
    """Documented synthetic values, separators stripped, from `content_blind_placeholders`.

    The identifier arm is what reads it: a checksum-valid value a repo has argued
    for in writing is exactly the exception this arm cannot infer.
    """
    raw = policy.get("content_blind_placeholders", [])
    if not isinstance(raw, list):
        return frozenset()
    return frozenset(re.sub(r"[ .\-/]", "", str(x)) for x in raw)


if __name__ == "__main__":
    sys.exit(main())
