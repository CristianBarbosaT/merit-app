import pandas as pd
from app import (
    compute_subset_digital, compute_subset_tv, compute_backfill, prepare_dataframe,
    PCODE_PATTERN, build_dropdown_options_digital, build_dropdown_options_tv,
    subset_key, find_lock_conflict_field, build_preview, resolve_new_values,
    round_preserving_sum, sorted_month_labels,
)

# ---------------------------------------------------------------------------
# Digital: same rows as before, now with an explicit Channel column
# ---------------------------------------------------------------------------
digital_rows = [
    # Date, Channel, Prisma_Campaign_Secondary, Raw_Partner, Package Name, CCD JTBD, Audience, Breakout, Impressions, Media_Cost
    ("2026-06-01", "Digital Social", "CampA_Secondary", "PINTEREST", "P3GHJCX_UNE_NEX_038", "Awareness", "Crystallizer Queen", "Brand Say", 1000, None),
    ("2026-06-02", "Digital Social", "CampA_Secondary", "PINTEREST", "P3GHJCX_UNE_NEX_038", "Awareness", "Crystallizer Queen", "Brand Say", 3000, 5.0),
    ("2026-06-03", "Digital Social", "CampA_Secondary", "PINTEREST", "P3GHJCX_UNE_NEX_038", "Awareness", "Crystallizer Queen", "Brand Say", 0, 2.0),  # 0 impressions -> weight 0
    ("2026-06-03", "Digital Social", "CampA_Secondary", "PINTEREST", "P3GHJCX_UNE_NEX_038", "Awareness", "Crystallizer Queen", "Brand Say", None, 2.0),  # NULL impressions -> weight 0
    # different breakout, should NOT be included
    ("2026-06-04", "Digital Social", "CampA_Secondary", "PINTEREST", "P3GHJCX_UNE_NEX_038", "Awareness", "Crystallizer Queen", "Other Say", 5000, 1.0),
    # garbage row - short/non-matching package code
    ("2026-06-05", "Digital Social", None, None, "ADJ-NOTE-MANUAL", None, None, None, None, 999.0),
    # a TV row with the SAME Raw_Partner-like value coincidentally populated, to prove
    # it never leaks into the Digital subset even if other fields happened to match
    ("2026-06-01", "TV", "CampA_Secondary", "PINTEREST", "P3GHJCX_UNE_NEX_038", "Awareness", "Crystallizer Queen", "Brand Say", 999999, 999999.0),
]

digital_df = pd.DataFrame(digital_rows, columns=[
    "Date", "Channel", "Prisma_Campaign_Secondary", "Raw_Partner", "Package Name",
    "CCD JTBD", "Audience", "Breakout", "Impressions", "Media_Cost",
])
digital_df = prepare_dataframe(digital_df)

subset = compute_subset_digital(
    digital_df, "June 2026", "CampA_Secondary", "PINTEREST", "P3GHJCX",
    "Awareness", "Crystallizer Queen", "Brand Say",
)
assert len(subset) == 4, f"expected 4 rows in subset (TV row must be excluded), got {len(subset)}"

target = 74330.85
new_cost, total_impressions = compute_backfill(subset, target, "Media_Cost", "Impressions")
assert total_impressions == 4000, f"expected total_impressions 4000, got {total_impressions}"

total_new = new_cost.sum()
assert abs(total_new - target) < 0.01, f"sum mismatch: {total_new} vs {target}"

zero_rows = new_cost[subset["Impressions"].fillna(0) == 0]
assert (zero_rows == 0).all(), "zero-impression rows should get 0 cost"

first_row_idx = subset.index[0]
assert new_cost.loc[first_row_idx] > 0, "row with impressions but null Media_Cost should receive backfilled cost"

assert PCODE_PATTERN.match("P3GHJCX")
assert not PCODE_PATTERN.match("ADJ-NOTE-MANUAL"[:7])

result, total = compute_backfill(
    subset[subset["Impressions"].fillna(0) == 0], target, "Media_Cost", "Impressions"
)
assert result is None, "should return None when total_impressions == 0"

# dropdown options for Digital must exclude the TV row entirely
digital_options = build_dropdown_options_digital(digital_df)
assert "PINTEREST" in digital_options["partners"]
assert list(digital_options["partners"]) == ["PINTEREST"], (
    f"TV's Raw_Partner value should not leak into Digital's partner dropdown, got {digital_options['partners']}"
)

print("DIGITAL TESTS PASSED")

# ---------------------------------------------------------------------------
# TV: reference example from addendum_tv_backfill.md section 4
# ---------------------------------------------------------------------------
tv_rows = [
    # Date, Channel, Brand, Audience, Daypart, Network_Name, Impressions, Media_Cost
    ("2026-06-01", "TV", "NEXXUS", "General", "Primetime", "COMCAST CORPORATION", 71200, 672.35),
    ("2026-06-02", "TV", "NEXXUS", "General", "Primetime", "COMCAST CORPORATION", 53050, None),
    ("2026-06-03", "TV", "NEXXUS", "General", "Primetime", "COMCAST CORPORATION", 356000, 2866.20),
    ("2026-06-04", "TV", "NEXXUS", "General", "Primetime", "COMCAST CORPORATION", 221750, None),
    ("2026-06-05", "TV", "NEXXUS", "General", "Primetime", "COMCAST CORPORATION", 545200, 5045.60),
    ("2026-06-06", "TV", "NEXXUS", "General", "Primetime", "COMCAST CORPORATION", 71200, 671.50),
    # a Digital row that should never leak into the TV subset
    ("2026-06-01", "Digital Social", "NEXXUS", "General", "Primetime", "COMCAST CORPORATION", 1, 1.0),
]
tv_df = pd.DataFrame(tv_rows, columns=[
    "Date", "Channel", "Brand", "Audience", "Daypart", "Network_Name", "Impressions", "Media_Cost",
])
tv_df = prepare_dataframe(tv_df)

tv_subset = compute_subset_tv(tv_df, "June 2026", "NEXXUS", "General", "Primetime", "COMCAST CORPORATION")
assert len(tv_subset) == 6, f"expected 6 TV rows (Digital row excluded), got {len(tv_subset)}"

# Backfill Impressions, weighted by Media_Cost, target = 800,000
new_impressions, total_media_cost = compute_backfill(tv_subset, 800000, "Impressions", "Media_Cost")
assert new_impressions is not None
assert abs(new_impressions.sum() - 800000) < 0.01, f"sum mismatch: {new_impressions.sum()} vs 800000"

# exact expected values from addendum_tv_backfill.md section 4
expected_impressions = [58113.69, 0, 247736.25, 0, 436109.84, 58040.22]
for got, exp in zip(new_impressions.tolist(), expected_impressions):
    assert abs(got - exp) < 1, f"Impressions backfill mismatch: got {got}, expected {exp}"

# Backfill Media_Cost, weighted by Impressions, target = 12,000 (same formula Digital already uses)
new_media_cost, total_impr = compute_backfill(tv_subset, 12000, "Media_Cost", "Impressions")
assert new_media_cost is not None
assert abs(new_media_cost.sum() - 12000) < 0.01, f"sum mismatch: {new_media_cost.sum()} vs 12000"

expected_media_cost = [648.06, 482.86, 3240.29, 2018.36, 4962.38, 648.06]
for got, exp in zip(new_media_cost.tolist(), expected_media_cost):
    assert abs(got - exp) < 1, f"Media_Cost backfill mismatch: got {got}, expected {exp}"

print("TV TESTS PASSED (matches addendum reference example within tolerance)")

# ---------------------------------------------------------------------------
# TV-only rule: Impressions all 0 (or NULL) + target 0 -> Media_Cost backfilled to 0,
# instead of being blocked like a normal "no weight basis" case.
# ---------------------------------------------------------------------------
zero_impressions_rows = [
    ("2026-06-01", "TV", "NEXXUS", "General", "Primetime", "GHOST NETWORK", 0, 45.0),
    ("2026-06-02", "TV", "NEXXUS", "General", "Primetime", "GHOST NETWORK", None, 12.0),
    ("2026-06-03", "TV", "NEXXUS", "General", "Primetime", "GHOST NETWORK", 0, None),
]
zero_df = pd.DataFrame(zero_impressions_rows, columns=[
    "Date", "Channel", "Brand", "Audience", "Daypart", "Network_Name", "Impressions", "Media_Cost",
])
zero_df = prepare_dataframe(zero_df)
zero_subset = compute_subset_tv(zero_df, "June 2026", "NEXXUS", "General", "Primetime", "GHOST NETWORK")
assert len(zero_subset) == 3

# plain compute_backfill still refuses (no change to the generic math helper)
raw_result, raw_total = compute_backfill(zero_subset, 0, "Media_Cost", "Impressions")
assert raw_result is None and raw_total == 0

# TV + target 0 -> resolve_new_values allows it, everything becomes 0
tv_zero_values = resolve_new_values("TV", 0, "Media_Cost", "Impressions", zero_subset)
assert tv_zero_values is not None, "TV should be able to backfill Media_Cost to 0 when Impressions are all 0"
assert (tv_zero_values == 0).all()
assert tv_zero_values.sum() == 0

# Digital must NOT get this exception, even with target 0 (same underlying situation)
digital_zero_values = resolve_new_values("DIGITAL", 0, "Media_Cost", "Impressions", zero_subset)
assert digital_zero_values is None, "Digital must keep the strict original behavior"

# TV with a NON-zero target and 0 impressions is still correctly blocked (only target==0 is special-cased)
tv_nonzero_target = resolve_new_values("TV", 500, "Media_Cost", "Impressions", zero_subset)
assert tv_nonzero_target is None, "a non-zero target with 0 impressions must still be blocked, even for TV"

# end-to-end through build_preview: target 0 with 0 impressions succeeds for TV
tv_zero_filters = {
    "Month": "June 2026", "Brand": "NEXXUS", "Audience": "General",
    "Daypart": "Primetime", "Network_Name": "GHOST NETWORK",
}
preview_zero, error_zero = build_preview(
    mode="TV", filters=tv_zero_filters, target_value=0, target_field="Media_Cost",
    weight_field="Impressions", subset=zero_subset, queue=[], log=[],
)
assert error_zero is None and preview_zero is not None
assert preview_zero["rows"] == 3
assert preview_zero["delta"] == -57.0  # target 0 - current sum (45+12+0) = -57

# same scenario through build_preview for Digital must still be rejected
# (digital_filters isn't defined yet at this point in the file, use an inline stand-in)
_digital_filters_stub = {
    "Month": "June 2026", "Campaign": "CampA_Secondary", "Partner": "PINTEREST",
    "Package (PCODE)": "P3GHJCX", "CCD JTBD": "Awareness", "Audience": "Crystallizer Queen",
    "Breakout": "Brand Say",
}
preview_zero_digital, error_zero_digital = build_preview(
    mode="DIGITAL", filters=_digital_filters_stub, target_value=0, target_field="Media_Cost",
    weight_field="Impressions", subset=zero_subset, queue=[], log=[],
)
assert preview_zero_digital is None
assert error_zero_digital == "The target must be a positive number."

print("TV ZERO-TARGET RULE TESTS PASSED")

# ---------------------------------------------------------------------------
# Lock: one backfill per subset per session (queue + log), independent of field
# ---------------------------------------------------------------------------
digital_filters = {
    "Month": "June 2026", "Campaign": "CampA_Secondary", "Partner": "PINTEREST",
    "Package (PCODE)": "P3GHJCX", "CCD JTBD": "Awareness", "Audience": "Crystallizer Queen",
    "Breakout": "Brand Say",
}
tv_filters = {
    "Month": "June 2026", "Brand": "NEXXUS", "Audience": "General",
    "Daypart": "Primetime", "Network_Name": "COMCAST CORPORATION",
}

# free subset: no conflict
assert find_lock_conflict_field("DIGITAL", digital_filters, queue=[], log=[]) is None
assert find_lock_conflict_field("TV", tv_filters, queue=[], log=[]) is None

# occupied via queue
queue_with_digital_item = [
    {"mode": "DIGITAL", "filters": digital_filters, "target_field": "Media_Cost"},
]
assert find_lock_conflict_field("DIGITAL", digital_filters, queue=queue_with_digital_item, log=[]) == "Media_Cost"
# a different subset (different breakout) must remain free
other_filters = {**digital_filters, "Breakout": "Other Say"}
assert find_lock_conflict_field("DIGITAL", other_filters, queue=queue_with_digital_item, log=[]) is None

# occupied via log (flat dict, as actually stored by the app)
log_with_tv_entry = [
    {"Mode": "TV", "Field": "Impressions", **tv_filters, "Target_Value": 800000},
]
assert find_lock_conflict_field("TV", tv_filters, queue=[], log=log_with_tv_entry) == "Impressions"
# locked regardless of which field is requested next on the SAME TV subset
assert find_lock_conflict_field("TV", tv_filters, queue=[], log=log_with_tv_entry) is not None

# TV and Digital subsets never collide with each other even with overlapping values
assert find_lock_conflict_field("DIGITAL", digital_filters, queue=[], log=log_with_tv_entry) is None

print("LOCK TESTS PASSED")

# ---------------------------------------------------------------------------
# build_preview: end-to-end validation ordering (target>0, rows>0, lock, weight>0)
# ---------------------------------------------------------------------------
preview, error = build_preview(
    mode="DIGITAL", filters=digital_filters, target_value=target, target_field="Media_Cost",
    weight_field="Impressions", subset=subset, queue=[], log=[],
)
assert error is None and preview is not None
assert preview["mode"] == "DIGITAL"
assert preview["rows"] == 4

# blocked by lock even though everything else about it is valid
preview2, error2 = build_preview(
    mode="DIGITAL", filters=digital_filters, target_value=target, target_field="Media_Cost",
    weight_field="Impressions", subset=subset, queue=queue_with_digital_item, log=[],
)
assert preview2 is None and error2 is not None and "already has a" in error2

print("BUILD_PREVIEW TESTS PASSED")

# ---------------------------------------------------------------------------
# Queue removal logic (mirrors the qid-based filtering used in app.py)
# ---------------------------------------------------------------------------
queue = [
    {"qid": 1, "filters": {"Month": "June 2026"}, "target_value": 100.0},
    {"qid": 2, "filters": {"Month": "July 2026"}, "target_value": 200.0},
    {"qid": 3, "filters": {"Month": "August 2026"}, "target_value": 300.0},
]

qid_to_remove = 2
queue = [item for item in queue if item["qid"] != qid_to_remove]
assert [item["qid"] for item in queue] == [1, 3], f"expected [1, 3], got {[i['qid'] for i in queue]}"
assert len(queue) == 2

qid_to_remove = 1
queue = [item for item in queue if item["qid"] != qid_to_remove]
assert [item["qid"] for item in queue] == [3]

qid_to_remove = 3
queue = [item for item in queue if item["qid"] != qid_to_remove]
assert queue == []

queue = [{"qid": 5, "filters": {}, "target_value": 1.0}]
before = len(queue)
queue = [item for item in queue if item["qid"] != 999]
assert len(queue) == before, "removing a non-existent qid should not change the queue"

queue = [
    {"qid": 10, "filters": {"Month": "June 2026"}, "target_value": 50.0},
    {"qid": 11, "filters": {"Month": "June 2026"}, "target_value": 50.0},
]
queue = [item for item in queue if item["qid"] != 10]
assert [item["qid"] for item in queue] == [11], "only the targeted qid should be removed, not both duplicates"

print("QUEUE REMOVAL TESTS PASSED")

# ---------------------------------------------------------------------------
# Regression: source sheet with NO blank cells in Impressions/Media_Cost gets read
# by pandas as int64, and writing fractional backfill results into an int64 column
# used to raise "TypeError: Invalid value '...' for dtype 'int64'". prepare_dataframe
# must force both columns to float64 so this can never happen.
# ---------------------------------------------------------------------------
int_rows = [
    ("2026-06-01", "TV", "NEXXUS", "General", "Primetime", "COMCAST CORPORATION", 71200, 672),
    ("2026-06-02", "TV", "NEXXUS", "General", "Primetime", "COMCAST CORPORATION", 53050, 480),
    ("2026-06-03", "TV", "NEXXUS", "General", "Primetime", "COMCAST CORPORATION", 356000, 3240),
]
int_df = pd.DataFrame(int_rows, columns=[
    "Date", "Channel", "Brand", "Audience", "Daypart", "Network_Name", "Impressions", "Media_Cost",
])
# confirm the premise: with no NaNs, pandas infers integer dtypes for both columns
assert int_df["Impressions"].dtype.kind == "i"
assert int_df["Media_Cost"].dtype.kind == "i"

int_df = prepare_dataframe(int_df)
assert int_df["Impressions"].dtype == "float64", "prepare_dataframe must force Impressions to float64"
assert int_df["Media_Cost"].dtype == "float64", "prepare_dataframe must force Media_Cost to float64"

int_subset = compute_subset_tv(int_df, "June 2026", "NEXXUS", "General", "Primetime", "COMCAST CORPORATION")
new_impressions = resolve_new_values("TV", 800000, "Impressions", "Media_Cost", int_subset)
# this exact assignment is what previously raised TypeError against an int64 column
# (still float64-typed even though every value is now a whole number, see rounding below)
int_df.loc[int_subset.index, "Impressions"] = new_impressions
assert int_df.loc[int_subset.index, "Impressions"].sum() == 800000

print("INT64-COLUMN REGRESSION TEST PASSED")

# ---------------------------------------------------------------------------
# Impressions are always rounded to whole numbers, sum-preserving (largest-remainder
# method), regardless of mode.
# ---------------------------------------------------------------------------
fractional = pd.Series([58113.699, 247736.251, 436109.845, 58040.205])
rounded = round_preserving_sum(fractional, 800000)
assert (rounded == rounded.round()).all(), "every value must be a whole number"
assert rounded.sum() == 800000, f"rounded values must still sum exactly to the target, got {rounded.sum()}"

# a case designed so naive per-row rounding would NOT preserve the sum, to prove the
# largest-remainder allocation is actually doing something (not a no-op)
tricky = pd.Series([1.5, 1.5, 1.5, 1.5])  # naive round() would give 2+2+2+2=8, but target is 6
tricky_rounded = round_preserving_sum(tricky, 6)
assert tricky_rounded.sum() == 6
assert set(tricky_rounded.tolist()) == {1.0, 2.0}, f"expected a mix of 1s and 2s, got {tricky_rounded.tolist()}"

# through the real Impressions backfill path (TV, weighted by Media_Cost)
new_impressions_2 = resolve_new_values("TV", 800000, "Impressions", "Media_Cost", tv_subset)
assert (new_impressions_2 == new_impressions_2.round()).all(), "backfilled Impressions must be whole numbers"
assert new_impressions_2.sum() == 800000

print("IMPRESSIONS ROUNDING TESTS PASSED")

# ---------------------------------------------------------------------------
# Months must sort chronologically, not alphabetically ("April" < "December" < "February"
# alphabetically, which is wrong order).
# ---------------------------------------------------------------------------
month_rows = [
    ("2026-12-01", "TV", "NEXXUS", "General", "Primetime", "COMCAST CORPORATION", 100, 10.0),
    ("2026-02-01", "TV", "NEXXUS", "General", "Primetime", "COMCAST CORPORATION", 100, 10.0),
    ("2026-04-01", "TV", "NEXXUS", "General", "Primetime", "COMCAST CORPORATION", 100, 10.0),
]
month_df = pd.DataFrame(month_rows, columns=[
    "Date", "Channel", "Brand", "Audience", "Daypart", "Network_Name", "Impressions", "Media_Cost",
])
month_df = prepare_dataframe(month_df)
assert sorted_month_labels(month_df) == ["February 2026", "April 2026", "December 2026"], (
    f"expected chronological order, got {sorted_month_labels(month_df)}"
)

tv_month_options = build_dropdown_options_tv(month_df)
assert tv_month_options["months"] == ["February 2026", "April 2026", "December 2026"]

print("MONTH SORTING TESTS PASSED")

print("ALL TESTS PASSED")
