# Upstream 2026 sync + UU WhatsApp platforms — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put this repo on the latest `d3i-infra/data-donation-task` `development` branch and add two UU platforms — `whatsapp_account_info` and `whatsapp_group_chat_uu` — built to upstream's ADRs.

**Architecture:** `git merge` upstream `development` into branch `upstream-2026` (take upstream on every conflict except README). Add an optional `donation_key` to `FlowBuilder` (ADR-0020). Add two platform modules under `packages/python/port/platforms/` following the ADR-0029 interface with docstring table configs (ADR-0028); the chat platform reuses upstream `whatsapp.py`'s public parsing and runs extractors through `run_extraction` with the parsed DataFrame as the "reader". Commit the two generated configs.

**Tech Stack:** Python 3.11+ (Pyodide runtime, desktop pytest + Pyright via Poetry), pandas, pnpm monorepo, `adg` ADR tool.

**Spec:** `docs/superpowers/specs/2026-11-04-upstream-2026-whatsapp-platforms-design.md`

**Conventions for every task**
- Repo root: `/home/turbo/d3i/projects/rense/dd-education-whatsapp-uu` (call it `$ROOT`).
- Python tests: `cd $ROOT && pnpm test:py -- <test path> -q` (paths relative to `packages/python`).
- Before editing a file, pull the ADR brief: `cd $ROOT && adg lean brief --model docs/decisions <paths>`.
- Fixtures are synthetic and built in-test only (ADR-0014). Never add files under `packages/python/tests/ddp/`.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## File map

| File | Action | Responsibility |
|---|---|---|
| (whole tree) | merge | upstream `development` |
| `README.md` | modify | UU intro + 2026 note + platform run/release instructions |
| `.gitignore` | modify | un-ignore the two UU configs |
| `packages/python/port/helpers/flow_builder.py` | modify | `donation_key` param |
| `packages/python/tests/test_flow_builder.py` | modify | `donation_key` tests |
| `docs/decisions/0020-use-session-platform-donation-keys.md` | modify | document override |
| `packages/python/port/platforms/whatsapp_account_info.py` | create | account-info platform |
| `packages/python/tests/test_whatsapp_account_info.py` | create | unit + flow tests |
| `packages/python/port/platforms/whatsapp_group_chat_uu.py` | create | UU group-chat platform |
| `packages/python/tests/test_whatsapp_group_chat_uu.py` | create | unit + flow tests |
| `packages/python/port/configs/whatsapp_account_info_config.json` | generate | runtime config |
| `packages/python/port/configs/whatsapp_group_chat_uu_config.json` | generate | runtime config |
| `packages/python/tests/test_extractor_integration_whatsapp_account_info.py` | create | ADR-0027 canary |
| `packages/python/tests/test_extractor_integration_whatsapp_group_chat_uu.py` | create | ADR-0027 canary |

---

### Task 1: Merge upstream `development`

**Files:** whole tree; hand-merge `README.md` only.

- [ ] **Step 1: Add the upstream remote (fetch only) and fetch**

```bash
cd $ROOT
git remote add upstream https://github.com/d3i-infra/data-donation-task.git
git remote set-url --push upstream DISABLED
git fetch upstream development
```
Expected: `upstream/development` exists (`git log -1 upstream/development`).

- [ ] **Step 2: Merge without committing**

```bash
git merge --no-ff --no-commit upstream/development
git status --short | grep -E '^(UU|AA|DU|UD|AU|UA|DD) '
```
Expected: a list of conflicted files.

- [ ] **Step 3: Resolve — take upstream for every conflicted path except README.md**

```bash
for f in $(git diff --name-only --diff-filter=U); do
  [ "$f" = "README.md" ] && continue
  if git cat-file -e upstream/development:"$f" 2>/dev/null; then
    git checkout --theirs -- "$f" && git add -- "$f"
  else
    git rm -q -- "$f"
  fi
done
```
Then also force the non-conflicting files the fork touched back to upstream's state (the UU logic moves to new modules):
```bash
git checkout upstream/development -- packages/python/port/platforms/whatsapp.py packages/python/port/main.py
git rm -q --ignore-unmatch packages/python/port/platforms/whatsapp_account_info.py
```
(The old `whatsapp_account_info.py` is re-created from scratch in Task 3.)

- [ ] **Step 4: Resolve README.md as upstream's README**

```bash
git checkout --theirs -- README.md && git add README.md
```
(UU text is re-added in Task 10.)

- [ ] **Step 5: Verify the tree equals upstream except for our spec/plan docs**

```bash
git diff --stat upstream/development -- . ':!docs/superpowers/specs/2026-11-04-*' ':!docs/superpowers/plans/2026-11-04-*'
```
Expected: no output.

- [ ] **Step 6: Install and run the baseline test suite**

```bash
pnpm install
(cd packages/python && poetry install)
pnpm test:py -- -q
```
Expected: all pass (this is upstream's own suite). If anything fails, stop and report — it is an upstream baseline issue, not ours.

- [ ] **Step 7: Commit the merge**

```bash
git commit -m "Merge upstream d3i-infra/data-donation-task development (2026 sync)

Takes upstream for every file. The UU WhatsApp flows are re-added as
separate platforms in follow-up commits.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `FlowBuilder` `donation_key` override

**Files:**
- Modify: `packages/python/port/helpers/flow_builder.py` (`__init__` at ~line 58, donate key at ~line 289)
- Test: `packages/python/tests/test_flow_builder.py` (append)
- Modify: `docs/decisions/0020-use-session-platform-donation-keys.md`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_flow_builder.py`:

```python
class KeyedStubFlow(StubFlow):
    """StubFlow with an explicit donation key."""

    def __init__(self, session_id="test-session", donation_key=None):
        with patch("port.helpers.flow_builder.load_public_key_pem", return_value=None):
            FlowBuilder.__init__(self, session_id, "Test Platform Name", donation_key=donation_key)
        self._validation_status = 0
        self._tables = StubFlow()._tables


class TestDonationKeyOverride:
    def test_default_key_is_lowercased_platform_name(self):
        flow = StubFlow()
        assert flow.donation_key == "testplatform"

    def test_explicit_donation_key_is_used_in_donate_command(self):
        flow = KeyedStubFlow(session_id="sess-42", donation_key="my_platform")
        gen = flow.start_flow()
        start_and_skip_logs(gen)
        advance_past_logs(gen, make_payload_file())
        cmd = advance_past_logs(gen, make_payload("PayloadJSON", value="{}"))
        assert isinstance(cmd, CommandSystemDonate)
        assert cmd.key == "sess-42-my_platform"

    def test_explicit_key_does_not_change_display_name(self):
        flow = KeyedStubFlow(donation_key="my_platform")
        assert flow.platform_name == "Test Platform Name"

    @pytest.mark.parametrize("bad", ["My_Platform", "my platform", "my-platform", ""])
    def test_invalid_donation_key_raises(self, bad):
        with pytest.raises(ValueError):
            KeyedStubFlow(donation_key=bad)
```

- [ ] **Step 2: Run, verify failure**

Run: `pnpm test:py -- tests/test_flow_builder.py -q -k DonationKeyOverride`
Expected: FAIL — `TypeError: ... unexpected keyword argument 'donation_key'` / `AttributeError: ... 'donation_key'`.

- [ ] **Step 3: Implement** in `port/helpers/flow_builder.py`

Add near the imports: `import re`, and at module level:
```python
#: ADR-0020: the donation-key platform segment is a machine key.
_DONATION_KEY_RE = re.compile(r"^[a-z0-9_]+$")
```
Change the signature and body of `FlowBuilder.__init__`:
```python
    def __init__(
        self,
        session_id: str,
        platform_name: str,
        config_key: str | None = None,
        donation_key: str | None = None,
    ):
```
Append to the docstring's Parameters:
```
        donation_key:
            Optional explicit donation-key segment (ADR-0020). Defaults to
            ``platform_name.lower()``. Must match ``^[a-z0-9_]+$``; pass it
            when the display name contains spaces or capitals.
```
After `self.platform_name = platform_name` add:
```python
        if donation_key is None:
            self.donation_key = platform_name.lower()
        elif _DONATION_KEY_RE.match(donation_key):
            self.donation_key = donation_key
        else:
            raise ValueError(f"Invalid donation_key {donation_key!r}: must match ^[a-z0-9_]+$")
```
Replace `donate_key = f"{self.session_id}-{self.platform_name.lower()}"` with:
```python
        donate_key = f"{self.session_id}-{self.donation_key}"
```

- [ ] **Step 4: Run the whole flow-builder file**

Run: `pnpm test:py -- tests/test_flow_builder.py -q`
Expected: all PASS (existing `TestDonateKeyFormat` still sees `sess-42-testplatform`).

- [ ] **Step 5: Document in ADR-0020** — add this bullet as the last item under `## Guidance`:

```markdown
- A platform whose display name is not itself a valid key (spaces, capitals) passes `donation_key=` to `FlowBuilder.__init__`; the explicit key must match `^[a-z0-9_]+$` (`ValueError` otherwise) and replaces `platform_name.lower()` in the donation key only — the display name and `config_key` are unaffected.
```
Then: `adg lean index --model docs/decisions --root .` — expected: exits 0.

- [ ] **Step 6: Commit**

```bash
git add packages/python/port/helpers/flow_builder.py packages/python/tests/test_flow_builder.py docs/decisions/
git commit -m "feat(flow_builder): optional donation_key override (ADR-0020)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `whatsapp_account_info` extractor

**Files:**
- Create: `packages/python/port/platforms/whatsapp_account_info.py`
- Create: `packages/python/tests/test_whatsapp_account_info.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_whatsapp_account_info.py`:

```python
"""Tests for the UU WhatsApp account-information platform.

Synthetic in-memory zips only (ADR-0014).
"""
import io
import json
import zipfile
from collections import Counter

import pandas as pd

from port.helpers.extraction_helpers import ZipArchiveReader
from port.platforms import whatsapp_account_info as wai


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
```

- [ ] **Step 2: Run, verify failure**

Run: `pnpm test:py -- tests/test_whatsapp_account_info.py -q`
Expected: FAIL — `ImportError: cannot import name 'whatsapp_account_info'`.

- [ ] **Step 3: Implement** — create `port/platforms/whatsapp_account_info.py`:

```python
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
    if not result.found:
        return None
    items = result.data.get(key) if isinstance(result.data, dict) else None
    if not isinstance(items, list):
        errors[f"UnexpectedShape({filename})"] += 1
        return None
    return len(items)


def _device_platform(reader: ZipArchiveReader, errors: Counter) -> str | None:
    """``"iphone"`` / ``"android"`` from registration_information.json, else None."""
    result = reader.json("registration_information.json")
    if not result.found:
        return None
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
    return pd.DataFrame(rows, columns=["Description", "Value"])  # pyright: ignore


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
```

- [ ] **Step 4: Run, verify pass**

Run: `pnpm test:py -- tests/test_whatsapp_account_info.py -q`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/python/port/platforms/whatsapp_account_info.py packages/python/tests/test_whatsapp_account_info.py
git commit -m "feat(whatsapp_account_info): UU account-info platform extractor

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: `whatsapp_account_info` validation, keys, extraction wiring

**Files:**
- Test: `packages/python/tests/test_whatsapp_account_info.py` (append)

- [ ] **Step 1: Write the tests** — append:

```python
import sys
from pathlib import Path
from unittest.mock import patch

import port.helpers.table_extractor as te

_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
from generate_port_config import build_config  # noqa: E402


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
```

- [ ] **Step 2: Run**

Run: `pnpm test:py -- tests/test_whatsapp_account_info.py -q`
Expected: all PASS (Task 3's implementation already covers these). If `test_validate_accepts_account_export` fails, inspect `validate_zip`'s scoring (`port/helpers/validate.py`) and make the fixture contain enough `known_files` — do not loosen `DDP_CATEGORIES`.

- [ ] **Step 3: Commit**

```bash
git add packages/python/tests/test_whatsapp_account_info.py
git commit -m "test(whatsapp_account_info): flow keys, validation and extraction wiring

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: `whatsapp_group_chat_uu` — anonymise and redact helpers

**Files:**
- Create: `packages/python/port/platforms/whatsapp_group_chat_uu.py`
- Create: `packages/python/tests/test_whatsapp_group_chat_uu.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_whatsapp_group_chat_uu.py`:

```python
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
        assert list(out["name"]) == ["Member 2", "Member 3", "Member 1", "Member 3"]

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
```

- [ ] **Step 2: Run, verify failure**

Run: `pnpm test:py -- tests/test_whatsapp_group_chat_uu.py -q`
Expected: FAIL — `ImportError: cannot import name 'whatsapp_group_chat_uu'`.

- [ ] **Step 3: Implement** — create `port/platforms/whatsapp_group_chat_uu.py` with the module header and helpers (extractors and flow follow in Tasks 6–7):

```python
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
```

- [ ] **Step 4: Run, verify pass**

Run: `pnpm test:py -- tests/test_whatsapp_group_chat_uu.py -q`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/python/port/platforms/whatsapp_group_chat_uu.py packages/python/tests/test_whatsapp_group_chat_uu.py
git commit -m "feat(whatsapp_group_chat_uu): anonymise and redact helpers

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: `whatsapp_group_chat_uu` — extractors and `extraction()`

Note: the old UU code redacted messages *before* computing emojis and
per-user statistics, so the emoji table and "emoji you used most" were always
empty (every emoji had become `*`). Here redaction applies only to the chat
table's `Message` column; emoji counts and statistics come from the
unredacted parsed frame and are still non-personal.

**Files:**
- Modify: `packages/python/port/platforms/whatsapp_group_chat_uu.py` (append)
- Test: `packages/python/tests/test_whatsapp_group_chat_uu.py` (append)

- [ ] **Step 1: Write the failing tests** — append:

```python
import sys
from pathlib import Path

import port.helpers.table_extractor as te

_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
from generate_port_config import build_config  # noqa: E402


def anonymized_frame():
    df = frame(
        ["Member 1", "Member 2", "Member 1", "Member 3"],
        ["Hoi 😀", "Hallo daar", "Leuk 😀😀", "Ok"],
    )
    return df


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
        m1 = dict(zip(out[out["Member"] == "Member 1"]["Description"], out[out["Member"] == "Member 1"]["Statistic"]))
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
```

- [ ] **Step 2: Run, verify failure**

Run: `pnpm test:py -- tests/test_whatsapp_group_chat_uu.py -q`
Expected: FAIL — `AttributeError: module ... has no attribute 'chat_messages_to_df'`.

- [ ] **Step 3: Implement** — append to `whatsapp_group_chat_uu.py`:

```python
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
    return pd.DataFrame(rows, columns=["Member", "Description", "Statistic"])  # pyright: ignore


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
```

- [ ] **Step 4: Run, verify pass**

Run: `pnpm test:py -- tests/test_whatsapp_group_chat_uu.py -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/python/port/platforms/whatsapp_group_chat_uu.py packages/python/tests/test_whatsapp_group_chat_uu.py
git commit -m "feat(whatsapp_group_chat_uu): docstring-configured extractors

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: `whatsapp_group_chat_uu` — flow (validation, name picker)

**Files:**
- Modify: `packages/python/port/platforms/whatsapp_group_chat_uu.py` (append)
- Test: `packages/python/tests/test_whatsapp_group_chat_uu.py` (append)

- [ ] **Step 1: Write the failing tests** — append:

```python
from unittest.mock import MagicMock, patch

from port.api.commands import CommandUIRender


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
        try:
            gen.send(payload("PayloadString", value="Cees"))
        except StopIteration:
            pass
        df = captured["df"]
        assert set(df["name"]) == {f"Member {i}" for i in range(1, 6)}
        assert list(df[df["name"] == "Member 1"]["chat_message"]) == ["Prima 😀😀"]
        assert "en een tweede regel" in df[df["name"] == "Member 5"]["chat_message"].iloc[0]

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
```
Also add `from port.api.d3i_props import ExtractionResult` to the test file's imports.

- [ ] **Step 2: Run, verify failure**

Run: `pnpm test:py -- tests/test_whatsapp_group_chat_uu.py -q`
Expected: FAIL — `AttributeError: ... no attribute 'WhatsAppGroupChatUUFlow'`.

- [ ] **Step 3: Implement** — append to `whatsapp_group_chat_uu.py`:

```python
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

    def extract_data(self, file: SeekableBinaryReader, validation):
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
```
Check before running: confirm `validate.BaseValidation` exists upstream with `status_code` and `get_status_code_id()` (`grep -n "class BaseValidation" -A15 packages/python/port/helpers/validate.py`); upstream `whatsapp.py` uses it the same way. Confirm the radio payload value is the selected item string (Netflix uses `selection.value` directly). If upstream's radio payload carries the item *id* instead, map it: `sorted(users)[int(selection.value)]`.

- [ ] **Step 4: Run, verify pass**

Run: `pnpm test:py -- tests/test_whatsapp_group_chat_uu.py -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/python/port/platforms/whatsapp_group_chat_uu.py packages/python/tests/test_whatsapp_group_chat_uu.py
git commit -m "feat(whatsapp_group_chat_uu): flow with >3-member validation and name picker

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Generate and commit configs

**Files:**
- Modify: `.gitignore`
- Generate: `packages/python/port/configs/whatsapp_account_info_config.json`, `packages/python/port/configs/whatsapp_group_chat_uu_config.json`

- [ ] **Step 1: Un-ignore the two UU configs** — in `.gitignore`, directly under `!*example_config.json`, add:

```
# UU course deployment configs (this fork ships them)
!packages/python/port/configs/whatsapp_account_info_config.json
!packages/python/port/configs/whatsapp_group_chat_uu_config.json
```

- [ ] **Step 2: Generate**

```bash
cd $ROOT
pnpm generate-config whatsapp_account_info
pnpm generate-config whatsapp_group_chat_uu
```
Expected: both files written and validated (the script runs `validate_port_config.py`). Then confirm: `git status --short packages/python/port/configs/` lists both as untracked (`??`).

- [ ] **Step 3: Validate at runtime level**

```bash
cd packages/python && poetry run python -c "
from port.helpers.port_config_validator import validate_or_raise
validate_or_raise('whatsapp_account_info'); validate_or_raise('whatsapp_group_chat_uu'); print('ok')"
```
Expected: `ok`. (If `validate_or_raise` lives elsewhere, find it with `grep -rn "def validate_or_raise" port/`.)

- [ ] **Step 4: Commit**

```bash
git add .gitignore packages/python/port/configs/whatsapp_account_info_config.json packages/python/port/configs/whatsapp_group_chat_uu_config.json
git commit -m "chore(configs): ship UU WhatsApp platform configs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Extractor-integration canaries (ADR-0027)

**Files:**
- Create: `packages/python/tests/test_extractor_integration_whatsapp_account_info.py`
- Create: `packages/python/tests/test_extractor_integration_whatsapp_group_chat_uu.py`

- [ ] **Step 1: Account-info canary**

```python
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
    assert not df.empty, f"{spec.name} returned an empty DataFrame"
```
Before running, check how `make_reader` opens the fixture (it passes `str(fixture)`; if upstream's `validate_zip` rejects paths, mirror whatever `test_extractor_integration_chatgpt.py` does at execution time — it is the reference).

- [ ] **Step 2: Group-chat canary** (the extractors take a parsed frame, not a reader)

```python
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
    assert not df.empty, f"{name} returned an empty DataFrame"
```
(The test layer may use the module's own helper; ADR-0008 governs cross-*layer* private imports in `port/`, not tests. If review objects, rename `_parse_members_only` to `parse_members_only`.)

- [ ] **Step 3: Run**

Run: `pnpm test:py -- tests/test_extractor_integration_whatsapp_account_info.py tests/test_extractor_integration_whatsapp_group_chat_uu.py -q -rs`
Expected: all SKIPPED with the "No ... fixture" reason.

- [ ] **Step 4: Commit**

```bash
git add packages/python/tests/test_extractor_integration_whatsapp_*.py
git commit -m "test: extractor-integration canaries for UU WhatsApp platforms

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: README

**Files:** Modify `README.md` (now upstream's).

- [ ] **Step 1: Prepend** this block above upstream's first heading:

```markdown
# WhatsApp data donation — Utrecht University course

This Feldspar application is used each year in a Sociology course at Utrecht University on novel data collection methods. It contains a WhatsApp data donation study for account information and for group chat information. Only non-personal data are collected in this application.

> **Adapted to 2026:** this repository was brought up to date in November 2026 with the latest `development` branch of [d3i-infra/data-donation-task](https://github.com/d3i-infra/data-donation-task). The course flows now live as two separate platforms that follow that repository's architecture decisions (`docs/decisions/`).

## The two UU platforms

| Platform (`VITE_PLATFORM`) | Upload | Donates |
|---|---|---|
| `whatsapp_account_info` | WhatsApp "Request account info" zip | number of contacts, number of groups, device platform (iphone/android) |
| `whatsapp_group_chat_uu` | WhatsApp group-chat export (zip) | anonymised chat (Member 1 = you) with redacted message text, emoji counts, per-member statistics; requires more than three members |

Run one locally:

```sh
VITE_PLATFORM=whatsapp_group_chat_uu pnpm start
```

Build the deployable zips (one per platform in `packages/python/port/configs/`):

```sh
pnpm release
```

---
```

- [ ] **Step 2: Check the scripts named above exist** — `grep -n '"start"\|"release"' package.json`. If `pnpm start` is named differently upstream (e.g. `dev`), change the README command to match.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(readme): UU course intro, 2026 adaptation note, platform usage

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Full verification

- [ ] **Step 1: ADR checks**

```bash
cd $ROOT
adg lean index --model docs/decisions --root .
adg lean check --model docs/decisions --root .
```
Expected: both exit 0. (If `adg lean check` takes different flags, run `adg lean check --help`.)

- [ ] **Step 2: Python suite + types**

```bash
pnpm verify:py
```
Expected: all tests pass, Pyright reports 0 errors. Fix any Pyright errors in the new modules (do not add blanket ignores).

- [ ] **Step 3: JS suite (sanity, nothing touched)**

```bash
pnpm test:js
```
Expected: pass.

- [ ] **Step 4: Release build smoke for one platform**

```bash
VITE_PLATFORM=whatsapp_account_info pnpm run build:release
```
Expected: build succeeds.

- [ ] **Step 5: Review against the brief's manual checks** for the two new modules: ADR-0009 (no `CommandUIRender(`/`PropsUIPage*(` outside port_helpers), ADR-0028 (both docstring blocks on every extractor), ADR-0029 (four symbols present), ADR-0042 (no date parsing calls).

```bash
grep -nE 'CommandUIRender\(|PropsUIPage|to_datetime|strptime|parser\.parse' packages/python/port/platforms/whatsapp_account_info.py packages/python/port/platforms/whatsapp_group_chat_uu.py
```
Expected: no output.
