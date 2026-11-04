"""Tests for the UU WhatsApp group-chat platform. Synthetic chats only (ADR-0014)."""
import io
import zipfile
from collections import Counter

import pandas as pd

from port.platforms import whatsapp_group_chat_uu as uu


def chat_zip(lines: list[str]) -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("WhatsApp Chat with Test Group.txt", "\n".join(lines) + "\n")
    buf.seek(0)
    return buf


#: Five members, 24h "dd/mm/yyyy, HH:MM - name: msg" format.
CHAT = [
    "01/02/2026, 09:00 - Anna: Goedemorgen allemaal 😀",
    "01/02/2026, 09:01 - Bram: Hoi Anna",
    "01/02/2026, 09:02 - Anna: Hoe gaat het?",
    "01/02/2026, 09:03 - Cees: Prima 😀😀",
    "01/02/2026, 09:04 - Dirk: Goed hoor",
    "01/02/2026, 09:05 - Eva: Hallo",
    "en een tweede regel",
    "01/02/2026, 09:06 - Anna: Leuk 👍",
]


def frame(names, messages):
    return pd.DataFrame({"date": ["2026-02-01T09:00:00"] * len(names), "name": names, "chat_message": messages})


class TestAnonymizeUsers:
    def test_selected_user_is_member_1_and_others_numbered(self):
        df = frame(["Bram", "Anna", "Cees", "Anna"], ["a", "b", "c", "d"])
        out = uu.anonymize_users(df, ["Anna", "Bram", "Cees"], "Cees")
        assert list(out["name"]) == ["Member 3", "Member 2", "Member 1", "Member 2"]

    def test_does_not_mutate_input(self):
        df = frame(["Anna", "Bram"], ["a", "b"])
        uu.anonymize_users(df, ["Anna", "Bram"], "Anna")
        assert list(df["name"]) == ["Anna", "Bram"]


class TestRedact:
    def test_non_whitespace_becomes_asterisk(self):
        assert uu.redact_non_whitespace("Hoi Anna 😀!") == "*** **** **"

    def test_empty(self):
        assert uu.redact_non_whitespace("") == ""


def test_members_sorted_numerically():
    df = frame(["Member 10", "Member 2", "Member 1"], ["a", "b", "c"])
    assert uu.members_in_order(df) == ["Member 1", "Member 2", "Member 10"]
