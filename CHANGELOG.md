---
pnode: [README.md]
---

# Changelog

All notable changes to this project are documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `python -m eninesites.plan list`: the subscription plans you can create a site on, cheapest
  first. Each slug is a value `site create --plan` and `site copy --plan` accept.

- `--dry-run` on every write verb: the request the verb would send, returned as its result
  and not sent.
- `python -m eninesites describe`: every command, its flags and its output schema, as data.
- `theme custom import --activate false` imports a custom theme without making it the live
  one; left out, the server's default holds and it goes live. The result now says whether it
  did (`active`) and which theme was live before (`previous_theme`), so the switch can be undone
  with `site configure --theme`.
- Under `--json`, a refusal is one JSON document on stderr (`status`, `code`, `detail`,
  `errors`, `method`, `path`), carrying the server's problem details instead of flattening
  them into a sentence; a usage error is the same document with `code` `usage`.

### Changed

- `site load` and `site restore` follow the server's API 2.2.0, where both replace the whole
  site: `load` sends a `.json` export as the request body and keeps the media library (every
  media name in it must already be there); `restore` uploads a `.zip` backup and replaces the
  content and media. Neither merges any more. `site dump --format` takes `json` (still the
  default) or `zip`; the server dropped `yaml`, `csv` and `media`.

- A write verb's api function returns `<Result> | PlannedRequest` and takes `dry_run`; a
  Python caller indexes the result through `eninesites.lib.dryrun.done(result)`, which
  returns `<Result>` and raises `TypeError` on a planned request.

- racecar's delivered files synced to `4f4a72b6`. The package gains `lib/error/`, racecar's
  error packet schema and its types, which nothing uses yet. `lib/cli.py` is racecar's own
  again: racecar now exits 2 on a missing required argument, as this CLI already did.

- racecar's delivered files synced to `ccd3547`; `pylint` pinned to 4.0.9, the version racecar
  lints its delivered files under.

- Every noun, verb and flag has real help text in `--help` and `describe`, in place of
  `TODO — what X means`. Each text is its word's summary in `docs/lexicon/`, and a test fails
  when the two differ. `--domain`, `--slug` and `--json` are reworded: `--slug` said "artifact"
  where it also names a media item or a tag.

### Removed

- `site restore --mode`: the server dropped `merge` and `clobber`, and a restore always
  replaces.

- The `page` and `chat` nouns (`page crawl`, `chat stream`, `chat magic-link`). Every verb on
  them only refused: crawling a page is a server chat tool with no REST endpoint, and the chat
  endpoints accept a browser session, never an API key. They no longer appear in the command
  listing or in `describe`.

- Flags that only the server's own `manage.py` takes, and that every command here refused:
  `site create --user --sample`, `site load --name --user --email`,
  `site restore --name --user --plan`, `site copy --user` and `audit run --limit`. Passing one
  now reads as an unknown flag.

### Fixed

- `site restore` describes itself as restoring a .zip backup; its help repeated `site load`'s.

- The SEO page commands work, as `python -m eninesites.seo`: the noun was `seo-page`, which
  racecar built as an unimportable package.

- `--id`, `--format` and `--copyright` show as `ID`, `FORMAT` and `COPYRIGHT` in usage instead
  of `ID_`, `FORMAT_` and `COPYRIGHT_`.

## 0.1.0 - 2026-10-05

### Added

- The `eninesites` package: a client of the eninesites REST API, usable as a Python library
  (`from eninesites.<noun> import api`) and as a command line (`python -m eninesites.<noun> <verb>`).
- Token authentication: `login`, `logout` and `config`, `--api-key`, `--base-url`,
  `--project-name`, `ENINESITES_*` environment variables and profiles in
  `~/.config/eninesites/config.toml`.
- Commands for sites, themes, custom themes, artifacts and their roles, maps, tags, images,
  design and AEO data; site tags, URLs, URL maps, media, users, audits and AEO inspection.
