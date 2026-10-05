"""Implementation behind the delivered scripts. Nothing here is ever run directly.

**Two categories, two homes.** A file directly under `scripts/` is something an adopter
RUNS -- `lexicon.py`, `ontology.py`, `topology.py`, `graph.py`, and every `check_*.py`.
Anything under `scripts/lib/` is something a run IMPORTS and nobody invokes. Keeping them
apart is what this directory is for, and the rule is checkable: every top-level
`scripts/*.py` carries a `__main__` guard, and nothing below here does.

**Why `lib/<noun>/` and not `<noun>/lib/`**, which would mirror `src/racecar/<noun>/lib/`
and read better: it cannot exist. `scripts/lexicon.py` is the entry point an adopter runs,
and a `scripts/lexicon/` package beside it SHADOWS it -- Python resolves `import lexicon`
to the directory and the module becomes unreachable. The delivered scripts import each
other as flat siblings (`import topology`), so the breakage is silent: the import succeeds
against the wrong object and fails somewhere else entirely. The nesting is forced, and
this note exists because the asymmetry reads as an oversight someone will try to tidy.

`lib` is therefore a reserved name here: no noun may ever be called `lib`.

**The base nouns live here, entirely.** Ontology, topology, lexicon, surface, graph and
package: their code is in `scripts/`, and `src/racecar/<noun>/` is only a wrapper over it,
through which `python -m racecar.<noun>` and the server reach the same code. `scripts/` is
delivered, so an adopter with no racecar installed runs every one of them.

**Every noun has one shape**, so a reader who has learned one has learned all six:

    scripts/
      <noun>.py              the entry: `parser(prog)` and `main(argv, prog)`, nothing else
      lib/<noun>/
        __init__.py          re-exports, nothing else
        _<verb>.py           one per verb: `run(...)` returns the verb's record, printing
                             nothing; `main(...)` prints that record -- through
                             `renderer.text` in prose, or as the record itself under `--json`
        renderer/
          text.py            every line this noun prints, rendered from a record
        _<helper>.py         anything else, named for its job

  - `scripts/<noun>.py` builds the parser in `parser(prog)` and dispatches in `main`. It
    holds no verb's work, so a verb's body has one home and every flag is read from one
    parser.
  - `lib/<noun>/_<verb>.py` exists for each verb that parser declares (`check-json` is
    `_check_json.py`) and ends in the `not_a_command()` guard. `run` is the work and its
    record is the verb's one result; `main` only chooses how to show it.
  - `lib/<noun>/renderer/text.py` is the only place a verb's text is made. Both routes print
    through it, so they print the same lines because the lines have one home.
  - `src/racecar/<noun>/__main__.py` builds its parser from `parser()` and hands its argv to
    `main()`, under its own `prog`; `src/racecar/<noun>/api.py` returns what the verbs'
    `run` return, and prints nothing. Neither renders.

Anything else below `lib/<noun>/` is a helper named for its job. `tests/test_noun_shape.py`
holds these rules for every `lib/<noun>/` that has a `scripts/<noun>.py`.

Complexity: O(1) -- a namespace, a rule, one path and one loader
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import NoReturn

#: `scripts/`, where the delivered checkers sit as flat siblings. ONE home for the depth,
#: for the two modules that need the directory as a PATH -- locating `check_cli_commands.py`
#: on disk. A module's own `parents[2]` is the number a move gets wrong SILENTLY: each
#: derived path resolves under the wrong directory and a checker reports a file it never
#: looked for.
#:
#: **It is not put on `sys.path` here, and nothing needs it to be.** Both ways in already
#: carry it: running `scripts/<noun>.py` puts the script's own directory there, and
#: `racecar.lib._dispatch.load_package` inserts the search directory before it imports.
#: An insert here would be a third, and an import with a side effect on interpreter state
#: is the magic this repo refuses.
SCRIPTS = Path(__file__).resolve().parent.parent


def not_a_command() -> NoReturn:
    """Refuse a direct `python scripts/lib/<noun>/<module>.py`. Never returns.

    The delivered twin of `racecar.lib._exit.not_a_command`, and it exists for the same
    reason: a module with no guard at all imports as `__main__`, runs nothing, and exits
    **0**, so anything invoking it becomes a step that checks nothing and reports that it
    passed. Exit 1 cannot be mistaken for that.

    `check_cli_commands._declares_not_a_command` recognises this by NAME -- the guard's
    body must be exactly one call spelled `not_a_command` -- so the delivered modules
    cannot simply inline `sys.exit(1)` and keep that checker's meaning.
    """
    raise SystemExit(1)


def load_file(source: Path, name: str) -> ModuleType:
    """The module in `source`, imported by file location under the private `name`.

    For code that belongs to the repo being read rather than to this one: a repo's CLI
    audit, or one of its CLI leaves. `sys.modules` caches by name, so a bare import of a
    second repo's module would return the first repo's; a name the caller keys on the
    repo or the file keeps them apart. The name is registered only while the module
    executes, which is what lets its own imports resolve it, and is removed afterwards.

    Raises ImportError when `source` has no import spec. Whatever the module raises as
    it executes propagates, for the caller to report in its own terms.
    """
    spec = importlib.util.spec_from_file_location(name, source)
    if spec is None or spec.loader is None:
        raise ImportError(f"no import spec for {source}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module
