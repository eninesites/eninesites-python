---
pnode: []
bearing: orientation
---

<!-- This README follows stripe-cli's shape by owner decision (2026-10-05), not racecar's
     templates/classic README; racecar's doc-drift report lists the template headings it lacks. -->

# eninesites CLI

The eninesites CLI lets you build and manage eninesites websites from the terminal, so the
same work runs from a script or a cron job as easily as by hand.

> **Status: early.** Every command below calls the eninesites REST API, except the few
> listed under [Not available over the API](#not-available-over-the-api).

**The CLI covers:**

- Sites: create, list, copy, configure, dump, load and restore
- Content: artifacts and their roles, maps, tags, images, design and AEO data
- Tags, external URLs, URL maps, media and site users
- Themes and custom themes
- XEO audits and AEO JSON-LD inspection

## Installation

The CLI needs Python 3.12 or later. It is not on PyPI yet; install it from GitHub.

### pipx (recommended)

```sh
pipx install git+https://github.com/eninesites/eninesites-python
```

### pip

```sh
pip install git+https://github.com/eninesites/eninesites-python
```

### From a clone

```sh
git clone https://github.com/eninesites/eninesites-python
cd eninesites-python
make install-dev
```

## Upgrading

```sh
pipx upgrade eninesites
# or
pip install --upgrade git+https://github.com/eninesites/eninesites-python
```

## Uninstalling

```sh
pipx uninstall eninesites
# or
pip uninstall eninesites
```

## Authentication

The CLI authenticates with an eninesites API key, sent as `Authorization: Token <key>`. An
eninesites operator issues keys; there is no browser sign-in for the API.

```sh
python -m eninesites login                 # paste the key at the hidden prompt
printf %s "$KEY" | python -m eninesites login   # or pipe it, for scripts and cron
python -m eninesites config                # which key, base URL and site a command uses
python -m eninesites logout                # remove the stored key (--all: every project)
```

`login` checks the key against the server before it stores it. Every command that talks to
the API also takes:

| Flag | Environment | Config key | Default |
|---|---|---|---|
| `--api-key` | `ENINESITES_API_KEY` | `api_key` | none |
| `--base-url` | `ENINESITES_BASE_URL` | `base_url` | `https://eninesites.com` |
| `--project-name` | `ENINESITES_PROJECT_NAME` | (the profile) | `default` |
| `--domain` | `ENINESITES_SITE` | `site` | none |

A flag beats the environment, which beats the config file. `python -m eninesites.site select
--domain example.com` stores the site later commands use when `--domain` is not given. It
checks the site with the server first and saves nothing if the site does not exist or you
are not a member of it.

The config file is `$XDG_CONFIG_HOME/eninesites/config.toml`, else
`~/.config/eninesites/config.toml`, with one `[profiles.<name>]` table per project. It is
written with mode 0600 in a 0700 directory. The key is never printed: `config` shows its last
four characters only. `--base-url` must be https, or http to `localhost` for a local server:

```sh
python -m eninesites login --project-name dev --base-url http://localhost:8000
python -m eninesites.site list --project-name dev
```

Write commands that take fields the flags do not name accept `--data`, a JSON file holding
those fields (`-` reads it from stdin), for example
`echo '{"card_template": "card"}' | python -m eninesites.artifact.design update --slug services --data -`.
Commands that send a file (`site load`, `site restore`, `site configure`,
`theme custom import`) take it as `--path <file>`.

## Usage

```sh
python -m eninesites                     # list every command
python -m eninesites.site --help         # the verbs of one noun
python -m eninesites.site create --help  # the options of one verb
```

A command is `python -m eninesites.<noun> <verb> [options]`; a sub-noun is dotted, as in
`python -m eninesites.artifact.role assign`.

`site create` puts a new site on the server's default plan unless you pass `--plan`. A site on
a plan without API access cannot be managed with this CLI; pass a plan that includes it.

## For agents and scripts

Every command keeps the form `python -m eninesites.<noun> <verb> [options]`. Four things make
it usable without reading its help:

- **`--json` on every verb** prints the result, and nothing else, on stdout as one JSON
  document.
- **A refusal is JSON too.** Under `--json`, a command that cannot run writes one JSON document
  on stderr and exits 2:

  ```json
  {"status": 404, "code": "not_found", "detail": "...", "errors": null,
   "method": "GET", "path": "/api/v1/site/example.com/artifacts/nope/"}
  ```

  `code` is the server's own when it sent one (`not_found`, `permission_denied`,
  `validation_error`, `site_already_exists`, ...), so an agent can decide what to do next:
  create the thing, stop, or retry. With no server code it is the client's: `refused` (bad
  input; nothing was sent), `unreachable`, `timeout`, `redirect_refused`, `not_problem` (an
  error reply that is not problem details), `not_json`, `not_available` (no REST endpoint) or
  `usage` (the command line itself was wrong; no help text is printed under `--json`).
  `errors` holds the server's per-field errors on a validation failure.
- **`--dry-run` on every write verb** shows the request the verb would send and sends nothing:
  `{"dry_run": true, "method": "DELETE", "path": "...", "body": ...}`. A dry run still sends the
  verb's GETs, so it needs the server and a key. `login`, `logout` and `site select` show the
  config-file change instead (`WRITE` or `REMOVE`).
- **`python -m eninesites describe --json`** lists every command at once: what to type, whether
  it writes, each flag, and the JSON Schema of its output, plus the shapes of a refusal and of a
  dry run.

Exit codes: 0 done, 1 ran and found something to report, 2 could not run.

## Commands

| Noun | Verbs |
|---|---|
| `aeo` | inspect |
| `artifact` | create, delete, get, list, update |
| `artifact.aeo` | create, delete, get, update |
| `artifact.design` | get, update |
| `artifact.image` | attach, detach, get, list |
| `artifact.map` | candidates, create, delete, get, list, update |
| `artifact.role` | assign, list, replace, unassign |
| `artifact.tag` | attach, detach, list |
| `audit` | get, run |
| `chat` | magic-link, stream |
| `media` | delete, get, list, update, upload |
| `page` | crawl |
| `seo` | create, delete, get, list, update |
| `site` | build, check, configure, copy, create, delete, dump, list, load, propose, randomize-subdomain, restore, review, select |
| `tag` | create, delete, get, list, update |
| `theme` | check, create, delete, list, review |
| `theme.custom` | export, import |
| `url` | create, delete, get, list, update |
| `urlmap` | create, delete, get, list, update |
| `user` | add, get, list, update |

## Not available over the API

These commands are declared but the eninesites REST API has no endpoint for them; each exits
2 with a message naming where the operation lives instead: `site delete`, `site check`,
`site review` and `theme create|delete|check|review` (server `manage.py` commands),
`site propose`, `site build` and `page crawl` (chat tools), and `chat stream` and
`chat magic-link` (browser-session endpoints).

## Documentation

Each command documents itself with `--help`. The words the commands use are declared in
[`docs/lexicon/`](docs/lexicon/README.md).

## Feedback

Got feedback? Open an issue with the Feedback template.

## Contributing

All contributions are governed by the [code of conduct](CODE_OF_CONDUCT.md).

## License

Copyright (c) Enine. All rights reserved.

Licensed under the [Apache License 2.0](LICENSE).
