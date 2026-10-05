---
name: racecar-lexicon
summary: >-
  The half of the lexicon racecar DELIVERS, authored here and landing at
  `.racecar/docs/lexicon/` in a governed repo. Every markdown file under here is canon
  racecar owns and overwrites there, the same contract the delivered checkers travel
  under; the repo's own `docs/lexicon/` is authored and is never touched.
pnode: [../../README.md]
bearing: contract
---

# `docs/rc_lexicon` — the half of the lexicon that travels

`docs/lexicon/` is racecar's own corpus: the words it fixes for itself, graded by
`scripts/lexicon.py` and `python -m racecar.graph`. This tree is the part of that corpus
that is **the same in every governed repo**, so racecar ships it rather than asking each
adopter to re-author it.

**Source and destination differ, and the names say which end you are at.** Here it is
`docs/rc_lexicon/`, beside `docs/lexicon/`, in the open — `rc_` marks the copy that
travels, and hiding racecar's own canon in a dot-directory would make the authored tree the
hard one to find. In an adopter it lands at `.racecar/docs/lexicon/`, because `.racecar/` is
one boundary for everything racecar owns in a repo: everything under it is racecar's,
overwritten on sync, never hand-edited. The layout inside that boundary mirrors the repo's
own, which is what lets `docs/lexicon` and `.racecar/docs/lexicon` be read as two halves of
one corpus without either needing a second name. The delivered checkers already have this
shape: authored in `scripts/`, received as `.racecar/scripts/`.

**Nothing declares the join, in the repo that receives it.** `docs/lexicon` and
`.racecar/docs/lexicon` are the pair, by position, and each is skipped when it is not on
disk — so a repo has the delivered kinds the moment the files land rather than one sync plus
one edit later. A repo that needs a third corpus declares it at
`[tool.racecar.lexicon] corpora` in `pyproject.toml`, beside its other bindings to racecar's
checkers, rather than in a corpus index where a reader would have to open one corpus to
learn that another exists.

**racecar joins its own canon by position too, not by declaring it.** The readers know both
spellings of the delivered corpus — `.racecar/docs/lexicon` where it lands, `docs/rc_lexicon`
where it is authored — because those are one corpus seen from the two ends of the delivery.
Declaring it instead would put it on the CUSTOM leg, which outranks the repo's own corpus, and
racecar would then be dogfooding the opposite precedence from the one it ships.

**The order is the resolution rule, and canon is LAST.**

    custom  >  the repo's own `docs/lexicon`  >  this corpus

A corpus a project declared at `[tool.racecar.lexicon] corpora` outranks everything: it is
the most specific statement in the repo, and a declaration that could be overruled by the
thing it was written to override would be pointless. The repo's own corpus next. Canon is the
FALLBACK — it supplies what nothing local says, and yields wherever something local does.

So a repo can narrow a delivered kind's `required:` and the narrower list wins. That is the
trade: `required:` composes with `base.required`, so a local answer that wins can make a gate
quieter than canon wrote it. The alternative makes canon unoverridable, and a repo that cannot
disagree with a default has no way to be right when the default is wrong for it. Both readers
print which copy was shadowed, so a quieter gate is visible rather than silent.

**The delivered copy carries its own provenance.** A sync writes `.racecar/.racecar-lexicon`
beside the corpus, holding git's tree object id for what it delivered — reproducible by hand
with `git rev-parse <ref>:docs/rc_lexicon` in a racecar checkout. A reader that finds a stamp
disagreeing with the tree leaves the delivered corpus OUT of the join and says so, because a
kind node is read as data: a `required:` list edited by hand in the delivered half changes
what every gate in the repo demands while still looking like canon. No stamp means trust it —
a corpus delivered before the stamp existed is not evidence of tampering.

The order of operations is the same for all three declarations: join the corpora, generate
the ontology / topology / graph from the union, then operate on that as everything used to
operate on `docs/lexicon` alone. Step one has one home per reader (`corpora`); step two is
built for the ontology and for the topology, and the graph's data walk still reads one tree.

A file here is graded as a document like any other — links resolve, `pnode` reaches the
root. Its home for "why is this delivered" is `src/racecar/lib/delivery/catalogue.py`,
beside every other deliverable. In the adopter, where the same bytes sit under a hidden
directory, being graded at all takes a carve-out: every other hidden directory is machine
state, so the checkers skip them, and `_files.CONTENT_DIRS` names `.racecar` as content.
