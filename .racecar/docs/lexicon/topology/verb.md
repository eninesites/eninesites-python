---
kind: schema
name: verb
carrier: file
domain: [racecar]
summary: "the leaf tier: a command, which contains nothing"
pnode: [noun.md]
bearing: contract
---

# tier: `verb`

The last tier: one command, at `<noun>/<verb>.md`.

`carrier: file` (issue #74), and it is the clearest case the option exists for. A verb
contains nothing — that is the second half of the containment rule — so a node at this tier
is inherently childless and a directory holding a lone `README.md` would be a container with
nothing to contain. Only the last tier may be `carrier: file`, for exactly that reason: a
file cannot hold a further tier inside it.

Its `pnode` is [`noun.md`](noun.md), which is what puts it after `noun` in the chain rather
than beside it.

Not to be confused with `../verb/`, the BUCKET. A node at `<noun>/<verb>.md` is a verb's
USE, exhaustive so the tree can be a source; a node at `verb/<verb>.md` is that word's
MEANING, and earns its place only when the verb cuts across nouns. Both declare
`kind: verb`; the tier is about where a node sits, not what it is.
