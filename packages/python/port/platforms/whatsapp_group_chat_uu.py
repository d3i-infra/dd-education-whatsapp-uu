"""
WhatsApp Group Chat (UU course)
===============================

The Utrecht University course variant of the WhatsApp group-chat flow. Parsing
is upstream's (``port.platforms.whatsapp``); this module adds the course's
privacy steps:

* the participant selects their own name; members are renamed ``Member 1``
  (the participant) to ``Member N``;
* message text in the chat table is redacted (every non-whitespace character
  becomes ``*``);
* a chat is only accepted when it has more than three members.

Extractors take ``(df, errors)`` like upstream WhatsApp (ADR-0029 signature
exception); the parsed DataFrame is handed to ``run_extraction`` as its reader.

Platform info::

    {
        "name": "WhatsApp group chat",
        "filetypes": ["zip"],
        "languages": ["en", "nl"],
        "description": "UU course variant of the WhatsApp group chat flow: members are anonymised (Member 1 is the participant) and message text is redacted. Requires a group chat with more than three members.",
        "time_last_tested": "not yet implemented"
    }
"""
import logging

import pandas as pd

logger = logging.getLogger(__name__)

#: Config filename key and ADR-0020 donation-key segment.
PLATFORM_KEY = "whatsapp_group_chat_uu"

#: A chat is accepted only with strictly more members than this.
MIN_MEMBERS_EXCLUSIVE = 3


def anonymize_users(df: pd.DataFrame, users: list[str], selected_user: str) -> pd.DataFrame:
    """Rename *selected_user* to ``Member 1`` and the others (sorted) to ``Member 2..N``."""
    others = sorted(u for u in users if u != selected_user)
    mapping = {user: f"Member {i + 2}" for i, user in enumerate(others)}
    mapping[selected_user] = "Member 1"
    out = df.copy()
    out["name"] = out["name"].replace(mapping)
    return out


def redact_non_whitespace(text: str) -> str:
    """Replace every non-whitespace character with ``*``."""
    return "".join("*" if not ch.isspace() else ch for ch in text)


def members_in_order(df: pd.DataFrame) -> list[str]:
    """Distinct ``Member N`` names ordered by N."""
    return sorted(set(df["name"]), key=lambda name: int(name.rsplit(" ", 1)[-1]))
