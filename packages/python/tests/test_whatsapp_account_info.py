"""Tests for the UU WhatsApp account-information platform.

Synthetic in-memory zips only (ADR-0014).
"""
import io
import json
import sys
import zipfile
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import pandas as pd

_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_port_config import build_config  # noqa: E402

import port.helpers.table_extractor as te  # noqa: E402
from port.helpers.extraction_helpers import ZipArchiveReader  # noqa: E402
from port.platforms import whatsapp_account_info as wai  # noqa: E402


def make_zip(files: dict[str, object]) -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content if isinstance(content, str) else json.dumps(content))
    buf.seek(0)
    return buf


def make_reader(buf: io.BytesIO) -> tuple[ZipArchiveReader, Counter]:
    with zipfile.ZipFile(buf) as zf:
        members = zf.namelist()
    buf.seek(0)
    errors: Counter = Counter()
    return ZipArchiveReader(buf, members, errors), errors


FULL_EXPORT = {
    "whatsapp_account_info/contacts.json": {"wa_contacts": [{"n": 1}, {"n": 2}, {"n": 3}]},
    "whatsapp_account_info/groups.json": {"wa_groups": [{"g": 1}, {"g": 2}]},
    "whatsapp_account_info/registration_information.json": {
        "wa_registration_info": {"platform": "iPhone 15"}
    },
}


def as_dict(df: pd.DataFrame) -> dict:
    return dict(zip(df["Description"], df["Value"]))


class TestAccountSummary:
    def test_full_export(self):
        reader, errors = make_reader(make_zip(FULL_EXPORT))
        df = wai.account_summary_to_df(reader, errors)
        assert list(df.columns) == ["Description", "Value"]
        assert as_dict(df) == {
            "Number of contacts": 3,
            "Number of groups": 2,
            "Platform name": "iphone",
        }
        assert not errors

    def test_android(self):
        files = dict(FULL_EXPORT)
        files["whatsapp_account_info/registration_information.json"] = {
            "wa_registration_info": {"platform": "ANDROID"}
        }
        reader, errors = make_reader(make_zip(files))
        assert as_dict(wai.account_summary_to_df(reader, errors))["Platform name"] == "android"

    def test_unknown_platform_row_is_omitted(self):
        files = dict(FULL_EXPORT)
        files["whatsapp_account_info/registration_information.json"] = {
            "wa_registration_info": {"platform": "KaiOS"}
        }
        reader, errors = make_reader(make_zip(files))
        assert "Platform name" not in as_dict(wai.account_summary_to_df(reader, errors))
        assert not errors

    def test_missing_files_are_not_errors(self):
        reader, errors = make_reader(make_zip({
            "whatsapp_account_info/groups.json": {"wa_groups": [{"g": 1}]},
        }))
        df = wai.account_summary_to_df(reader, errors)
        assert as_dict(df) == {"Number of groups": 1}
        assert not errors

    def test_unexpected_shape_counts_an_error(self):
        reader, errors = make_reader(make_zip({
            "whatsapp_account_info/contacts.json": {"something_else": []},
        }))
        df = wai.account_summary_to_df(reader, errors)
        assert df.empty
        assert sum(errors.values()) == 1

    def test_no_files_gives_empty_frame(self):
        reader, errors = make_reader(make_zip({"other.txt": "x"}))
        assert wai.account_summary_to_df(reader, errors).empty


def test_registry_lists_the_extractor():
    assert wai.EXTRACTOR_REGISTRY == {"account_summary_to_df": wai.account_summary_to_df}


def make_flow():
    with patch("port.helpers.flow_builder.load_public_key_pem", return_value=None), \
         patch("port.helpers.flow_builder.load_reference_timezone", return_value=None):
        return wai.WhatsAppAccountInfoFlow("sess")


class TestFlow:
    def test_names_and_keys(self):
        flow = make_flow()
        assert flow.platform_name == "WhatsApp account information"
        assert flow.donation_key == "whatsapp_account_info"

    def test_validate_accepts_account_export(self):
        files = dict(FULL_EXPORT)
        files["whatsapp_account_info/index.html"] = "<html></html>"
        v = make_flow().validate_file(make_zip(files))
        assert v.get_status_code_id() == 0

    def test_validate_rejects_unrelated_zip(self):
        v = make_flow().validate_file(make_zip({"foo/bar.csv": "a,b"}))
        assert v.get_status_code_id() != 0


def test_extraction_builds_config_driven_table(monkeypatch):
    config = te._build_config(build_config("whatsapp_account_info"), wai.EXTRACTOR_REGISTRY)
    monkeypatch.setattr(wai, "load_port_config", lambda registry, platform: config)
    buf = make_zip(FULL_EXPORT)
    v = make_flow().validate_file(buf)
    buf.seek(0)
    result = wai.extraction(buf, v)
    assert [t.id for t in result.tables] == ["whatsapp_account_info"]
    assert len(result.tables[0].data_frame) == 3
