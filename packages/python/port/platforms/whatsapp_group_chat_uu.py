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
from collections import Counter
from typing import Callable

import pandas as pd

import port.helpers.port_helpers as ph
import port.helpers.validate as validate
from port.api.d3i_props import ExtractionResult
from port.api.file_utils import SeekableBinaryReader
from port.api.props import Translatable
from port.helpers.flow_builder import FlowBuilder
from port.helpers.table_extractor import load_port_config, run_extraction
from port.platforms import whatsapp as wa

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


def chat_messages_to_df(df: pd.DataFrame, errors: Counter) -> pd.DataFrame:
    """The anonymised group chat with redacted message text.

    ``Timestamp`` comes from upstream's ``whatsapp.parse_chat`` (ISO string; the
    ADR-0042 carve-out lives in ``whatsapp.py``) and is declared as a date
    column below (ADR-0043).

    Table documentation::

        {
          "summary": "Each row is one message of the group chat: when it was sent, the anonymised sender, and the message text with every non-whitespace character replaced by '*'.",
          "source_file": "WhatsApp chat export (.zip)",
          "columns": {
            "Timestamp": "Time the message was sent, on the phone's clock (ISO 8601, no time zone).",
            "Name": "Anonymised sender: Member 1 is the participant.",
            "Message": "Redacted message text (word lengths preserved)."
          }
        }

    Table config::

        {
          "id": "whatsapp_uu_group_chat",
          "title": {"en": "Your group chat", "nl": "Je groepsgesprek"},
          "description": {
            "en": "The contents of your group chat, with names anonymised and message text hidden. Try searching in your group chat, the figures should change accordingly! Timestamps (and therefore some figures) can be incorrect as the European date format is assumed.",
            "nl": "De inhoud van je groepsgesprek, met geanonimiseerde namen en verborgen berichttekst. Probeer te zoeken in je groepsgesprek, de figuren veranderen dan mee! Tijdstempels (en dus sommige figuren) kunnen onjuist zijn omdat het Europese datumformaat wordt aangenomen."
          },
          "headers": {
            "Timestamp": {"en": "Timestamp", "nl": "Tijdstempel"},
            "Name": {"en": "Name", "nl": "Naam"},
            "Message": {"en": "Message", "nl": "Bericht"}
          },
          "date_columns": {"Timestamp": {"encoding": "iso-8601"}},
          "visualizations": [
            {
              "title": {"en": "Total chats per hour of the day", "nl": "Totaal chats per uur van de dag"},
              "type": "bar",
              "group": {"column": "Timestamp", "dateFormat": "hour_cycle"},
              "values": [{}]
            }
          ]
        }
    """
    out = df.rename(columns={"date": "Timestamp", "name": "Name", "chat_message": "Message"})
    out["Message"] = out["Message"].map(redact_non_whitespace)
    return out[["Timestamp", "Name", "Message"]]


def emoji_usage_to_df(df: pd.DataFrame, errors: Counter) -> pd.DataFrame:
    """The 100 most used emojis across all members.

    Table documentation::

        {
          "summary": "Each row is one emoji used in the group chat, ranked by frequency across all members.",
          "source_file": "WhatsApp chat export (.zip)",
          "columns": {
            "Emoji": "The emoji character.",
            "Count": "Total number of times this emoji was used."
          }
        }

    Table config::

        {
          "id": "whatsapp_uu_emoji_usage",
          "title": {"en": "The 100 most used emojis in the group", "nl": "De 100 meest gebruikte emoji's in de groep"},
          "description": {
            "en": "Analysis of emoji frequency used by all members in the chat.",
            "nl": "Analyse van emoji-frequentie gebruikt door alle leden in de chat."
          },
          "headers": {
            "Emoji": {"en": "Emoji", "nl": "Emoji"},
            "Count": {"en": "Count", "nl": "Aantal"}
          }
        }
    """
    return wa.find_emojis(df)


def member_statistics_to_df(df: pd.DataFrame, errors: Counter) -> pd.DataFrame:
    """Messaging statistics per anonymised member.

    Table documentation::

        {
          "summary": "Each row is one messaging statistic for one anonymised member (Member 1 is the participant).",
          "source_file": "WhatsApp chat export (.zip)",
          "columns": {
            "Member": "Anonymised member: Member 1 is the participant.",
            "Description": "Name of the statistic.",
            "Statistic": "Value of the statistic."
          }
        }

    Table config::

        {
          "id": "whatsapp_uu_member_statistics",
          "title": {"en": "Chat statistics per member (you are Member 1)", "nl": "Chatstatistieken per lid (jij bent Member 1)"},
          "description": {
            "en": "For each anonymised member of the group chat: who reacts to them the most, who they react to the most, the number of messages and words they sent, and their most used emoji.",
            "nl": "Voor elk geanonimiseerd lid van de groepschat: wie het meest op hen reageert, op wie zij het meest reageren, het aantal verstuurde berichten en woorden, en hun meest gebruikte emoji."
          },
          "headers": {
            "Member": {"en": "Member", "nl": "Lid"},
            "Description": {"en": "Description", "nl": "Beschrijving"},
            "Statistic": {"en": "Statistic", "nl": "Statistiek"}
          }
        }
    """
    rows: list[tuple[str, str, object]] = []
    for member in members_in_order(df):
        rows.extend([
            (member, "who reacted to you the most", wa.who_reacted_to_you_the_most(df, member)),
            (member, "who you reacted to the most", wa.who_you_reacted_to_the_most(df, member)),
            (member, "total number of messages you send", wa.total_number_of_messages(df, member)),
            (member, "total number of words you send", wa.total_number_of_words(df, member)),
            (member, "the emoji you used most", wa.favorite_emoji(df, member)),
        ])
    return pd.DataFrame(rows, columns=["Member", "Description", "Statistic"])


EXTRACTOR_REGISTRY: dict[str, Callable[..., pd.DataFrame]] = {
    "chat_messages_to_df": chat_messages_to_df,
    "emoji_usage_to_df": emoji_usage_to_df,
    "member_statistics_to_df": member_statistics_to_df,
}


def extraction(df: pd.DataFrame) -> ExtractionResult:
    """Run the config-driven tables over an anonymised chat DataFrame.

    ``run_extraction`` passes its first argument straight to each extractor, so
    the parsed frame stands in for the archive reader.
    """
    config = load_port_config(EXTRACTOR_REGISTRY, PLATFORM_KEY)
    return run_extraction(df, Counter(), config)


def _parse_members_only(file: SeekableBinaryReader) -> tuple[pd.DataFrame, list[str]]:
    """Parse the chat with upstream's parser, keep only detected members."""
    df = wa.parse_chat(file)
    if df.empty:
        return df, []
    df = wa.remove_empty_chats(df)
    users = wa.extract_users(df)
    return wa.keep_users(df, users), users


class WhatsAppGroupChatUUFlow(FlowBuilder):
    def __init__(self, session_id: str):
        super().__init__(
            session_id,
            "WhatsApp group chat",
            config_key=PLATFORM_KEY,
            donation_key=PLATFORM_KEY,
        )

    def validate_file(self, file: SeekableBinaryReader) -> validate.BaseValidation:
        df, users = _parse_members_only(file)
        if not df.empty and len(users) > MIN_MEMBERS_EXCLUSIVE:
            return validate.BaseValidation(status_code=0)
        return validate.BaseValidation(status_code=1)

    def extract_data(self, file, validation):
        file.seek(0)
        df, users = _parse_members_only(file)
        title = Translatable({"en": "Select your WhatsApp name", "nl": "Kies jouw WhatsApp naam"})
        empty_text = Translatable({"en": "", "nl": ""})
        radio_prompt = ph.generate_radio_prompt(title, empty_text, sorted(users))
        selection = yield ph.render_page(empty_text, radio_prompt)
        if getattr(selection, "__type__", None) != "PayloadString" or selection.value not in users:
            return ExtractionResult(tables=[], errors=Counter())
        df = anonymize_users(df, users, selection.value)
        return extraction(df)


def process(session_id: str):
    flow = WhatsAppGroupChatUUFlow(session_id)
    return flow.start_flow()
