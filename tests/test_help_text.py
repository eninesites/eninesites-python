"""Every help text the cli shows is its word's lexicon summary, copied exactly.

The lexicon (``docs/lexicon/``) is the one home of what each noun, verb and flag means; the
cli's help is a copy racecar's generator made once and nothing re-copies. This holds the two
equal. The lexicon is read with racecar's own reader, the one the generator used, so the
test cannot disagree with racecar about which file a word resolves to.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from eninesites.root.api import describe_root

ROOT = Path(__file__).resolve().parent.parent
# The delivered scripts are not a package of this repo; their reader is reached by path, as
# racecar's own tooling reaches it.
sys.path.insert(0, str(ROOT / ".racecar" / "scripts"))
# pylint: disable-next=import-error,wrong-import-position,wrong-import-order
from lib.lexicon import describe, lexicon_corpora  # type: ignore[import-not-found]

# pylint: disable-next=import-error,wrong-import-position,wrong-import-order
from lib.shared import _frontmatter  # type: ignore[import-not-found]

LEXICON = lexicon_corpora(ROOT)
ROOT_NOUN = "eninesites"


def _flat(text: str | None) -> str:
    return " ".join(str(text or "").split())


def _param(name: str) -> str:
    found = LEXICON.find(f"param/{name}.md")
    assert found is not None, f"--{name}: no docs/lexicon/param/{name}.md"
    return str(_frontmatter.load(found).get("summary"))


def _nodes() -> list[tuple[str, ModuleType]]:
    """Every node as (its lexicon noun, its ``__main__``), in ``commands()`` order."""
    found: list[tuple[str, ModuleType]] = []

    def walk(package: str, noun: str) -> None:
        node = importlib.import_module(f"{package}.__main__")
        found.append((noun, node))
        for child, _ in node.commands():
            walk(
                f"{package}.{child}", child if noun == ROOT_NOUN else f"{noun}.{child}"
            )

    walk("eninesites", ROOT_NOUN)
    return found


NODES = _nodes()


def _summary(noun: str, verb: str | None = None) -> str:
    declared: dict[str, Any] = describe(LEXICON, noun, verb)
    return str(
        declared["summary"] if verb is None else declared["verbs"][verb]["summary"]
    )


@pytest.mark.parametrize("noun,node", NODES, ids=[noun for noun, _ in NODES])
def test_a_nouns_texts_are_its_summaries(noun: str, node: ModuleType) -> None:
    assert node.parser().description == _summary(noun)
    for child, text in node.commands():
        assert text == _summary(
            child if noun == ROOT_NOUN else f"{noun}.{child}"
        ), child
    for verb, text in node.subcommands():
        assert text == _summary(noun, verb), verb


@pytest.mark.parametrize("noun,node", NODES, ids=[noun for noun, _ in NODES])
def test_a_nouns_docstrings_state_its_summary(noun: str, node: ModuleType) -> None:
    package = node.__name__.rsplit(".", 1)[0]
    homes = [
        node,
        importlib.import_module(package if noun != ROOT_NOUN else "eninesites.root"),
    ]
    for module in homes:
        assert _flat(_summary(noun)) in _flat(module.__doc__), module.__name__


def test_every_flag_help_is_its_params_summary() -> None:
    wrong = [
        f"{command['command']} {arg['flags'][0]}: {arg['help']!r}"
        for command in describe_root()["commands"]
        for arg in command["args"]
        if arg["flags"] and arg["help"] != _param(arg["flags"][0].lstrip("-"))
    ]
    assert not wrong, "\n".join(wrong)


def test_no_help_text_is_a_placeholder() -> None:
    shown = [str(c["description"]) for c in describe_root()["commands"]]
    shown += [str(a["help"]) for c in describe_root()["commands"] for a in c["args"]]
    shown += [node.parser().description or "" for _, node in NODES]
    shown += [text for _, node in NODES for _, text in node.commands()]
    assert not [text for text in shown if "TODO" in text]
