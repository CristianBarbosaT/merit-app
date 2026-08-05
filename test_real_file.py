"""Runs the real 150k-row workbook through the same functions the app uses, to confirm
the sub-type taxonomy and every operation behave on production data (the synthetic tests
elsewhere only prove the logic in isolation).

Skips itself cleanly if the file isn't on this machine.
"""
import os

import pandas as pd

from tools.rroi_backfill import (
    prepare_dataframe, build_dropdown_options_subtype, compute_subset_digital,
    compute_new_values, build_preview, find_lock_conflict, FILTER_SPECS,
    SUBTYPE_SOCIAL, SUBTYPE_RESERVE, SUBTYPE_PROGRAMMATIC, SUBTYPE_UNCLASSIFIED,
    SOCIAL_SELECT_BY_PACKAGE, OPERATIONS,
)

PATH = r"C:\Users\Cristian.Barbosa\Documents\Proyecto app\B&W_RROI Data QA_April-June_Investment_V1.xlsx"

if not os.path.exists(PATH):
    print("SKIPPED — the real workbook is not on this machine")
    raise SystemExit(0)

print("Loading the real workbook...")
raw = pd.read_excel(PATH, sheet_name="Raw", engine="openpyxl")
df = prepare_dataframe(raw)
print(f"  {len(df)} rows")

# ---------------------------------------------------------------------------
# 1. The taxonomy partitions the real data the way the analysis said it would
# ---------------------------------------------------------------------------
counts = df["Digital_Subtype"].value_counts()
digital_total = int((df["Channel"] != "TV").sum())
tv_total = int((df["Channel"] == "TV").sum())
print("\nSub-type split:")
for k, v in counts.items():
    print(f"  {k:16} {v:7}")

assert counts[SUBTYPE_PROGRAMMATIC] == 85182, counts[SUBTYPE_PROGRAMMATIC]
assert counts[SUBTYPE_SOCIAL] == 54468, counts[SUBTYPE_SOCIAL]
assert counts[SUBTYPE_RESERVE] == 8033, counts[SUBTYPE_RESERVE]
# unclassified = the 312 bonus/added-value Digital rows + every TV row
assert counts[SUBTYPE_UNCLASSIFIED] == 312 + tv_total, counts[SUBTYPE_UNCLASSIFIED]
classified = counts[SUBTYPE_PROGRAMMATIC] + counts[SUBTYPE_SOCIAL] + counts[SUBTYPE_RESERVE]
assert classified + 312 == digital_total, "every Digital row must land in exactly one bucket"

# no TV row ever gets a Digital sub-type
tv_rows = df[df["Channel"] == "TV"]
assert (tv_rows["Digital_Subtype"] == SUBTYPE_UNCLASSIFIED).all()

# the lowercase "X Corp" partner really is present, and really is Social
foxsports = df[df["Raw_Partner"] == "FOXSPORTS.COM - X Corp"]
assert len(foxsports) == 61, len(foxsports)
assert (foxsports["Digital_Subtype"] == SUBTYPE_SOCIAL).all(), (
    "the lowercase 'X Corp' partner must classify as Social"
)
print("\nTAXONOMY ON REAL DATA: PASSED")

# ---------------------------------------------------------------------------
# 2. Per-subtype dropdowns match the counts from the analysis
# ---------------------------------------------------------------------------
opts = {s: build_dropdown_options_subtype(df, s)
        for s in (SUBTYPE_SOCIAL, SUBTYPE_RESERVE, SUBTYPE_PROGRAMMATIC)}
print("\nDropdown sizes:")
for s, o in opts.items():
    print(f"  {s:14} campaigns={len(o['campaigns']):3} partners={len(o['partners']):3} "
          f"packages={len(o['packages']):4} placements={len(o['placements']):4} "
          f"channels={len(o['channels'])} audiences={len(o['audiences']):3}")

assert len(opts[SUBTYPE_SOCIAL]["partners"]) == 9
assert len(opts[SUBTYPE_RESERVE]["partners"]) == 12
assert len(opts[SUBTYPE_PROGRAMMATIC]["partners"]) == 7
assert len(opts[SUBTYPE_PROGRAMMATIC]["channels"]) == 5
# Social is the only bucket confined to a single channel
assert len(opts[SUBTYPE_SOCIAL]["channels"]) == 1
# no bucket's partner list leaks into another
assert not (set(opts[SUBTYPE_SOCIAL]["partners"]) & set(opts[SUBTYPE_RESERVE]["partners"]))
print("PER-SUBTYPE DROPDOWNS ON REAL DATA: PASSED")

# ---------------------------------------------------------------------------
# 3. Every operation runs on a real, non-trivial Social subset
# ---------------------------------------------------------------------------
social = df[df["Digital_Subtype"] == SUBTYPE_SOCIAL]
pkg_specs = FILTER_SPECS[SUBTYPE_SOCIAL][SOCIAL_SELECT_BY_PACKAGE]
# find the biggest real Social subset so the test exercises a meaningful number of rows
grp = social.groupby(
    ["Month_Label", "Prisma_Campaign_Secondary", "Raw_Partner", "Package Name",
     "CCD JTBD", "Audience", "Breakout"], observed=True
).size().sort_values(ascending=False)
key = grp.index[0]
filters = dict(zip(["Month", "Campaign", "Partner", "Package", "CCD JTBD", "Audience",
                    "Breakout"], key))
subset = compute_subset_digital(df, SUBTYPE_SOCIAL, filters, pkg_specs)
print(f"\nBiggest Social subset: {len(subset)} rows")
print(f"  campaign={key[1][:50]}  partner={key[2]}  audience={key[5]}")
assert len(subset) == grp.iloc[0]
assert (subset["Digital_Subtype"] == SUBTYPE_SOCIAL).all()

TARGET = 50000.0
for op_id, spec in OPERATIONS.items():
    target = TARGET if spec["needs_target"] else None
    values, error = compute_new_values(subset, op_id, target, "DIGITAL")
    assert error is None, f"{op_id} failed on real data: {error}"
    assert len(values) == len(subset)
    assert values.notna().all(), f"{op_id} produced NaNs"
    assert (values >= 0).all(), f"{op_id} produced negative values"
    if spec["needs_target"]:
        assert abs(values.sum() - TARGET) < 1.0, (
            f"{op_id} should total {TARGET}, got {values.sum()}"
        )
    if spec["field"] == "Impressions":
        assert (values == values.round()).all(), f"{op_id} must yield whole impressions"
    print(f"  {op_id:20} -> sum={values.sum():>18,.2f}  ok")
print("ALL OPERATIONS ON REAL DATA: PASSED")

# ---------------------------------------------------------------------------
# 4. Reserve with genuinely multi-valued filters, and the row-overlap lock
# ---------------------------------------------------------------------------
reserve_specs = FILTER_SPECS[SUBTYPE_RESERVE]
reserve = df[df["Digital_Subtype"] == SUBTYPE_RESERVE]
month = reserve["Month_Label"].dropna().iloc[0]
campaign = reserve[reserve["Month_Label"] == month]["Prisma_Campaign_Secondary"].iloc[0]
scoped = reserve[(reserve["Month_Label"] == month)
                 & (reserve["Prisma_Campaign_Secondary"] == campaign)]
all_partners = sorted(scoped["Raw_Partner"].dropna().unique())
all_audiences = sorted(scoped["Audience"].dropna().unique())
print(f"\nReserve scope: {month} / {campaign[:45]}")
print(f"  partners={all_partners}")

everything = compute_subset_digital(df, SUBTYPE_RESERVE, {
    "Month": month, "Campaign": campaign,
    "Partner": all_partners, "Audience": all_audiences,
}, reserve_specs)
assert len(everything) == len(scoped), (
    f"selecting every value must match the whole scope: {len(everything)} vs {len(scoped)}"
)

if len(all_partners) > 1:
    first_only = compute_subset_digital(df, SUBTYPE_RESERVE, {
        "Month": month, "Campaign": campaign,
        "Partner": all_partners[:1], "Audience": all_audiences,
    }, reserve_specs)
    assert 0 < len(first_only) < len(everything), "narrowing partners must shrink the subset"
    # the lock must catch the overlap between "all partners" and "just the first one"
    queued = [{"qid": 1, "operation_label": "test", "indices": list(everything.index)}]
    assert find_lock_conflict(first_only.index, queued, []) is not None, (
        "a subset contained in an already-queued one must be rejected"
    )
    print(f"  narrowed to 1 partner: {len(first_only)} rows (of {len(everything)}), "
          "overlap correctly detected")
print("MULTI-VALUE FILTERS + LOCK ON REAL DATA: PASSED")

# ---------------------------------------------------------------------------
# 5. A full preview -> apply round trip actually rewrites the real column
# ---------------------------------------------------------------------------
preview, error = build_preview("DIGITAL", SUBTYPE_SOCIAL, filters, "MC_WEIGHTED",
                               50000.0, subset, [], [])
assert error is None, error
before = df.loc[subset.index, "Media_Cost"].fillna(0).sum()
values, error = compute_new_values(subset, "MC_WEIGHTED", 50000.0, "DIGITAL")
assert error is None
df.loc[subset.index, "Media_Cost"] = values
after = df.loc[subset.index, "Media_Cost"].sum()
assert abs(after - 50000.0) < 0.01, after
assert abs(preview["current_sum"] - before) < 0.01
assert abs(preview["delta"] - (50000.0 - before)) < 0.01
print(f"\nApplied on real data: {len(subset)} rows, ${before:,.2f} -> ${after:,.2f}")
print("PREVIEW/APPLY ROUND TRIP ON REAL DATA: PASSED")

print("\nALL REAL-FILE TESTS PASSED")
