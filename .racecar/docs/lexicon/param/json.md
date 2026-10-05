---
name: json
kind: param
domain: [racecar]
type: boolean
defined: true
summary: emit the report as JSON on stdout instead of prose
pnode: [README.md]
bearing: contract
---

# json

Emit the command's report as JSON on stdout rather than the prose a person reads. Every verb
takes it: the form racecar builds a command in gives each verb `--json`. That is why it is
delivered, so a package that receives racecar knows the word without declaring it: a word that
many commands share is one they can otherwise come to mean different things by.

**It changes the rendering and never the work.** A command with `--json` does exactly what it
does without it, decides the same way, and exits the same code. Anything that only happens under
`--json` is a second behaviour wearing a formatting flag.

**Not a substitute for a declared output shape.** What the JSON contains is the leaf's own
`output()`, rendered on that verb's node in the nounspace; this flag only selects the
machine-readable rendering of it.
