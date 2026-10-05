"""Repo opt-in: the agent-instruction file declares racecar."""

from __future__ import annotations

from pathlib import Path

from ..shared._agent_docs import AGENT_DOC_NAMES
from ._findings import Finding


def check_optin(root: Path) -> list[Finding]:
    """Advise that an existing agent-instruction file declares racecar.

    A repo with an AGENTS.md (or CLAUDE.md) is writing instructions for the agent;
    if it applies racecar, that file should say so, or a clone without the
    author's global ~/.claude block sees nothing tying it to racecar. The check
    fires only on a file that exists but never names racecar; an absent file is
    `check_required_docs.py`'s finding, not this one's. This
    is a presence check on the declaration, never a path check: racecar is located
    by each developer's own install, not a hard-coded path. Advisory (Finding)."""
    present = [name for name in AGENT_DOC_NAMES if (root / name).is_file()]
    if not present:
        return []
    for name in present:
        text = (root / name).read_text(encoding="utf-8", errors="replace")
        if "racecar" in text.lower():
            return []
    return [
        Finding(
            "Finding",
            present[0],
            "missing-racecar-optin",
            f"{present[0]} does not reference racecar — repo not portably opted in",
        )
    ]
