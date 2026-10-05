---
name: param
kind: schema
domain: [racecar]
summary: "a param a verb takes, fixed once on a node of its own"
pnode: [README.md]
bearing: contract
required: [type]
---

# `kind: param`

A flag, fixed once for every verb that takes it.

## `type:`, and why it is the one required field

A param owes `type:` — `path`, `flag`, `string`, and so on. Like a
[verb](verb.md)'s `params:`, it is required because it is **checkable**: the declared type is
comparable against the `dest`/`type`/`action` the argparse tree actually builds, so the node
either agrees with the code or produces a finding.

## `required:`, `position:` and `defined:`, and what their absence means

Three optional fields, each with a default a node takes by omitting it:

| field | type | default | says |
|---|---|---|---|
| `required` | boolean | `false` | the verb refuses to run without it |
| `position` | list of `<noun>.<verb>` | `[]` | the verbs that take it by position rather than as a `--flag` |
| `defined` | boolean | `false` | a person has written its type, `required` and `position` |

`required` and `position` are checkable the way `type` is: argparse builds each verb's
arguments, so the node either agrees with every verb that takes the word or `check` reports
the verb it disagrees with (`param-use`). One node serves every verb, so a word that is
required in one verb and optional in another cannot be stated, and is reported rather than
chosen between.

`defined` is not checkable against the code, and is not meant to be. `create` writes a node
for each param it declares with `type: string`, `required: false`, `position: []` and
`defined: false`, because none of those can be known from a name, and the code built from
that node is a stub. `check` lists every `defined: false` param until a person sets them.

## A param's meaning is a node, not a field

A param is fixed once, at `<corpus>/param/<name>.md`, and a verb's `params:` list is
spellings pointing at that bucket.

    # docs/lexicon/param/data.md
    ---
    name: data
    kind: param
    domain: [acme]
    type: path
    summary: the corpus a command reads
    pnode: [README.md]
    bearing: contract
    ---

Which flags earn a node and which are left to their own `--help` is that bucket's own index
to say; the point here is that the meaning is never carried by the verb, so it is a
relationship between two nodes rather than a field on either, and a schema that describes one
node at a time cannot declare it. That is also why
this file can require `type:` and cannot require anything about which verbs use the word:
`required:` reaches the node it names and no further.
