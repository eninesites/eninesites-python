# eninesites

## Orientation

"A command-line tool for eninesites" (`[project].description`): the Python package `eninesites`,
a client of the eninesites REST API and nothing else. It imports no server code and touches no
database; its only contract with the server is the API. First moves: `make install-dev`, then
`.venv/bin/python -m eninesites` lists every noun, and `make check` runs the gate.

## Architecture

racecar's `lib -> api -> surfaces`, one vertical per noun under `src/eninesites/<noun>/`
(sub-nouns nest, e.g. `artifact/role/`): `__main__.py` is the argparse surface, `api.py` holds one
function per verb and is the only place a request is decided, `lib/results.py` declares the
records it returns, `lib/renderer/plaintext.py` prints them. Everything that talks to the server
is shared in `src/eninesites/lib/client/`: `http.py` (the one opener, `http.py:79`), `credentials.py`
(which key, base URL, profile and site a command uses), `config.py` (the profile file),
`records.py` (request and record helpers). The declared spec is `surface.jsonl` and
`docs/lexicon/`.

## Conventions

- REST only. Every server call goes through `lib/client/http.py`. A verb with no REST endpoint
  raises `not_over_rest` (`records.py:135`, exit 2); never call a guessed endpoint.
- Precedence is racecar's: flag, then `ENINESITES_*` environment variable, then the config
  file, then the default. An explicit flag always wins.
- Never print an API key; `credentials.redact` (`credentials.py:149`) is the only form that
  reaches output. The config file is written 0600 in a 0700 directory.
- Add a noun, verb or param with `.racecar/scripts/surface.py create --surface cli`, not by hand.
- A file is passed as `--path`; `file` and `templates` are booleans in racecar's vocabulary.
- A missing required flag exits 2 with the help on stderr, not racecar's exit 0 (CLI.md B2):
  this CLI runs from cron. The decision is recorded in `lib/cli.py` `VerbParser`.
- Name a new noun without a hyphen: racecar builds the noun's word as its Python package name,
  and a hyphen makes it unimportable (`seo` replaced `seo-page` for this reason).
- Tests answer from `FakeServer` (`tests/conftest.py:69`); no test reaches a real host.
