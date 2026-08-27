# Current App State — M.E.R.I.T APP

> This document describes the implementation **as it stands today**, not the original spec (`instructivo_backfill_app.md`) nor the first queue/cache addendum. Where current behavior differs from those earlier versions, it is called out explicitly.
>
> Generated from the real code in `app.py` on 2026-07-19, after integrating `addendum_tv_backfill.md` (TV support + one-backfill-per-subset lock) and translating the entire codebase, UI, and documentation to English.
>
> **Updated 2026-08-05** — major revision. Digital now splits into three sub-types (Social / Reserve / Programmatic) with their own filter sets, the single hardcoded weighting was replaced by six selectable operations, several filters accept multiple values, and the subset lock was rebuilt on row overlap. Sections 11–13 cover all of it; §3's weighting formula still describes the `MC_WEIGHTED` / `IMPR_WEIGHTED` operations, but is no longer the only path.
>
> **Updated 2026-08-05 (same day, second follow-up)** — the single-purpose app became **M.E.R.I.T APP** (Media Evaluation, Reconciliation & Integrity Tool), a shell with a home menu mounting multiple independent tools. The former app.py became `tools/rroi_backfill.py` unchanged in substance; a new **Data Caveats Generator** tool was added (ported from a standalone script). See §15.
>
> **Updated 2026-08-14** — third tool added: **TV Data Standardization**, which reconciles the TV team's spot-level files against the platform export and corrects it. Built from a written spec (`PROMPT - Logica Proceso TV Data.md`) plus the real workbook it describes. See §16.

---

## 1. Project file structure

```
merit_V1/
├── app.py                          # M.E.R.I.T. shell: home menu + tool registry/mounting only
├── tools/
│   ├── __init__.py
│   ├── rroi_backfill.py            # The entire backfill tool (formerly all of app.py) — see §2-14
│   ├── data_caveats.py             # Data Caveats Generator — see §15
│   ├── data_caveats_template.xlsx  # Bundled default Data Caveat Log template (25 KB)
│   ├── tv_standardization.py       # TV Data Standardization — see §16
│   └── tv_mappings.json            # Its lookup tables (estimate names, networks, dayparts, brands)
├── requirements.txt                # streamlit, pandas, openpyxl (no pinned versions)
├── .venv/                          # Local virtual environment (not versioned)
├── test_logic.py                   # RROI Backfill: taxonomy, operations, multi-value subsets, lock, build_preview
├── test_apptest_flow.py            # RROI Backfill: end-to-end via streamlit.testing.v1.AppTest
├── test_apptest_cache.py           # RROI Backfill: export-cache correctness/invalidation
├── test_real_file.py               # RROI Backfill: the real 150k-row workbook through taxonomy + every operation
├── test_data_caveats.py            # Data Caveats: pipeline functions + a real write against the bundled template
├── test_tv_standardization.py      # TV: synthetic logic tests + the real-file §10 control-figure regression
├── test_apptest_home.py            # Home menu navigation + Data Caveats settings/generate/download, via AppTest
├── USER_GUIDE.md                   # Non-technical user manual — RROI Manual Backfill
├── DATA_CAVEATS_GUIDE.md           # Non-technical user manual — Data Caveats Generator
├── TV_STANDARDIZATION_GUIDE.md     # Non-technical user manual — TV Data Standardization
└── estado_actual_app.md            # This document
```

**Relevant installed versions** (`.venv`): `streamlit==1.59.2`, `pandas==3.0.3`, `openpyxl==3.1.5`.

Git repository hosted on GitHub at `https://github.com/CristianBarbosaT/merit-app` (branch `main`). No `README.md` file. **The `tools/` package and its tests are new, uncommitted work** — not yet pushed.

**Sections 2–14 below describe `tools/rroi_backfill.py`** exactly as they described `app.py` before this restructure (only the module changed, not the code or behavior). §15 covers the new shell and the Data Caveats Generator.

---

## 2. Current functional flow, step by step

1. **Upload**: `st.file_uploader` accepts an `.xlsx`. If reading fails (`pd.ExcelFile`), an error is shown and execution stops (`st.stop()`).
2. **Sheet selection**: if the file has more than one sheet, an `st.selectbox` lets the user pick one; if there's only one, it's used automatically.
3. **Load sheet** (button): on click,
   - critical columns are validated for **both modes independently** (`CRITICAL_COLUMNS_DIGITAL`, `CRITICAL_COLUMNS_TV`, see §4). If **both** modes are missing something, it's a hard error and `st.stop()` (the file is unusable). If only one is missing something, loading continues anyway — that mode is flagged unavailable while the other works normally;
   - the DataFrame is prepared (`prepare_dataframe`): parses `Date`, derives `Month_Label` and `Parent_PCODE` (with a guard if `Package Name` doesn't exist);
   - **two** independent sets of dropdown options are computed and cached in session — one per mode — each **explicitly excluding the other channel's rows** (`build_dropdown_options_digital` filters `Channel != "TV"`; `build_dropdown_options_tv` filters `Channel == "TV"`). If a mode is missing critical columns, its option set is `None`;
   - the default download file name is initialized (`{original_name}_backfilled`);
   - the mode selector resets to "Digital";
   - any previous queue, preview, or log from an earlier load is cleared.
4. **Mode selector**: an `st.radio` ("Digital" / "TV", `key="mode_selector"`) **outside the `st.form`**, so switching it immediately updates which filters are shown without waiting for a submit. If the selected mode doesn't have enough columns in the file, an error explains what's missing and the filter form for that mode isn't rendered (the other mode remains available).
5. **Backfill filters** — form contents depend on the mode:
   - **Digital** (7 filters, unchanged behavior from the previous version): Month, Campaign (`Prisma_Campaign_Secondary`), Partner, Package (PCODE), CCD JTBD, Audience, Breakout + Target Media Cost. The field being backfilled is always `Media_Cost`, always weighted by `Impressions`.
   - **TV** (5 filters, new): Month, Brand, Audience, Daypart, Network_Name + a **"Field to backfill"** selector (`Media_Cost` or `Impressions`) + a numeric target whose label changes dynamically based on the chosen field. The field not chosen is automatically used as the weight (`FIELD_PAIRS`).
   - In both cases, the widgets live inside an `st.form` (`filters_form_digital` / `filters_form_tv`, separate forms per mode): changing a dropdown does not trigger a re-run; only the submit button ("Preview") recalculates.
6. **Preview** (form submit): runs 4 validations in order via `build_preview` — positive target, non-empty subset, **one-backfill-per-subset lock** (new, see §4), and total weight > 0 — and if everything passes, stores the result in `st.session_state.preview_result` (including `mode`, `target_field`, `weight_field`) and shows 4 scorecards (`st.metric`): Rows in subset, Current `{target_field}` sum, Target sum, Delta. Number formatting changes based on the field: `$X,XXX.XX` for Media_Cost, `X,XXX` (no decimals) for Impressions (`format_field_value`).
7. **Add to queue**: takes the current `preview_result` and appends it as an item with a unique `qid` to `st.session_state.queue`, now including `mode`, `target_field`, and `weight_field`. Clears the preview afterward.
8. **Backfill queue**: summary table with `Mode` and `Field` columns added, plus every possible filter column from both modes combined (`Month, Campaign, Partner, Package, CCD JTBD, Brand, Daypart, Network, Audience, Breakout` — whichever don't apply to an item's mode are left blank in that row). Below that:
   - **Remove from queue**: by unique `qid` (mechanism unchanged, now works the same with mixed items from both modes — verified with a test).
   - **Clear queue**: unchanged.
   - **Run full queue**: iterates each item, picks `compute_subset_digital` or `compute_subset_tv` based on `item["mode"]`, recomputes the subset against the current DataFrame, revalidates (0 rows / total weight 0 → skips that item with a reason, doesn't abort the rest), and if valid, writes to the `item["target_field"]` column (not always `Media_Cost` — can be `Impressions` for TV). When done, clears the queue, stores per-item results, and if at least one item was applied, bumps `data_version`.
9. **Result of the last queue run**: same as before, now with `Mode`/`Field` visible per item.
10. **Downloads**: mechanism unchanged — configurable file name, `.xlsx` (working sheet only, no helper columns), `.csv` log. The log now has `Mode`, `Field`, `Sum_Before`, `Sum_After` columns (see change note in §5).
11. **Reset**: clears all of `st.session_state`, including the new `missing_columns`, and resets the mode selector to "Digital".

---

## 3. Backfill business logic — as implemented

### Subsets (two separate functions, one per mode)

`compute_subset_digital(df, month_label, campaign, partner, pcode, ccd_jtbd, audience, breakout)`:
```python
mask = (
    (df["Channel"] != "TV")                              # ← new: explicitly excludes TV
    & (df["Month_Label"] == month_label)
    & (df["Prisma_Campaign_Secondary"] == campaign)
    & (df["Raw_Partner"] == partner)
    & (df["Parent_PCODE"] == pcode)
    & (df["CCD JTBD"] == ccd_jtbd)
    & (df["Audience"] == audience)
    & (df["Breakout"] == breakout)
)
```

`compute_subset_tv(df, month_label, brand, audience, daypart, network_name)` (new):
```python
mask = (
    (df["Channel"] == "TV")
    & (df["Month_Label"] == month_label)
    & (df["Brand"] == brand)
    & (df["Audience"] == audience)
    & (df["Daypart"] == daypart)
    & (df["Network_Name"] == network_name)
)
```

### Weighting formula (generalized, a single `compute_backfill` for both modes)

```python
def compute_backfill(subset, target_value, target_field, weight_field):
    weights_raw = subset[weight_field].fillna(0)
    total_weight = weights_raw.sum()
    if total_weight == 0:
        return None, total_weight          # blocks the backfill
    weights = weights_raw / total_weight
    new_values = weights * target_value
    return new_values, total_weight
```

- **Digital**: always called with `target_field="Media_Cost", weight_field="Impressions"` — no numeric behavior change from before.
- **TV**: called with whatever the user chose in "Field to backfill" — `("Media_Cost", "Impressions")` or `("Impressions", "Media_Cost")` (reciprocal direction).
- The original value of `target_field` in each row of the subset is **not used** in the calculation — it's fully overwritten.
- Rows with `weight_field` NULL or 0 → new `target_field` value = 0.
- Only the chosen `target_field` column is modified; `weight_field` is never touched.
- Numerically validated against the addendum's reference example (`test_logic.py`): Impressions backfill weighted by Media_Cost (target 800,000) and Media_Cost backfill weighted by Impressions (target 12,000) on the same 6-row subset — both cases reproduce the expected values within rounding tolerance.
- Digital does **not** get a field selector — it stays fixed to `Media_Cost`/`Impressions`, with no selector shown in its form.

### TV exception: target = 0 with a zero weight basis (new, 2026-07-19)

`compute_backfill` itself **did not change** — it still always blocks when `total_weight == 0` (it's a pure numeric function, with no business rules or notion of mode). The special case lives in a new wrapper, `resolve_new_values(mode, target_value, target_field, weight_field, subset)`:

- If `compute_backfill` succeeds, its result is returned as-is.
- If `compute_backfill` returns `None` (zero weight basis) **and** `mode == "TV"` **and** `target_value == 0`, it returns a series of pure zeros for `target_field` instead of blocking — there's no real ambiguity in distributing a $0 target across rows with no weight basis; every row simply gets 0.
- In every other case (Digital, or TV with a non-zero `target_value`), it still blocks exactly as before.

Both `build_preview` (preview) and the "Run full queue" loop call `resolve_new_values` instead of `compute_backfill` directly, so the rule can't end up out of sync between the two call sites.

The "positive target" validation in `build_preview` was also adjusted: for TV it now accepts `target_value >= 0` (allows exactly 0); Digital stays strictly `> 0`, unchanged.

**Scope implemented**: the exception is symmetric by design — it applies to `target_value == 0` regardless of which of the two fields is the target and which is the weight (e.g. it also allows backfilling Impressions to 0 when total Media_Cost is 0). The original request only mentioned the Impressions=0 → Media_Cost=0 case, but restricting the rule to that single direction would have been an arbitrary inconsistency given the math reasoning is identical in both directions. Worth confirming this is the expected scope.

---

## 4. Validations and business rules (including what this addendum added)

| Validation | Current behavior |
|---|---|
| Critical columns on sheet load | Now validates **two independent lists**: `CRITICAL_COLUMNS_DIGITAL` = `Channel, Date, Prisma_Campaign_Secondary, Raw_Partner, Package Name, CCD JTBD, Audience, Breakout, Impressions, Media_Cost`; `CRITICAL_COLUMNS_TV` = `Channel, Date, Brand, Audience, Daypart, Network_Name, Impressions, Media_Cost`. `Channel` is critical for **both** modes (needed to exclude TV from Digital and vice versa). If both are missing something → hard error, `st.stop()`. If only one is → persistent warning (`st.warning`, non-blocking) and that mode stays unusable until a file with all the required columns is loaded. |
| Positive target | Unchanged — validated in `build_preview` before anything else. |
| Subset with 0 rows | Unchanged — blocks preview, revalidated at queue execution time. |
| **Lock: one backfill per subset per session (new)** | An exact subset (identified by mode + the filters that define it, `subset_key`) can only have **one** item associated with it — pending in the queue **or** already applied in the log — regardless of which field was used. If the user tries to preview a subset that's already occupied, `build_preview` blocks it with a message indicating which field already occupies it, **before** reaching "Add to queue". The conflict search scans both `st.session_state.queue` and `st.session_state.log` (`find_lock_conflict_field`). It's not revalidated at queue execution time because, by construction, two queue items can never point at the same subset (the lock already prevented that at preview time). |
| Total weight == 0 | Mechanism unchanged, now generic over `weight_field` (previously hardcoded to `Impressions`). The error message names the actual weight field (e.g. "0 total Media_Cost" for a TV Impressions backfill). |
| PCODE pattern | Unchanged — only applies to the Digital dropdown. |
| File format | Unchanged — `.xlsx` only. |

**Behaviors added by this addendum that weren't there before:**

- **Digital/TV mode selector**, outside the form, instantly changes which filters are shown.
- **Two independent dropdown option sets**, each explicitly excluding the other channel's rows — prevents TV network names from showing up in Digital's Partner dropdown (TV's `Raw_Partner` is actually populated, unlike other Digital columns that are empty on TV rows).
- **Partial degradation for incomplete files**: if the file only has columns for one of the two modes, the app stays usable for the mode that has everything it needs, with a persistent notice about the unavailable mode.
- **`compute_backfill` generalized** to any `(target_field, weight_field)` pair, not just `Media_Cost`/`Impressions`.
- **Conditional number formatting** (`format_field_value`): `$` with 2 decimals for `Media_Cost`, integer with thousands separator for `Impressions` — previously everything was forced to display as currency.

---

## 5. Design decisions made along the way (including this addendum's, not documented before)

1. **`Channel` promoted to a Digital critical column**, not just TV's — needed so Digital can exclude TV rows from its own calculations, exactly as the addendum explicitly requested (section 1).
2. **Pure logic functions, no internal `st.session_state` reads**: `find_lock_conflict_field(mode, filters, queue, log)` and `build_preview(..., queue, log)` receive the queue and log as explicit arguments instead of reading them from `st.session_state` — same principle already applied earlier to `build_excel_bytes`/`build_log_csv_bytes` (underscore-prefixed parameters). This lets the lock and the full validation be tested with synthetic data, without needing a real Streamlit session.
3. **Subset identity (`subset_key`) defined as a tuple, not a dict** — `("DIGITAL", month, campaign, partner, pcode, ccd_jtbd, audience, breakout)` or `("TV", month, brand, audience, daypart, network)`. Reused both for queue items (which store `filters` as a nested dict) and log entries (which have the same filter fields flattened directly into the dict, thanks to the `**f` spread already in use) — no need to add a new state structure for the lock, exactly as the addendum requested ("Don't create a new state structure").
4. **Log column rename: `Suma_Media_Cost_Antes`/`Suma_Media_Cost_Despues` → `Sum_Before`/`Sum_After`** — **deliberate deviation** from the addendum's literal wording ("the rest of the log fields stay the same"). Done because keeping the literal `Media_Cost`-named column in a log row where `Impressions` was actually backfilled would be a misleading column name (it would show an impressions total under a "Media_Cost" header). The `Field` column already indicates which field it was, so the generic name is more correct. **Worth confirming with the user whether they'd rather revert to the original literal names.**
5. **`FIELD_PAIRS` as a simple reciprocity dict** (`{"Media_Cost": "Impressions", "Impressions": "Media_Cost"}`) instead of scattered conditional logic — the field the user didn't choose in TV is automatically inferred as the weight field.
6. **Dynamic TV target label** (`f"Target {target_field}"`) read from the "Field to backfill" selector within the same `st.form`, since within a single `script run` widget values are available sequentially even though the form doesn't trigger a rerun until submit. Accepted side effect: if the user changes the field selector without submitting the form yet, the target label can visually lag until the next rerun — this doesn't affect the value actually used on submit, which is always read fresh.
7. **Missing-column warnings per mode are persistent** (derived from `st.session_state.missing_columns` on every render), not one-off messages — it was found that showing the notice right before an immediate `st.rerun()` made it vanish before the user could see it.
8. **The lock is not revalidated when running the queue** (unlike "0 rows"/"0 weight", which are revalidated) — explicit decision: since the lock already prevents two queue items from pointing at the same subset from the moment of preview, there's no way for the queue to have an internal conflict by execution time.

*(Decisions inherited from the previous version — queue with unique IDs, `st.form` to avoid per-filter reruns, export caching via `data_version`, preview reduced to scorecards — remain unchanged; see the "What didn't change" section below.)*

---

## 6. Current `st.session_state` structure

| Key | Type | What it stores |
|---|---|---|
| `df` | `pd.DataFrame \| None` | Full working DataFrame (Digital + TV mixed together, as it comes in the file), plus `Month_Label` and `Parent_PCODE`. Mutated in place on both `Media_Cost` and `Impressions`, depending on which field each executed item backfilled. |
| `log` | `list[dict]` | **Applied** backfills (not previews). Each entry: `Timestamp`, `Mode` (new), `Field` (new), the filters used (flattened, different keys depending on `Mode`), `Target_Value`, `Rows_Affected`, `Sum_Before` (renamed, see §5.4), `Sum_After` (renamed). |
| `filename` | `str \| None` | Unchanged. |
| `sheet_name` | `str \| None` | Unchanged. |
| `preview_result` | `dict \| None` | Now includes `mode`, `target_field`, `weight_field` in addition to `filters`, `target_value`, `rows`, `current_sum`, `delta`. |
| `queue` | `list[dict]` | Each item now includes `mode`, `target_field`, `weight_field` in addition to `qid`, `filters`, `target_value`, `rows`, `current_sum`, `delta`. |
| `queue_next_id` | `int` | Unchanged. |
| `last_execution_results` | `list[dict] \| None` | Each entry now includes `Mode`/`Field` in addition to the filters and `Status`. |
| `output_basename` | `str \| None` | Unchanged. |
| `dropdown_options` | `dict \| None` | **Shape changed**: previously a flat dict of lists; now `{"DIGITAL": dict \| None, "TV": dict \| None}`. `DIGITAL` has `months, campaigns, partners, pcodes, ccd_jtbds, audiences, breakouts`; `TV` has `months, brands, audiences, dayparts, networks`. A `None` value in either key means that mode is unavailable for the loaded file (missing critical columns). |
| `missing_columns` | `dict` | **New.** `{"DIGITAL": [...], "TV": [...]}` — critical columns found missing when the sheet was loaded, per mode. Empty lists if the mode is complete. Used both to decide whether `dropdown_options[mode]` is `None` and to show the persistent warning messages. |
| `data_version` | `int` | Mechanism unchanged — incremented if "Run full queue" applied at least one item, regardless of whether it was Digital or TV. |
| `mode_selector` | `str` | **New** (widget key, not initialized in `init_state`). Lives implicitly in `st.session_state` because the mode selector's `st.radio` uses `key="mode_selector"`. Explicitly forced to `"Digital"` when loading a new file and in `reset_all()`. |

**Note on session handling**: unchanged — everything in memory, no disk persistence, reloading the browser resets everything.

---

## 7. Cached functions — mechanism unchanged

`build_excel_bytes(_df, version, sheet_name)` and `build_log_csv_bytes(_log, version)` did not change: they're still pure functions cached with `st.cache_data`, with `_df`/`_log` excluded from hashing (underscore prefix) and `version` (`data_version`) as the only real invalidation key. The fact that `df` can now have both `Media_Cost` and `Impressions` modified doesn't affect the mechanism — any real mutation still bumps `data_version` exactly as before.

---

## 8. What did NOT change from the previous version (queue + caching)

- The queue mechanism (unique `qid`, "Remove from queue" by `qid`, "Clear queue", "Run full queue" with individual skipping of invalid items) keeps working exactly the same — it was only generalized to operate over `mode`/`target_field` instead of always assuming Digital/Media_Cost. Verified with tests that mix Digital and TV items in the same queue.
- The `st.form` that avoids reruns on filter changes stays the same, now there are two forms (one per mode) instead of one.
- Export caching via `data_version` stays the same.
- The preview reduced to 4 scorecards stays the same (now with a dynamic label/format based on the field).
- Only the `target_field` columns corresponding to each executed item are modified — never `Delivered Spend`, `Even Allocated Spend`, `GRPs`, or any other column outside of `Media_Cost`/`Impressions`.
- The downloaded file still contains only the working sheet, without helper columns.
- No disk/database persistence, no authentication, no SharePoint integration.
- Single-value filters per dimension (no support for lists of values).

---

## 9. Language (new, 2026-07-19)

The entire codebase (`app.py`, comments, variable/dict names), all UI-facing text (labels, buttons, error/warning/success messages, table headers), and all documentation in this project are now in English. This includes internal filter dict keys that were previously Spanish words used both as display labels and as dict keys throughout the code (`"Mes"` → `"Month"`, `"Campaña"` → `"Campaign"`, `"Modo"` → `"Mode"`, `"Campo"` → `"Field"`) — renamed consistently everywhere they're referenced: `subset_key`, `find_lock_conflict_field`, the queue table, the execution loop, and the log entries.

---

## 10. Post-launch bug fixes

Four issues reported after real usage, all fixed with accompanying regression tests:

1. **`TypeError: Invalid value '...' for dtype 'int64'` when running the queue.** If the source sheet has no blank cells in `Impressions` or `Media_Cost`, pandas reads that column as `int64`. A proportional backfill always produces fractional values, and pandas refuses to write a float64 result into an int64 column in place. Fix: `prepare_dataframe` now forces both `Media_Cost` and `Impressions` to `float64` right after loading (`pd.to_numeric(...).astype("float64")`), regardless of what pandas inferred from the source file. Covered by a regression test that builds an all-integer sheet and confirms the exact assignment that used to crash now succeeds.
2. **Impressions must always be whole numbers.** `resolve_new_values` now rounds any backfilled `Impressions` result via `round_preserving_sum` — a largest-remainder (Hare-Niemeyer) allocation that rounds every row to an integer while keeping the total exactly equal to the target, rather than naive per-row rounding (which can drift the sum off by a few units). This applies uniformly regardless of mode, though in practice only TV can ever target `Impressions`. Digital is unaffected (it never backfills `Impressions`).
3. **App title changed** from "Weighted Media Cost Backfill" to **"Weighted Backfills App"** (both `st.set_page_config(page_title=...)` and the on-page `st.title(...)`).
4. **Month dropdown now sorts chronologically, not alphabetically.** `sorted(["April 2026", "December 2026", "February 2026"])` previously put them in that exact (wrong) order because it sorted the label strings. New helper `sorted_month_labels(df)` sorts by the underlying `Date` column instead (one row per unique `Month_Label`, ordered by date), used by both `build_dropdown_options_digital` and `build_dropdown_options_tv`.
5. **"Preview" required two clicks after switching "Field to backfill".** Root cause: the TV target `st.number_input`'s label is dynamic (`f"Target {target_field}"`, i.e. "Target Media_Cost" vs "Target Impressions"), and without an explicit `key=`, Streamlit derives a widget's identity partly from its label — so relabeling it makes Streamlit treat it as a brand-new widget and silently reset it to 0. Fix: added a stable `key="tv_target_value"` so the widget's identity (and stored value) no longer depends on which field is selected. Verified with an AppTest regression that types a value under "Media_Cost", switches to "Impressions" *without submitting*, and confirms the value survives and the very first "Preview" click uses it correctly. (The widget now uses `key=f"target_value_{target_field}"`, which keeps that property while giving each field its own remembered value.)

---

## 11. Digital sub-types: Social / Reserve / Programmatic (2026-08-05)

### The rule

A Digital row's sub-type is derived from a token inside `Package_Placement_Name`, plus — for the `UNE` ones — whether the partner is a social platform:

| Sub-type | Rule |
|---|---|
| **Programmatic** | `Package_Placement_Name` contains `UUT` |
| **Social** | contains `UNE` **and** `Raw_Partner` is a social platform |
| **Reserve** | contains `UNE` **and** it is not |
| *Unclassified* | neither token — cannot be backfilled through the app |

Social platforms are `FACEBOOK.COM`, `TIKTOK`, `REDDIT.COM`, `PINTEREST`, `SNAP INC FK SNAPCHAT`, plus **any partner whose name contains `X CORP`**.

Computed once per file in `prepare_dataframe` into a `Digital_Subtype` column (rather than re-running `str.contains` on every filter operation), and never applied to TV rows.

### Validated against the real file before building

| Bucket | Rows |
|---|---|
| Programmatic | 85,182 |
| Social | 54,468 |
| Reserve | 8,033 |
| Unclassified | 312 |

The partition is clean: **0 rows contain both tokens**, so rule ordering never actually matters on this data (the code still resolves `UUT` first, deliberately). The 312 unclassified rows are the bonus / added-value lines whose placement is free text — e.g. `Awareness AV BONUS $4,608.39` — the same population already flagged in the structure analysis. The app shows a persistent `st.info` naming that count so it is never silently ignored.

**The `X CORP` match is case-insensitive on purpose.** The real file contains both `CNBC.COM - X CORP` and `FOXSPORTS.COM - X Corp`; a case-sensitive match would have silently classified the latter's 61 rows as Reserve. There is a dedicated test for exactly this row.

### Filters per sub-type

| Sub-type | Filters |
|---|---|
| **Social** (by Package) | Month, Campaign, Partner, Package, CCD JTBD, Audience, Breakout — the last three are required, per spec |
| **Social** (by Placement) | Month, Campaign, Partner, Placement — exactly one placement, nothing else needed |
| **Reserve** | Month, Campaign, **Partner\***, **Audience\*** |
| **Programmatic** | Month, Campaign, Partner, **Channel\***, Package, **CCD JTBD\***, **Audience\*** |

`*` = accepts one, several, or all values (`st.multiselect`, defaulting to everything selected so "all" costs no clicks). Everything else is exactly one value.

Social's Package-vs-Placement choice is a radio **outside** the filter form, so switching it re-renders the right filter set immediately.

All of this is declarative: `FILTER_SPECS` maps each sub-type to a list of `(label, dataframe column, options key, is_multi)` tuples, and a single generic `compute_subset` walks that list — `isinstance(value, (list, tuple, set))` decides between `.isin(...)` and `==`. Adding or moving a filter is a one-line change to the spec, with no new subset function.

---

## 12. The six operations (2026-08-05)

The old behavior — Digital always writes `Media_Cost` weighted by `Impressions` — is now just one of six choices. The analyst picks a **field** and then an **operation**:

| Operation | Writes | Needs a target? | What it does |
|---|---|---|---|
| `MC_WEIGHTED` | Media_Cost | yes | Splits the target proportionally to each row's Impressions *(the original behavior)* |
| `MC_EVEN` | Media_Cost | yes | `target / number of rows` on every row |
| `MC_COPY_RECONCILED` | Media_Cost | **no** | Copies `Delivered Spend (Reconciled)` row by row |
| `MC_COPY_PRISMA` | Media_Cost | **no** | Copies `Delivered Spend (Prisma)` row by row |
| `IMPR_WEIGHTED` | Impressions | yes | Splits the target proportionally to the **current Impressions**, so the daily delivery shape is preserved; falls back to weighting by `Media_Cost` only when the subset has no impressions at all |
| `IMPR_COPY_WPU` | Impressions | **no** | Copies `Weighted Planned Units` row by row |

Declared in one `OPERATIONS` dict (field, label, `needs_target`, optional `source` column, help text) and dispatched by a single pure function, `compute_new_values(subset, operation_id, target_value, mode)`, returning `(Series, None)` or `(None, error)`. Both the preview and the queue execution call it, so they can never drift apart.

**Design notes:**

- **Copy operations take no target at all.** `needs_target: False` drives both the validation (the positive-target check is skipped entirely) and the UI (the number input is not rendered; a caption names the source column instead). `target_value` is stored as `None` and shown as `—`.
- **A missing source column fails cleanly**, both in the UI (the operation is refused with a message before the form renders) and in `compute_new_values`, rather than raising a `KeyError`.
- **Impressions are always whole numbers**, on every path: `IMPR_WEIGHTED` goes through `round_preserving_sum` (largest-remainder, exact-sum) and `IMPR_COPY_WPU` rounds the copied values.
- **`IMPR_WEIGHTED` weighting by `Impressions` itself is intentional**, not a bug: re-scaling a column by its own proportions is exactly what "keep the daily trend, change the total" means.
- **The operations apply to TV as well as Digital.** The spec only described them under Digital, but TV already had a Media_Cost/Impressions choice and the operations are field-specific, not mode-specific — restricting them to Digital would have been an arbitrary inconsistency. This is additive: nothing about TV's previous behavior changed. **Worth confirming this is the intended scope.**

---

## 12b. Target = 0 unified across modes (2026-08-05, same-day follow-up)

**Reported bug**: Digital rejected a target of `0` outright — `build_preview` threw "The target must be a positive number." before the subset was even computed, regardless of the operation. Reported specifically for zeroing out a miscoded cost, which is a legitimate backfill (the target isn't unknown or missing, it's deliberately zero).

**Fix, two call sites:**

1. `build_preview`'s sign check no longer branches on `mode`. Both Digital and TV now accept `target_value >= 0` and reject only genuinely negative values, with the same message ("The target must be a number greater than or equal to 0.") either way. This is the one that was actually blocking the report — `MC_EVEN`/`MC_WEIGHTED` at target 0 is mathematically fine on any valid (non-zero) weight basis; nothing downstream needed the mode restriction, it was purely this upfront gate.
2. `compute_new_values`'s zero-weight-basis exception — previously "TV-only: a zero target across a zero weight basis is unambiguous, Digital keeps the strict original behavior" (§12) — now applies regardless of mode: `if target_value == 0: new_values = 0 for every row`, no `mode == "TV"` check. Splitting zero across zero delivery is exactly as unambiguous for Digital as it is for TV; the original mode restriction was a deliberate scope decision in the TV addendum, not a mathematical necessity, and kept it strict only because Digital's zero-basis case hadn't come up yet. **This is a deviation from that documented decision — worth confirming it's wanted**, though it only ever changes behavior in the narrow case where a Digital subset already has 0 total Impressions/Media_Cost *and* the analyst explicitly types a target of 0 (previously blocked with "0 total X. There is no basis to distribute", now succeeds with all rows set to 0).

A non-zero target on a zero weight basis is still blocked on both modes — only the target-is-exactly-0 case changed.

---

## 13. The lock, rebuilt on row overlap (2026-08-05)

The previous lock compared *filter values* (`subset_key`) to decide whether two backfills targeted the same subset. Multi-value filters break that: selecting partners `[A, B]` and then `[B, C]` produces two different keys but overlapping rows, so the old check would have waved it through and **silently written to B's rows twice**.

`find_lock_conflict(indices, queue, applied)` now compares the actual dataframe row indices and reports a conflict on any intersection. Queue items carry their `indices`; applied backfills are recorded in a new `st.session_state.applied_indices` list (kept separate from `log` so the exported CSV stays clean). This is strictly stronger than the old rule — it still catches every case the key comparison did, plus partial overlaps — and it removed `subset_key` entirely.

The error message names the offender (`#3 (Digital · Reserve · …), still queued` / `…, already applied in this session`) instead of just saying the subset is taken.

### What the preview / queue / log now record

Every one of them carries the operation, per the spec's "el nivel de detalle del backfill debe contener cuál fue el tipo de operación":

- **Preview** — a heading with the full operation label (`Digital · Social · Media_Cost · Weighted by impressions`) above the four scorecards. The third card is now **Resulting sum** rather than "Target sum", since for a copy operation there is no target to show but there is always a result.
- **Queue table** — `Mode`, `Type` (sub-type), `Field`, `Operation` columns, then one column per filter that item actually used (multi-value selections render as `3 selected` past three values), then Current Sum / Target / Resulting Sum / Delta.
- **Execution results and the CSV log** — same `Mode` / `Type` / `Field` / `Operation` columns, with `Target_Value` left blank for copy operations.

### Session state changes

| Key | Change |
|---|---|
| `applied_indices` | **New.** `[{"label": str, "indices": [int, ...]}]` — the applied side of the lock. |
| `queue` items | Now carry `subtype`, `operation`, `operation_label`, `resulting_sum` and `indices`; `weight_field` is gone (the operation implies it). |
| `preview_result` | Same additions. |
| `dropdown_options` | **Shape changed** from `{"DIGITAL": ..., "TV": ...}` to one entry per Digital sub-type plus `"TV"`: `{"Social": {...}, "Reserve": {...}, "Programmatic": {...}, "TV": {...}}`. |
| `mode_selector` | Joined by `subtype_selector`, `social_select_by`, `field_selector` and `operation_selector_{field}` widget keys. |

### UI ordering, and one deviation

The screen is now three numbered steps: **1 · What are you backfilling?** (mode → sub-type → package/placement), **2 · How should the values be calculated?** (field → operation), **3 · Which rows?** (the filter form, the target when the operation needs one, and Preview).

The spec put the operation choice *after* the filters. It sits before them instead, because the operation decides whether a target input is rendered at all, and Streamlit only re-renders a form's contents on submit — putting the operation inside the form would reproduce the exact "click Preview twice" bug fixed in §10.5.

---

## 14. Cascading, numbered filters (2026-08-05)

### What changed

Filters are now **numbered** (`1 · Month`, `2 · Campaign`, …) and **cascade**: each one only offers the values that still exist given everything chosen above it, and everything below the first unanswered filter is locked behind a disabled `Pick <parent> first` placeholder.

Concretely, the case that prompted it: on Social, `CCD JTBD` / `Audience` / `Breakout` show nothing at all until a Package is picked, and then only that package's real values. On the production file that takes Audience from **46 options down to 2**, and CCD JTBD from 4 to 1.

The cascade applies to every sub-type and to TV, not just Social — the numbering implies an order, so honouring it everywhere is the consistent read.

### `st.form` had to go

This is a real trade-off, and it reverses an earlier decision. A `st.form` deliberately suppresses reruns until submit — which is exactly what made the app feel fast when picking filters, but also means a filter's options **cannot** react to a sibling's value. Cascading and `st.form` are mutually exclusive.

Measured before switching, on the real 149,993-row file: recomputing the whole cascade costs **58–115 ms**, well inside normal Streamlit rerun overhead. The expensive work (`compute_subset`, the operation math) still only happens on the Preview click, so the per-keystroke cost is just re-deriving option lists.

Two consequences handled explicitly:

- **Single-selects now start unanswered** (`index=None` + placeholder) rather than defaulting to the first option. Without that there is nothing to gate on — a selectbox always has a value, so the dependent filters could never be "waiting for a package".
- **A preview can go stale**, since there is no submit boundary any more. `selection_signature(...)` records exactly what a preview was computed for, and the preview is discarded the moment any filter, operation or target moves — so a set of scorecards can never sit next to filters it doesn't describe.

### Keeping widget state consistent as options change

Two helpers run before each cascading widget renders, because Streamlit raises if a widget's stored value isn't in its own option list:

- `_forget_stale_single(key, choices)` — drops a stored single-select value that the parent change has made unavailable, so the widget comes back unselected instead of erroring.
- `_reset_multi_on_new_choices(key, choices)` — a multi-value filter means "all of what's available", so when the available set itself changes it re-selects everything rather than keeping the old intersection (which would silently leave newly-valid values unselected).

Widget keys are `filters_{mode}_{subtype}_{select_by}_{options_key}` (previously prefixed `filters_form_`), and locked placeholders add a `_locked` suffix so they never collide with the real widget's stored value.

### Testing

`test_apptest_flow.py` proves the narrowing is genuine rather than incidental: the fixture deliberately contains a **second** Social package (`PKG_SOCIAL2`) on the same partner carrying a JTBD and an audience the first one doesn't have. The test asserts CCD JTBD drops `Consideration` and Audience drops `AudZ` once `PKG_SOCIAL` is chosen — without that second package, narrowing by package would shrink nothing and the test would pass while proving nothing. It also checks the numbered labels, that filters start unanswered, and that a locked filter offers an empty option list.

---

## 15. M.E.R.I.T APP: multi-tool shell + Data Caveats Generator (2026-08-05)

### Why

The request was explicit: turn this from a single-purpose app into a shell that can host several tools, starting with a home menu, the existing backfill tool renamed "RROI Manual Backfill", and a new "Data Caveats Generator" ported from a standalone script (`generar_data_caveats.py`, previously run by hand against a local folder).

### The shell (`app.py`)

`app.py` no longer contains any backfill logic — it's now ~50 lines: `st.set_page_config` (called exactly once, here, since Streamlit requires that), a `TOOLS` registry (`{key: {"label", "description", "render"}}`), and a home screen (`render_home()`) with the M.E.R.I.T title, subtitle, and one bordered `st.container` per tool with an "Open" button. `st.session_state.active_tool` (`None` / `"backfill"` / `"caveats"`) decides whether `render_home()` or `TOOLS[active_tool]["render"]()` runs. Adding a future tool means writing its module and adding one entry to `TOOLS` — no other change to `app.py`.

**Why a plain `session_state` flag instead of Streamlit's native multipage app support** (`st.navigation`/`st.Page`, or a `pages/` folder): native multipage puts each tool behind its own URL and a persistent sidebar nav, which is a reasonable alternative, but the ask was specifically a **menu you land on and choose from** — closer to a landing page than a permanently-visible nav rail. The session-state-flag approach was already proven (it's exactly how the backfill tool's own upload → work screen transition already worked), so it was reused rather than introducing a second navigation paradigm into the same app.

**Each tool is a separate module with its own `init_state()`/`render()`** (`tools/rroi_backfill.py`, `tools/data_caveats.py`). This was a deliberate namespacing decision: the backfill tool already used simple session-state keys (`df`, `log`, `queue`, …); rather than risk collisions as more tools get added, the Data Caveats tool's keys are all prefixed `caveats_` (`caveats_data`, `caveats_results`, …) from day one. The backfill tool's existing keys were **not** renamed — no functional need (nothing else uses those names) and renaming them would have been pure churn against a large, already-tested module.

Every tool renders a **"← Back to menu"** button at the very top of `render()`, which sets `active_tool = None` and reruns.

### Data Caveats Generator (`tools/data_caveats.py`)

Detects **"Null impressions"** (cost present, impressions never, for a placement's whole month) and **"Null cost"** (the reverse) at placement-month grain, and writes one Data Caveat Log per brand from the corporate template — same detection rules and same output shape as the original script, entirely in-memory (no disk I/O) so it runs as a normal upload/download Streamlit flow instead of a folder-watching script.

**What ported unchanged (business logic):**
- The two caveat patterns and their exact English labels (`Null value check` / `Leave as is - data is correct` / `Null impressions` / `Null cost`) — these are **fixed values from the template's own dropdown lists** (columns A and I, `Type` and `Month`), so they cannot be translated or reworded without breaking the template's data validation.
- Detection at **placement-month** grain (`GROUP_KEYS = [Brand, Category, Channel, Campaign, Site, Placement, Retailer, Period]`), with the two detection modes (`month` = only the month total; `row` = also flags an individual day matching the pattern even if the month total is complete).
- The validation pass (`validate()`): coarse-grain channels (no Campaign/Placement, e.g. TV), masked single-day gaps, zero-total-but-active (GRPs/Video Views) lines, negative values, and brands with zero caveat lines.
- `find_log_table` / the template-writing mechanics: locate the table via `ws.tables`, clear the template's example rows, write styled cells, shrink the table's `ref` and the two dropdown validations' (`A`, `I`) row range to match the actual row count — including the **empty-caveats case**, where the table still needs exactly 1 formatted (blank) row rather than 0, since an Excel table can't have zero data rows.
- `build_sheet_name`'s 31-character Excel tab-name limit handling (drop category first, then trim the brand — never trim the INC#).
- `BRAND_NAME_OVERRIDES = {"TRESemme": "Tresemme"}` — cosmetic-only, output file name/tab, never affects detection. Kept hardcoded, consistent with how the backfill tool already hardcodes this same client's domain rules (the Social/Reserve/Programmatic taxonomy).

**What changed for the in-app flow:**
- **Folder scanning → file uploader.** `st.file_uploader(..., accept_multiple_files=True)` replaces `glob.glob(INPUT_FOLDER)`. Each file is read via `.getvalue()` (bytes) and cached with `@st.cache_data` keyed on those bytes, so re-running "Generate" after only changing a setting doesn't re-parse a 10 MB file.
- **Template file → bundled default + optional override.** `tools/data_caveats_template.xlsx` (a copy of the corporate template, 25 KB, small enough to ship in the repo) is used unless the user uploads their own via an "Advanced" expander — mirrors the self-service default pattern already used elsewhere in this project (bundle a working default, let power users override it).
- **`SHEET_SELECTION` simplified to a fixed "last sheet with all required columns."** The original script supported 4 selection strategies plus per-file overrides; every real sample file observed puts the working data on the right-most tab (a blank "Sheet1" often comes first), so the other strategies were dropped as unnecessary configuration surface for v1. If a real file needs a different rule, this is the first place to extend.
- **`(year, month)` config tuples → a detected-months picker.** Instead of typing `RANGE_START`/`RANGE_END`, the app reads the periods actually present across the uploaded files and offers them as an `st.select_slider` (or, with only one month present, a caption — a slider needs two distinct points). Removes an entire class of typo ("configured a range that doesn't match the file") that the original script could silently produce.
- **Console + summary.txt → on-screen results + a ZIP.** Every `log(...)` line, the per-issue console block, and the final `RESUMEN` table now render as Streamlit elements (`st.dataframe`, colored callouts by level). Since a web app has no output folder, the per-brand `.xlsx` files, the validation report (`.xlsx`, if validation ran), and the summary (`.txt`) are bundled into one ZIP via a single `st.download_button`, rather than several download buttons or a virtual folder.
- **Levels translated to English.** The original script's `AVISO` level is now `WARNING` (`ERROR`/`FLAG`/`INFO` were already English) — purely an internal label used for sorting/coloring issues, never written into the output template.
- **Dropped for v1** (scope cuts, not fixed to be impossible): per-file `SHEET_OVERRIDES`; `OVERWRITE_EXISTING` (meaningless without a persisted output folder); separate `WRITE_VALIDATION_REPORT`/`WRITE_SUMMARY_FILE` toggles (both are now unconditionally included in the ZIP whenever validation runs, since there's no per-file disk-write cost to gate in a web flow); the console `VALIDATION_PREVIEW_ROWS` truncation (an `st.dataframe` scrolls natively, so the full detail table is shown instead of a fixed preview).

### Testing

`test_data_caveats.py` exercises the pure pipeline directly against small synthetic delivery files built in-memory (`pd.DataFrame(...).to_excel(BytesIO())`, matching the real RROI column schema): reading/cleaning, the two caveat patterns at month grain, the masked-day case under both detection modes, all five `validate()` findings in isolation, `filter_by_range` actually filtering, and — importantly — **a real write against the actual bundled template**, asserting the output table's `ref` shrinks to exactly the right number of rows (including the zero-caveats case) and that the written cells match. `test_apptest_home.py` covers the shell itself (home menu renders both tools, each opens and returns home) and the Data Caveats settings → generate → download flow through real widgets, seeding `caveats_data` with the output of the real `read_delivery_file` (upload simulation isn't possible with `AppTest`, same limitation noted throughout this project) rather than a hand-built stand-in for its shape.

### Documentation

`USER_GUIDE.md` (RROI Manual Backfill) now opens with a pointer to the home menu and to the Data Caveats guide. A new `DATA_CAVEATS_GUIDE.md`, matching the same non-technical style, covers the second tool end to end — kept as a **separate file** rather than folded into `USER_GUIDE.md`, since the two tools have unrelated audiences/workflows and the code itself is already split the same way (one module per tool).

---

## 16. TV Data Standardization (2026-08-14)

### What it does

Normalizes the TV team's raw spot-level files: `AFFID DATE` converted to a real date, networks and dayparts mapped to consistent names, impressions scaled to real units. The user uploads one file per product and chooses how the standardized result comes back — separate files per product, one consolidated file, or both.

Built from `PROMPT - Logica Proceso TV Data.md` plus the real `CONSOLIDATED TV DATA.xlsx` the spec describes. Everything below was verified against that workbook rather than taken on trust.

### Scope correction, same day

The spec describes a full 6-step process — normalize the TV files, then reconcile them against the reporting platform's export and propose corrections (phantom spend, missing impressions), ending in a 6-sheet workbook (`DATA`/`RECONCILIATION`/`TRACKER`/`CLEAN`/`VERIFICATION`/`LOG`). The tool was first built to that full spec, with the UI requiring **two** uploads (TV files + platform export).

The user's actual intent was narrower: just the normalization step (spec §3), exposed as a simple upload → standardize → download tool, with the platform export out of scope for now ("Sin pedir el export de la plataforma... La reconciliación/corrección contra la plataforma queda fuera de esta herramienta por ahora"). They also wanted the output format (separate / consolidated / both) chosen by the user before generating, not always all three.

`render()` was rewritten accordingly: single file uploader, no export/sheet selection, an output-format radio, one download. The reconciliation pipeline below (§ "Proposal rules" onward) is **fully implemented and tested but not wired into the UI** — `read_platform_export`, `build_reconciliation`, `propose_corrections`, `judgment_calls`, `apply_corrections`, `build_output_workbook` all remain in `tools/tv_standardization.py` as library functions, kept because they're real-data-verified and the user's own framing was "por ahora," not "never." A future phase could wire them back in behind, e.g., an "advanced" toggle.

### The central transformation: AFFID DATE → real date

`AFFID DATE` arrives as `MMMDD` text (`JUN28`) with **no year**. The platform files spots by the affidavit date (when the station certified the spot aired), not the planned `DATE`, so this conversion is what makes the two sides line up at all.

`effective_date(affid, planned)`:
- inherits the year from the planned `DATE`;
- if the result lands more than ~45 days from the plan, nudges the year ±1 — an affidavit of `JAN02` against a `12/30/26` plan is 2027, not 2026. This doesn't occur in the current dataset (all Apr–Jun 2026) but is covered and tested;
- falls back to the planned date when the affidavit is blank (**244 of 4,819 rows**, arriving as `' '` — a space, not an empty cell);
- falls back rather than raising on anything unparseable (`JUN99`, garbage text).

**Measured on the real files**, aggregating by (Product, Network, day): the affidavit date gives **1,042 exact spend matches of 1,080 keys (96.5%)** versus **39.9%** using the planned date. The spec claimed 1,042 of 1,091 (95.5%) — the numerator matches exactly; the denominator differs slightly because this implementation counts keys present on both sides (an inner join) rather than the union. The claim itself is confirmed, and the test asserts the 1,042.

### Ingestion notes

- **The header row is found by scanning column A for `ESTIMATE NAME`**, never hardcoded to row 33 — the report preamble's length isn't guaranteed. Tested with the header at a different offset.
- **Columns are read by position, not name.** `NETWORK` appears twice (positions 3 and 9) so name-based lookup is ambiguous. The header is still checked, and a mismatch produces a *warning* rather than a failure, since position is the reliable signal.
- **`ASSIGNED GROSS`/`ASSIGNED NET` vs `GROSS ASSIGNED`/`NET ASSIGNED`** — both spellings accepted (the VIC re-pull uses the flipped order).
- **Product code comes from the filename's leading token**, since it isn't a column in the file.
- **Impressions arrive in thousands** and are multiplied by 1,000.
- **An unmapped network or estimate name raises**, naming the offending value. This is deliberate and matches the spec: passing the raw value through would make the row silently vanish from the join and unbalance the reconciliation.

### Re-pull handling — a deliberate divergence from the workbook

When two files cover the same product, `resolve_repulls` keeps the **more recent** pull (by the date token in the filename) and logs the discard. The consolidated workbook kept the *older* VIC file, leaving every VIC row with `ACTIMP = 0` even though the re-pull had real audience data; the spec calls that a slip. Verified: the newer VIC pull carries **4,334,900** actual impressions where the older had 0.

The real-file regression deliberately reconstructs the workbook's own choice (older VIC) when checking §10's control figures, so the comparison is like-for-like, while the tool itself defaults to the newer pull.

### Proposal rules, and where they stop (implemented, not yet wired into the UI)

The spec lists `TRACKER` as an *output* ("acciones propuestas"), so the tool derives the corrections rather than asking for them. Both rules require the platform to be reporting **nothing** where TV is unambiguous — that is what makes them safe to automate:

| Action | Rule | Key |
|---|---|---|
| **Zero out spend** | platform cost > 0, platform impressions = 0, **and** TV impressions = 0 | Product × Month × Network (no daypart) |
| **Backfill impressions** | TV impressions > 0 **and** platform impressions = 0, with rows present in the export | Product × Month × Daypart × Network |

**Measured against the analyst's actual corrections in the workbook:**

- Zero-out proposes **exactly** the 12 groups that were zeroed — no false positives, no misses.
- Backfill proposes **16 of the 20** that were filled, with **no false positives**.

The 4 it doesn't propose are cases where **both** sides report impressions but disagree (830,000 vs 780,000; 414,450 vs 262,900; 36,000 vs 42,000; and the VIC group whose TV total was 0 only because of the older pull). No threshold separates these from ordinary measurement drift — at a >2% relative gap there are 28 such groups and the analyst corrected only 3 of them. **So the tool does not guess.** `judgment_calls()` surfaces them in a dedicated, sorted table, and an "add a correction manually" form (cascading dropdowns sourced from the reconciliation, so a correction can never target rows that don't exist) lets the analyst add what they decide is warranted.

An earlier, looser draft of these rules proposed 137 corrections touching 2,235 rows against the analyst's 20/435 — worth recording as the reason the rules are deliberately conservative.

### Spec §10 control figures — verified, with one correction to the spec

Every ingestion figure reproduces exactly: **4,819 DATA rows** (DHC 567 / TRE 4,240 / VIC 12), month split **APR 1,555 / MAY 1,915 / JUN 1,349**, **244** blank affidavits, export **2,475 rows** spanning 2026-04-06 to 2026-06-30, and only `Media_Cost`/`Impressions` ever modified.

**Two of the spec's correction figures are wrong**, and the tests assert the measured values instead:

- §10 claims zero-out changed **85 rows in 13 groups**. The workbook's own `7.16 CLEAN` shows **82 rows in 12 groups**. The difference is `TRE / Jun / ASPIRE`: §6.1 lists it among the applied entries, but its 3 rows were **already at $0**, so zeroing them changed nothing. The spec counts a no-op as a modification. (It already uses a "no-op (ya estaba en 0)" label for BEIN SPORTS SPANISH and CBS TV NETWORK — ASPIRE belongs in that bucket too.)
- §6.2's table lists **20 backfill groups**, but the tracker sheet only contains 19 with a computed row count. The 20th — `VIC / Jun / Women Cable / BLACK ENTERTAINMENT` — was applied directly to `7.16 CLEAN` with no tracker entry at all. The impressions figure of **435 rows / 20 groups** is correct; the tracker just doesn't account for one of them.

Also confirmed from the workbook: `VIC / Jun / BLACK ENTERTAINMENT`'s **zero-out was never applied** — it's still carrying $666,065.10, exactly as §6.1 flags. Under this tool's rules it isn't proposed either (the platform reports 4,334,600 impressions there, so it isn't phantom spend), which happens to agree with what the analyst actually did rather than with what the tracker said.

### Configuration

`tools/tv_mappings.json` holds `estimate_names` (raw → clean + daypart), `networks` (57 entries, raw → platform `Network_Name`), `daypart_to_platform` (bridging `WOMEN'S CABLE` → `Women Cable`), and `product_brands`. JSON rather than YAML to avoid adding a dependency; the spec asked for external config, not a specific format. Extracted programmatically from the workbook's `MAPPING` sheet, so it matches byte-for-byte.

### Testing

`test_tv_standardization.py` runs in two parts, unchanged by the scope correction since it tests functions, not `render()`. Part 1 (12 checks, always runs) covers the pure logic on synthetic data: the date conversion including both year-boundary directions and every fallback, re-pull resolution, `'NULL'` coercion, impression precedence, reconciliation deltas being *undefined* rather than `#DIV/0!`, corrections touching only the two metric columns, the no-matching-rows and already-zero reports, an unmapped network raising, a shifted header row, and the flipped `NET ASSIGNED` spelling. Part 2 is the real-file regression described above; it skips cleanly when the TV files aren't present.

`test_apptest_home.py` TEST 5 exercises the new `render()` end to end through real Streamlit widgets: seeds `tv_data` the way "Standardize" would have left it (using the real `read_tv_file` on a file shaped like a real TV pull, not a hand-built stand-in), asserts the platform-export uploader is gone, checks the output-format radio's three options, clicks **Generate**, and confirms a non-empty file lands in `tv_output` with a real download button.

### Not carried over

The spec's `RUN_VALIDATION` / `STOP_ON_VALIDATION_ISSUES` / `WRITE_*` toggles have no analogue: in the library-level reconciliation code the reconciliation table *is* the validation and `build_output_workbook` always assembles all six sheets in one call, but neither is reachable from the UI right now (see "Scope correction" above). `AFFID TIME` is parsed and preserved in `DATA` but unused, exactly as in the manual process.

## 17. Data Caveats: a second source schema, LCA (2026-08-26)

### The bug

`read_delivery_file` was hardcoded to one column schema (the RROI raw-file schema `COLS`). Files from `C:\Users\Cristian.Barbosa\Downloads\OneDrive_1_8-26-2026` — a different delivery pull the user called "LCA" — failed with "No sheet has all the expected columns", because `pick_sheet` requires every `REQUIRED_COLS` entry, and `Media_Cost` (the required cost column) doesn't exist in these files at all: it's spelled `Media Cost`, with a space.

### What LCA actually is

Verified against all 6 real files in that folder (DMC, Dove, Nexxus, Shea, Tresemme, Vaseline — one sheet each, header identical across all 6): same underlying fields as RROI, plus 9 extra columns the caveat detection has no use for (`Partnership`, `Campaign`, `Product_Line`, `Subcategory`, `Format`, `Audience`, `Daypart`, `Breakout`, `Clicks`), and exactly two column names differing by a space instead of an underscore: `Media Cost` (→ `Media_Cost`) and `Video Views` (→ `Video_Views`). Every other required column (`Channel`, `Date`, `Brand`, `Category`, `Prisma_Campaign_Secondary`, `Raw_Partner`, `Package_Placement_Name`, `Impressions`) matches RROI exactly.

### The fix

`COLS` (the RROI→canonical-field mapping) was split into `COLS_RROI` and `COLS_LCA = {**COLS_RROI, "cost": "Media Cost", "video_views": "Video Views"}`, registered in `FORMAT_PROFILES = {"RROI": {...}, "LCA": {...}}`. `pick_sheet` and `read_delivery_file` now take the column map as a parameter instead of reading the old module-level `COLS`/`REQUIRED_COLS` globals; `required_cols(cols_map)` replaces the old fixed `REQUIRED_COLS` set. `render()` gained a "Delivery file format" radio (RROI / LCA) shown above the uploader, applied to every file in that "Read files" click — the file-summaries table now also shows which format was used per file.

One format applies per batch. If a user has both RROI and LCA files to process together, the workflow is: read + generate the first batch, **Start over**, switch the selector, read + generate the second — there's no per-file format override, since every real file seen from either source is internally consistent.

### Testing

`test_data_caveats.py` TEST H builds a synthetic LCA-shaped file (all 21 columns, spaced `Media Cost` / `Video Views`) and checks: `read_delivery_file(..., format_key="LCA")` correctly maps `Media Cost` → `Cost`; the same bytes under `format_key="RROI"` raise `ValueError` naming the missing `Media_Cost` column (proving the two schemas are genuinely distinct, not silently permissive). Also spot-checked directly against the real `DMC Hair Care LCA Data_'23-Q1'26.xlsx` (9,420 rows, 0 dropped, 2 caveat lines found) — not part of the automated suite since the file isn't in the repo, but confirms the fix against real data end to end.

## 18. Merit Inspect + Merit Deliver integrated from merit_V1 (2026-08-27)

### What was integrated

Two tools built by a teammate in a parallel repo (`C:\Users\Cristian.Barbosa\Documents\merit_V1\merit_app`) were brought into this app, along with his home-menu layout:

- **Merit Inspect** (`tools/merit_inspect.py`, 1,660 lines) — monthly QA pass: a rules engine (~17 rules: negative cost, placeholder placements, audience-code mismatches, Twitter/X partner, Knorr Product_Line and Breakout rules, TV audience, channel/type conflicts…), a spend-vs-delivery analysis per unit, a channel/month summary, an offline-presence view, a reconciliation table and a brand/category/channel coverage checklist, all written into one formatted Excel report.
- **Merit Deliver** (`tools/merit_deliver.py`, 583 lines) — builds the 18-column client-facing deliverable, reconciles its totals against the source on Channel × Product_Line, scans for live formulas, classifies visual duplicates (`TRUE DUP` / `REVIEW` / `EXPECTED` by whether the differentiating columns are benign), and ships deliverable + backup + QA as one zip.
- **`tools/config/audience_codes.csv`** (586 codes) — Merit Inspect's audience catalog, resolved relative to the module (`os.path.dirname(__file__)/config/`), with an in-app uploader override. Verified it loads from the new location after the copy.

Both modules were copied **unchanged**: they already followed this project's conventions (`init_state()`/`reset_all()`, a `← Back to menu` button at the top of `render()`, and their own `inspect_`/`deliver_`-prefixed session-state keys), so nothing needed adapting to avoid collisions.

### The home menu (his layout, adopted wholesale)

`app.py` now uses his version: five numbered, icon-prefixed cards laid out `CARDS_PER_ROW = 3` (so 3 + 2), a CSS block that hides Streamlit's header anchor icons and forces equal-height cards (`min-height: 260px`, flex with the button anchored at the bottom regardless of description length), and the title spelled **`M.E.R.I.T. APP`** — with the trailing period, which is also now the `page_title`. Order: 1 Merit Inspect, 2 TV Data Standardization, 3 RROI Manual Backfill, 4 Merit Deliver, 5 Data Caveats Generator.

The `TOOLS` registry gained an `"icon"` key per tool. Adding a tool is still just one entry.

### Divergences resolved during the merge

His repo was forked from this one before the last two changes here, so his copies of the shared modules were older. **This repo's versions were kept** for everything shared (`rroi_backfill.py`, `tv_standardization.py`, `tv_mappings.json` were byte-identical anyway; `data_caveats.py` was not):

- Kept here, absent from his: the **LCA source-schema selector** (§17) and the **multi-category handling** (a brand spanning Hair Care + Skin Care keeps both rather than being standardized to the first).
- **Present in his, adopted in §19 below:** the `Month` column as a real date rather than a `"Jun"` string. Initially held back over a suspected conflict with the template's dropdown; that turned out to be backwards (see §19).

### Testing

`test_apptest_home.py` was updated for the new home (5 `Open` buttons, asserted **in order** by key, and the `M.E.R.I.T. APP` spelling with its period) and gained **TEST 6**, which mounts Merit Inspect and Merit Deliver, asserting each renders without exception, shows its title, exposes its own keyed back button and file uploader, and starts with its own `<tool>_results` state key at `None` — i.e. that the two namespaces don't collide.

Both tools were also exercised end to end outside the UI against synthetic data matching their real schemas: Merit Deliver builds an 18-column deliverable preserving every row, reconciles clean, classifies a planted benign-differentiated duplicate as `EXPECTED`, and writes real QA/deliverable bytes; Merit Inspect fires the expected rules on planted violations (negative cost, placeholder placement) alongside the Knorr and TV rules, and writes a complete Excel report.

### Data loss noted the same day

Six `test_*.py` files, the untracked `test_tv_standardization.py`, and the whole `C:\Users\Cristian.Barbosa\Documents\TV Files` folder disappeared from disk between the previous session and this one (cause unknown — the source modules were untouched). The six tracked test files were restored from `HEAD` via `git show HEAD:<file> > <file>`, then this session's lost additions were rewritten: TEST H (LCA) and a new TEST I (multi-category) in `test_data_caveats.py`, and TEST 5 (the TV normalize→generate→download flow) in `test_apptest_home.py`.

**`test_tv_standardization.py` was recovered by the user from the Recycle Bin** the next day (403 lines, unmodified). Re-verified: all 12 synthetic checks pass, and the real-file regression skips itself cleanly as designed, since `C:\Users\Cristian.Barbosa\Documents\TV Files` is still missing. That regression stays dormant until those files are restored — the skip is by design, not a silent pass.

Everything of value is back. The lesson stands: `test_tv_standardization.py`, `tv_standardization.py`, `tv_mappings.json` and `TV_STANDARDIZATION_GUIDE.md` are all still **untracked** — committing them is what makes the next accident recoverable from git rather than from the Recycle Bin.

## 19. Data Caveats: the Month column carries its year (2026-08-27)

### The change

`classify()` now writes `Month` as a **real date** — the month's first day, via `caveats["Period"].dt.to_timestamp()` — instead of a 3-letter abbreviation (`.dt.strftime("%b")`). `write_brand_file_bytes` gives that cell the number format `MONTH_CELL_FORMAT = "mmm-yy"`, so the log still *reads* as `Jun-26`. Originally a teammate's change in the `merit_V1` fork (§18), adopted here after verifying it against the template.

### Why the earlier hesitation was wrong

The change was initially held back on the theory that column I's data-validation dropdown listed month **names**, and that writing a date would trip it. Inspecting the template settled it the other way: the dropdown's source range `$Y$3:$Y$13` contains **`datetime` values**, not strings.

So the template was always designed to hold dates in that column — the `"Jun"` string was the mismatch, and this change removes it rather than introducing one.

### Why it matters beyond tidiness

A bare `"Jun"` cannot distinguish `Jun'25` from `Jun'26`. That is not hypothetical for the current inputs: the real LCA files span **Aug 2023 → Mar 2026**, so any log covering more than twelve months had genuinely ambiguous rows. Confirmed end to end on the real `DMC Hair Care LCA Data_'23-Q1'26.xlsx`: both caveat lines now write `datetime(2026, 3, 1)` with format `mmm-yy`.

Two details worth knowing:

- The dropdown's source only enumerates 2025 months (and skips June — `Y8` jumps from May to July). A 2026 date therefore isn't among the listed options. This is harmless here: list validation only fires on *manual* entry in Excel, not on values written programmatically by openpyxl, and `allowBlank` is true. Worth mentioning to whoever maintains the template, since the same gap affects anyone picking from the dropdown by hand.
- `_detail()` (the validation report) keeps its own `out["Period"].astype(str)` rendering and is unaffected.

### Testing

`test_data_caveats.py` TEST B's assertion moved from `{"Jun"}` to `{pd.Timestamp("2026-06-01")}`, and a new **TEST J** covers the point directly: two rows for the same placement in Jun 2025 and Jun 2026 must stay **two distinct caveat lines**, and the cells written into the real bundled template must be genuine `datetime` values carrying format `mmm-yy` — asserting the type, the format string and both years, so a regression to a text month fails loudly.
