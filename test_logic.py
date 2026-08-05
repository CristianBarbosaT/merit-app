import pandas as pd

from tools.rroi_backfill import (
    OPERATIONS, OPERATIONS_BY_FIELD, SUBTYPE_SOCIAL, SUBTYPE_RESERVE, SUBTYPE_PROGRAMMATIC,
    SUBTYPE_UNCLASSIFIED, FILTER_SPECS, TV_FILTER_SPEC, SOCIAL_SELECT_BY_PACKAGE,
    SOCIAL_SELECT_BY_PLACEMENT, PCODE_PATTERN,
    prepare_dataframe, classify_digital_subtype, sorted_month_labels,
    build_dropdown_options_subtype, build_dropdown_options_tv,
    compute_subset_digital, compute_subset_tv, compute_backfill, compute_new_values,
    round_preserving_sum, find_lock_conflict, build_preview, operation_label,
    missing_critical_columns, CRITICAL_COLUMNS_DIGITAL, CRITICAL_COLUMNS_TV,
)

COLUMNS = [
    "Date", "Channel", "Prisma_Campaign_Secondary", "Raw_Partner", "Package Name",
    "Package_Placement_Name", "CCD JTBD", "Audience", "Breakout", "Brand", "Daypart",
    "Network_Name", "Impressions", "Media_Cost", "Delivered Spend (Reconciled)",
    "Delivered Spend (Prisma)", "Weighted Planned Units",
]


def make_df(rows):
    return prepare_dataframe(pd.DataFrame(rows, columns=COLUMNS))


def row(date="2026-06-01", channel="Digital Social", campaign="CampA", partner="PINTEREST",
        package="P3GHJCX_UNE_NEX_038", placement="P3GHJCX_UNE_NEX_038_PINTEREST_1x1",
        jtbd="Awareness", audience="AudA", breakout="Brand Say", brand=None, daypart=None,
        network=None, impressions=1000, media_cost=10.0, reconciled=0.0, prisma=0.0, wpu=0.0):
    return (date, channel, campaign, partner, package, placement, jtbd, audience, breakout,
            brand, daypart, network, impressions, media_cost, reconciled, prisma, wpu)


# ===========================================================================
# 1. Digital sub-type taxonomy
# ===========================================================================
taxonomy_rows = [
    # Social: placement has UNE + a social platform partner
    row(placement="P1_UNE_X_FACEBOOK", partner="FACEBOOK.COM"),
    row(placement="P2_UNE_X_TIKTOK", partner="TIKTOK"),
    row(placement="P3_UNE_X_PIN", partner="PINTEREST"),
    row(placement="P4_UNE_X_REDDIT", partner="REDDIT.COM"),
    row(placement="P5_UNE_X_SNAP", partner="SNAP INC FK SNAPCHAT"),
    # 'X CORP' is a CONTAINS match, and the real file mixes casing -- both must be Social
    row(placement="P6_UNE_X_XCORP", partner="CNBC.COM - X CORP"),
    row(placement="P7_UNE_X_XCORP", partner="FOXSPORTS.COM - X Corp"),
    # Reserve: placement has UNE but the partner is not a social platform
    row(placement="P8_UNE_X_AMAZON", partner="AMAZON.COM"),
    row(placement="P9_UNE_X_PEACOCK", partner="PEACOCK"),
    # Programmatic: placement has UUT (partner is irrelevant)
    row(placement="P10_UUT_X_YOUTUBE", partner="YOUTUBE.COM", channel="Digital Video"),
    row(placement="P11_UUT_X_TTD", partner="THE TRADE DESK INC", channel="Digital Display"),
    # a UUT placement on a social platform is still Programmatic (UUT wins)
    row(placement="P12_UUT_X_FB", partner="FACEBOOK.COM"),
    # Unclassified: neither token (bonus / added-value lines in the real file)
    row(placement="Awareness AV BONUS $4,608.39", partner="PINTEREST"),
    # TV rows are never given a Digital sub-type
    row(channel="TV", placement="TV_UNE_SOMETHING", partner="FACEBOOK.COM",
        brand="NEXXUS", daypart="Primetime", network="COMCAST"),
]
tax_df = make_df(taxonomy_rows)
got = tax_df["Digital_Subtype"].tolist()
expected = (
    [SUBTYPE_SOCIAL] * 7
    + [SUBTYPE_RESERVE] * 2
    + [SUBTYPE_PROGRAMMATIC] * 3
    + [SUBTYPE_UNCLASSIFIED]
    + [SUBTYPE_UNCLASSIFIED]
)
assert got == expected, f"taxonomy mismatch:\n got={got}\n exp={expected}"

# the lowercase "X Corp" row specifically -- a case-sensitive match would drop it
assert tax_df.loc[6, "Digital_Subtype"] == SUBTYPE_SOCIAL, (
    "'FOXSPORTS.COM - X Corp' (lowercase Corp) must still classify as Social"
)
# UUT beats UNE-on-social
assert tax_df.loc[11, "Digital_Subtype"] == SUBTYPE_PROGRAMMATIC
# a TV row is never Social even though its placement says UNE and partner is Facebook
assert tax_df.loc[13, "Digital_Subtype"] == SUBTYPE_UNCLASSIFIED

# classify_digital_subtype survives a file with no Package_Placement_Name column at all
no_placement = pd.DataFrame({"Channel": ["Digital Social"], "Raw_Partner": ["PINTEREST"]})
assert classify_digital_subtype(no_placement).tolist() == [SUBTYPE_UNCLASSIFIED]

print("TAXONOMY TESTS PASSED")

# ===========================================================================
# 2. Per-subtype dropdown options are scoped to that subtype only
# ===========================================================================
options_social = build_dropdown_options_subtype(tax_df, SUBTYPE_SOCIAL)
options_reserve = build_dropdown_options_subtype(tax_df, SUBTYPE_RESERVE)
options_prog = build_dropdown_options_subtype(tax_df, SUBTYPE_PROGRAMMATIC)

assert "AMAZON.COM" not in options_social["partners"], "Reserve partner leaked into Social"
assert "PINTEREST" in options_social["partners"]
assert set(options_reserve["partners"]) == {"AMAZON.COM", "PEACOCK"}
assert "FACEBOOK.COM" in options_prog["partners"], (
    "the UUT-on-Facebook row belongs to Programmatic, so its partner must appear there"
)
assert "AMAZON.COM" not in options_prog["partners"]
assert set(options_prog["channels"]) == {"Digital Social", "Digital Video", "Digital Display"}

print("PER-SUBTYPE OPTIONS TESTS PASSED")

# ===========================================================================
# 3. The six operations
# ===========================================================================
op_rows = [
    row(impressions=6000, media_cost=None, reconciled=11.0, prisma=21.0, wpu=6100.4),
    row(impressions=3000, media_cost=None, reconciled=12.0, prisma=22.0, wpu=3050.6),
    row(impressions=1000, media_cost=None, reconciled=None, prisma=23.0, wpu=1000.0),
]
op_df = make_df(op_rows)
op_subset = op_df

# --- MC_WEIGHTED: proportional to impressions ---
vals, err = compute_new_values(op_subset, "MC_WEIGHTED", 1000.0, "DIGITAL")
assert err is None
assert vals.tolist() == [600.0, 300.0, 100.0], vals.tolist()
assert abs(vals.sum() - 1000.0) < 1e-9

# --- MC_EVEN: same amount on every row ---
vals, err = compute_new_values(op_subset, "MC_EVEN", 900.0, "DIGITAL")
assert err is None
assert vals.tolist() == [300.0, 300.0, 300.0], vals.tolist()
assert abs(vals.sum() - 900.0) < 1e-9

# --- MC_COPY_RECONCILED: row-by-row copy, NULL becomes 0 ---
vals, err = compute_new_values(op_subset, "MC_COPY_RECONCILED", None, "DIGITAL")
assert err is None
assert vals.tolist() == [11.0, 12.0, 0.0], vals.tolist()

# --- MC_COPY_PRISMA ---
vals, err = compute_new_values(op_subset, "MC_COPY_PRISMA", None, "DIGITAL")
assert err is None
assert vals.tolist() == [21.0, 22.0, 23.0], vals.tolist()

# --- IMPR_WEIGHTED: weights by the impressions already there (keeps the daily curve) ---
vals, err = compute_new_values(op_subset, "IMPR_WEIGHTED", 20000.0, "DIGITAL")
assert err is None
assert vals.tolist() == [12000.0, 6000.0, 2000.0], vals.tolist()
assert vals.sum() == 20000.0
# proportions must be identical to the original ones
before = op_subset["Impressions"] / op_subset["Impressions"].sum()
after = vals / vals.sum()
assert (before - after).abs().max() < 1e-9, "IMPR_WEIGHTED must preserve the daily shape"

# --- IMPR_COPY_WPU: copies and rounds to whole impressions ---
vals, err = compute_new_values(op_subset, "IMPR_COPY_WPU", None, "DIGITAL")
assert err is None
assert vals.tolist() == [6100.0, 3051.0, 1000.0], vals.tolist()
assert (vals == vals.round()).all()

print("OPERATION MATH TESTS PASSED")

# --- IMPR_WEIGHTED falls back to Media_Cost when there are no impressions at all ---
fallback_rows = [
    row(impressions=0, media_cost=75.0),
    row(impressions=None, media_cost=25.0),
]
fb_df = make_df(fallback_rows)
vals, err = compute_new_values(fb_df, "IMPR_WEIGHTED", 1000.0, "DIGITAL")
assert err is None, err
assert vals.tolist() == [750.0, 250.0], vals.tolist()
assert vals.sum() == 1000.0

# ...and errors out when BOTH bases are empty
dead_df = make_df([row(impressions=0, media_cost=0.0), row(impressions=None, media_cost=None)])
vals, err = compute_new_values(dead_df, "IMPR_WEIGHTED", 1000.0, "DIGITAL")
assert vals is None and "0 total Media_Cost" in err, err

# --- MC_WEIGHTED with no impressions and a non-zero target is still blocked,
# regardless of mode: there's real ambiguity in splitting a non-zero amount with
# no weight basis to go by ---
vals, err = compute_new_values(dead_df, "MC_WEIGHTED", 500.0, "DIGITAL")
assert vals is None and "0 total Impressions" in err, err
vals, err = compute_new_values(dead_df, "MC_WEIGHTED", 500, "TV")
assert vals is None and err is not None

# --- ...but a target of exactly 0 is allowed on EITHER mode: there's nothing
# ambiguous about splitting zero across a zero weight basis, every row just gets 0 ---
vals, err = compute_new_values(dead_df, "MC_WEIGHTED", 0, "TV")
assert err is None and (vals == 0).all() and vals.sum() == 0
vals, err = compute_new_values(dead_df, "MC_WEIGHTED", 0, "DIGITAL")
assert err is None and (vals == 0).all() and vals.sum() == 0

# --- a copy operation whose source column is absent fails cleanly ---
slim = make_df([row()]).drop(columns=["Delivered Spend (Prisma)"])
vals, err = compute_new_values(slim, "MC_COPY_PRISMA", None, "DIGITAL")
assert vals is None and "Delivered Spend (Prisma)" in err, err

# --- an empty subset never reaches the math ---
vals, err = compute_new_values(op_df.iloc[0:0], "MC_EVEN", 100.0, "DIGITAL")
assert vals is None and "0 rows" in err

print("OPERATION EDGE-CASE TESTS PASSED")

# --- every operation is reachable from the UI registry, and vice versa ---
assert set(OPERATIONS_BY_FIELD["Media_Cost"] + OPERATIONS_BY_FIELD["Impressions"]) == set(OPERATIONS)
for field, ids in OPERATIONS_BY_FIELD.items():
    for oid in ids:
        assert OPERATIONS[oid]["field"] == field, f"{oid} is listed under the wrong field"
        if not OPERATIONS[oid]["needs_target"]:
            assert "source" in OPERATIONS[oid], f"{oid} needs no target so it must name a source"

print("OPERATION REGISTRY TESTS PASSED")

# ===========================================================================
# 4. Subsets, including the multi-value filters
# ===========================================================================
subset_rows = [
    # Reserve rows across 2 partners x 2 audiences
    row(placement="R1_UNE", partner="AMAZON.COM", audience="AudA", media_cost=10.0),
    row(placement="R2_UNE", partner="AMAZON.COM", audience="AudB", media_cost=20.0),
    row(placement="R3_UNE", partner="PEACOCK", audience="AudA", media_cost=30.0),
    row(placement="R4_UNE", partner="PEACOCK", audience="AudB", media_cost=40.0),
    # a Social row that must never be caught by a Reserve filter
    row(placement="S1_UNE", partner="PINTEREST", audience="AudA", media_cost=99.0),
    # another month
    row(date="2026-07-01", placement="R5_UNE", partner="AMAZON.COM", audience="AudA", media_cost=50.0),
]
sub_df = make_df(subset_rows)
reserve_specs = FILTER_SPECS[SUBTYPE_RESERVE]

# one partner, one audience
s = compute_subset_digital(sub_df, SUBTYPE_RESERVE, {
    "Month": "June 2026", "Campaign": "CampA",
    "Partner": ["AMAZON.COM"], "Audience": ["AudA"],
}, reserve_specs)
assert len(s) == 1 and s["Media_Cost"].tolist() == [10.0]

# both partners, both audiences ("all")
s = compute_subset_digital(sub_df, SUBTYPE_RESERVE, {
    "Month": "June 2026", "Campaign": "CampA",
    "Partner": ["AMAZON.COM", "PEACOCK"], "Audience": ["AudA", "AudB"],
}, reserve_specs)
assert len(s) == 4, f"expected all 4 June Reserve rows, got {len(s)}"
assert s["Media_Cost"].sum() == 100.0
assert 99.0 not in s["Media_Cost"].tolist(), "the Social row must never leak into Reserve"

# a multi-value filter with several (but not all) values
s = compute_subset_digital(sub_df, SUBTYPE_RESERVE, {
    "Month": "June 2026", "Campaign": "CampA",
    "Partner": ["PEACOCK"], "Audience": ["AudA", "AudB"],
}, reserve_specs)
assert s["Media_Cost"].sum() == 70.0

# month is a single-value filter and really does scope the subset
s = compute_subset_digital(sub_df, SUBTYPE_RESERVE, {
    "Month": "July 2026", "Campaign": "CampA",
    "Partner": ["AMAZON.COM", "PEACOCK"], "Audience": ["AudA", "AudB"],
}, reserve_specs)
assert s["Media_Cost"].tolist() == [50.0]

print("MULTI-VALUE SUBSET TESTS PASSED")

# --- Social: package path vs placement path ---
social_rows = [
    row(package="PKG1", placement="PL1_UNE", jtbd="Awareness", audience="AudA",
        breakout="Brand Say", media_cost=1.0),
    row(package="PKG1", placement="PL2_UNE", jtbd="Awareness", audience="AudA",
        breakout="Brand Say", media_cost=2.0),
    row(package="PKG1", placement="PL3_UNE", jtbd="Awareness", audience="AudB",
        breakout="Brand Say", media_cost=4.0),
]
soc_df = make_df(social_rows)
pkg_specs = FILTER_SPECS[SUBTYPE_SOCIAL][SOCIAL_SELECT_BY_PACKAGE]
plc_specs = FILTER_SPECS[SUBTYPE_SOCIAL][SOCIAL_SELECT_BY_PLACEMENT]

by_package = compute_subset_digital(soc_df, SUBTYPE_SOCIAL, {
    "Month": "June 2026", "Campaign": "CampA", "Partner": "PINTEREST", "Package": "PKG1",
    "CCD JTBD": "Awareness", "Audience": "AudA", "Breakout": "Brand Say",
}, pkg_specs)
assert by_package["Media_Cost"].sum() == 3.0, "package path must respect JTBD/Audience/Breakout"

by_placement = compute_subset_digital(soc_df, SUBTYPE_SOCIAL, {
    "Month": "June 2026", "Campaign": "CampA", "Partner": "PINTEREST", "Placement": "PL3_UNE",
}, plc_specs)
assert by_placement["Media_Cost"].tolist() == [4.0], "placement path targets exactly one placement"

print("SOCIAL PACKAGE-VS-PLACEMENT TESTS PASSED")

# ===========================================================================
# 5. The lock, now based on row overlap
# ===========================================================================
q_item = {"qid": 1, "operation_label": "Digital · Reserve · Media_Cost · Even allocation",
          "indices": [10, 11, 12]}

assert find_lock_conflict([20, 21], [q_item], []) is None, "non-overlapping rows are free"
assert find_lock_conflict([12, 13], [q_item], []) is not None, "a single shared row is a conflict"
assert "#1" in find_lock_conflict([12], [q_item], [])

applied = [{"label": "Digital · Social · Impressions · Weighted", "indices": [30, 31]}]
assert find_lock_conflict([31], [], applied) is not None
assert "already applied" in find_lock_conflict([31], [], applied)
assert find_lock_conflict([32], [], applied) is None

# THE CASE THE OLD FILTER-EQUALITY LOCK MISSED: two different multi-select selections
# that share rows. Partners [A,B] then [B,C] are different filter values, but both
# touch B's rows -- comparing filters would have let this through and double-written.
overlap_a = compute_subset_digital(sub_df, SUBTYPE_RESERVE, {
    "Month": "June 2026", "Campaign": "CampA",
    "Partner": ["AMAZON.COM", "PEACOCK"], "Audience": ["AudA"],
}, reserve_specs)
overlap_b = compute_subset_digital(sub_df, SUBTYPE_RESERVE, {
    "Month": "June 2026", "Campaign": "CampA",
    "Partner": ["PEACOCK"], "Audience": ["AudA", "AudB"],
}, reserve_specs)
shared = set(overlap_a.index) & set(overlap_b.index)
assert shared, "test setup: these two selections are supposed to share a row"
queued_a = {"qid": 7, "operation_label": "x", "indices": list(overlap_a.index)}
assert find_lock_conflict(overlap_b.index, [queued_a], []) is not None, (
    "partially overlapping multi-select subsets must be caught by the lock"
)

print("ROW-OVERLAP LOCK TESTS PASSED")

# ===========================================================================
# 6. build_preview end to end
# ===========================================================================
prev_specs = FILTER_SPECS[SUBTYPE_RESERVE]
prev_filters = {"Month": "June 2026", "Campaign": "CampA",
                "Partner": ["AMAZON.COM", "PEACOCK"], "Audience": ["AudA", "AudB"]}
prev_subset = compute_subset_digital(sub_df, SUBTYPE_RESERVE, prev_filters, prev_specs)

preview, err = build_preview("DIGITAL", SUBTYPE_RESERVE, prev_filters, "MC_EVEN", 400.0,
                             prev_subset, [], [])
assert err is None and preview is not None
assert preview["rows"] == 4
assert preview["current_sum"] == 100.0
assert preview["resulting_sum"] == 400.0
assert preview["delta"] == 300.0
assert preview["operation"] == "MC_EVEN"
assert "Even allocation" in preview["operation_label"]
assert "Reserve" in preview["operation_label"]
assert set(preview["indices"]) == set(prev_subset.index)

# a copy operation reports the resulting sum without any target
prisma_rows = [row(placement="R1_UNE", partner="AMAZON.COM", media_cost=1.0, prisma=500.0),
               row(placement="R2_UNE", partner="AMAZON.COM", media_cost=2.0, prisma=250.0)]
prisma_df = make_df(prisma_rows)
prisma_subset = compute_subset_digital(prisma_df, SUBTYPE_RESERVE, {
    "Month": "June 2026", "Campaign": "CampA", "Partner": ["AMAZON.COM"], "Audience": ["AudA"],
}, prev_specs)
preview_copy, err = build_preview("DIGITAL", SUBTYPE_RESERVE, {
    "Month": "June 2026", "Campaign": "CampA", "Partner": ["AMAZON.COM"], "Audience": ["AudA"],
}, "MC_COPY_PRISMA", None, prisma_subset, [], [])
assert err is None, err
assert preview_copy["target_value"] is None
assert preview_copy["resulting_sum"] == 750.0
assert preview_copy["current_sum"] == 3.0

# a target of exactly 0 is a legitimate backfill on Digital too (e.g. zeroing out a
# miscoded cost) -- it must NOT be rejected by the sign check
preview_zero, err = build_preview("DIGITAL", SUBTYPE_RESERVE, prev_filters, "MC_EVEN", 0,
                                  prev_subset, [], [])
assert err is None, err
assert preview_zero["resulting_sum"] == 0

# only a genuinely negative target is rejected, on either mode
_, err = build_preview("DIGITAL", SUBTYPE_RESERVE, prev_filters, "MC_EVEN", -1, prev_subset, [], [])
assert err == "The target must be a number greater than or equal to 0."
_, err = build_preview("TV", None, prev_filters, "MC_EVEN", -1, prev_subset, [], [])
assert err == "The target must be a number greater than or equal to 0."

# validation order continues: empty multi-select, empty subset, lock
_, err = build_preview("DIGITAL", SUBTYPE_RESERVE,
                       {**prev_filters, "Partner": []}, "MC_EVEN", 100.0, prev_subset, [], [])
assert err == "Pick at least one value for Partner."

_, err = build_preview("DIGITAL", SUBTYPE_RESERVE, prev_filters, "MC_EVEN", 100.0,
                       prev_subset.iloc[0:0], [], [])
assert "0 rows match" in err

blocking = [{"qid": 3, "operation_label": "something", "indices": list(prev_subset.index)}]
_, err = build_preview("DIGITAL", SUBTYPE_RESERVE, prev_filters, "MC_EVEN", 100.0,
                       prev_subset, blocking, [])
assert "overlap" in err and "#3" in err

# a copy operation is exempt from the target validation entirely
preview_no_target, err = build_preview("DIGITAL", SUBTYPE_RESERVE, prev_filters,
                                       "MC_COPY_RECONCILED", None, prev_subset, [], [])
assert err is None and preview_no_target is not None

# TV still accepts a target of exactly 0
tv_rows = [row(channel="TV", brand="NEXXUS", daypart="Primetime", network="COMCAST",
               audience="General", impressions=0, media_cost=45.0),
           row(channel="TV", brand="NEXXUS", daypart="Primetime", network="COMCAST",
               audience="General", impressions=0, media_cost=12.0)]
tv_df = make_df(tv_rows)
tv_filters = {"Month": "June 2026", "Brand": "NEXXUS", "Audience": "General",
              "Daypart": "Primetime", "Network_Name": "COMCAST"}
tv_subset = compute_subset_tv(tv_df, tv_filters)
assert len(tv_subset) == 2
preview_tv, err = build_preview("TV", None, tv_filters, "MC_WEIGHTED", 0, tv_subset, [], [])
assert err is None, err
assert preview_tv["resulting_sum"] == 0
assert preview_tv["delta"] == -57.0
assert preview_tv["operation_label"].startswith("TV · Media_Cost"), preview_tv["operation_label"]

print("BUILD_PREVIEW TESTS PASSED")

# ===========================================================================
# 7. Regressions carried over from the previous version
# ===========================================================================
# int64 columns must be coerced to float64 or writing fractional results raises TypeError
int_df = pd.DataFrame(
    [("2026-06-01", "TV", None, None, None, None, None, "General", None, "NEXXUS",
      "Primetime", "COMCAST", 71200, 672, 0, 0, 0),
     ("2026-06-02", "TV", None, None, None, None, None, "General", None, "NEXXUS",
      "Primetime", "COMCAST", 53050, 480, 0, 0, 0)],
    columns=COLUMNS,
)
assert int_df["Impressions"].dtype.kind == "i" and int_df["Media_Cost"].dtype.kind == "i"
int_df = prepare_dataframe(int_df)
assert int_df["Impressions"].dtype == "float64" and int_df["Media_Cost"].dtype == "float64"
int_subset = compute_subset_tv(int_df, {
    "Month": "June 2026", "Brand": "NEXXUS", "Audience": "General",
    "Daypart": "Primetime", "Network_Name": "COMCAST",
})
new_vals, err = compute_new_values(int_subset, "IMPR_WEIGHTED", 800000, "TV")
assert err is None
int_df.loc[int_subset.index, "Impressions"] = new_vals
assert int_df.loc[int_subset.index, "Impressions"].sum() == 800000

# largest-remainder rounding keeps the sum exact where naive rounding would not
tricky = pd.Series([1.5, 1.5, 1.5, 1.5])
rounded = round_preserving_sum(tricky, 6)
assert rounded.sum() == 6 and set(rounded.tolist()) == {1.0, 2.0}

# months sort chronologically, not alphabetically
month_df = make_df([
    row(date="2026-12-01"), row(date="2026-02-01"), row(date="2026-04-01"),
])
assert sorted_month_labels(month_df) == ["February 2026", "April 2026", "December 2026"]

# PCODE pattern is still used for the derived column
assert PCODE_PATTERN.match("P3GHJCX") and not PCODE_PATTERN.match("Awarene!")

# critical-column checks still work
assert missing_critical_columns(tax_df, CRITICAL_COLUMNS_DIGITAL) == []
assert missing_critical_columns(tax_df, CRITICAL_COLUMNS_TV) == []
assert "Package_Placement_Name" in CRITICAL_COLUMNS_DIGITAL, (
    "the sub-type taxonomy reads this column, so Digital cannot work without it"
)

print("REGRESSION TESTS PASSED")

print("ALL TESTS PASSED")
