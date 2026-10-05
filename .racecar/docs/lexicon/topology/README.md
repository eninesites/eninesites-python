---
name: racecar-lexicon-topology
summary: >-
  The index this directory's tier nodes hang from, and nothing else. Identity and a
  parent: the corpus-level statements belong to the corpus, and the corpus is the
  adopter's.
pnode: [../README.md]
bearing: contract
---

# The delivered tiers

Two tier nodes — [`noun`](noun.md) and [`verb`](verb.md) — each carrying its own
`carrier:` and the argument for its own shape. Together they are the containment rule
every governed repo's CLI already obeys:

    a noun may contain nouns and verbs; a verb contains nothing.

That is why they travel. A noun is a command group and a verb is a command in every repo
racecar governs — the same reason `noun`, `verb` and `param` travel one directory over in
[`../ontology/`](../ontology/README.md) — so re-authoring them per repo would be asking
each adopter to restate a shape they have no freedom about anyway.

**The order is the `pnode` chain**, and it is self-contained here: `noun.md` takes its
`pnode` from this index and `verb.md` from `noun.md`, so reading down gives back
`noun -> verb` without either end reaching into the joining corpus. A tier contains the
next one, so containment and order are the same fact rather than two that can disagree.

**This index is stripped on purpose**, exactly as [`../ontology/README.md`](../ontology/README.md)
is. `root_pattern`, `partition` and `buckets:` are statements about a CORPUS — which paths
are roots, which field the corpus splits into projections along, which depth-1 directories
are word buckets rather than nouns. This directory is not a corpus; it is two tiers a
corpus may join in. racecar's own `docs/lexicon/topology/README.md` carries those keys for
racecar's corpus, and an adopter's index carries them for the adopter's — shipping a copy
would have every join argue with the repo's own answer, and `buckets:` in particular is a
list of racecar's own word trees that means nothing in another repo.
