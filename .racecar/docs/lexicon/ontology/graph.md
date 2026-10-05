---
name: graph
kind: schema
domain: [racecar]
summary: "one graph a repo declares: what its nodes are, what an edge means, who reads it"
pnode: [README.md]
bearing: contract
required: [node, edge, source, reader]
---

# `kind: graph`

One graph a repo declares. A repo has several — a doc graph, an import graph, an axiom
graph — and which ones it has is a fact about that repo rather than about racecar.

## Why this kind is delivered

Before it, the set was a tuple in racecar's own generator: eight functions, hardcoded.
Eight is racecar's number. An adopter has their own graphs and their own README, and a
generator that ships its author's list projects the wrong repo's structure into every
tree it reaches. Declaring the set moves it to the repo it describes, which is the same
scoping rule every other delivered kind follows: an adopter who declares none gets an
empty answer rather than somebody else's.

## The four required fields

`node:` and `edge:` say what ONE node is and what ONE edge means — "contract" and
"`import`" for the import graph. They are the column headings of any rendering, and they
are authored because no predicate recovers "an edge here means one module importing
another" from the tree.

`source:` is where the graph is read from: a path, or a glob. It is the answer to "where
would I look", and it is what a reader states rather than what a reader infers.

`reader:` names the code that counts it, as `module:function`. Explicit rather than found
by convention from `name:`, because a convention that resolves silently resolves wrongly
just as silently — and the failure would be a graph quietly reporting zero.

## What is NOT declared, and why

**The counts.** How many nodes, how many edges: those are the reader's return. Declaring
them would put a number in two places, and the copy in the declaration would be wrong
within one commit of anything moving. The rule is that a count is read from the artifact
that owns it, so it cannot drift from it.

**Whether the edges are countable.** A graph whose edges nothing declares — cross-
references in prose, say — reports `not declared`, which is a different statement from
zero. That distinction is the reader's to make and no declaration can express it.

## `edges:` is correspondence, not derivation

A graph may declare `edges:` — the other graphs it is CHECKED AGAINST, each with the file
that implements the check and what that check asserts. It is not a derivation edge: a checker
comparing two structures is not one structure building the other, and conflating them would
put a build order on a relationship that has none.

(No link here on purpose. This node is DELIVERED, and a relative link out of it has to
resolve at both ends of the delivery -- from `docs/rc_lexicon/ontology/` here and from
`.racecar/docs/lexicon/ontology/` in an adopter. The param pages are racecar's own and do
not travel, so naming one would be a dead link in every repo that received this.) Backward-pointing, like every other edge in a racecar graph: a node says what
it is checked against, never what checks it.

An `against:` naming something that is no declared graph is legal. The endpoints of a real
correspondence are not all graphs — a README is not one — and the claim is closed by the
implementing file existing rather than by both ends being declared.
