"""Integration canary for WhatsApp account-info extractors.

Requires a real export at ``tests/ddp/whatsapp_account_info_<anything>.zip``.
Skips when absent — CI runs clean without real data (ADR-0014, ADR-0027).
"""
import pytest

from extractor_integration_helpers import ExtractorSpec, find_fixture, make_reader
from port.platforms.whatsapp_account_info import DDP_CATEGORIES, account_summary_to_df

SPECS = [ExtractorSpec(name="account_summary_to_df", extractor=account_summary_to_df)]


@pytest.fixture(scope="module")
def reader():
    fixture = find_fixture("whatsapp_account_info")
    if fixture is None:
        pytest.skip("No whatsapp_account_info_*.zip fixture found in tests/ddp/")
    return make_reader(fixture, DDP_CATEGORIES)


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.name)
def test_extractor_not_empty(spec, reader):
    df = spec.run(reader)
    assert not df.empty, (
        f"{spec.name} returned an empty DataFrame — the extractor may have "
        "crashed, found no matching file, or the DDP format changed."
    )
