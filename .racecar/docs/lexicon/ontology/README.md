---
name: racecar-lexicon-ontology
summary: >-
  The index this directory's kind nodes hang from, and nothing else. Identity and a
  parent: the corpus-level statements belong to the corpus, and the corpus is the
  adopter's.
pnode: [../README.md]
bearing: contract
---

# The delivered kinds

Three kind nodes — [`noun.md`](noun.md), [`verb.md`](verb.md), [`param.md`](param.md) —
each naming a kind in its own `name:` and what that kind owes in its own `required:`. A
corpus picks them up because the tree they are delivered into, `.racecar/docs/lexicon`, is one
of the two corpora that join by position; it declares nothing to opt in. In racecar itself,
where they are authored rather than delivered, `[tool.racecar.lexicon] corpora` names this
directory instead.

**This index is stripped on purpose.** `discriminator`, `partition`, `base` and a `kinds:`
block are all statements about a CORPUS — which field names a node's kind, which field it
splits into projections along, what every node carries whatever its kind. This directory is
not a corpus; it is three nodes a corpus may join in. Declaring those keys here would give
each of them a second home, and on a join the delivered answer would be arguing with the
adopter's own. The repo's own `docs/lexicon/ontology/README.md` carries them for that corpus,
and an adopter's index carries them for the adopter's.

So the fields a kind node here names — `name`, `kind`, `domain`, `summary`, `pnode`,
`bearing` — are named as the reader will find them in the joining corpus's `base`, not
declared as required here.
