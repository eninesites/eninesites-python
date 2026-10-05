---
name: noun
kind: schema
domain: [racecar]
summary: "a command group, and a position that is its address"
pnode: [README.md]
bearing: contract
required: []
---

# `kind: noun`

A command group: what `python -m <pkg>.<noun>` addresses, declared by a `README.md` that
says `kind: noun`.

    # docs/lexicon/store/README.md
    ---
    name: store
    kind: noun
    domain: [acme]
    summary: the artifact store and the verbs that move things into it
    pnode: [../README.md]
    bearing: contract
    ---

## Why it requires nothing of its own

A noun owes exactly what the joining corpus's own `base` already demands of every node — a
name, a kind, a domain, a summary, a parent, a bearing — and nothing further. Its two other
facts are not fields:

- **What it contains** is its position. A noun's verbs are the `*.md` beside its
  `README.md`, and its sub-nouns are the directories under it; nothing about a verb is
  stored on the noun, so there is no `verbs:` list to require and none to let drift.
- **Which tier it may sit at** is the corpus's declared topology's, not this file's. The
  ontology says a noun is a thing; the topology says where a noun is allowed to sit.
  Requiring a field here to restate the containment rule would give one fact two homes.

The discriminator does the work a directory name cannot. `graph/` holds a noun and its
commands; a node declaring `kind: noun` is one whatever it is filed under.
