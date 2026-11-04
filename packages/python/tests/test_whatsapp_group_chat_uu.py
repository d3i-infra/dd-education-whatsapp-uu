"""Tests for the UU WhatsApp group-chat platform. Synthetic chats only (ADR-0014)."""
import io
import sys
import zipfile
from collections import Counter
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_port_config import build_config  # noqa: E402

import port.helpers.table_extractor as te  # noqa: E402
from port.api.commands import CommandSystemDonate, CommandSystemLog, CommandUIRender  # noqa: E402
from port.api.d3i_props import ExtractionResult  # noqa: E402
from port.platforms import whatsapp_group_chat_uu as uu  # noqa: E402


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


def anonymized_frame():
    return frame(
        ["Member 1", "Member 2", "Member 1", "Member 3"],
        ["Hoi 😀", "Hallo daar", "Leuk 😀😀", "Ok"],
    )


class TestExtractors:
    def test_chat_table_is_redacted_and_renamed(self):
        out = uu.chat_messages_to_df(anonymized_frame(), Counter())
        assert list(out.columns) == ["Timestamp", "Name", "Message"]
        assert list(out["Message"]) == ["*** *", "***** ****", "**** **", "**"]
        assert list(out["Name"]) == ["Member 1", "Member 2", "Member 1", "Member 3"]

    def test_chat_table_does_not_mutate_input(self):
        df = anonymized_frame()
        uu.chat_messages_to_df(df, Counter())
        assert df["chat_message"][0] == "Hoi 😀"

    def test_emoji_usage_counts_unredacted_emojis(self):
        out = uu.emoji_usage_to_df(anonymized_frame(), Counter())
        assert dict(zip(out["Emoji"], out["Count"])) == {"😀": 3}

    def test_member_statistics_one_block_per_member(self):
        out = uu.member_statistics_to_df(anonymized_frame(), Counter())
        assert list(out.columns) == ["Member", "Description", "Statistic"]
        assert list(dict.fromkeys(out["Member"])) == ["Member 1", "Member 2", "Member 3"]
        m1_rows = out[out["Member"] == "Member 1"]
        m1 = dict(zip(m1_rows["Description"], m1_rows["Statistic"]))
        assert m1["total number of messages you send"] == 2
        assert m1["total number of words you send"] == 4
        assert m1["the emoji you used most"] == "😀"
        assert m1["who reacted to you the most"] == "Member 2"


def test_extraction_produces_three_config_driven_tables(monkeypatch):
    config = te._build_config(build_config("whatsapp_group_chat_uu"), uu.EXTRACTOR_REGISTRY)
    monkeypatch.setattr(uu, "load_port_config", lambda registry, platform: config)
    result = uu.extraction(anonymized_frame())
    ids = [t.id for t in result.tables]
    assert ids == ["whatsapp_uu_group_chat", "whatsapp_uu_emoji_usage", "whatsapp_uu_member_statistics"]
    chat = result.tables[0]
    assert chat.date_columns == {"Timestamp": {"encoding": "iso-8601"}}


def make_flow():
    with patch("port.helpers.flow_builder.load_public_key_pem", return_value=None), \
         patch("port.helpers.flow_builder.load_reference_timezone", return_value=None):
        return uu.WhatsAppGroupChatUUFlow("sess")


def payload(type_name, **attrs):
    p = MagicMock()
    p.__type__ = type_name
    for k, v in attrs.items():
        setattr(p, k, v)
    return p


class TestFlow:
    def test_names_and_keys(self):
        flow = make_flow()
        assert flow.platform_name == "WhatsApp group chat"
        assert flow.donation_key == "whatsapp_group_chat_uu"

    def test_validate_accepts_more_than_three_members(self):
        assert make_flow().validate_file(chat_zip(CHAT)).get_status_code_id() == 0

    def test_validate_rejects_three_members(self):
        three = [line for line in CHAT if " - Dirk:" not in line and " - Eva:" not in line]
        assert make_flow().validate_file(chat_zip(three)).get_status_code_id() == 1

    def test_validate_rejects_non_chat(self):
        assert make_flow().validate_file(chat_zip(["just some text"])).get_status_code_id() == 1

    def test_extract_data_asks_name_then_anonymises(self, monkeypatch):
        captured = {}

        def fake_extraction(df):
            captured["df"] = df
            return ExtractionResult(tables=[], errors=Counter())

        monkeypatch.setattr(uu, "extraction", fake_extraction)
        gen = make_flow().extract_data(chat_zip(CHAT), None)
        prompt = next(gen)
        assert isinstance(prompt, CommandUIRender)
        with pytest.raises(StopIteration) as stop:
            gen.send(payload("PayloadString", value="Cees"))
        assert isinstance(stop.value.value, ExtractionResult)
        df = captured["df"]
        assert set(df["name"]) == {f"Member {i}" for i in range(1, 6)}
        assert list(df[df["name"] == "Member 1"]["chat_message"]) == ["Prima 😀😀"]
        assert "en een tweede regel" in df[df["name"] == "Member 5"]["chat_message"].iloc[0]

    def test_unknown_name_returns_no_tables(self):
        gen = make_flow().extract_data(chat_zip(CHAT), None)
        next(gen)
        with pytest.raises(StopIteration) as stop:
            gen.send(payload("PayloadString", value="Mallory"))
        assert isinstance(stop.value.value, ExtractionResult)
        assert stop.value.value.tables == []

    def test_radio_prompt_lists_sorted_members(self):
        gen = make_flow().extract_data(chat_zip(CHAT), None)
        cmd = next(gen)
        page = cmd.toDict()["page"]
        radios = [b for b in page["body"] if b.get("__type__") == "PropsUIPromptRadioInput"]
        assert len(radios) == 1
        assert [item["value"] for item in radios[0]["items"]] == ["Anna", "Bram", "Cees", "Dirk", "Eva"]

    def test_extract_data_skip_returns_no_tables(self):
        gen = make_flow().extract_data(chat_zip(CHAT), None)
        next(gen)
        try:
            gen.send(payload("PayloadFalse"))
            raise AssertionError("generator should have returned")
        except StopIteration as stop:
            result = stop.value
        assert result.tables == []
        assert not result.errors


class _Upload(io.BytesIO):
    """BytesIO with the JS-reported ``size`` the upload safety check reads."""

    @property
    def size(self):
        return len(self.getvalue())


def _skip_logs(gen, response=None):
    cmd = gen.send(response)
    while isinstance(cmd, CommandSystemLog):
        cmd = gen.send(payload("PayloadVoid"))
    return cmd


def test_full_flow_upload_pick_name_consent_donate(monkeypatch):
    config = te._build_config(build_config("whatsapp_group_chat_uu"), uu.EXTRACTOR_REGISTRY)
    monkeypatch.setattr(uu, "load_port_config", lambda registry, platform: config)
    gen = make_flow().start_flow()

    cmd = next(gen)
    while isinstance(cmd, CommandSystemLog):
        cmd = gen.send(payload("PayloadVoid"))
    assert isinstance(cmd, CommandUIRender)  # file prompt

    upload = _Upload(chat_zip(CHAT).getvalue())
    cmd = _skip_logs(gen, payload("PayloadFile", value=upload))
    assert isinstance(cmd, CommandUIRender)
    assert "PropsUIPromptRadioInput" in str(cmd.toDict())  # name picker

    cmd = _skip_logs(gen, payload("PayloadString", value="Cees"))
    assert isinstance(cmd, CommandUIRender)
    rendered = str(cmd.toDict())
    for table_id in ("whatsapp_uu_group_chat", "whatsapp_uu_emoji_usage", "whatsapp_uu_member_statistics"):
        assert table_id in rendered

    cmd = _skip_logs(gen, payload("PayloadJSON", value="[]"))
    assert isinstance(cmd, CommandSystemDonate)
    assert cmd.key == "sess-whatsapp_group_chat_uu"
