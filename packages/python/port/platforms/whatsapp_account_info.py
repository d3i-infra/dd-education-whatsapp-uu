"""
WhatsApp Account Information (UU course)
========================================

Handles the WhatsApp "Request account info" export (a zip of JSON/HTML files)
used in the Utrecht University course on novel data collection methods. Only
non-personal counts are extracted: the number of contacts, the number of
groups, and whether WhatsApp runs on an iPhone or Android device.

Platform info::

    {
        "name": "WhatsApp account information",
        "filetypes": ["zip"],
        "languages": ["en", "nl"],
        "description": "Handles the WhatsApp account information export (zip with JSON/HTML files). Extracts the number of contacts, the number of groups and the device platform (iphone/android).",
        "time_last_tested": "not yet implemented"
    }
"""
import logging
from collections import Counter
from typing import Callable

import pandas as pd

import port.helpers.validate as validate
from port.api.d3i_props import ExtractionResult
from port.api.file_utils import SeekableBinaryReader
from port.helpers.extraction_helpers import ZipArchiveReader
from port.helpers.flow_builder import FlowBuilder
from port.helpers.table_extractor import load_port_config, run_extraction
from port.helpers.validate import DDPCategory, DDPFiletype, Language, ValidateInput

logger = logging.getLogger(__name__)

#: Config filename key and ADR-0020 donation-key segment.
PLATFORM_KEY = "whatsapp_account_info"

DDP_CATEGORIES = [
    DDPCategory(
        id="json_html_en",
        ddp_filetype=DDPFiletype.JSON,
        language=Language.EN,
        known_files=[
            "index.html",
            "avatars_information.html",
            "avatars_information.json",
            "registration_information.html",
            "registration_information.json",
            "user_information.html",
            "user_information.json",
            "contacts.html",
            "contacts.json",
            "groups.html",
            "groups.json",
            "account_settings.html",
            "account_settings.json",
            "terms_of_service.html",
            "terms_of_service.json",
        ],
    )
]


def _count_list(reader: ZipArchiveReader, errors: Counter, filename: str, key: str) -> int | None:
    """Length of ``data[key]`` in *filename*; None when the file is absent
    (expected, ADR-0024) or has an unexpected shape (counted in *errors*)."""
    result = reader.json(filename)
    if not result.found or not result.data:
        return None  # absent (ADR-0024) or unreadable: the reader already recorded any decode error
    items = result.data.get(key) if isinstance(result.data, dict) else None
    if not isinstance(items, list):
        errors[f"UnexpectedShape({filename})"] += 1
        return None
    return len(items)


def _device_platform(reader: ZipArchiveReader, errors: Counter) -> str | None:
    """``"iphone"`` / ``"android"`` from registration_information.json, else None."""
    result = reader.json("registration_information.json")
    if not result.found or not result.data:
        return None  # absent (ADR-0024) or unreadable: the reader already recorded any decode error
    info = result.data.get("wa_registration_info") if isinstance(result.data, dict) else None
    if not isinstance(info, dict):
        errors["UnexpectedShape(registration_information.json)"] += 1
        return None
    platform = str(info.get("platform", "")).lower()
    if "iphone" in platform:
        return "iphone"
    if "android" in platform:
        return "android"
    return None


def account_summary_to_df(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    """Summarise the account export as non-personal counts.

    Table documentation::

        {
          "summary": "One row per available statistic about the participant's WhatsApp account: number of contacts, number of groups, and the device platform.",
          "source_file": "contacts.json, groups.json, registration_information.json",
          "columns": {
            "Description": "Name of the statistic.",
            "Value": "Value of the statistic (a count, or iphone/android for the platform)."
          }
        }

    Table config::

        {
          "id": "whatsapp_account_info",
          "title": {
            "en": "WhatsApp account information",
            "nl": "WhatsApp-accountinformatie"
          },
          "description": {
            "en": "In this table you can see: the number of groups you are a part of, the number of contacts you have, and the platform you use WhatsApp on.",
            "nl": "In deze tabel zie je: het aantal groepen waar je lid van bent, het aantal contacten dat je hebt, en het platform waarop je WhatsApp gebruikt."
          },
          "headers": {
            "Description": {"en": "Description", "nl": "Beschrijving"},
            "Value": {"en": "Value", "nl": "Waarde"}
          }
        }
    """
    rows: list[tuple[str, object]] = []
    n_contacts = _count_list(reader, errors, "contacts.json", "wa_contacts")
    if n_contacts is not None:
        rows.append(("Number of contacts", n_contacts))
    n_groups = _count_list(reader, errors, "groups.json", "wa_groups")
    if n_groups is not None:
        rows.append(("Number of groups", n_groups))
    device = _device_platform(reader, errors)
    if device is not None:
        rows.append(("Platform name", device))
    return pd.DataFrame(rows, columns=["Description", "Value"])


EXTRACTOR_REGISTRY: dict[str, Callable[..., pd.DataFrame]] = {
    "account_summary_to_df": account_summary_to_df,
}


def extraction(archive: SeekableBinaryReader, validation: ValidateInput) -> ExtractionResult:
    config = load_port_config(EXTRACTOR_REGISTRY, PLATFORM_KEY)
    errors: Counter = Counter()
    reader = ZipArchiveReader(archive, validation.archive_members, errors)
    return run_extraction(reader, errors, config)


class WhatsAppAccountInfoFlow(FlowBuilder):
    def __init__(self, session_id: str):
        super().__init__(
            session_id,
            "WhatsApp account information",
            config_key=PLATFORM_KEY,
            donation_key=PLATFORM_KEY,
        )

    def validate_file(self, file: SeekableBinaryReader) -> ValidateInput:
        return validate.validate_zip(DDP_CATEGORIES, file)

    def extract_data(self, file_value: SeekableBinaryReader, validation: ValidateInput) -> ExtractionResult:
        return extraction(file_value, validation)


def process(session_id: str):
    flow = WhatsAppAccountInfoFlow(session_id)
    return flow.start_flow()
