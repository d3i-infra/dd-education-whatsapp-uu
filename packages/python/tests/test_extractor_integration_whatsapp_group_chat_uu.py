"""Integration canary for the UU WhatsApp group-chat extractors.

Requires a real chat export at ``tests/ddp/whatsapp_group_chat_uu_<anything>.zip``.
Skips when absent (ADR-0014, ADR-0027).
"""
from collections import Counter

import pytest

from extractor_integration_helpers import find_fixture
from port.platforms import whatsapp_group_chat_uu as uu


@pytest.fixture(scope="module")
def anonymized_df():
    fixture = find_fixture("whatsapp_group_chat_uu")
    if fixture is None:
        pytest.skip("No whatsapp_group_chat_uu_*.zip fixture found in tests/ddp/")
    with open(fixture, "rb") as fh:
        df, users = uu._parse_members_only(fh)
    return uu.anonymize_users(df, users, sorted(users)[0])


@pytest.mark.parametrize("name", list(uu.EXTRACTOR_REGISTRY))
def test_extractor_not_empty(name, anonymized_df):
    df = uu.EXTRACTOR_REGISTRY[name](anonymized_df, Counter())
    assert not df.empty, (
        f"{name} returned an empty DataFrame — the extractor may have "
        "crashed or the chat export format changed."
    )
