"""The site views as terminal text.

Every line this noun's cli prints is written here. Each ``print_<verb>`` takes that verb's
result and writes it; it reads no store and decides nothing, and it reads the same types
the api returns, so what it prints cannot drift from them.
"""

from __future__ import annotations

import sys

from eninesites.lib.renderer import text

from ..results import (
    BuildSite,
    CheckSite,
    ConfigureSite,
    CopySite,
    CreateSite,
    DeleteSite,
    DumpSite,
    ListSite,
    LoadSite,
    ProposeSite,
    RandomizeSubdomainSite,
    RestoreSite,
    ReviewSite,
    SelectSite,
)


def print_create(result: CreateSite) -> None:
    """``site create`` as text: the domain created."""
    text.line(f"Created site {result['domain']}")


def print_list(result: ListSite) -> None:
    """``site list`` as text: one row per site."""
    text.table(result["results"], ["domain", "name"])


def print_dump(result: DumpSite) -> None:
    """``site dump`` as text: where the export went."""
    text.line(
        f"Exported {result['domain']} ({result['format']}, {result['bytes']} bytes) "
        f"to {result['path']}"
    )


def print_load(result: LoadSite) -> None:
    """``site load`` as text: the file and the site it went into."""
    text.line(f"Loaded {result['file']} into {result['domain']}")


def print_restore(result: RestoreSite) -> None:
    """``site restore`` as text: the archive, the site and the mode."""
    text.line(
        f"Restored {result['file']} over {result['domain']} (mode {result['mode']})"
    )


def print_copy(result: CopySite) -> None:
    """``site copy`` as text: source and destination."""
    text.line(f"Copied {result['source']} -> {result['domain']}")


def print_configure(result: ConfigureSite) -> None:
    """``site configure`` as text: the sections the server updated."""
    updated = ", ".join(result["updated"]) or "nothing"
    text.line(f"Updated {result['domain']}: {updated}")


def print_delete(result: DeleteSite) -> None:
    """``site delete`` never returns (no REST endpoint); kept for the form."""
    text.record(result)


def print_check(result: CheckSite) -> None:
    """``site check`` never returns (no REST endpoint); kept for the form."""
    text.record(result)


def print_review(result: ReviewSite) -> None:
    """``site review`` never returns (no REST endpoint); kept for the form."""
    text.record(result)


def print_select(result: SelectSite) -> None:
    """``site select`` as text: the site now selected, and for which project."""
    text.line(
        f"Selected {result['site']} for project {result['project_name']} "
        f"({result['config_path']})"
    )


def print_randomize_subdomain(result: RandomizeSubdomainSite) -> None:
    """``site randomize-subdomain`` as text: the new subdomain."""
    text.line(f"{result['domain']}: new subdomain {result['subdomain']}")


def print_propose(result: ProposeSite) -> None:
    """``site propose`` never returns (no REST endpoint); kept for the form."""
    text.record(result)


def print_build(result: BuildSite) -> None:
    """``site build`` never returns (no REST endpoint); kept for the form."""
    text.record(result)


def error(message: str) -> None:
    """A refusal the api raised, on stderr, so stdout stays empty."""
    print(message, file=sys.stderr)
