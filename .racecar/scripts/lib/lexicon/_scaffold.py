"""Writing: the entries `create` and `check --apply` put on disk, and nothing that grades.

Part of `lib.lexicon`, the package `scripts/lexicon.py` is a command line over. A
caller imports what it needs: the tests, the `lexicon` noun's api and the delivered CLI
all reach the same functions instead of loading a script.

Complexity: O(W), W = nodes written; nothing is read that the caller did not hand over
"""

from __future__ import annotations

from pathlib import Path

from lib.lexicon._corpora import Lexicon, LexiconError
from lib.lexicon._eligible import reserved_nouns
from lib.lexicon._graph import (
    Graph,
    Row,
    word_node,
)
from lib.lexicon._nodes import (
    DEFAULT_DOMAIN,
    corpus_domain,
    root_noun,
    verb_node,
)
from lib.shared import _frontmatter, _spec
from lib.shared._root import package_dir, project_name

#: What `create` says when given neither of its two forms. The lexicon writes entries and
#: never code, so a bare `create` is refused rather than read as a sweep.
CREATE_FORMS = (
    "name what to declare: `--noun N [--verb V [--param P ...]]`, or `--tuple "
    "DOMAIN/NOUN/VERB` as `check` reports it. The lexicon writes no code; "
    "`racecar.surface create --surface cli --noun N` builds a declared noun."
)


#: The fields a bucket node's kind requires (the delivered `ontology/verb.md` and
#: `ontology/param.md`), with the values `create` writes for them. A bucket node written
#: without them is refused by the `required` check on the next run of the same command.
_BUCKET_FIELDS = {
    "verb": {"params": "[]"},
    "param": {
        "type": "string",
        "required": "false",
        "defined": "false",
        "position": "[]",
    },
}


def _stub_node(name: str, kind: str, domains: list[str]) -> str:
    """Derivable frontmatter and an EMPTY body.

    The meaning cannot be derived, so it is not written. The fields the node's kind
    requires are, with the values `create` gives a new node of that kind.
    """
    head = [
        "---",
        f"name: {name}",
        f"kind: {kind}",
        f"domain: [{', '.join(domains)}]",
        *(f"{key}: {value}" for key, value in _BUCKET_FIELDS.get(kind, {}).items()),
        f"summary: TODO — what `{name}` means, and what it may not name",
        "pnode: [../README.md]",
        "bearing: draft",
        "---",
        "",
        f"# {name}",
        "",
    ]
    head += [f"## {d}" + "\n" for d in domains] if len(domains) > 1 else []
    return "\n".join(head) + "\n"


def scaffold_words(g: Graph, selected: list[str]) -> list[str]:
    """Write the FRAME for every cut-across word that has no node. `--apply` only.

    The write half of `cuts_across`, kept apart from it because a grading method never writes
    and `--apply` authorises rather than filters. Same counts, from the same list, so the
    report and the write cannot disagree about which words cut across.

    Only BUCKET nodes — `verb/<word>.md` and `param/<word>.md`. A node under a noun mints a
    tuple, and putting a verb into canon is the one intentional act in this system.
    """
    made: list[str] = []
    for bucket, users in (("verb", g.verb_users), ("param", g.param_users)):
        for word, who in sorted(users.items()):
            node = g.lexicon.own / bucket / f"{word}.md"
            if len(who) < 2 or word_node(g, bucket, word) is not None:
                continue
            node.parent.mkdir(parents=True, exist_ok=True)
            node.write_text(
                _stub_node(word, bucket, selected or [DEFAULT_DOMAIN]), encoding="utf-8"
            )
            made.append(str(node))
    return made


def parse_tuple(spec: str, lexicon: Lexicon) -> Row:
    """`domain/noun/verb` — the spelling `check` hands back and `create --tuple` takes.

    Slashes rather than commas so a shell needs no quoting, and three parts because that is
    what a tuple IS. The node path is derived rather than given: where a declaration goes is
    the graph's business, not the caller's.
    """
    parts = spec.split("/")
    if len(parts) != 3 or not all(parts):
        raise LexiconError(
            f"not a tuple: {spec!r} — a tuple is `domain/noun/verb`, three parts, "
            "exactly as `check` prints it"
        )
    domain, noun, verb = parts
    return Row(domain, noun, verb, verb_node(lexicon, noun, verb))


def plan_tuple(row: Row) -> str | None:
    """What `write_tuple` WOULD create for this tuple, or None because it would not.

    The preview and the act answer the same question, and they have to answer it the same
    way. Reporting the path unconditionally would tell a caller a node will be created
    when `write_tuple` declines it for already existing -- a dry run that overstates is
    worse than none, because it is the run people read before deciding.
    """
    return None if row.node.exists() else str(row.node)


def write_tuple(row: Row, g: Graph) -> str | None:
    """Put one tuple into canon: write the node that declares it. Returns the path, or None.

    **One of the intentional acts that put entries into canon.** `create --noun` (`declare`)
    and `derive --apply`, which calls `declare`, are the others, and each writes only when a
    person runs it by name; no gate writes a node under a noun. A verb the tree implements
    stays reported and ungraded until a person runs one of them.

    Never overwrites. A node that exists is a declaration somebody made, and this verb's job is
    to add one rather than to settle what an existing one says.
    """
    verb = row.verb
    if verb is None:
        raise LexiconError(
            f"{row.noun}: `create --tuple` mints a verb node; a noun's README is written by hand"
        )
    if row.node.exists():
        return None
    # The root node only, not `declare(root=...)`: that would also propose a spec row for a
    # verb the tree already implements, which is what this verb adopts.
    _root_node(g.lexicon, g.root)
    declare(g.lexicon, row.noun, verb, (), row.domain)
    return str(row.node)


def _root_node(lexicon: Lexicon, root: Path) -> list[str]:
    """Get-or-create the lexicon's root node, with the repo's README as its parent so every
    node below it is reachable.

    The root noun is named for the one package under `src/`, else for `[project].name`. A
    repo with no package still serves commands and needs a lexicon (SURFACES.md, "Homes"),
    and the flat `django` shape has none. The directory's name is never used: a worktree or
    a clone names it per checkout, so it would write a wrong noun without a word.
    """
    readme = lexicon.own / "README.md"
    if readme.is_file():
        return []
    package = package_dir(root)
    name = package.name if package is not None else project_name(root)
    if name is None:
        raise LexiconError(
            f"{readme} does not exist, {root / 'src'} holds no single package, and "
            f"{root / 'pyproject.toml'} declares no [project].name, so nothing names the "
            "lexicon's root noun. Declare [project].name, or write that README by hand"
        )
    lexicon.own.mkdir(parents=True, exist_ok=True)
    readme.write_text(
        _declaration(name, "noun", name, "../../README.md"), encoding="utf-8"
    )
    return [str(readme)]


def _declaration(name: str, kind: str, domain: str, pnode: str, **extra: str) -> str:
    """A node's frontmatter with a stub summary, and a heading. The meaning is not derived."""
    lines = [
        "---",
        f"name: {name}",
        f"kind: {kind}",
        f"domain: [{domain}]",
        *(f"{key}: {value}" for key, value in extra.items()),
        f"summary: TODO — what `{name}` means",
        f"pnode: [{pnode}]",
        "bearing: draft",
        "---",
        "",
        f"# {name}",
        "",
    ]
    return "\n".join(lines)


def _add_params(node: Path, params: list[str]) -> bool:
    """Append to a verb node's `params:` the ones it does not list. True when it changed."""
    listed = [str(p) for p in _frontmatter.load(node).get("params") or []]
    missing = [p for p in params if p not in listed]
    if not missing:
        return False
    head, body = _frontmatter.split(node.read_text(encoding="utf-8"))
    kept = (head or "").splitlines()
    line = f"params: [{', '.join(listed + missing)}]"
    at = next((i for i, text in enumerate(kept) if text.startswith("params:")), None)
    if at is None:
        kept.insert(next(i for i, t in enumerate(kept) if t.startswith("pnode:")), line)
    else:
        end = at + 1
        while end < len(kept) and kept[end].startswith("  -"):
            end += 1
        kept[at:end] = [line]
    node.write_text("---\n" + "\n".join(kept) + "\n---\n" + body, encoding="utf-8")
    return True


def declare(
    lexicon: Lexicon,
    noun: str,
    verb: str | None = None,
    params: tuple[str, ...] | list[str] = (),
    domain: str | None = None,
    *,
    root: Path | None = None,
) -> list[str]:
    """Declare a noun, a verb of it, and the verb's params: get-or-create. Returns what changed.

    With `root`, the repo the lexicon belongs to, it also gets-or-creates the lexicon's root
    node, and each verb's row in `surface.jsonl` there: `proposed`, with the params the
    lexicon declares, until a face builds it.

    Each node is written only where it is absent, and a verb node that exists gains only
    the params it does not list, so a second run with the same arguments changes nothing.
    A sub-noun (`graph.ontology`) declares each noun above it the same way. A param is
    listed in the verb's `params:` and gets a node at `param/<name>.md` where it has none, with
    `defined: false` and the type and defaults of a guess (`_param_nodes`) -- except that a
    word the union already types is written with that type. What any of them means is not
    derivable, so every summary is a TODO for a person to write.
    """
    if params and verb is None:
        raise LexiconError(f"{noun}: a param belongs to a verb; name one with --verb")
    changed: list[str] = [] if root is None else _root_node(lexicon, root)
    domain = domain or corpus_domain(lexicon)
    parts = [] if noun == root_noun(lexicon) else noun.split(".")
    if parts and parts[0] in reserved_nouns(lexicon):
        raise LexiconError(
            f"`{parts[0]}` is reserved by racecar's delivered lexicon and is not a noun a "
            "repo may declare; name the noun for what it does"
        )
    for depth in range(1, len(parts) + 1):
        readme = lexicon.own.joinpath(*parts[:depth], "README.md")
        if not readme.is_file():
            readme.parent.mkdir(parents=True, exist_ok=True)
            readme.write_text(
                _declaration(parts[depth - 1], "noun", domain, "../README.md"),
                encoding="utf-8",
            )
            changed.append(str(readme))
    if verb is not None:
        node = verb_node(lexicon, noun, verb)
        if not node.is_file():
            node.write_text(
                _declaration(
                    verb, "verb", domain, "./README.md", params=f"[{', '.join(params)}]"
                ),
                encoding="utf-8",
            )
            changed.append(str(node))
        elif _add_params(node, list(params)):
            changed.append(str(node))
        changed += [str(path) for path in _param_nodes(lexicon, domain, list(params))]
        if root is not None:
            changed += _spec_row(lexicon, root, noun, verb, node)
    return changed


def _spec_row(
    lexicon: Lexicon, root: Path, noun: str, verb: str, node: Path
) -> list[str]:
    """Get-or-create the verb's row in the repo's `surface.jsonl`.

    A `proposed` row takes the params the lexicon declares for the verb; a built row's
    params are its function's, which the face that built it wrote, so they are left alone.
    """
    group = _spec.ROOT_GROUP if noun == root_noun(lexicon) else noun
    spec = _spec.spec_path(root)
    ident = _spec.row_id(group, verb)
    rows = _spec.read_rows(spec) if spec.is_file() else []
    row = next((r for r in rows if r.get("id") == ident), None)
    if row is not None and row.get("status") != "proposed":
        return []
    params = [str(p) for p in _frontmatter.load(node).get("params") or []]
    return (
        [f"{spec}: {ident}"]
        if _spec.upsert_row(spec, ident, group, {"params": params})
        else []
    )


def _known_type(lexicon: Lexicon, name: str) -> str | None:
    """The `type:` an existing node for `name` declares, or None where none does.

    Looked up in the union, home by home in precedence order, taking the first node that
    declares a type. So a word racecar delivers, such as `json`, keeps its type in a repo
    with no racecar checkout.
    """
    position = f"param/{name}.md"
    for entry in (e for e in lexicon.entries if e.position == position):
        declared = _frontmatter.load(lexicon.path(entry)).get("type")
        if declared:
            return str(declared)
    return None


def _param_tree(tree: Path, domain: str) -> list[Path]:
    """The `param/` tree's own node, written the first time a param node lands in it.

    Every param node names `README.md` beside it as its parent, so a tree without one
    leaves each node pointing at nothing, which `check_doc_graph.py` refuses. The node
    carries no index table: a table is a duty only where a README publishes one.
    """
    readme = tree / "README.md"
    if readme.exists():
        return []
    readme.write_text(
        _declaration("param", "index", domain, "../README.md"), encoding="utf-8"
    )
    return [readme]


def _param_nodes(lexicon: Lexicon, domain: str, params: list[str]) -> list[Path]:
    """Write `param/<name>.md` for each param that has no node yet. Returns what it wrote.

    A node that exists is left exactly as it is, so the second verb to take a word takes it
    the way the first did. What a `create` writes is a guess and says so: `required: false`,
    `position: []`, and `defined: false` until a person sets them, and `type: string` unless
    a node the lexicon already reads types the word (`_known_type`). A local node may
    extend canon and may not redefine it, so writing `string` for a word canon calls
    `boolean` would make the lexicon check refuse the node `create` just wrote.
    """
    written: list[Path] = []
    for name in params:
        node = lexicon.own / "param" / f"{name}.md"
        if node.exists():
            continue
        node.parent.mkdir(parents=True, exist_ok=True)
        written += _param_tree(node.parent, domain)
        node.write_text(
            _declaration(
                name,
                "param",
                domain,
                "README.md",
                type=_known_type(lexicon, name) or "string",
                required="false",
                defined="false",
                position="[]",
            ),
            encoding="utf-8",
        )
        written.append(node)
    return written
