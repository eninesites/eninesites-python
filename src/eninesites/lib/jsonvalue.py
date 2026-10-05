"""A JSON value of bounded depth, for server fields whose shape the server does not fix.

``schema.py`` publishes every result as JSON Schema and refuses ``Any`` and recursive
types, so a free-form field (a JSON-LD graph, an artifact's ``extra_data``, a site's
``address``) cannot be typed as "any JSON". ``Json`` is the honest substitute: any JSON
value nested at most six levels deep. Each level is written out because ``schema.py``
expands a type inline and a recursive alias would never terminate.
"""

from __future__ import annotations

from typing import TypeAlias

Scalar: TypeAlias = str | int | float | bool | None
_Json1: TypeAlias = Scalar | list[Scalar] | dict[str, Scalar]
_Json2: TypeAlias = Scalar | list[_Json1] | dict[str, _Json1]
_Json3: TypeAlias = Scalar | list[_Json2] | dict[str, _Json2]
_Json4: TypeAlias = Scalar | list[_Json3] | dict[str, _Json3]
_Json5: TypeAlias = Scalar | list[_Json4] | dict[str, _Json4]
Json: TypeAlias = Scalar | list[_Json5] | dict[str, _Json5]
JsonObject: TypeAlias = dict[str, _Json5]
