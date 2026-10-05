#!/usr/bin/env python3
"""Run several make targets at once and render their output in a FIXED order.

Complexity: O(n) processes for n legs; wall time is the slowest leg, not their sum.

`check-full` fans out into legs that share nothing — one grades the code and runs the
fast tier, one lints the suites, one runs the slow tier, one does typecheck + arch. They
are a partition, so running them concurrently is free. What is not free is the output:
four recipes writing to one terminal produce a transcript whose order changes run to run,
and a gate you cannot read is a gate people stop reading.

GNU Make solves this with `--output-sync=target`, which arrived in **make 4.0**. macOS
ships **3.81** (2006), where the option is not merely absent but rejected, so a Makefile
that passes it does not degrade -- it dies. racecar already carries one workaround for
that same ancient make (the `export PATH :=` execvp bug in racecar.mk), and this is the
second. Requiring an adopter to install a newer make to read their own gate is a
toolchain dependency bought for cosmetics; a stdlib script is not.

## Ordered, and still progressive

The naive fix -- wait for everything, then print -- makes a 30s gate silent for 30s. This
prints each leg the moment every leg BEFORE it has finished, so output begins as soon as
leg 1 is done and the order is always the declared one. A leg that finishes early is
buffered; a leg that finishes late holds only the legs behind it. That is the same
algorithm `--output-sync=target` uses, and it is why the flag exists rather than a plain
"collect then dump".

## What it does not do

It does not parse or reformat a leg's output. Each recipe in `racecar.mk` already traps
its own, reduces it to a message-code histogram and prints one block; re-parsing here
would be a second home for a rendering the recipes already own. This orders blocks. It
also does not decide what runs -- the caller names the targets, in the order it wants
them read.

Usage:
    python3 gate_orchestrate.py --make "make" -- _check lint-tests test-slow

Exit code is the worst leg's, so a failure anywhere fails the gate. Every leg runs to
completion even when an earlier one has already failed: a gate that stops at the first
failure hides the other three, and the whole point of running them together is to learn
everything in one pass.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import threading
import time


def _spawn(make: list[str], target: str) -> subprocess.Popen[str]:
    """Start one leg, with its stdout and stderr merged into one captured stream.

    Merged on purpose: a recipe's summary goes to stdout and its failures to stderr, and
    splitting them here would put a leg's own error in a different block from the leg's
    own report -- exactly the interleaving this script exists to remove, reintroduced one
    level down.
    """
    return subprocess.Popen(
        [*make, "--no-print-directory", target],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def main(argv: list[str] | None = None) -> int:
    """Run every target concurrently; print them in argv order; return the worst code."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # SPLIT, not used whole: `$(MAKE)` is a command line, not a filename -- it carries
    # whatever flags make was invoked with, and treating it as one executable fails with a
    # FileNotFoundError naming a string that looks perfectly valid.
    parser.add_argument("--make", default="make", help="the make command to invoke")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="omit the per-leg timing footer",
    )
    parser.add_argument("targets", nargs="+", help="make targets, in render order")
    args = parser.parse_args(argv)

    started = time.monotonic()
    make = shlex.split(args.make)
    results: list[dict[str, object]] = []

    def drain(slot: dict[str, object]) -> None:
        """Read one leg to EOF and record when it actually ended."""
        proc = slot["proc"]
        assert isinstance(proc, subprocess.Popen)
        slot["output"] = proc.communicate()[0]
        slot["code"] = proc.returncode
        slot["elapsed"] = time.monotonic() - started

    # A reader thread per leg, because the finish time has to be taken when the leg ENDS,
    # not when this loop gets around to it. Draining them in order from the main thread
    # would make every leg report the first leg's duration -- each one would genuinely
    # have been waiting that long by the time it was read, so the number would be true
    # and meaningless.
    #
    # It is also what keeps a chatty leg from blocking: a pipe whose buffer fills stops
    # the writer until someone reads it, so a leg that out-talks the buffer while the main
    # thread is blocked on an earlier leg would deadlock rather than finish.
    threads = []
    for target in args.targets:
        slot: dict[str, object] = {"target": target, "proc": _spawn(make, target)}
        results.append(slot)
        thread = threading.Thread(target=drain, args=(slot,), daemon=True)
        thread.start()
        threads.append(thread)

    worst = 0
    for slot, thread in zip(results, threads):
        thread.join()
        code = int(slot["code"])  # type: ignore[call-overload]
        worst = worst or code
        status = "ok" if code == 0 else f"FAILED ({code})"
        print(
            f"===== {slot['target']}: {status} in {slot['elapsed']:.1f}s =====",
            flush=True,
        )
        output = slot["output"]
        if output:
            print(str(output).rstrip("\n"), flush=True)

    if not args.quiet:
        total = time.monotonic() - started
        # The per-leg times above sum to more than this. That gap IS the parallelism, and
        # printing both is what makes it visible -- a leg that has stopped overlapping with
        # the others shows up as its own time approaching the total.
        print(f"gate_orchestrate: {len(results)} leg(s), {total:.1f}s wall", flush=True)
    return worst


if __name__ == "__main__":
    sys.exit(main())
