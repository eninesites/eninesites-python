"""The one error this package raises: a request it refuses, said in a sentence.

Delivered code imports nothing from racecar's package, so it cannot raise
`racecar.lib._exit.ApiError`. `racecar.surface` wraps this package and turns a
`SurfaceError` into its own `ApiError` at the boundary, the way `racecar.lexicon` turns
`LexiconError`; `scripts/surface.py` prints it and exits 2.
"""

from __future__ import annotations


class SurfaceError(Exception):
    """A refusal: the arguments name something this package will not do, and why."""
