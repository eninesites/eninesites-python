---
name: verb
kind: schema
domain: [racecar]
summary: "a command: what it takes, and where its binding to code is written"
pnode: [README.md]
bearing: contract
required: [params]
---

# `kind: verb`

A command — one word run against a [noun](noun.md), living at `<noun>/<verb>.md` because
position is the address: `graph/topology/check.md` is
`python -m racecar.graph.topology check`.

## `params:`, and why it is the one required field

A verb owes `params:`: the flags it declares, as spellings, in one list. It is required
because it is **checkable** — `scripts/lexicon.py` compares the list against what argparse
builds for that command, so a node that drifts from its own code is a finding rather than a
stale sentence. A kind whose `required:` cannot fail would be the decoration racecar's P-07
(intent over ceremony) names; this one fails the moment a flag is added and not written down.

There is no second file listing a verb's flags. The list is spellings only — what each
spelling MEANS is [`param`](param.md)'s job, and a word taking a node there is a
relationship between two nodes rather than a field on either.

A verb that ships nothing is exempt. `verb/lint.md` is reserved rather than implemented, and
demanding `params:` of a word with no implementation would force a lie — the
`status:`/`instead:` exemption suspends every kind's `required:`, not just this one.

## `invocations:`, optional: the command lines that exercise the verb

A verb may declare the command lines a before-and-after comparison runs, beside its
`params:`: one entry per line, the arguments after the verb as a string, or a mapping with
`args`, `before` (the noun's own flags, which go ahead of the verb, such as `--root`) and
`fixture` (a repo-relative directory inside the tree's copy that the line runs from).

    invocations: ["", "--json", {before: "--root examples", args: ""}]

It lives here, and not in the code, because a check carries information only when its two
terms were authored apart (P-07): the list says which paths matter, and the code is what
runs them. Every entry of a built verb runs, whatever its kind: each line runs in its own
copy of the tree, with a scratch home and no credentials in its environment, so what a
`write` line writes lands in the copy and nothing it does can reach a tracker, a bucket or a
host that needs a key. The parser's own lines — the bare node, `-h`, an unknown verb and
flag, `<verb> -h` — are derived and never declared. `python3 .racecar/scripts/surface.py
check` reports a built `read` or `write` verb with no entry, and `update` proposes one from
its parser for the author to prune. A `job` verb owes none: it starts work that keeps
running, so a line replaying it is chosen, never demanded. `surface create` writes
`invocations: [""]` on each `read` or `write` verb it records that declares none.

## A verb's binding is not in this corpus at all

It is a module-level `VERBS = {...}` dict in the noun's `api.py`, mapping the CLI spelling to
the function that runs it. Spelling and binding are separate because forcing them to be one
string lets Python edit the vocabulary (#136): `list` is a builtin, and `import` cannot be
bound at any level of indirection — `import.py` is a SyntaxError and `importlib` raises on it
— so two ordinary CLI words would be unavailable. As a dict key the same word is just data.

    # src/acme/store/api.py
    from acme.store.lib._import import fan_out

    VERBS = {"import": fan_out}

The map is optional, so a repo that has never heard of it is graded exactly as before, and a
repo may adopt it for one awkward verb and bind the rest by name. Its keys must be string
literals: a map built at run time exposes nothing the checker can read, and a verb declared
that way would read as undeclared, so `unreadable_verb_maps` reports a `VERBS` it cannot read
rather than skipping it in silence.

`VERBS = {}` is legal and exposes nothing beyond the `def`s and import aliases already in the
file — an empty literal is readable, so it is not a finding, and a repo with no awkward verb
needs no map at all.

## The second map, which racecar does not read

A repo whose CLI dispatches by table rather than by argparse subparsers carries a second map,
private to the leaf:

    # src/acme/store/__main__.py
    _KINDS = {"create": "write", "build": "write", "report": "read", "list": "read"}

    _VERBS = {
        "build": _build.main,
        "create": _create.main,
        "list": _list.main,
        "report": _report.main,
    }

The two are not one map wearing two names. `api.VERBS` is the exposed surface every other
surface reaches the noun through, which is why it is the one graded; `_VERBS` is how that
repo's command line reaches it. Underscored, so neither is part of the api.

`_KINDS` beside them marks which verbs write. **racecar carries that fact somewhere else** —
`surface.jsonl` gives every row a `kind` of `read`, `write` or `job`, 41 rows
today — so the leaf dict above is one adopter's way of holding it, not a racecar convention,
and this node does not grade it either way. It is shown because a reader who has seen that
shape should know which of the two maps racecar reads.

## racecar declares no `VERBS` map of its own, and still shadows the builtin

`src/racecar/lexicon/api.py` binds `list` directly, paying a `redefined-builtin` suppression
and giving up annotations for the whole file. That shadow is now removable in principle and
is deliberately left: `surface.jsonl:38` binds `lexicon.list` by name, and
that file is owner-authorized. Changing the binding is a decision somebody makes, not a
cleanup, and an adopter reading this should know the mechanism is carrying its author's own
exception.
