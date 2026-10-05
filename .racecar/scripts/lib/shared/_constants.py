"""Canon definitions (mirror arch-python/PACKAGING.md §3 §6 §7)."""

from __future__ import annotations

import re

CANON_DEV_TOOLS = [
    "black",
    "isort",
    # Pinned: racecar lints the files it delivers under this version, and a newer pylint
    # reports on them what racecar never saw (pylint 4.1.2 with astroid 4.3.3 flagged
    # W0102 in lib/surface/_conform.py). An adopter's lint must match racecar's. Move the
    # pin here, in racecar's own pyproject and in the template together.
    "pylint==4.0.9",
    "pylint-pytest",
    "mypy",
    "pytest",
    "pytest-cov",
    "pip-audit",
    "import-linter",
    "pre-commit",
    "validate-pyproject",
    "pyyaml",
    "pytest-xdist",  # parallel test workers; inert until PYTEST_ARGS enables -n (PACKAGING.md §6)
]

# Django shapes carry a second PEP 735 group, [dependency-groups].django. Two
# tools are racecar-canonical there (PACKAGING.md §6): djhtml (template formatter)
# and pylint-django (the pylint plugin that teaches the linter the ORM, loaded by
# racecar.mk's `lint` target on the server). The rest of that group is project-
# choice. Asserted only when the repo is Django.
CANON_DJANGO_TOOLS = ["djhtml", "pylint-django"]

CANON_REQUIRES_PYTHON = ">=3.12"
CANON_BLACK_TARGET = ["py312"]
CANON_ISORT_PROFILE = "black"
# >=77 is the PEP 639 floor, not a version-chasing bump: below it `[project].license`
# as an SPDX expression is rejected and `license-files` is ignored, so a repo cannot
# state its license in the one place tooling reads. Build-time only -- pip fetches the
# backend in an isolated environment, so the floor costs an adopter nothing at runtime.
CANON_BUILD_REQUIRES = ["setuptools>=77"]
CANON_BUILD_BACKEND = "setuptools.build_meta"

# NOTE: racecar asserts NOTHING about [tool.pylint."MESSAGES CONTROL"].disable. There is no
# required set and no forbidden set, by design. Which pylint messages a repo suppresses is the
# owner's call, and a checker that graded it would make racecar the decider on a judgement that
# is not its to make (shared/OWNERSHIP.md: tooling enables design and confirms correctness;
# responsibility stays with the owner). racecar advises through what it SCAFFOLDS -- see
# templates/classic/library-pyproject.toml -- and a scaffolded default is a starting point the
# owner edits, not a rule enforced forever.
#
# What is asserted about pylint is config LOCATION, not content: no standalone .pylintrc
# (FORBIDDEN_PYLINTRC below), because tool config has one home. That is a structural rule about
# where a decision is recorded, not a ruling on the decision.
# Standalone pylint config files — forbidden; config lives in the library
# pyproject [tool.pylint] (PACKAGING.md, "pylint canon" + §7).
FORBIDDEN_PYLINTRC = [".pylintrc", "pylintrc", "src/.pylintrc", "server/.pylintrc"]

# Forbidden top-level [tool.<key>] blocks (per §1 §2).
FORBIDDEN_TOOL_KEYS = {"uv", "ruff", "poetry", "pdm"}
FORBIDDEN_HATCH_SUBKEYS = {"envs"}

# Lockfiles produced by non-canon tools (per §5).
FORBIDDEN_LOCKFILES = ["uv.lock", "poetry.lock", "pdm.lock", "Pipfile.lock"]

REQUIRED_PRECOMMIT_HOOKS = {
    "black",
    "isort",
    "import-linter",
    "validate-pyproject",
    "no-upward-imports-in-business-modules",
    "doc-coherence-mechanical-pre-pass",
    "file-placement",
}

# Package-only hooks: they audit library-package structure and have nothing to act on
# in the flat `django` shape (a config-home site, not a package) — no import-linter
# contracts, no [project] to validate, no src-package upward-imports. Exempted from the
# required set for that shape (SG3), the same reasoning that skips its library-pyproject
# audit. The rest of REQUIRED_PRECOMMIT_HOOKS (format, doc-coherence, placement)
# is shape-independent and stays required.
PACKAGE_ONLY_PRECOMMIT_HOOKS = {
    "import-linter",
    "validate-pyproject",
    "no-upward-imports-in-business-modules",
}

# Make variables retired by a canon rename. A repo-owned scaffold file is not content-synced,
# so a stale reference survives a racecar upgrade: the import-linter hook body calls
# `make -s print-<VAR>`, and a retired <VAR> resolves to empty, silently dropping the server
# root from PYTHONPATH.
# Map each retired name to its current replacement; the precommit check flags any occurrence.
RETIRED_MAKE_VARS = {"DJAPP": "SERVER"}

REQUIRED_MAKEFILE_TARGETS = {
    "help",
    "install",
    "install-dev",
    "check",
    "check-full",
    "fix",
    "fmt",
    "fmt-check",
    "lint",
    "test",
    "coverage",
    "typecheck",
    "arch",
    "audit",
    "docs",
    "clean",
    "distclean",
    "system-deps",
}

FORBIDDEN_MAKEFILE_TOOLS = {"uv", "ruff", "poetry", "pdm", "pipenv"}

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][\w.-]+)?$")

# A released version: exactly `X.Y.Z`, no prerelease or build tag. What a version home, a
# changelog heading and a brief stamp carry.
RELEASE_RE = re.compile(r"^\d+\.\d+\.\d+$")

# Where racecar's files land in an adopter, and what sync writes there to record it.
#
# VERBATIM from `racecar.lib.delivery.record`, which is the authored home. A delivered
# checker runs from an adopter's `rc_scripts/` with no racecar installed, so it cannot
# import that module and needs the value delivered to it instead -- the same arrangement
# `_files.py` and `_root.py` have, and `tests/slow/test_delivered_record_is_found.py` holds the
# two equal.
#
# The legacy spellings are kept because an adopter that has not synced recently still
# has its record at a legacy path, and a reader that knows only the current path
# strands it.
DELIVERY_DIR = ".racecar/scripts"
DELIVERED_RECORD_REL = ".racecar-delivered.txt"

# The boundary root, and the two provenance stamps sync writes at it -- one per delivered
# tree, each holding git's own tree object id for what racecar delivered. `lib.lexicon`
# reads these from here rather than spelling them a second time; it sits in the same
# delivered directory and already takes `find_repo_root` from this package.
DELIVERY_ROOT = ".racecar"
LEXICON_STAMP_REL = ".racecar-lexicon"
SCRIPTS_STAMP_REL = ".racecar-scripts"
CORPUS_REL = "docs/lexicon"
LEGACY_DELIVERY_DIRS = ("rc_scripts", "scripts")
LEGACY_DELIVERY_DIR = LEGACY_DELIVERY_DIRS[0]
LEGACY_DELIVERED_REL = "racecar-manifest.txt"

# Every place a delivered record has ever lived, newest first. One tuple, so a reader never
# spells a path itself.
DELIVERED_RECORDS = (
    f"{DELIVERY_ROOT}/{DELIVERED_RECORD_REL}",
    f"{DELIVERY_DIR}/{DELIVERED_RECORD_REL}",
    *(f"{legacy}/{DELIVERED_RECORD_REL}" for legacy in LEGACY_DELIVERY_DIRS),
    *(f"{legacy}/{LEGACY_DELIVERED_REL}" for legacy in LEGACY_DELIVERY_DIRS),
)
