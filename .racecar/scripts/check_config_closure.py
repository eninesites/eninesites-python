#!/usr/bin/env python3
"""GATE: close the repo README against `config.toml`, in both directions.

A README tells a reader what a project's settings are and what they default
to. `check_required_docs.py` grades the README's existence, its frontmatter
and its `pnode` key; past that, no other check grades README CONTENT, so
without this one a README can name a default the code never uses and every
gate stays green.

THREE DIRECTIONS, because any one of them alone leaves a hole:

  forward   every setting `config.toml` declares is named in the README.
            Catches the setting nobody wrote down -- the one an operator
            cannot discover.
  backward  every setting-shaped claim in the README names something
            `config.toml` declares. Catches the setting deleted from the code
            and left in the prose -- the sentence that sends a reader to a
            variable that does nothing.
  values    a scalar `default` appears in the README verbatim. This is the
            half that catches a README naming a default the code never
            reads, and it is decidable because
            it is a substring test against a declared literal rather than a
            parse of English.

WHAT IT DELIBERATELY DOES NOT DO:

  * It does not gate a heading. "Package config" is a section a repo writes,
    not a string to grep for; `doc-coherence/PROTOCOL.md` argues that forcing
    headings is theater, and a repo documenting its settings in a table, under
    `## Configuration`, or under `## Getting started` is conformant. The gate
    keys on the setting NAMES and the declared default LITERALS, which is what
    actually has to be true.
  * It does not generate the section. `config.toml` is an assertion, authored
    so code can be found in violation of it; the README's account is a second
    assertion by a human. Generating one from the other makes it a transcript
    -- two artifacts that agree by construction, where the agreement was the
    thing worth checking. Contrast the README's `## CLI` block, which IS
    generated, correctly, because the command tree is a projection of code.
  * It does not read a nested-dict default. There is no single literal to look
    for, so it declines rather than guessing.

CONDITIONAL. No `config.toml`, no check, no finding -- the same
validate-if-present shape `_check_racecar_mode` uses, and for the same reason:
absence is a legitimate state, so absence cannot be an error without
special-casing repos by name.

Output:
  - One line per finding: `check_config_closure: <severity>: <message>`.
  - Summary: `check_config_closure: OK` (exit 0) or `... N errors` (exit 1).

Usage:
    python3 <path-to>/check_config_closure.py [--root <path>]

Complexity: O(S + R), S = settings declared, R = lines in the README. Two
files read once each; no treewalk.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

from lib.shared._report import Findings, emit
from lib.shared._root import find_repo_root

#: A leaf in `config.toml` is a table that states what a setting owes. The file's
#: own header names these three as required: "`tiers`, `kind` and `default` are
#: the three a setting must state." Two are enough to tell a setting from the
#: nesting tables above it (`[acme]` may hold `data_dir` and `log_level` and is not
#: itself a setting).
_LEAF_KEYS = ("kind", "tiers")

#: What a setting-shaped claim looks like in prose, for the backward direction.
#: An UPPER_SNAKE token of two or more segments is an environment variable by
#: universal convention, and it is the only shape read: a backticked dotted key
#: would also match ordinary module paths, and a check that reports
#: `racecar.graph.check` as an undeclared setting is one nobody leaves on.
#:
#: A file name is not a setting either. `\b` fires between `R` and `.`, so without the
#: lookahead the stem of `CLAUDE_RACECAR.md` matches as a whole token; the lookahead
#: refuses a match followed by a full stop and a letter or digit, the shape of
#: `NAME.md` or `NAME.py`.
#: It names `.` only: `$RACECAR_HOME/scripts` is a variable followed by `/`, and a variable
#: that ends a sentence (`set FOO_BAR.` then a space or the end) is still read.
#: WHAT THAT GIVES UP: a variable typed with no space before the next word, `FOO_BAR.Next`,
#: is not read. That is a typo in prose, and a check that fails on every linked file
#: name to catch it is one nobody leaves on.
_ENVVAR = re.compile(r"\b([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)\b(?!\.[A-Za-z0-9])")

#: Environment variables that are not this repo's settings. `PATH` and friends
#: are the operating system's, and a README explaining how to run something
#: names them without claiming to own them.
_NOT_OURS = frozenset(
    {
        "PATH",
        "PYTHONPATH",
        "HOME",
        "SHELL",
        "EDITOR",
        "LC_ALL",
        "LANG",
        "TERM",
        "TMPDIR",
        "GIT_EDITOR",
        "GIT_SEQUENCE_EDITOR",
        "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL",
        "GIT_COMMITTER_NAME",
        "GIT_COMMITTER_EMAIL",
        "CI",
        "DEBIAN_FRONTEND",
        "SOURCE_DATE_EPOCH",
    }
)


def settings(declared: dict[str, Any], prefix: tuple[str, ...] = ()) -> dict[str, Any]:
    """Every declared setting, keyed by its dotted name.

    Walks nested tables because a real declaration nests: an `acme` table
    holding two settings is not one itself. A flat read would report `acme` as
    undocumented and miss both.
    """
    out: dict[str, Any] = {}
    for key, value in declared.items():
        if not isinstance(value, dict):
            continue
        if all(k in value for k in _LEAF_KEYS):
            out[".".join((*prefix, key))] = value
        else:
            out.update(settings(value, (*prefix, key)))
    return out


def env_names(spec: dict[str, Any]) -> list[str]:
    """The environment variables a setting's chain names, in tier order."""
    tiers = spec.get("tiers") or []
    return [
        str(tier.get("value"))
        for tier in tiers
        if isinstance(tier, dict) and tier.get("type") == "env" and tier.get("value")
    ]


def documented(readme: str, name: str, spec: dict[str, Any]) -> bool:
    """Is this setting named in the README, by dotted name or by env var?

    Either spelling counts. A README that says `ACME_DATA_DIR` has
    told the reader what to set; insisting it also write `acme.data_dir`
    would be gating a house style rather than a fact.
    """
    if name in readme:
        return True
    return any(env in readme for env in env_names(spec))


def literal_of(spec: dict[str, Any]) -> str | None:
    """The default as the string a README would carry, or None if it has none.

    A bool is rendered the way prose writes it, lowercase, because
    `default = true` in TOML is `true` to a reader. A nested default has no
    single literal and returns None, which the caller reads as "decline".
    """
    value = spec.get("default")
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, str)) and str(value).strip():
        return str(value)
    return None


def grade(root: Path, f: Findings) -> None:
    """Put `config.toml` and the README against each other, both ways."""
    config = root / "config.toml"
    readme = root / "README.md"
    if not config.is_file():
        f.info("no config.toml; nothing to close the README against")
        return
    if not readme.is_file():
        f.info("no README.md to grade")
        return
    try:
        declared = tomllib.loads(config.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError) as err:
        f.error(f"config.toml does not parse: {err}")
        return

    text = readme.read_text(encoding="utf-8", errors="replace")
    found = settings(declared)
    if not found:
        f.info("config.toml declares no setting; nothing to close")
        return

    for name, spec in sorted(found.items()):
        if not documented(text, name, spec):
            envs = env_names(spec)
            spelling = f" (or {', '.join(envs)})" if envs else ""
            f.error(
                f"config.toml declares `{name}`{spelling} and README.md never names "
                "it. A setting nobody wrote down is one an operator cannot discover."
            )
            continue
        literal = literal_of(spec)
        if literal is not None and literal not in text:
            f.error(
                f"`{name}` defaults to `{literal}` and README.md does not carry that "
                "literal. A documented default the declaration contradicts sends a "
                "reader somewhere the code never looks."
            )

    ours = {env for spec in found.values() for env in env_names(spec)}
    for claimed in sorted(set(_ENVVAR.findall(text)) - ours - _NOT_OURS):
        f.error(
            f"README.md names `{claimed}` and config.toml declares no setting for "
            "it. A setting deleted from the code and left in the prose sends a "
            "reader to a variable that does nothing."
        )


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, grade the pair, print findings, return an exit code."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=None, help="repo root")
    args = parser.parse_args(argv)

    root = args.root or find_repo_root(Path.cwd())
    if root is None:
        print("check_config_closure: info: not a repository; nothing to grade")
        print("check_config_closure: OK")
        return 0

    f = Findings()
    grade(root, f)
    return emit(f, "check_config_closure")


if __name__ == "__main__":
    sys.exit(main())
