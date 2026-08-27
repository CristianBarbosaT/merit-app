"""Tests for the TV Data Standardization tool.

Part 1 exercises the pure logic on synthetic data (always runs). Part 2 is the real
regression: it runs the actual TV files through the pipeline and checks every control
figure in section 10 of the spec, plus the AFFID-DATE claim from section 1 and the
correction rules against what the manual process actually produced. Part 2 skips itself
cleanly when the TV files aren't on this machine.
"""
import glob
import os
from io import BytesIO

import pandas as pd

from tools.tv_standardization import (
    ACTION_BACKFILL_ACTUAL, ACTION_BACKFILL_ESTIMATED, ACTION_ZERO_OUT, DATA_COLUMNS,
    apply_corrections, build_reconciliation, coerce_numeric, effective_date,
    judgment_calls, load_mappings, month_key, normalize_header, parse_affid_month,
    product_code_from_filename, propose_corrections, pull_timestamp, read_platform_export,
    read_tv_file, resolve_repulls, tv_impressions,
)

MAPPINGS = load_mappings()

# ===========================================================================
# PART 1 — pure logic on synthetic data
# ===========================================================================

# --- the central transformation: AFFID DATE -> real date (spec 3.5) ---
assert effective_date("JUN28", "2026-06-22") == pd.Timestamp("2026-06-28")
assert effective_date("MAY15", "2026-05-12") == pd.Timestamp("2026-05-15")
assert effective_date("APR06", "2026-04-01") == pd.Timestamp("2026-04-06")
# a blank affidavit (arrives as a space, not an empty cell) falls back to the planned date
assert effective_date(" ", "2026-06-22") == pd.Timestamp("2026-06-22")
assert effective_date("", "2026-06-22") == pd.Timestamp("2026-06-22")
assert effective_date(None, "2026-06-22") == pd.Timestamp("2026-06-22")
# garbage falls back rather than raising
assert effective_date("NOTAMONTH", "2026-06-22") == pd.Timestamp("2026-06-22")
assert effective_date("JUN99", "2026-06-22") == pd.Timestamp("2026-06-22")  # day 99 invalid

# the year is inherited from DATE, and nudged when the affidavit crosses a year boundary
assert effective_date("JAN02", "2026-12-30") == pd.Timestamp("2027-01-02"), (
    "an affidavit in January against a December plan belongs to the NEXT year"
)
assert effective_date("DEC30", "2027-01-02") == pd.Timestamp("2026-12-30"), (
    "an affidavit in December against a January plan belongs to the PREVIOUS year"
)
# ...but a normal within-year gap keeps the plan's year
assert effective_date("JUN28", "2026-06-22").year == 2026
print("TEST 1 OK: AFFID DATE conversion, blanks, garbage and year-boundary crossings")

# --- AFFID MONTH falls back to MONTH when the affidavit is blank (spec 3.4) ---
assert parse_affid_month("JUN28", "MAY") == "JUN"
assert parse_affid_month(" ", "MAY") == "MAY"
assert parse_affid_month("", "jun") == "JUN"
print("TEST 2 OK: AFFID MONTH derivation and fallback")

# --- product code comes from the filename, not a column (spec 3.2) ---
assert product_code_from_filename("DHC 4.1-6.30 TV Data.xlsx") == "DHC"
assert product_code_from_filename("VIC June Data 7.22.xlsx") == "VIC"
assert product_code_from_filename("TRE_something.xlsx") == "TRE"
print("TEST 3 OK: product code parsed from the filename")

# --- re-pull resolution keeps the newer pull (spec 3.3) ---
assert pull_timestamp("VIC June Data 7.22.xlsx") == (7, 22)
assert pull_timestamp("VIC 4.1-6.30 TV Data.xlsx") == (6, 30)
assert pull_timestamp("no date here.xlsx") is None

old = pd.DataFrame({"PRODUCT CODE": ["VIC"] * 3, "P2+ ACTIMP": [0, 0, 0]})
new = pd.DataFrame({"PRODUCT CODE": ["VIC"] * 3, "P2+ ACTIMP": [10, 20, 30]})
other = pd.DataFrame({"PRODUCT CODE": ["DHC"] * 2, "P2+ ACTIMP": [1, 2]})
kept, discarded = resolve_repulls([
    ("VIC 4.1-6.30 TV Data.xlsx", old),
    ("VIC June Data 7.22.xlsx", new),
    ("DHC 4.1-6.30 TV Data.xlsx", other),
])
kept_names = sorted(n for n, _ in kept)
assert kept_names == ["DHC 4.1-6.30 TV Data.xlsx", "VIC June Data 7.22.xlsx"], kept_names
assert len(discarded) == 1
assert discarded[0]["Discarded file"] == "VIC 4.1-6.30 TV Data.xlsx"
assert discarded[0]["Kept instead"] == "VIC June Data 7.22.xlsx"
print("TEST 4 OK: re-pull resolution keeps the newer pull and reports the discard")

# --- 'NULL' strings must not poison the sums (spec 4 / 8.2) ---
s = pd.Series([100, "NULL", 50.5, None, "null"])
assert coerce_numeric(s).tolist() == [100.0, 0.0, 50.5, 0.0, 0.0]
print("TEST 5 OK: literal 'NULL' strings coerce to 0")

# --- actual impressions win over estimated (spec 3.6) ---
assert tv_impressions(500.0, 300.0) == 500.0
assert tv_impressions(0.0, 300.0) == 300.0
assert tv_impressions(0.0, 0.0) == 0.0
assert normalize_header("  assigned   net ") == "ASSIGNED NET"
print("TEST 6 OK: impression precedence and header normalization")


# --- reconciliation, corrections and their reports, end to end on synthetic data ---
def tv_row(product, network, daypart, affid, planned, cost, actimp, estimp):
    return {
        "PRODUCT CODE": product, "CLEAN NETWORK": network, "DAYPART": daypart,
        "AFFID DATE": affid, "DATE": pd.Timestamp(planned),
        "EFFECTIVE DATE": effective_date(affid, planned),
        "ASSIGNED NET": cost, "P2+ ACTIMP*1000": actimp, "P2+ ESTIMP*1000": estimp,
        "UNITS": 1,
    }


tv = pd.DataFrame([
    # a group the platform reports as zero impressions -> backfill candidate
    tv_row("DHC", "ACC NETWORK", "CABLE SPORTS", "JUN10", "2026-06-08", 100.0, 0.0, 90000.0),
    # phantom spend: no impressions on either side -> zero-out candidate
    tv_row("DHC", "INDEPENDENT TV NETWORK", "NEWS", "JUN12", "2026-06-12", 500.0, 0.0, 0.0),
    # a group that already agrees -> no correction
    tv_row("DHC", "FOX NEWS", "NEWS", "JUN15", "2026-06-15", 200.0, 50000.0, 40000.0),
])

export = pd.DataFrame([
    {"Date": pd.Timestamp("2026-06-10"), "Product Code": "DHC", "Network_Name": "ACC NETWORK",
     "Daypart": "Cable Sports", "Media_Cost": 100.0, "Impressions": 0},
    {"Date": pd.Timestamp("2026-06-11"), "Product Code": "DHC", "Network_Name": "ACC NETWORK",
     "Daypart": "Cable Sports", "Media_Cost": 0.0, "Impressions": 0},
    {"Date": pd.Timestamp("2026-06-12"), "Product Code": "DHC",
     "Network_Name": "INDEPENDENT TV NETWORK", "Daypart": "News",
     "Media_Cost": 500.0, "Impressions": 0},
    {"Date": pd.Timestamp("2026-06-15"), "Product Code": "DHC", "Network_Name": "FOX NEWS",
     "Daypart": "News", "Media_Cost": 200.0, "Impressions": 50000},
])

recon = build_reconciliation(tv, export, MAPPINGS)
by_network = {r["Network_Name"]: r for _, r in recon.iterrows()}
assert by_network["FOX NEWS"]["Media Cost Delta"] == 0.0, "an agreeing group must show delta 0"
assert by_network["FOX NEWS"]["Impression Delta"] == 0.0
# the platform reports 0 impressions, so the delta is undefined rather than a #DIV/0!
assert pd.isna(by_network["ACC NETWORK"]["Impression Delta"])
assert by_network["ACC NETWORK"]["TV_Impressions"] == 90000.0, "estimated used when no actual"
print("TEST 7 OK: reconciliation deltas, with undefined rather than #DIV/0! on a zero divisor")

proposals = propose_corrections(recon, export)
actions = {(r["Action"], r["Network_Name"]) for _, r in proposals.iterrows()}
assert (ACTION_ZERO_OUT, "INDEPENDENT TV NETWORK") in actions
assert (ACTION_BACKFILL_ESTIMATED, "ACC NETWORK") in actions, "no actual impressions -> estimated"
assert not any(n == "FOX NEWS" for _, n in actions), "an agreeing group must not be proposed"
# zero-outs are ordered first so the result is reproducible (spec 8.9)
assert proposals.iloc[0]["Action"] == ACTION_ZERO_OUT
print("TEST 8 OK: proposals cover phantom spend and zero-reported impressions only")

clean, report = apply_corrections(export, proposals)
assert clean.loc[clean["Network_Name"] == "INDEPENDENT TV NETWORK", "Media_Cost"].tolist() == [0.0]
acc = clean.loc[clean["Network_Name"] == "ACC NETWORK", "Impressions"]
assert acc.tolist() == [45000.0, 45000.0], "90,000 spread evenly over 2 export rows"
assert clean.loc[clean["Network_Name"] == "FOX NEWS", "Media_Cost"].tolist() == [200.0]
# nothing outside the two metric columns may change
for col in export.columns:
    if col not in ("Media_Cost", "Impressions"):
        assert export[col].astype(str).equals(clean[col].astype(str)), f"{col} was modified"
print("TEST 9 OK: corrections applied; only Media_Cost and Impressions touched")

# a correction aimed at rows that don't exist is reported, never a silent #DIV/0! (spec 6.3)
ghost = pd.DataFrame([{
    "Apply": True, "Action": ACTION_ZERO_OUT, "Product Code": "DHC", "Month": "Jun",
    "Daypart": "", "Network_Name": "NETWORK THAT ISN'T THERE", "TV Total": 0.0,
    "Export Rows": 0, "Value Per Row": 0.0, "Platform Now": 0.0, "Reason": "test",
}])
_, ghost_report = apply_corrections(export, ghost)
assert ghost_report.iloc[0]["Status"] == "No matching rows in the export"
assert ghost_report.iloc[0]["Rows Changed"] == 0

# a zero-out over rows already at zero reports 'no change', not 'applied' -- re-running
# the same correction on the already-corrected export is the cleanest way to prove it
noop = pd.DataFrame([{
    "Apply": True, "Action": ACTION_ZERO_OUT, "Product Code": "DHC", "Month": "Jun",
    "Daypart": "", "Network_Name": "INDEPENDENT TV NETWORK", "TV Total": 0.0,
    "Export Rows": 1, "Value Per Row": 0.0, "Platform Now": 0.0, "Reason": "test",
}])
_, noop_report = apply_corrections(clean, noop)
assert noop_report.iloc[0]["Status"] == "No change (already zero)", noop_report.iloc[0]["Status"]
assert noop_report.iloc[0]["Rows Matched"] == 1, "it still matched the row, it just changed nothing"
print("TEST 10 OK: no-matching-rows and already-zero cases are reported explicitly")

# --- an unmapped network must fail loudly, never silently vanish (spec 7.2) ---
def build_raw_tv_bytes(rows, header_offset=32, gross_first=True):
    """Builds a file shaped like a real TV pull: a report preamble, then the header row
    marked by 'ESTIMATE NAME' in column A, then the data."""
    gross = "ASSIGNED GROSS" if gross_first else "GROSS ASSIGNED"
    net = "ASSIGNED NET" if gross_first else "NET ASSIGNED"
    header = ["ESTIMATE NAME", "PACKAGE", "NETWORK", "QUARTER", "DAYPART", "PROGRAM NAME",
              "DATE", "MONTH", "NETWORK", "AFFID DATE", "AFFID TIME", "LEN", "UNITS",
              gross, net, "P2+ ACTIMP", "P2+ ESTIMP"]
    preamble = [["DETAILS OF REQUEST"] + [None] * 16 for _ in range(header_offset)]
    frame = pd.DataFrame(preamble + [header] + rows)
    buf = BytesIO()
    frame.to_excel(buf, index=False, header=False)
    return buf.getvalue()


good_row = ["25/26 CABLE SPORTS", "PKG", "ACCN ACC NETWORK", "APR-JUN", "SPORTS", "PROG",
            "06/08/26", "JUN", "ACCN", "JUN10", "653P", "15", 1, 128.0, 108.8, 0.0, 3.5]
bad_row = list(good_row)
bad_row[2] = "ZZZZ NETWORK NOBODY MAPPED"

df_ok, warns = read_tv_file(build_raw_tv_bytes([good_row]), "DHC test.xlsx", MAPPINGS)
assert list(df_ok.columns) == DATA_COLUMNS
assert len(df_ok) == 1
assert df_ok.iloc[0]["CLEAN NETWORK"] == "ACC NETWORK"
assert df_ok.iloc[0]["DAYPART"] == "CABLE SPORTS"
assert df_ok.iloc[0]["PRODUCT CODE"] == "DHC"
assert df_ok.iloc[0]["AUDIENCE"] == "P2+"
assert df_ok.iloc[0]["P2+ ESTIMP*1000"] == 3500.0, "impressions arrive in thousands"
assert df_ok.iloc[0]["EFFECTIVE DATE"] == pd.Timestamp("2026-06-10")

try:
    read_tv_file(build_raw_tv_bytes([bad_row]), "DHC test.xlsx", MAPPINGS)
    raise AssertionError("an unmapped network must raise, not pass the raw value through")
except ValueError as exc:
    assert "ZZZZ NETWORK NOBODY MAPPED" in str(exc)
print("TEST 11 OK: raw file parsed into DATA shape; an unmapped network fails loudly")

# the header row is found by scanning, not hardcoded, and the flipped ASSIGNED/NET
# spelling used by re-pull files still reads correctly (spec 2.1)
df_shift, _ = read_tv_file(build_raw_tv_bytes([good_row], header_offset=12),
                           "DHC test.xlsx", MAPPINGS)
assert len(df_shift) == 1 and df_shift.iloc[0]["CLEAN NETWORK"] == "ACC NETWORK"
df_flip, flip_warns = read_tv_file(build_raw_tv_bytes([good_row], gross_first=False),
                                   "VIC test.xlsx", MAPPINGS)
assert df_flip.iloc[0]["ASSIGNED NET"] == 108.8, "NET ASSIGNED must map to ASSIGNED NET"
assert not flip_warns, "a known header variant should not warn"
print("TEST 12 OK: header located by scanning; the NET ASSIGNED spelling variant reads correctly")

print("\nALL SYNTHETIC TV TESTS PASSED")

# ===========================================================================
# PART 2 — regression against the real files (spec section 10)
# ===========================================================================
TV_DIR = r"C:\Users\Cristian.Barbosa\Documents\TV Files"
CONSOLIDATED = os.path.join(TV_DIR, "CONSOLIDATED TV DATA.xlsx")

if not os.path.exists(CONSOLIDATED):
    print("\nREAL-FILE REGRESSION SKIPPED — the TV files are not on this machine")
    raise SystemExit(0)

print("\n" + "=" * 70)
print("REAL-FILE REGRESSION (spec section 10 control figures)")
print("=" * 70)

parsed = []
for path in sorted(glob.glob(os.path.join(TV_DIR, "*.xlsx"))):
    name = os.path.basename(path)
    if "CONSOLIDATED" in name.upper():
        continue
    with open(path, "rb") as fh:
        df, _ = read_tv_file(fh.read(), name, MAPPINGS)
    parsed.append((name, df))

assert len(parsed) == 4, f"expected 4 TV files, found {len(parsed)}"

# The consolidated workbook used the OLDER VIC pull, so reproduce that choice to compare
# against its control figures. The tool itself defaults to the newer pull (spec 3.3).
as_workbook = pd.concat(
    [df for n, df in parsed if n != "VIC June Data 7.22.xlsx"], ignore_index=True
)

assert len(as_workbook) == 4819, len(as_workbook)
counts = as_workbook["PRODUCT CODE"].value_counts().to_dict()
assert counts == {"TRE": 4240, "DHC": 567, "VIC": 12}, counts
months = as_workbook["MONTH"].value_counts().to_dict()
assert months["APR"] == 1555 and months["MAY"] == 1915 and months["JUN"] == 1349, months
assert int((as_workbook["AFFID DATE"] == "").sum()) == 244
print("  [OK] DATA: 4,819 rows (DHC 567 / TRE 4,240 / VIC 12)")
print("  [OK] MONTH split: APR 1,555 / MAY 1,915 / JUN 1,349")
print("  [OK] 244 rows with a blank AFFID DATE")

# re-pull resolution picks the newer VIC file
kept, discarded = resolve_repulls(parsed)
assert len(discarded) == 1 and discarded[0]["Discarded file"] == "VIC 4.1-6.30 TV Data.xlsx"
newer = pd.concat([df for _, df in kept], ignore_index=True)
old_vic_actimp = as_workbook.loc[as_workbook["PRODUCT CODE"] == "VIC", "P2+ ACTIMP*1000"].sum()
new_vic_actimp = newer.loc[newer["PRODUCT CODE"] == "VIC", "P2+ ACTIMP*1000"].sum()
assert old_vic_actimp == 0, "the older VIC pull has no actual impressions"
assert new_vic_actimp > 0, "the newer VIC pull does — which is why it is preferred"
print(f"  [OK] re-pull: newer VIC file carries {new_vic_actimp:,.0f} actual impressions "
      f"(the older one had 0)")

with open(CONSOLIDATED, "rb") as fh:
    consolidated_bytes = fh.read()
export = read_platform_export(consolidated_bytes, "7.16")
assert len(export) == 2475, len(export)
assert str(export["Date"].min().date()) == "2026-04-06"
assert str(export["Date"].max().date()) == "2026-06-30"
print("  [OK] export: 2,475 rows, 2026-04-06 to 2026-06-30")

# --- the affidavit-vs-planned-date claim (spec section 1) ---
platform_daily = export.copy()
platform_daily["_d"] = platform_daily["Date"].dt.date
platform_daily = (platform_daily.groupby(["Product Code", "Network_Name", "_d"], observed=True)
                  ["Media_Cost"].sum().rename("pf").reset_index()
                  .rename(columns={"Product Code": "k1", "Network_Name": "k2", "_d": "k3"}))


def exact_match_rate(date_column):
    tv = as_workbook.copy()
    tv["_d"] = pd.to_datetime(tv[date_column]).dt.date
    grouped = (tv.groupby(["PRODUCT CODE", "CLEAN NETWORK", "_d"], observed=True)["ASSIGNED NET"]
               .sum().rename("tv").reset_index()
               .rename(columns={"PRODUCT CODE": "k1", "CLEAN NETWORK": "k2", "_d": "k3"}))
    joined = grouped.merge(platform_daily, on=["k1", "k2", "k3"], how="inner")
    hit = (joined["tv"] - joined["pf"]).abs() < 0.01
    return int(hit.sum()), len(joined)

affid_hits, affid_total = exact_match_rate("EFFECTIVE DATE")
plan_hits, plan_total = exact_match_rate("DATE")
assert affid_hits == 1042, f"expected the spec's 1,042 exact matches, got {affid_hits}"
assert affid_hits / affid_total > 0.95
assert (affid_hits / affid_total) > (plan_hits / plan_total) * 2, (
    "affidavit dating must comfortably beat planned dating -- that is the whole premise"
)
print(f"  [OK] affidavit dating: {affid_hits}/{affid_total} keys match exactly "
      f"({affid_hits / affid_total:.1%}) vs {plan_hits / plan_total:.1%} using the planned date")

# --- the correction rules against what the manual process actually did ---
clean_actual = read_platform_export(consolidated_bytes, "7.16 CLEAN")
month = month_key(export["Date"])
mc_changed = ~((export["Media_Cost"] - clean_actual["Media_Cost"]).abs() < 1e-6)
im_changed = ~((export["Impressions"] - clean_actual["Impressions"]).abs() < 1e-6)

human_zeroed = set(map(tuple, pd.DataFrame({
    "p": export.loc[mc_changed, "Product Code"], "m": month[mc_changed],
    "n": export.loc[mc_changed, "Network_Name"]}).drop_duplicates().values))
human_backfilled = set(map(tuple, pd.DataFrame({
    "p": export.loc[im_changed, "Product Code"], "m": month[im_changed],
    "d": export.loc[im_changed, "Daypart"],
    "n": export.loc[im_changed, "Network_Name"]}).drop_duplicates().values))
assert int(mc_changed.sum()) == 82 and len(human_zeroed) == 12
assert int(im_changed.sum()) == 435 and len(human_backfilled) == 20
print(f"  [OK] manual CLEAN: {int(mc_changed.sum())} Media_Cost rows in {len(human_zeroed)} "
      f"groups, {int(im_changed.sum())} Impressions rows in {len(human_backfilled)} groups")

recon_real = build_reconciliation(as_workbook, export, MAPPINGS)
proposals_real = propose_corrections(recon_real, export)
zero_props = proposals_real[proposals_real["Action"] == ACTION_ZERO_OUT]
back_props = proposals_real[proposals_real["Action"] != ACTION_ZERO_OUT]

proposed_zero = set(map(tuple, zero_props[["Product Code", "Month", "Network_Name"]].values))
proposed_back = set(map(tuple, back_props[["Product Code", "Month", "Daypart", "Network_Name"]].values))

# Zero-out reproduces the analyst's decisions exactly.
assert proposed_zero == human_zeroed, (
    f"zero-out mismatch: only-proposed={proposed_zero - human_zeroed}, "
    f"only-human={human_zeroed - proposed_zero}"
)
print(f"  [OK] zero-out rule: proposes exactly the {len(human_zeroed)} groups the analyst "
      f"zeroed — no false positives, no misses")

# Backfill proposes a strict subset: everything it proposes, the analyst also did.
assert proposed_back <= human_backfilled, (
    f"backfill proposed groups the analyst did NOT correct: {proposed_back - human_backfilled}"
)
assert len(proposed_back) == 16, len(proposed_back)
missed = human_backfilled - proposed_back
assert len(missed) == 4, missed
print(f"  [OK] backfill rule: proposes {len(proposed_back)} of the analyst's "
      f"{len(human_backfilled)} groups with no false positives")
print(f"       the {len(missed)} it leaves out are judgment calls where BOTH sides report "
      f"impressions but disagree")

# Those 4 are surfaced for review rather than silently dropped.
judgment = judgment_calls(recon_real)
judgment_keys = set(map(tuple, judgment[["Product Code", "Month", "Daypart", "Network_Name"]].values))
surfaced = {k for k in missed if k in judgment_keys}
assert len(surfaced) >= 3, (
    f"the judgment-call table should surface the disagreeing groups, only found {surfaced}"
)
print(f"  [OK] {len(judgment)} judgment calls surfaced for review, covering {len(surfaced)} "
      f"of the 4 the rules skip")

# --- applying the proposals only ever touches the two metric columns ---
clean_ours, report = apply_corrections(export, proposals_real)
for col in export.columns:
    if col not in ("Media_Cost", "Impressions"):
        assert export[col].astype(str).equals(clean_ours[col].astype(str)), f"{col} modified"
assert (report["Status"] != "No matching rows in the export").all(), (
    "every proposed correction should match rows, since proposals come from the export itself"
)
mc_ours = int((~((export["Media_Cost"] - clean_ours["Media_Cost"]).abs() < 1e-6)).sum())
assert mc_ours == 82, f"zero-out should change the same 82 rows the analyst did, got {mc_ours}"
print(f"  [OK] applying the proposals changes {mc_ours} Media_Cost rows — the same rows the "
      f"analyst changed — and no column outside Media_Cost / Impressions")

# --- verification: the corrected groups now reconcile ---
verification = build_reconciliation(as_workbook, clean_ours, MAPPINGS)
for _, p in back_props.iterrows():
    row = verification[
        (verification["Product Code"] == p["Product Code"])
        & (verification["Month"] == p["Month"])
        & (verification["Daypart"] == p["Daypart"])
        & (verification["Network_Name"] == p["Network_Name"])
    ]
    assert len(row) == 1
    delta = row.iloc[0]["Impression Delta"]
    assert abs(delta) < 1e-6, f"{p['Network_Name']} still off after correction: {delta}"
print(f"  [OK] verification: all {len(back_props)} backfilled groups now show a zero "
      f"impression delta")

print("\nALL REAL-FILE TV REGRESSION TESTS PASSED")
