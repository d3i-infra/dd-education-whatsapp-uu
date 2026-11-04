# Upstream 2026 sync + UU WhatsApp platforms — design

Date: 2026-11-04
Branch: `upstream-2026` (this repo, `d3i-infra/dd-education-whatsapp-uu`)

## Goal

Bring this repo onto the latest `development` branch of
`d3i-infra/data-donation-task` and re-add the two UU course flows —
WhatsApp account information and the UU WhatsApp group chat — as two extra
platforms that follow upstream's ADRs (`docs/decisions/`). All commits land in
this repo; nothing is pushed upstream.

Non-goal: changing the UU privacy behaviour (message redaction, Member-N
anonymisation, self-selection). It is ported as-is.

## 1. Integration

- Branch `upstream-2026` off `master`.
- Add remote `upstream` = `https://github.com/d3i-infra/data-donation-task.git`
  (fetch only) and `git merge upstream/development`. The repos share history
  (merge base `5abe50d`, 2025-10-28).
- Conflict policy: take upstream for every file (dependency bumps, lockfiles,
  `main.py`, `whatsapp.py`, helpers, front end) **except** `README.md`, which is
  merged by hand (section 6). This repo's local edits to `whatsapp.py` and
  `main.py` are dropped; the UU logic moves into new modules.
- Files that only exist on this side and upstream removed (e.g. the old
  `port/platforms/flow_builder.py`) follow upstream: removed.

## 2. `FlowBuilder` donation-key override

`FlowBuilder.__init__(session_id, platform_name, config_key=None, donation_key=None)`.

- `donation_key=None` → key segment is `platform_name.lower()` (unchanged for
  every existing platform).
- An explicit `donation_key` must match `^[a-z0-9_]+$`; otherwise `ValueError`.
- `start_flow()` donates under `f"{session_id}-{self.donation_key}"`.
- ADR-0020 guidance gains one bullet documenting the override; re-run
  `adg lean index --model docs/decisions --root .`.

## 3. Platform `whatsapp_account_info`

File: `packages/python/port/platforms/whatsapp_account_info.py`.

- `DDP_CATEGORIES`: the existing JSON/HTML English account-info file list.
- Extractor `account_summary_to_df(reader: ZipArchiveReader, errors: Counter)`
  → DataFrame `Description`, `Value` with rows, each only when available:
  - `Number of contacts` = `len(contacts.json["wa_contacts"])`
  - `Number of groups` = `len(groups.json["wa_groups"])`
  - `Platform name` = `iphone` / `android` from
    `registration_information.json["wa_registration_info"]["platform"]`
    (lower-cased substring match; anything else → row omitted).
  Missing files are expected (`result.found` False, ADR-0024); malformed JSON
  increments `errors`.
- Docstring carries `Table config::` (id `whatsapp_account_info`) and
  `Table documentation::` (ADR-0028); `EXTRACTOR_REGISTRY`, `extraction()`,
  `WhatsAppAccountInfoFlow(FlowBuilder)`, `process()` (ADR-0029).
- Names: UI `"WhatsApp account information"`, `config_key="whatsapp_account_info"`,
  `donation_key="whatsapp_account_info"`.

## 4. Platform `whatsapp_group_chat_uu`

File: `packages/python/port/platforms/whatsapp_group_chat_uu.py`.

- Reuses upstream's public parsing from `port.platforms.whatsapp`
  (`parse_chat`, `remove_empty_chats`, `extract_users`, `keep_users`,
  `find_emojis`, `who_reacted_to_you_the_most`, `who_you_reacted_to_the_most`,
  `total_number_of_messages`, `total_number_of_words`, `favorite_emoji`).
  Same-layer import (ADR-0007); timestamp conversion therefore stays inside the
  existing `whatsapp.py` carve-out of ADR-0042.
- UU-specific, unchanged in behaviour:
  - `validate_file`: valid iff parsed chat (after `remove_empty_chats`) is
    non-empty and has **more than 3** detected users.
  - `extract_data`: parse → filter users → radio prompt
    (`ph.generate_radio_prompt` + `ph.render_page`) "Select your WhatsApp name"
    → `anonymize_users` (selected → `Member 1`, others `Member 2..N`) →
    `redact_non_whitespace` on messages → `extraction(df)`.
  - Radio prompt not answered with a `PayloadString` → `ExtractionResult` with
    no tables (no-data path, ADR-0019).
- Extractors `(df, errors)` (WhatsApp signature exception, ADR-0029), each with
  docstring config:
  - `chat_messages_to_df` → `Timestamp`, `Name`, `Message` (redacted),
    `date_columns` `Timestamp: iso-8601`, bar viz "Total chats per hour of the day".
  - `emoji_usage_to_df` → `Emoji`, `Count` (top 100).
  - `member_statistics_to_df` → `Member`, `Description`, `Statistic`: one table
    for all members (replaces the previous variable number of per-user tables,
    since tables are config-driven).
- Names: UI `"WhatsApp group chat"`, `config_key` and `donation_key`
  `"whatsapp_group_chat_uu"`.

## 5. Configs

Generate with `pnpm generate-config whatsapp_account_info` and
`pnpm generate-config whatsapp_group_chat_uu`; commit both
(`packages/python/port/configs/*_config.json`). `release.sh` discovers them.

## 6. README

Upstream README, prefixed with the UU course paragraph and a note that the
application was adapted in 2026 to the latest `d3i-infra/data-donation-task`
`development` branch, plus how to run/release the two platforms
(`VITE_PLATFORM=whatsapp_account_info` / `whatsapp_group_chat_uu`).

## 7. Testing

Synthetic fixtures only, built in-test (ADR-0014).

- `test_flow_builder.py`: default key unchanged; explicit `donation_key` used
  in the donate command; invalid key → `ValueError`.
- `test_whatsapp_account_info.py`: extractor on in-memory zips (all files,
  missing files, unknown platform); validation accepts/rejects.
- `test_whatsapp_group_chat_uu.py`: anonymisation, redaction, validation
  (≤3 vs >3 users), flow driven with `send()` through the radio prompt
  (selection and skip).
- `test_extractor_integration_whatsapp_account_info.py` /
  `..._whatsapp_group_chat_uu.py`: canary specs, skip without `tests/ddp/`
  fixtures (ADR-0027).
- Gate: `pnpm test:py`, `pnpm typecheck:py`, `adg lean check`, config validation.
