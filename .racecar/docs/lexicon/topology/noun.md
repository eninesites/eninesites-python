---
kind: schema
name: noun
carrier: dir
domain: [racecar]
summary: "the tier a command group sits at"
pnode: [README.md]
bearing: contract
---

# tier: `noun`

The first tier, and the recursive one: a directory holding a `README.md` that declares
`kind: noun`. Its children are the nouns and verbs of that command group, which is the
containment rule this topology exists to state — a noun may contain nouns and verbs.

`carrier: dir`, and that is what makes nesting possible at all. `graph/topology/` is a noun
inside a noun, so `python -m racecar.graph.topology` is addressable; a tier that could not
hold another tier would flatten the CLI to one level.

**Position is the address.** `graph/topology/check.md` is
`python -m racecar.graph.topology check` because of where it sits, not because a field says
so — and the same path names `src/racecar/graph/topology/`, which is what
`scripts/lexicon.py` compares. What the node IS stays declared:
[`../ontology/noun.md`](../ontology/noun.md) says what a noun
owes, and a directory name implies nothing.
