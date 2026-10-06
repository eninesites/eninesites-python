---
pnode: [README.md]
---

# Changelog

All notable changes to this project are documented in this file. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `--dry-run` on every write verb: the request the verb would send, returned as its result
  and not sent.
- `python -m eninesites describe`: every command, its flags and its output schema, as data.
- Under `--json`, a refusal is one JSON document on stderr (`status`, `code`, `detail`,
  `errors`, `method`, `path`), carrying the server's problem details instead of flattening
  them into a sentence; a usage error is the same document with `code` `usage`.

### Changed

- A write verb's api function returns `<Result> | PlannedRequest` and takes `dry_run`; a
  Python caller indexes the result through `eninesites.lib.dryrun.done(result)`, which
  returns `<Result>` and raises `TypeError` on a planned request.

- racecar's delivered files synced to `4f4a72b6`. The package gains `lib/error/`, racecar's
  error packet schema and its types, which nothing uses yet. `lib/cli.py` is racecar's own
  again: racecar now exits 2 on a missing required argument, as this CLI already did.

- racecar's delivered files synced to `ccd3547`; `pylint` pinned to 4.0.9, the version racecar
  lints its delivered files under.

### Fixed

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
