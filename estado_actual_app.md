# Current App State — Weighted Media Cost Backfill

> This document describes the implementation **as it stands today**, not the original spec (`instructivo_backfill_app.md`) nor the first queue/cache addendum. Where current behavior differs from those earlier versions, it is called out explicitly.
>
> Generated from the real code in `app.py` on 2026-07-19, after integrating `addendum_tv_backfill.md` (TV support + one-backfill-per-subset lock) and translating the entire codebase, UI, and documentation to English.

---

## 1. Project file structure

```
backfill-media-cost-app/
├── app.py                     # Full Streamlit app (everything lives in one script)
├── requirements.txt           # streamlit, pandas, openpyxl (no pinned versions)
├── .venv/                     # Local virtual environment (not versioned)
├── test_logic.py              # Pure tests: Digital/TV formula, lock, build_preview, remove-from-queue
├── test_apptest_flow.py       # End-to-end tests via streamlit.testing.v1.AppTest (Digital+TV, queue, lock, mixed execution)
├── test_apptest_cache.py      # Correctness/invalidation tests for the export cache
├── USER_GUIDE.md              # Non-technical user manual
└── estado_actual_app.md       # This document
```

**Relevant installed versions** (`.venv`): `streamlit==1.59.2`, `pandas==3.0.3`, `openpyxl==3.1.5`.

No git repository initialized in this folder. No `README.md` file.

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
5. **"Preview" required two clicks after switching "Field to backfill".** Root cause: the TV target `st.number_input`'s label is dynamic (`f"Target {target_field}"`, i.e. "Target Media_Cost" vs "Target Impressions"), and without an explicit `key=`, Streamlit derives a widget's identity partly from its label — so relabeling it makes Streamlit treat it as a brand-new widget and silently reset it to 0. Fix: added a stable `key="tv_target_value"` so the widget's identity (and stored value) no longer depends on which field is selected. Verified with an AppTest regression that types a value under "Media_Cost", switches to "Impressions" *without submitting*, and confirms the value survives and the very first "Preview" click uses it correctly.
