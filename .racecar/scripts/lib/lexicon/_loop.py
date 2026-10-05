"""The loop: every check, both directions, over the list of tuples.

Registration and dispatch only. The checks themselves are in `_checks`; this holds what
runs them, what a finding is worth, and how the answers become a report — so `_checks` can
grow a method without this file changing, which is the whole claim the design makes.

Complexity: O(C*R), C = registered checks, R = tuples; plus one sweep per reverse half
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, NamedTuple

from lib.lexicon import _checks, _params, _shipped, _specified
from lib.lexicon._graph import Answer, Finding, Graph, Row, row_order
from lib.lexicon._nodes import FLAG_DIR, NOUN_DIR
from lib.lexicon._scaffold import scaffold_words
from lib.lexicon._terms import read_terms, retirements, scan


class Method(NamedTuple):
    """One check, registered once, owing BOTH answers.

    Every question this tool asks has two directions, and a check that answers one of them is
    half a check:

        is the lexicon in the surface?   — for each tuple, does the tree have it
        is the surface in the lexicon?   — for each thing the tree has, does a tuple name it

    `undeclared_verbs` is the return leg of `implemented`; `undeclared_flags` is the
    return leg of `flag-type`. Registered apart, one could ship and the other be
    forgotten.

    `forward` runs per tuple and is the loop's half. `reverse` is handed the whole graph and
    sweeps the surface for what no tuple names — you cannot find a missing thing by iterating
    the things you have.

    BOTH are REQUIRED, and `NO_REVERSE` / `NO_FORWARD` are how a check says it has one. Each
    sentinel takes a reason, so "this question has one direction" is a claim somebody wrote
    down rather than a gap nobody noticed. The reason is itself checkable.

    `severity` lives here rather than on a finding because it is a fact about the QUESTION, not
    about an answer: a stub is a minor finding every time one is found, and deciding that
    per-finding is how two callers come to disagree about what the same check means.
    """

    name: str
    forward: Any
    reverse: Any
    severity: str


class NoReverse(NamedTuple):
    """A check with one direction, and the reason it has one.

    Not `None`. A missing second half and a deliberate absence look identical in code, and
    telling them apart afterwards is impossible.
    """

    why: str


def NO_REVERSE(why: str) -> NoReverse:  # pylint: disable=invalid-name
    """Declare that this question has no surface-to-lexicon direction, and say why."""
    return NoReverse(why)


class NoForward(NamedTuple):
    """A check with no per-tuple direction, and the reason it has none.

    The mirror of `NoReverse`. `forward` is handed a tuple, a tuple is a command, and a
    command's nodes declare this repo's own domain by construction. A question about a
    WORD -- does any node disown a domain whose CLI ships that word -- is asked of the
    corpus, not of a command, and `reverse` is the leg that sweeps the corpus.
    """

    why: str


def NO_FORWARD(why: str) -> NoForward:  # pylint: disable=invalid-name
    """Declare that this question has no lexicon-to-surface direction, and say why."""
    return NoForward(why)


# The whole of the growth story. A new check is ONE entry here; a new tuple, a new domain and
# a new param are zero lines anywhere. Order is report order and nothing else — no method
# depends on another having run.
METHODS: tuple[Method, ...] = (
    Method(
        "collision",
        _checks.check_flag_collision,
        NO_REVERSE(
            "a spelling with two types is a fact about the CODE alone; the lexicon cannot "
            "carry a contradiction for a sweep to find"
        ),
        "major",
    ),
    Method(
        "cuts-across",
        _checks.check_cuts_across,
        NO_REVERSE(
            "the reverse -- a bucket node for a word no tuple uses -- is canon serving "
            "adopters, not drift: a spelling this repo has no occasion for is still fixed"
        ),
        "major",
    ),
    Method(
        "flag-type", _checks.check_flag_type, _checks.check_undeclared_flags, "major"
    ),
    Method(
        "domain",
        _checks.check_domain,
        NO_REVERSE(
            "a domain is declared by nodes; the tree carries no domains to sweep"
        ),
        "major",
    ),
    Method(
        "implemented",
        _checks.check_implemented,
        _checks.check_undeclared_verbs,
        "major",
    ),
    Method("indexed", _checks.check_indexed, _checks.check_unindexed, "major"),
    Method(
        "required",
        _checks.check_required,
        NO_REVERSE(
            "required fields are the ontology's claim about nodes; code has none"
        ),
        "major",
    ),
    Method(
        "shipped",
        NO_FORWARD(
            "a tuple is a command, and a command's nodes declare this repo's own domain by "
            "construction -- so the per-tuple leg could only ever visit nodes the rule has "
            "nothing to say about. The borrowed words sit in the kind buckets no tuple "
            "reaches, which is the corpus, which is the reverse leg's subject"
        ),
        _shipped.shipped_findings,
        "major",
    ),
    Method(
        "specified",
        NO_FORWARD(
            "a node with no spec line is already a finding on both sides: built, and "
            "check_surface.py fails on the command it cannot find in the spec; not built, "
            "and `implemented` fails on the node. Only a spec line nothing asked for "
            "reaches neither, and that is the reverse leg"
        ),
        _specified.undeclared_rows,
        "major",
    ),
    Method(
        "param-use",
        _params.check_param_use,
        NO_REVERSE(
            "a param's use is graded from its node; code has no node to start from"
        ),
        "minor",
    ),
    Method(
        "defined",
        _params.check_defined,
        NO_REVERSE(
            "whether a person has defined a param is a fact about its node only"
        ),
        "minor",
    ),
    Method(
        "stub",
        _checks.check_stub,
        NO_REVERSE(
            "prose is written by hand; the tree has none for a sweep to compare"
        ),
        "minor",
    ),
)


def grade(g: Graph) -> list[Answer]:
    """Every check, both directions, as ONE flat list of `(check, tuple, implemented, missing)`.

    One loop over the list of tuples for the forward half — is the lexicon in the surface —
    then one sweep for the reverse — is the surface in the lexicon. A check supplies both or
    says in its registration why it has one.

    Flat, so a caller filters instead of walking a structure: every answer from every check in
    one list, each carrying which check it came from. `grade` stamps that name, because it is
    the one thing that knows which method it called.

    A REVERSE answer's `row` is a tuple the lexicon does not have, synthesised from the
    surface and feedable to `lexicon create --tuple`.

    Answers with the same check, tuple and gaps are kept once: several tuples reach one node,
    and a stubbed `param/strict.md` is one fact however many verbs declare `--strict`.
    """
    out: list[Answer] = []
    for method in METHODS:
        seen: dict[tuple[Row, tuple[str, ...]], Answer] = {}
        if not isinstance(method.forward, NoForward):
            for row in g.rows:
                # A noun's own row is not a command to grade. Skipped here, once, so no
                # per-verb check ever sees one.
                if row.verb is None:
                    continue
                for found in method.forward(row, g):
                    seen.setdefault((found.row, found.missing), found)
        if not isinstance(method.reverse, NoReverse):
            for found in method.reverse(g):
                seen.setdefault((found.row, found.missing), found)
        out += [found._replace(check=method.name) for found in seen.values()]
    return out


def gaps(graded: list[Answer]) -> list[tuple[str, str]]:
    """`(check, line)` for every DISTINCT gap any check found, in the order found.

    The one place an answer becomes a sentence. A method never formats for a surface, and a
    surface never re-derives what a method found. `checked` reads the same gaps as records.

    Deduplicated HERE and not in the answers, and the difference matters. Every tuple gets its
    own answer even when several reach one node -- that is the data, and collapsing it would
    lose which tuples were graded. A stubbed `param/strict.md` is still one fact, so the eight
    verbs that declare `--strict` must not print it eight times.
    """
    return [(check, str(gap)) for check, gap in _distinct(graded)]


def _distinct(graded: list[Answer]) -> list[tuple[str, Finding]]:
    """`(check, finding)` for every distinct gap, in the order found: `gaps`, as records."""
    seen: dict[tuple[str, Finding], None] = {}
    for found in graded:
        for gap in found.missing:
            seen.setdefault((found.check, gap), None)
    return list(seen)


def creatable(graded: list[Answer]) -> list[Row]:
    """Every tuple the lexicon does not have, from whichever check found it.

    A reverse answer names something the surface has and the lexicon does not, so the report is
    not only a complaint: `row` is the argument that closes it, ready for
    `lexicon create --tuple <domain>/<noun>/<verb>`.
    """
    reversed_checks = {
        method.name for method in METHODS if not isinstance(method.reverse, NoReverse)
    }
    return sorted(
        {
            found.row
            for found in graded
            if found.missing and found.check in reversed_checks and found.row.verb
        },
        key=row_order,
    )


def one_directional() -> list[tuple[str, str]]:
    """`(check, why)` for every check that answers only lexicon-to-surface.

    Printed rather than hidden. "This question has one direction" is a claim.
    """
    return [
        (method.name, method.reverse.why)
        for method in METHODS
        if isinstance(method.reverse, NoReverse)
    ]


def severity_of(name: str) -> str:
    """What a finding from `name` is worth. Read from the one place the check is registered."""
    for method in METHODS:
        if method.name == name:
            return method.severity
    return "major"


def by_severity(graded: list[Answer]) -> tuple[list[str], list[str]]:
    """`(major, minor)` — the split every surface renders and `--strict` decides on.

    Downstream of the loop and shaping nothing about it. A method never learns which of these
    its gap lands in; that is declared beside the check and applied here.
    """
    major: list[str] = []
    minor: list[str] = []
    for check, gap in gaps(graded):
        (minor if severity_of(check) == "minor" else major).append(gap)
    return major, minor


def _short(text: str, root: Path) -> str:
    """A path a reader can scan: repo-relative, and unchanged if it is not one of ours."""
    prefix = f"{root}/"
    return text.replace(prefix, "")


def matrix(graded: list[Answer], root: Path | None = None) -> list[dict[str, Any]]:
    """Every tuple against every check, as records: the whole answer set, nothing summarised.

    `grade` already returns one flat list; this is that list rendered for a reader, with the
    tuple spelled the way `create --tuple` takes it so a row can be acted on rather than only
    counted. Rows per run: checks x tuples, plus one per reverse answer.

    Nothing is dropped and nothing is collapsed. A reader asking "which checks passed for
    `arch check`" or "which tuples has any check nothing to say about" is filtering this, and
    a view that only showed failures could answer neither.
    """
    here = root if root is not None else Path.cwd()
    return [
        {
            "check": found.check,
            "tuple": f"{found.row.domain}/{found.row.noun}/{found.row.verb or ''}",
            "node": _short(str(found.row.node), here),
            "ok": found.ok,
            "implemented": [_short(x, here) for x in found.implemented],
            "missing": [_short(str(x), here) for x in found.missing],
        }
        for found in sorted(
            graded,
            key=lambda a: (*row_order(a.row), a.check),
        )
    ]


class Checked(NamedTuple):
    """One run of `check`: its findings as records, what `--apply` wrote, and the answers."""

    findings: list[dict[str, str]]
    made: list[str]
    answers: list[Answer]


def record(severity: str, subject: str, rule: str, message: str) -> dict[str, str]:
    """A finding as the record every racecar finding list uses (`racecar.lib._exit.Finding`).

    Plain dict with the same four field names rather than an import of the class, because
    this package is delivered to repos that never installed racecar.
    """
    return {"severity": severity, "subject": subject, "rule": rule, "message": message}


def checked(g: Graph, *, apply: bool = False) -> Checked:
    """Run the whole lexicon check once: every route that runs `check` calls this.

    The loop's answers, graded by the severity each check registers; the per-noun half of
    `implemented` (`findings`), where the repo declares a nounspace; prose that addresses a
    command wrongly; both index tables; the retired terms; and a word this repo's own code
    reserves with no node to explain it. `apply` writes what is
    derivable: the index tables, and the frame of a word that cuts across. A fact found by two
    of these is one record, reported once.
    """
    answers = grade(g)
    out: list[dict[str, str]] = []
    for check, gap in _distinct(answers):
        out.append(
            record(
                severity_of(check).capitalize(),
                _short(gap.where, g.root),
                check,
                gap.what,
            )
        )
    made = scaffold_words(g, list(g.selected)) if apply else []
    extra: list[Finding] = []
    if g.kinds:
        extra += _checks.findings(g)
    # CHANGELOG.md is a RECORD: it says what was true at the time and is never rewritten.
    extra += _checks.command_prose_findings(g, exempt=("CHANGELOG.md",))
    extra += _checks.check_index(g.root, FLAG_DIR, "type", apply)
    extra += _checks.check_index(g.root, NOUN_DIR, "kind", apply)
    out += [record("Major", _short(f.where, g.root), f.method, f.what) for f in extra]
    words = read_terms(g.root)
    if words:
        out += [
            record("Major", hit.where(), "retired", hit.message())
            for hit in scan(g.root, words, retirements(words))[1]
        ]
    unique = list({tuple(r.items()): r for r in out}.values())
    return Checked(unique, made, answers)


def exit_code(findings: list[dict[str, str]], strict: bool) -> int:
    """1 on any Major finding, and on a Minor one only under `strict`; else 0."""
    counted = {"Major", "Minor"} if strict else {"Major"}
    return 1 if any(f["severity"] in counted for f in findings) else 0
