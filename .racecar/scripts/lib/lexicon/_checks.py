"""The checks: one loop over the list of tuples, n methods, both directions.

Part of `lib.lexicon`, the package `scripts/lexicon.py` is a command line over. A module
of its own so a caller imports what it needs: the tests, the `lexicon` noun's api and
the delivered CLI all reach the same functions instead of loading a script.

Complexity: O(1) per tuple per check -- every read the checks need is on the Graph
"""

from __future__ import annotations

import re
from pathlib import Path

from lib.lexicon import _audit
from lib.lexicon._audit import (
    _DISTINGUISHABLE,
    _EXPECTED,
    _NARROWS,
    _NODES_CACHE,
    _cli_gap,
    _well_formed,
    verb_gap,
)
from lib.lexicon._graph import (
    Answer,
    Finding,
    Graph,
    Row,
    answer,
    footprint,
    undeclared,
    word_node,
)
from lib.lexicon._nodes import (
    API_NAMES,
    DEFAULT_DOMAIN,
    FLAG_TREE,
    NOUN_TREE,
    NOUNSPACE_REL,
    ONTOLOGY_REL,
    _has_prose,
    _sections,
    domains_of,
    ontology_path,
    root_noun,
)
from lib.lexicon._terms import instead_disagrees
from lib.shared import _frontmatter
from lib.shared._files import repo_files
from lib.shared._root import package_root

#: What a declared noun with no code is told. The lexicon writes no code, so the advice
#: names the tool that builds it. `racecar.surface` is not delivered, so an adopter with only
#: `.racecar/scripts/` needs racecar installed to run it, which is why the skill is named too.
ADVICE = (
    "Declared, and no code yet: `python -m racecar.surface create --surface cli --noun "
    "{noun}` (the `/racecar-surface` skill) builds it, or remove the declaration."
)


def nouns_of(g: Graph) -> dict[tuple[str, ...], Path]:
    """`{chain: the README that declares it}` — every noun the LIST names, from its own row.

    From the list of tuples, not from a walk. Each noun is a row with no verb, so
    `graph` is here whether or not it has verbs of its own.
    """
    root = root_noun(g.terms)
    return {
        () if row.noun == root else tuple(row.noun.split(".")): row.node
        for row in g.rows
        if row.verb is None
    }


def findings(g: Graph) -> list[Finding]:
    """Grade the package tree against the NOUNS the list names; return the findings.

    It grades and writes nothing: building the code a declaration describes is
    `racecar.surface create`'s, not the lexicon's.

    Two trees, compared shape for shape: a noun the list names must reach code, and a vertical
    must have an api for anything to reach it through. The per-VERB half is `implemented`, in
    the loop; what is left here is per-NOUN, which is a different question from any one tuple.
    """
    out: list[Finding] = []

    if not g.kinds:
        return [
            Finding(
                str(ontology_path(g.terms)),
                "no ontology declared. The nounspace cannot be graded against a set of "
                "directory names; declare `kinds:` here.",
                "implemented",
            )
        ]

    pkg = g.pkg
    if pkg is None:
        out.append(
            Finding(
                str(package_root(g.root)),
                "no single package found; cannot place a vertical.",
                "implemented",
            )
        )
        return out

    declared = nouns_of(g)
    if not declared:
        out.append(
            Finding(
                str(g.terms),
                "no noun declares itself. The nounspace is empty.",
                "implemented",
            )
        )

    for chain in sorted(declared, key=lambda c: (len(c), c)):
        node = declared[chain].relative_to(g.root)
        module = pkg.joinpath(*chain)
        rel = module.relative_to(g.root)

        # Two routes to code, graded INDEPENDENTLY. `scripts/` ships to repos that never
        # installed racecar, so a checker there cannot import the package it grades -- which
        # is why the script layer exists and why a noun can live entirely in it. Having
        # neither is the only failure.
        #
        # Independently, because a noun can have BOTH and the vertical's obligations do not
        # lapse because a second route exists. Skipping the vertical whenever a script
        # is present would contradict the coverage table printed directly above these
        # findings, where `bin` and `cli` are two columns scored separately.
        vertical = (module / "__init__.py").is_file()
        # A delivered script is addressed `<noun>`, flat, so it can only ever be the route to
        # a TOP-LEVEL noun. Keying on the LAST segment would make the sub-noun
        # `graph.topology` look for a script named for `topology` alone -- a file that
        # would merely share its last segment, and whose presence would silently stop
        # the sub-noun being graded.
        script = g.root / "scripts" / f"{chain[0]}.py" if len(chain) == 1 else None
        has_script = script is not None and script.is_file()

        if not vertical and not has_script:
            out.append(
                Finding(
                    str(node),
                    f"declares the noun {'.'.join(chain) or pkg.name!r}, which reaches "
                    f"no code: no vertical at {rel}"
                    + (
                        f" and no script at scripts/{chain[0]}.py"
                        if len(chain) == 1
                        else ""
                    )
                    + ". "
                    + ADVICE.format(noun=".".join(chain) or pkg.name),
                    "implemented",
                )
            )
            continue

        if (
            vertical
            and chain
            and not any((module / candidate).exists() for candidate in API_NAMES)
        ):
            out.append(
                Finding(
                    str(rel),
                    f"no {' or '.join(API_NAMES)}. Every surface reaches a noun through its "
                    "api, so a vertical without one can be reached by nothing.",
                    "implemented",
                )
            )

    # The reverse direction -- a package addressable as `python -m <pkg>.<noun>` that no node
    # declares -- is `check_undeclared_verbs`'s, whose answer carries the tuple that closes it.
    # Stating it here as well would report one undeclared noun twice.
    return out


def check_undeclared_verbs(g: Graph) -> list[Answer]:
    """A command the CLI offers that the list of tuples does not name.

    The one direction a loop over the list cannot take, because you cannot iterate
    declarations to find an undeclared thing — so it is a set difference with the list as one
    operand rather than a method on a tuple. racecar cannot check what it was not told, and
    this is how it says so.

    Only nouns the list already names are asked about. A verb of a noun nothing declares is
    that noun's finding, reported once by the projection check, and saying it again per verb
    would turn one fact into five.
    """
    if g.pkg is None:
        return []
    root = root_noun(g.terms)
    domain = (g.selected or (DEFAULT_DOMAIN,))[0]
    declared: dict[str, set[str]] = {}
    for row in g.rows:
        # A noun's own row declares the noun and names no verb.
        named = declared.setdefault("" if row.noun == root else row.noun, set())
        if row.verb is not None:
            named.add(row.verb)
    out: list[Answer] = []
    for chain, named in sorted(declared.items()):
        parts = tuple(chain.split(".")) if chain else ()
        module = ".".join((g.pkg.name, *parts))
        offered = g.cli.get(module)
        if not offered:
            continue
        where = g.terms.joinpath(*parts)
        out += [
            Answer(
                "",
                undeclared(domain, chain or root, verb, g.terms),
                (f"python -m {module} {verb}",),
                (
                    Finding(
                        f"{where}/{verb}.md",
                        f"`python -m {module} {verb}` is offered and has no node. Either "
                        "the command should not exist, or the lexicon should name it — "
                        f"`lexicon create --tuple {domain}/{chain or root}/{verb}`.",
                        "",
                    ),
                ),
            )
            for verb in sorted(offered - named)
        ]

    # And the same question one level up: a package addressable as `python -m <pkg>.<noun>`
    # that no node declares a noun. The rule stated as a rule -- a node absent from the
    # nounspace may not be a node.
    out += [
        Answer(
            "",
            undeclared(domain, child.name, None, g.terms),
            (f"python -m {g.pkg.name}.{child.name}",),
            (
                Finding(
                    str(child.relative_to(g.root)),
                    f"addressable as `python -m {g.pkg.name}.{child.name}` but no "
                    f"`{NOUNSPACE_REL}/{child.name}/README.md` declares it a noun.",
                    "",
                ),
            ),
        )
        for child in sorted(g.pkg.iterdir())
        if (child / "__main__.py").is_file() and child.name not in declared
    ]
    return out


def check_undeclared_flags(g: Graph) -> list[Answer]:
    """A flag used by more than one command, with no node fixing what it means.

    The missing direction. `check_flags` walks the NODES and asks whether the code agrees, so
    a flag in use with no node is never visited and never reported.

    **Why more than one site, and not every flag.** A flag used once is that command's
    own option; a flag used at eight is vocabulary, and an unfixed word is one two
    commands can quietly come to mean different things by. Requiring a node for every
    flag would fire on every single-use option on the first run, which is a gate an
    adopter switches off -- and would fix words that are not shared, which is not what a
    controlled vocabulary is for.

    Short flags are exempt: `-m`, `-F`, `-v` are terse spellings, and the word they spell is
    what a node fixes.
    """
    documented = set(g.flag_canon) | set(g.flag_local)
    # No `__main__.py` means no flags in use, so there is nothing a node could be missing
    # FOR. The audit is not merely empty here -- it cannot run: pointed at a repo with no
    # package root it fails with an import error that says nothing about vocabulary.
    combined: dict[str, set[str]] = (
        {flag: set(sites) for flag, sites in _audit.flag_sites(g.root).items()}
        if _audit.has_cli(g.root)
        else {}
    )
    for flag, sites in _audit.script_flag_sites(g.root).items():
        combined.setdefault(flag, set()).update(sites)
    out: list[Answer] = []
    domain = (g.selected or (DEFAULT_DOMAIN,))[0]
    for flag, sites in sorted(combined.items()):
        if not flag.startswith("--") or flag[2:] in documented or len(sites) < 2:
            continue
        where = ", ".join(sorted(sites)[:3]) + ("..." if len(sites) > 3 else "")
        out.append(
            Answer(
                "",
                undeclared(domain, "param", flag[2:], g.terms),
                tuple(sorted(sites)),
                (
                    Finding(
                        f"--{flag[2:]}",
                        f"accepted by {len(sites)} commands ({where}) and no node fixes "
                        "what it means. A word two commands share can drift between them; "
                        f"add docs/lexicon/param/{flag[2:]}.md.",
                        "",
                    ),
                ),
            )
        )
    return out


ROW = "| [{label}]({href}) | {second} | {gloss} |"


def index_body(root: Path, subdir: Path, second_key: str) -> str:
    """Render a tree's index table from its nodes' frontmatter.

    DERIVED, never stored. `DOC_GRAPH.md` forbids writing down what the graph already
    encodes — children are the inverse of `pnode` and are computed by scanning — and a
    hand-kept table points at files that no longer exist the moment a node moves.

    The gloss comes from each node's own `summary`, so a node owns its one-line
    description in the same place it owns its argument.
    """
    # The kind comes out of `meta`, which `_audit.nodes()` already parsed.
    # `kind_of(path)` reads FRONTMATTER, so calling it here would re-read and re-parse
    # the same file -- twice per row, since the sort key calls it too.
    table = []
    for path, meta in sorted(
        _audit.nodes(root, subdir),
        key=lambda pm: (str(pm[1].get("kind") or ""), pm[0].stem),
    ):
        href = path.relative_to(root / subdir).as_posix()
        second = (
            meta.get("kind", "?") if second_key == "kind" else meta.get(second_key, "?")
        )
        table.append(
            ROW.format(
                label=meta.get("name", path.stem),
                href=href,
                second=second,
                gloss=meta.get("summary", ""),
            )
        )
    return "\n".join(table)


def check_index(
    root: Path, subdir: Path, second_key: str, write: bool
) -> list[Finding]:
    # Every other check starts from the list of tuples, and this one correctly does not.
    # Its subject is a RENDERING of a directory against that
    # directory -- "does the table in this README still match the nodes beside it" -- and the
    # answer has to come from the directory or the table could omit a node and agree with
    # itself. Listing only what the tuples reach would drop the orphan nodes from the
    # index, which is the one place a reader would otherwise find them.
    """Hold a tree's index table to its nodes, or rewrite it when `write`.

    The duty is the block, and nothing else: a tree whose README carries the INDEX
    markers has published a derived table and must keep it true, and a tree without them
    has not. Requiring the block would conscript every adopter that keeps two extension
    nodes into maintaining a generated table — a duty racecar has and they do not.
    Deleting racecar's own markers is not a hole this needs to plug: every node declares
    the tree README as its `pnode`, so a README that stops existing is
    `check_doc_graph.py`'s finding, stated once where that rule lives.

    The check-vs-write split exploits idempotence: `want` (the regenerated form) is
    computed once and reused both to detect drift (`rebuilt == text`) and, when `write`,
    as the thing actually written -- the same shape `black --check` / `gofmt -l` /
    `terraform fmt -check` use, never a second derivation that could disagree with the
    first.
    """
    directory = root / subdir
    if not directory.is_dir() or not _audit.nodes(root, subdir):
        return []
    readme = directory / "README.md"
    if not readme.is_file():
        return []
    text = readme.read_text(encoding="utf-8")
    start, end = "<!-- BEGIN INDEX -->", "<!-- END INDEX -->"
    if start not in text or end not in text:
        return []
    head, rest = text.split(start, 1)
    _, tail = rest.split(end, 1)
    header = f"| term | {second_key} | in one line |\n|---|---|---|"
    body = index_body(root, subdir, second_key)
    want = f"{start}\n\n{header}\n{body}\n\n{end}"
    rebuilt = head + want + tail
    if rebuilt == text:
        return []
    if write:
        readme.write_text(rebuilt, encoding="utf-8")
        _NODES_CACHE.pop((root, subdir), None)
        return []
    return [
        Finding(
            str(readme.relative_to(root)),
            "index is stale against the nodes. Regenerate with `lexicon.py check "
            "--apply`; it is derived, not written.",
            "indexed",
        )
    ]


_COMMAND_IN_PROSE = re.compile(r"python -m ([a-z_][\w.]*)((?:\s+[a-z][\w-]*)*)")


def address_table(g: Graph) -> tuple[set[str], dict[str, set[str]]]:
    """`(dotted noun chains, noun -> its verbs)` — every address, FROM the list of tuples.

    Rebuilding this from node positions by walking the corpus would be a second answer
    to a question the list already answers. The chain for the root is the empty string, because
    that is how `python -m <pkg>` is spelled with nothing after the package.
    """
    root = root_noun(g.terms)
    nouns: set[str] = set()
    verbs: dict[str, set[str]] = {}
    for row in g.rows:
        chain = "" if row.noun == root else row.noun
        nouns.add(chain)
        known = verbs.setdefault(chain, set())
        if row.verb is not None:
            known.add(row.verb)
    return nouns, verbs


def command_prose_findings(g: Graph, exempt: tuple[str, ...] = ()) -> list[Finding]:
    """Every `python -m <pkg>…` written in prose, checked against the declared tree.

    **A sub-noun takes a DOT and a verb takes a SPACE**, because the launcher is a
    prefix-stripper over `python -m` and nothing else: `racecar graph.topology check` is
    `python -m racecar.graph.topology check` with the prefix removed. `ontology` and
    `topology` have their own `__main__.py`, so they are sub-nouns and
    `racecar.graph ontology check` is not a thing.

    `check_docs.py` validates a cited PATH; this validates a cited COMMAND.

    The lexicon is what makes it decidable — position is the address, so the tree already
    knows which segments are nouns.
    """
    nouns, verbs = address_table(g)
    root = g.root
    # The PACKAGE name, from the graph root's own `name:` -- not the directory, which is
    # `lexicon` and matches no module. Getting this wrong is silent: every citation reads as
    # belonging to some other package and the checker returns a confident zero.
    pkg = root_noun(g.terms)
    out: list[Finding] = []
    # `repo_files`, not a private rglob. The shared walk already excludes `.venv`, agent
    # worktrees and vendored trees; a hand-rolled one re-learns each exclusion by being
    # wrong about it first, which is why `tests/slow/test_repo_files.py` fails on a fourth
    # private walk appearing.
    scanned = sorted(repo_files(root, "*.md")) + sorted(repo_files(root, "*.py"))
    for path in scanned:
        rel = path.relative_to(root).as_posix()
        if any(rel == e or rel.startswith(e) for e in exempt):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "python -m " not in text:
            continue
        for match in _COMMAND_IN_PROSE.finditer(text):
            dotted, rest = match.group(1), match.group(2).split()
            head, *tail = dotted.split(".")
            if head != pkg:
                continue
            # `addressed` is the dotted noun chain walked so far -- a STRING, unlike the
            # tuple `chain` above.
            addressed = ".".join(tail)
            if addressed and addressed not in nouns:
                continue
            for word in rest:
                candidate = f"{addressed}.{word}" if addressed else word
                if candidate in nouns:
                    line = text[: match.start()].count("\n") + 1
                    out.append(
                        Finding(
                            f"{rel}:{line}",
                            f"`{match.group(0).strip()}` addresses the sub-noun `{word}` "
                            f"with a space. A sub-noun takes a dot: "
                            f"`python -m {pkg}.{candidate} …`.",
                            "prose",
                        )
                    )
                    break
                if word not in verbs.get(addressed, set()):
                    break
                addressed = candidate if candidate in nouns else addressed
    return out


def check_stub(row: Row, g: Graph) -> list[Answer]:
    """Is any node this tuple reaches still a stub — frontmatter, headings, nothing said?

    What stops `--apply` being a green button. A stub that satisfied the gate would make the
    whole comparison machine-satisfiable, which is P-07's vacuous check: the tool writes the
    answer and then agrees with it. `--apply` scaffolds the BUCKET nodes — `verb/<word>.md`
    and `param/<word>.md` — so those are exactly the nodes this has to reach, and it reaches
    them because the tuple names them.

    The test is CONTENT, not a marker. Authors mark hand-written words `bearing: draft`
    on purpose, so reporting every draft would hide a real stub among them. Emptiness
    cannot be gamed the way a field can.
    """
    written = [str(p) for p in footprint(row, g) if _has_prose(p)]
    empty = [
        Finding(
            str(node),
            "stubbed — frontmatter only, no prose. What the word MEANS cannot be "
            "derived, so `--apply` did not write it.",
            "stub",
        )
        for node in footprint(row, g)
        if not _has_prose(node)
    ]
    return answer(row, written, empty)


def check_domain(row: Row, g: Graph) -> list[Answer]:
    """Does every node this tuple reaches declare who fixes its word, and section it per domain?

    The subset rule is what makes each projection a rooted DAG rather than a set of fragments:
    a node whose domains are not a subset of its parent's leaves the parent's OTHER
    projections with a hole, and the union stays green while the projection does not.

    Only a LEAF owes a section per domain. A container spans domains because its children do —
    the root README carries `ansible` so `host/` has a parent in the Ansible projection — and
    that is a structural fact about the tree, not a claim that the word means two things.
    """
    if not g.partitioned:
        return answer(row, [], [])
    out: list[Finding] = []
    for node in footprint(row, g):
        rel = str(g.terms / node.relative_to(g.terms))
        mine = domains_of(node)
        if not mine:
            out.append(
                Finding(
                    rel,
                    "no `domain:`. Every lexicon node declares who fixes the word.",
                    "domain",
                )
            )
            continue
        container = node.name == "README.md"
        if len(mine) > 1 and not container:
            have = _sections(node)
            out += [
                Finding(
                    rel,
                    f"declares `domain: {mine}` but has no `## {dom}` section. "
                    "One file per named thing, one section per domain.",
                    "domain",
                )
                for dom in mine
                if dom not in have
            ]
        parent = (
            node.parent / "README.md"
            if node.name != "README.md"
            else node.parent.parent / "README.md"
        )
        if parent.exists() and parent != node:
            up = domains_of(parent)
            if up and not set(mine) <= set(up):
                out.append(
                    Finding(
                        rel,
                        f"domain {mine} is not a subset of its parent "
                        f"{parent.relative_to(g.terms)} {up} — that leaves a projection "
                        "rootless.",
                        "domain",
                    )
                )
    faulted = {f.where for f in out}
    kept = [
        str(p)
        for p in footprint(row, g)
        if str(g.terms / p.relative_to(g.terms)) not in faulted
    ]
    return answer(row, kept, out)


def check_required(row: Row, g: Graph) -> list[Answer]:
    """Does every node this tuple reaches carry what its own declared kind asks of it?

    The ontology doing its job. Without this the `required:` block is decoration:
    deleting a required field would produce no finding anywhere, because the reader
    tolerates the absence and `graph.ontology check` is a FIT SCORER — a percentage
    against a threshold — rather than a per-node gate. A scorer cannot say no about one
    node.

    A node declaring a kind the ontology does not is a finding too: the kinds are a closed set,
    so adding one is a decision somebody makes on purpose. Reported per node, it names
    the node, which is what a reader has to have.

    A RESERVED or RETIRED word owes its kind nothing beyond a replacement. `verb/lint.md` is a
    verb racecar deliberately does not ship, kept so the control-repo check is never named
    `lint`, and demanding `params:` of a word with no implementation would force a lie.
    """
    if not g.kinds:
        return answer(row, [], [])
    out: list[Finding] = []
    above = g.terms.parent.parent
    for node in footprint(row, g):
        meta = _frontmatter.load(node)
        declared = str(meta.get("kind") or "")
        spec = g.kinds.get(declared)
        if spec is None:
            out.append(
                Finding(
                    str(node),
                    f"declares `kind: {declared}`, which {ONTOLOGY_REL.as_posix()} does "
                    "not declare. Declare it, or use a kind that is.",
                    "required",
                )
            )
            continue
        if meta.get("status"):
            if instead_disagrees(str(meta["status"]), str(meta.get("instead") or "")):
                out.append(
                    Finding(
                        str(node),
                        f"declares `status: {meta['status']}` with no `instead:` — a "
                        "retirement that names no replacement says what to stop writing "
                        "and not what to write.",
                        "required",
                    )
                )
            continue
        missing = [
            field
            for field in (*g.base, *(spec.get("required") or []))
            if field not in meta
        ]
        if missing:
            where = node.relative_to(above) if above in node.parents else node
            out.append(
                Finding(
                    str(where),
                    f"kind {declared!r} requires {', '.join(missing)} — declared in "
                    f"{ONTOLOGY_REL.as_posix()} and absent here.",
                    "required",
                )
            )
    faulted = {f.where for f in out}
    kept = [
        str(p)
        for p in footprint(row, g)
        if str(p) not in faulted
        and str(p.relative_to(above) if above in p.parents else p) not in faulted
    ]
    return answer(row, kept, out)


def noun_reaches_code(chain: tuple[str, ...], g: Graph) -> list[Finding]:
    """Does the noun this tuple belongs to reach code, and can anything reach it?

    Two routes, graded INDEPENDENTLY. `scripts/` ships to repos that never installed racecar,
    so a checker there cannot import the package it grades -- which is why the script layer
    exists and why a noun can live entirely in it. Having NEITHER is the only failure.

    Independently, because a noun can have both and the vertical's obligations do not lapse
    because a second route exists. Skipping the vertical whenever a script is present
    would contradict the coverage table printed above these findings, where `bin` and
    `cli` are two columns scored separately.
    """
    if g.pkg is None:
        return []
    module = g.pkg.joinpath(*chain)
    rel = module.relative_to(g.root)
    vertical = (module / "__init__.py").is_file()
    # A delivered script is addressed `<noun>`, flat, so it can only ever be the route to a
    # TOP-LEVEL noun. Keying on the LAST segment would make the sub-noun
    # `graph.topology` look for a script named for `topology` alone -- a file that would
    # merely share its last segment, and whose presence would silently stop the sub-noun
    # being graded.
    scripted = len(chain) == 1 and (g.root / "scripts" / f"{chain[0]}.py").is_file()
    node = (g.terms.joinpath(*chain) / "README.md").relative_to(g.root)

    if not vertical and not scripted:
        return [
            Finding(
                str(node),
                f"declares the noun {'.'.join(chain) or g.pkg.name!r}, which reaches no "
                f"code: no vertical at {rel}"
                + (
                    f" and no script at scripts/{chain[0]}.py"
                    if len(chain) == 1
                    else ""
                )
                + ". "
                + ADVICE.format(noun=".".join(chain) or g.pkg.name),
                "implemented",
            )
        ]
    if vertical and chain and not any((module / c).exists() for c in API_NAMES):
        return [
            Finding(
                str(rel),
                f"no {' or '.join(API_NAMES)}. Every surface reaches a noun through its "
                "api, so a vertical without one can be reached by nothing.",
                "implemented",
            )
        ]
    return []


def check_implemented(row: Row, g: Graph) -> list[Answer]:
    """Does the tree implement what this tuple declares?

    The core, and the reason the list has to be AUTHORED rather than derived: if a
    generator wrote these nodes from the CLI, this would compare the CLI to itself.

    Two INDEPENDENT questions, and only one of them is unanswerable for the root. "Does the CLI
    offer this verb?" is answerable everywhere — the audit keys the root under the bare package
    name. "Does the noun's api expose it?" is not, because `src/<pkg>/api/` is the `api` NOUN's
    own vertical rather than the root's, so reading it would grade the root's verbs against a
    different node's. So the two are guarded separately.

    No guard on an empty `cli`. `offered is None` means "there is no CLI to ask", which
    `verb_gap` answers by leaving that half unanswered and still asking the api half.
    """
    verb = row.verb
    if verb is None:  # a noun's own row names no command; `grade` never passes one
        return answer(row, [], [])
    if g.pkg is None:
        return answer(row, [], [])
    chain = tuple(row.noun.split(".")) if row.noun != root_noun(g.terms) else ()
    module_path = ".".join((g.pkg.name, *chain))

    # The NOUN half, asked here rather than in a function of its own. It is the same question
    # one level up -- does the tree have what the lexicon names -- and splitting it out
    # would let the verb half be checked while the noun half is not.
    # Several tuples share a noun, so the same finding arrives several times; `grade` keeps one.
    unreachable = noun_reaches_code(chain, g)
    if unreachable:
        return answer(row, [], unreachable)
    reachable = g.api.get(".".join(chain)) if chain else None
    unmet = (
        verb_gap(verb, g.cli.get(module_path), set(reachable))
        if reachable is not None
        else _cli_gap(verb, g.cli.get(module_path))
    )
    if unmet is None:
        # The PASS case, and it answers rather than staying silent. `implemented` is the
        # evidence half of `(check, tuple, implemented, missing)`; a check that returned
        # nothing when it found nothing wrong could not be told from one that never ran.
        return answer(row, [f"python -m {module_path} {row.verb}"], [])
    rel = g.pkg.joinpath(*chain).relative_to(g.root)
    where = row.node.relative_to(g.root) if g.root in row.node.parents else row.node
    return answer(
        row,
        [],
        [
            Finding(
                str(where),
                f"declares the verb {row.verb!r}, which "
                + unmet.format(module=module_path, api=f"{rel}/api"),
                "implemented",
            )
        ],
    )


def check_cuts_across(row: Row, g: Graph) -> list[Answer]:
    """Does a word this tuple uses cut across more than one thing and still have no node?

    Symmetric for verbs and params, because "free-standing" means the same for both: it cuts
    across. The counts come from the list — a verb's users are the nouns whose tuples carry it,
    a param's are the `noun verb` pairs that declare it — so nothing is recounted by walking.

    Reporting only. `--apply` writes the FRAME for these nodes and never the prose, and that
    write belongs to the verb rather than to a grading method.
    """
    verb = row.verb
    if verb is None:  # a noun's own row uses no word; `grade` never passes one
        return answer(row, [], [])
    out: list[Finding] = []
    fixed: list[str] = []
    for bucket, word, users, over in (
        ("verb", verb, g.verb_users.get(verb, frozenset()), "nouns"),
        *(
            ("param", flag, g.param_users.get(flag, frozenset()), "verbs")
            for flag in g.attrs[row].params
        ),
    ):
        if len(users) < 2:
            continue
        node = g.terms / bucket / f"{word}.md"
        where = word_node(g, bucket, word)
        if where is not None:
            fixed.append(where)
            continue
        who = ", ".join(sorted(users)[:3]) + ("..." if len(users) > 3 else "")
        out.append(
            Finding(
                str(node),
                f"`{word}` cuts across {len(users)} {over} ({who}) and has no node.",
                "cuts-across",
            )
        )
    return answer(row, fixed, out)


def check_flag_type(row: Row, g: Graph) -> list[Answer]:
    """Does each param this tuple declares have a node that agrees with the code?

    Three questions per param, in the order a reader asks them: is the node well formed, does
    a local node contradict canon, and does the declared `type:` match what the code actually
    declares for that spelling.

    A local node may EXTEND the vocabulary and may not redefine it. Taking a disagreement to
    racecar is the fix; overriding it here would make the canon mean whatever the last repo
    said, which is the whole reason there is a canon.

    It may also NARROW it, which is not a redefinition (`_NARROWS`). A repo whose
    `--type` takes a closed set has made canon's `string` stricter, not false, so the
    canon-agreement check stands aside and the argparse-agreement check below decides.
    Otherwise such a repo could not conform by any edit to its own node: `enum`
    contradicts canon and `string` contradicts its own code.
    """
    out: list[Finding] = []
    agreed: list[str] = []
    for flag in g.attrs[row].params:
        node = g.flag_local.get(flag) or g.flag_canon.get(flag)
        if node is None:
            continue  # no node yet; `cuts-across` is what asks for one
        malformed = _well_formed(node)
        if malformed:
            where, _, what = malformed.partition(": ")
            out.append(Finding(where, what, "flag-type"))
            continue
        fixed = g.flag_canon.get(flag)
        narrows = fixed is not None and fixed.kind in _NARROWS.get(node.kind, set())
        if not node.canon and fixed and fixed.kind != node.kind and not narrows:
            out.append(
                Finding(
                    node.where,
                    f"`type: {node.kind}` contradicts canon, which declares "
                    f"`{fixed.kind}` in {fixed.where}. A local node may extend the "
                    "vocabulary and may not redefine it — take the disagreement to "
                    "racecar rather than overriding it here.",
                    "flag-type",
                )
            )
            continue
        actual = g.flag_types.get(f"--{flag}")
        if actual is None:
            continue  # documented for adopters; this repo has no occasion for it
        expected = _EXPECTED.get(node.kind)
        wrong = actual & _DISTINGUISHABLE if expected is None else set()
        if (expected is None and wrong) or (
            expected is not None and not actual & expected
        ):
            out.append(
                Finding(
                    node.where,
                    f"documented `type: {node.kind}` but this repo declares --{flag} as "
                    f"{sorted(wrong or actual)}",
                    "flag-type",
                )
            )
        else:
            agreed.append(f"--{flag}")
    return answer(row, agreed, out)


def check_flag_collision(row: Row, g: Graph) -> list[Answer]:
    """Does a param this tuple declares carry two incompatible types inside one domain?

    The case the per-domain sections deliberately do NOT cover. Two meanings across two
    domains is a fact of life and the node carries a section each; two meanings inside one
    domain is something the owner can and must fix, because racecar can rename its own flag
    and cannot rename Ansible's.

    `declared_flag_types` maps each flag to a SET of types; this asks whether the set
    has two members in it.
    """
    out: list[Finding] = []
    for flag in g.attrs[row].params:
        clashing = g.flag_types.get(f"--{flag}", frozenset()) & _DISTINGUISHABLE
        if len(clashing) > 1:
            out.append(
                Finding(
                    f"--{flag}",
                    f"declared as {' and '.join(sorted(clashing))} in this repo — one "
                    "spelling with two meanings inside one domain. Rename one; racecar "
                    "can fix its own words.",
                    "collision",
                )
            )
    # Negative, like `shipped`: it fires only on a spelling with two meanings, so a clean
    # answer is empty rather than a list of flags that are fine.
    return answer(row, [], out)


def check_indexed(row: Row, g: Graph) -> list[Answer]:
    """Is every node this tuple reaches carried by its tree's index table?

    The FORWARD half — is the lexicon in the surface — where the surface is the derived table
    in a tree's README. `docs/lexicon/README.md` and `docs/lexicon/param/README.md` each
    publish one, and a tree that publishes one has taken on keeping it true.

    Only a tree that carries the INDEX markers is asked. Requiring the block would conscript
    every adopter with two extension nodes into maintaining a generated table — a duty racecar
    has and they do not.
    """
    out: list[Finding] = []
    listed_ok: list[str] = []
    for node in footprint(row, g):
        # A tree's README carries the table; it is not a row in it. Asking for one is asking
        # the index to list itself.
        if node.name == "README.md":
            continue
        listed = index_rows(node.parent)
        if listed is None:
            continue  # this tree publishes no index, so it owes nothing
        if node.name in listed:
            listed_ok.append(str(node))
            continue
        out.append(
            Finding(
                str(node.parent / "README.md"),
                f"index carries no row for `{node.name}`. The table is derived from the "
                "nodes beside it; regenerate with `lexicon.py check --apply`.",
                "indexed",
            )
        )
    return answer(row, listed_ok, out)


def check_unindexed(g: Graph) -> list[Answer]:
    """Does any index table carry a row for a node that is not there?

    The REVERSE half — is the surface in the lexicon. A row pointing at a file that moved is
    the half a forward pass cannot see: every node can be listed and the table still carry
    rows for files nobody can open.
    """
    out: list[Answer] = []
    domain = (g.selected or (DEFAULT_DOMAIN,))[0]
    for subdir in (NOUN_TREE, FLAG_TREE):
        directory = g.root / subdir
        listed = index_rows(directory)
        if listed is None:
            continue
        out += [
            Answer(
                "",
                undeclared(domain, subdir.name, Path(href).stem, g.terms),
                (),
                (
                    Finding(
                        str(directory / "README.md"),
                        f"index carries a row for `{href}`, which is not a node here. The "
                        "table is derived; regenerate with `lexicon.py check --apply`.",
                        "",
                    ),
                ),
            )
            for href in sorted(listed)
            if not (directory / href).is_file()
        ]
    return out


def index_rows(directory: Path) -> set[str] | None:
    """The hrefs a tree's index table lists, or None when the tree publishes no table.

    None and an empty set are different answers and the difference is the whole rule: no
    markers means no duty, an empty table between markers means a duty being failed.
    """
    readme = directory / "README.md"
    if not readme.is_file():
        return None
    text = readme.read_text(encoding="utf-8")
    start, end = "<!-- BEGIN INDEX -->", "<!-- END INDEX -->"
    if start not in text or end not in text:
        return None
    block = text.split(start, 1)[1].split(end, 1)[0]
    return set(re.findall(r"\]\(([^)]+)\)", block))
