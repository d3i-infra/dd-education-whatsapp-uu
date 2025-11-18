"""
DDP Whatsapp account info module

This module contains functions to handle *.jons files contained within Whatsapp account info
"""

from pathlib import Path
import logging
import zipfile

import pandas as pd

import port.api.props as props
import port.api.d3i_props as d3i_props
import port.helpers.extraction_helpers as eh
import port.helpers.validate as validate
from port.platforms.flow_builder import FlowBuilder

from port.helpers.validate import (
    DDPCategory,
    DDPFiletype,
    Language,
)


logger = logging.getLogger(__name__)


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
            "terms_of_service.json"
         ],
    )
]


def ncontacts_ngroups_device_to_df(whatsapp_account_info_zip: str) -> pd.DataFrame:
    out = pd.DataFrame()
    datapoints = []

    # Extract number of contacts
    b = eh.extract_file_from_zip(whatsapp_account_info_zip, "contacts.json")
    d = eh.read_json_from_bytes(b)
    try:
        items = d["wa_contacts"]
        datapoints.append(("Number of contacts", len(items)))
    except Exception as e:
        logger.error("Exception caught: %s", e)

    # Extract number of groups
    b = eh.extract_file_from_zip(whatsapp_account_info_zip, "groups.json")
    d = eh.read_json_from_bytes(b)
    try:
        items = d["wa_groups"]
        datapoints.append(("Number of groups", len(items)))
    except Exception as e:
        logger.error("Exception caught: %s", e)

    # Extract platform 
    b = eh.extract_file_from_zip(whatsapp_account_info_zip, "registration_info.json")
    d = eh.read_json_from_bytes(b)
    print(d)
    try:
        platform = d["wa_registration_info"].get("platform", "").lower()
        description = "Platform name"
        print(platform)
        if "iphone" in platform:
            datapoints.append((description, "iphone"))
        elif "android" in platform:
            datapoints.append((description, "android"))
        else:
            pass # dont append datapoint

    except Exception as e:
        logger.error("Exception caught: %s", e)

    if len(datapoints) > 0:
        out = pd.DataFrame(datapoints, columns=["Description", "Value"])

    return out


def extract(account_info_zip: str) -> list[props.PropsUIPromptConsentFormTable]:
    """
    Main data extraction function
    Assemble all extraction logic here
    """
    tables_to_render = []

    # Extract comments
    df = ncontacts_ngroups_device_to_df(account_info_zip)
    if not df.empty:
        table_title = props.Translatable({
            "en": "Whatsapp Account information",
            "nl": "Whatsapp Account information",
        })
        table_description = props.Translatable({
            "en": "In this table you can see: the number of groups you are a part of, the number of contacts you have, and you use WhatsApp on", 
            "nl": "In this table you can see: the number of groups you are a part of, the number of contacts you have, and you use WhatsApp on", 
        })
        table = d3i_props.PropsUIPromptConsentFormTableViz("all", table_title, df, table_description)
        tables_to_render.append(table)

    return tables_to_render


class WhatsAppAccountInfo(FlowBuilder):
    def __init__(self, session_id: int):
        super().__init__(session_id, "WhatsApp account information")
        
    def validate_file(self, file):
        return validate.validate_zip(DDP_CATEGORIES, file)
        
    def extract_data(self, file_value, validation):
        return extract(file_value)


def process(session_id):
    flow = WhatsAppAccountInfo(session_id)
    return flow.start_flow()

