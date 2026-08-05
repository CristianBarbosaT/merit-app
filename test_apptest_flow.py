import pandas as pd
from streamlit.testing.v1 import AppTest

from tools.rroi_backfill import (
    prepare_dataframe, build_dropdown_options_subtype, build_dropdown_options_tv,
    DIGITAL_SUBTYPES, SUBTYPE_SOCIAL, SUBTYPE_RESERVE, SUBTYPE_PROGRAMMATIC,
)

COLUMNS = [
    "Date", "Channel", "Prisma_Campaign_Secondary", "Raw_Partner", "Package Name",
    "Package_Placement_Name", "CCD JTBD", "Audience", "Breakout", "Brand", "Daypart",
    "Network_Name", "Impressions", "Media_Cost", "Delivered Spend (Reconciled)",
    "Delivered Spend (Prisma)", "Weighted Planned Units",
]

rows = []
# --- Social: PINTEREST, one package, two audiences, 10 rows each ---
for i in range(10):
    rows.append(("2026-06-01", "Digital Social", "CampA", "PINTEREST", "PKG_SOCIAL",
                 "PL_SOCIAL_A_UNE", "Awareness", "AudA", "Brand Say", None, None, None,
                 1000 + i, 0.0, 5.0, 7.0, 1100 + i))
for i in range(10):
    rows.append(("2026-06-01", "Digital Social", "CampA", "PINTEREST", "PKG_SOCIAL",
                 "PL_SOCIAL_B_UNE", "Awareness", "AudB", "Brand Say", None, None, None,
                 2000 + i, 0.0, 6.0, 8.0, 2100 + i))
# a SECOND Social package on the same partner, with a JTBD and an audience that
# PKG_SOCIAL does not have — this is what makes the cascade provable: without it,
# narrowing by package would not shrink any dropdown and the test would prove nothing
for i in range(4):
    rows.append(("2026-06-01", "Digital Social", "CampA", "PINTEREST", "PKG_SOCIAL2",
                 "PL_SOCIAL_C_UNE", "Consideration", "AudZ", "Brand Say", None, None, None,
                 500 + i, 0.0, 3.0, 4.0, 520 + i))
# --- Reserve: two partners x two audiences ---
for partner in ("AMAZON.COM", "PEACOCK"):
    for audience in ("AudA", "AudB"):
        for i in range(5):
            rows.append(("2026-06-01", "Digital Display", "CampA", partner, "PKG_RESERVE",
                         f"PL_RESERVE_{partner}_UNE", "Awareness", audience, "Brand Say",
                         None, None, None, 500 + i, 10.0, 4.0, 9.0, 550 + i))
# --- Programmatic: two channels ---
for channel in ("Digital Video", "Digital Display"):
    for i in range(6):
        rows.append(("2026-06-01", channel, "CampA", "YOUTUBE.COM", "PKG_PROG",
                     "PL_PROG_UUT", "Reach", "AudC", "Brand Say", None, None, None,
                     3000 + i, 20.0, 12.0, 15.0, 3100 + i))
# --- TV ---
for i in range(6):
    rows.append(("2026-06-01", "TV", None, None, None, None, None, "General", None,
                 "NEXXUS", "Primetime", "COMCAST", 71200 + i * 1000, 600.0 + i * 10,
                 0.0, 0.0, 0.0))

df = prepare_dataframe(pd.DataFrame(rows, columns=COLUMNS))

DROPDOWN_OPTIONS = {s: build_dropdown_options_subtype(df, s) for s in DIGITAL_SUBTYPES}
DROPDOWN_OPTIONS["TV"] = build_dropdown_options_tv(df)


def fresh_app():
    at = AppTest.from_file("app.py")
    at.session_state["active_tool"] = "backfill"
    at.session_state["df"] = df.copy()
    at.session_state["filename"] = "test.xlsx"
    at.session_state["sheet_name"] = "Raw"
    at.session_state["dropdown_options"] = DROPDOWN_OPTIONS
    at.session_state["missing_columns"] = {"DIGITAL": [], "TV": []}
    at.session_state["log"] = []
    at.session_state["applied_indices"] = []
    at.session_state["queue"] = []
    at.session_state["queue_next_id"] = 1
    at.session_state["last_execution_results"] = None
    at.session_state["output_basename"] = "test_backfilled"
    at.session_state["data_version"] = 0
    at.session_state["preview_result"] = None
    return at


def fkey(options_key, mode="DIGITAL", subtype=SUBTYPE_SOCIAL, select_by="Package"):
    """Rebuilds a filter widget's key, which app.py derives from mode/sub-type so that
    switching either gives Streamlit genuinely different widgets."""
    return f"filters_{mode}_{subtype}_{select_by}_{options_key}"


def preview_button(at):
    return next(b for b in at.button if b.label == "Preview")


def click(at, label):
    next(b for b in at.button if b.label == label).click()
    at.run()
    assert not at.exception, f"unexpected exception clicking {label!r}: {at.exception}"


def fill(at, pairs, **key_kwargs):
    """Answers cascading single-select filters in order. Each one has to be set and the
    app re-run before the next becomes available, which is the whole point of the
    cascade: until a filter is answered, everything below it is locked."""
    for options_key, value in pairs:
        at.selectbox(fkey(options_key, **key_kwargs)).select(value)
        at.run()
        assert not at.exception, f"unexpected exception selecting {value!r}: {at.exception}"


SOCIAL_PACKAGE_PATH = [
    ("months", "June 2026"), ("campaigns", "CampA"), ("partners", "PINTEREST"),
    ("packages", "PKG_SOCIAL"), ("ccd_jtbds", "Awareness"), ("audiences", "AudA"),
    ("breakouts", "Brand Say"),
]


# ===========================================================================
# TEST 1 — the app boots on Digital/Social and shows the sub-type selector
# ===========================================================================
at = fresh_app()
at.run()
assert not at.exception, f"unexpected exception: {at.exception}"
subtype_radio = at.radio(key="subtype_selector")
assert list(subtype_radio.options) == DIGITAL_SUBTYPES
assert subtype_radio.value == SUBTYPE_SOCIAL
assert at.radio(key="social_select_by").value == "Package"
print("TEST 1 OK: Digital shows the Social/Reserve/Programmatic selector, Social defaults to Package")

# ===========================================================================
# TEST 1b — the cascade: nothing is preselected, and everything below the first
# unanswered filter is locked until it is answered
# ===========================================================================
month_box = at.selectbox(fkey("months"))
assert month_box.label == "1 · Month", f"filters must be numbered, got {month_box.label!r}"
assert month_box.value is None, "filters must start unanswered so the cascade actually gates"

# with Month unanswered, Campaign onwards are locked placeholders offering nothing
locked = at.selectbox(fkey("campaigns") + "_locked")
assert locked.value is None and list(locked.options) == [], (
    "a filter below an unanswered one must offer no options at all"
)
assert "Pick Month first" in locked.placeholder, locked.placeholder
print("TEST 1b OK: filters are numbered, start empty, and lock everything below them")

# ===========================================================================
# TEST 2 — Social by package: the dependent filters only offer what exists for
# the chosen package, then a weighted Media_Cost backfill end to end
# ===========================================================================
fill(at, SOCIAL_PACKAGE_PATH[:3])  # month, campaign, partner

# this partner has TWO packages, carrying two different JTBDs and three audiences
# between them — the whole point of the next few assertions is that picking one
# package cuts those lists down to what that package really has
assert set(at.selectbox(fkey("packages")).options) == {"PKG_SOCIAL", "PKG_SOCIAL2"}
assert at.selectbox(fkey("ccd_jtbds") + "_locked").options == [], (
    "CCD JTBD must offer nothing at all until a package is chosen"
)

fill(at, [("packages", "PKG_SOCIAL")])
jtbd_box = at.selectbox(fkey("ccd_jtbds"))
assert jtbd_box.label == "5 · CCD JTBD", jtbd_box.label
assert jtbd_box.options == ["Awareness"], (
    f"CCD JTBD must drop 'Consideration' (only PKG_SOCIAL2 has it), got {jtbd_box.options}"
)

fill(at, [("ccd_jtbds", "Awareness")])
audience_box = at.selectbox(fkey("audiences"))
assert audience_box.label == "6 · Audience"
assert set(audience_box.options) == {"AudA", "AudB"}, (
    f"Audience must drop 'AudZ' (only PKG_SOCIAL2 has it), got {audience_box.options}"
)

fill(at, SOCIAL_PACKAGE_PATH[5:])  # audience, breakout

at.number_input(key="target_value_Media_Cost").set_value(1000.0)
at.run()
preview_button(at).click()
at.run()
assert not at.exception, f"unexpected exception: {at.exception}"
pr = at.session_state["preview_result"]
assert pr is not None, f"expected a preview, errors were: {[e.value for e in at.error]}"
assert pr["subtype"] == SUBTYPE_SOCIAL
assert pr["operation"] == "MC_WEIGHTED"
assert pr["rows"] == 10, f"expected the 10 AudA rows, got {pr['rows']}"
assert abs(pr["resulting_sum"] - 1000.0) < 0.01
assert "Social" in pr["operation_label"] and "Weighted by impressions" in pr["operation_label"]
print("TEST 2 OK: dependent filters narrowed to the package; weighted preview correct")

click(at, "Add to queue")
assert len(at.session_state["queue"]) == 1
assert at.session_state["queue"][0]["operation"] == "MC_WEIGHTED"
print("TEST 3 OK: queued with its operation recorded")

# ===========================================================================
# TEST 4 — the lock rejects a second backfill on rows already queued
# ===========================================================================
at.number_input(key="target_value_Media_Cost").set_value(2000.0)
preview_button(at).click()
at.run()
assert not at.exception
assert at.session_state["preview_result"] is None, "the same rows must not preview twice"
assert any("overlap" in e.value for e in at.error), [e.value for e in at.error]
print("TEST 4 OK: re-selecting already-queued rows is blocked by the row-overlap lock")

# ===========================================================================
# TEST 5 — switching to a copy operation hides the target input
# ===========================================================================
at.selectbox(key="operation_selector_Media_Cost").select("MC_COPY_PRISMA")
at.run()
assert not at.exception, f"unexpected exception: {at.exception}"
assert not at.number_input, "a copy operation must not ask for a target total"
print("TEST 5 OK: copy operations hide the target input")

# ===========================================================================
# TEST 6 — Reserve with multi-select partners/audiences
# ===========================================================================
at2 = fresh_app()
at2.run()
at2.radio(key="subtype_selector").set_value(SUBTYPE_RESERVE)
at2.run()
assert not at2.exception, f"unexpected exception: {at2.exception}"

reserve_key = lambda k: fkey(k, subtype=SUBTYPE_RESERVE, select_by="None")

# the multi-selects sit below two single-selects, so they are locked until those
# are answered — the cascade applies to every sub-type, not just Social
# a locked filter is always rendered as an empty, disabled selectbox, whether the
# real filter is single- or multi-value
assert at2.selectbox(reserve_key("partners") + "_locked").options == []
fill(at2, [("months", "June 2026"), ("campaigns", "CampA")],
     subtype=SUBTYPE_RESERVE, select_by="None")

partners = at2.multiselect(reserve_key("partners"))
audiences = at2.multiselect(reserve_key("audiences"))
assert partners.label == "3 · Partner (one, several or all)", partners.label
assert set(partners.value) == {"AMAZON.COM", "PEACOCK"}, (
    f"multi-select filters must default to everything selected, got {partners.value}"
)
assert set(audiences.value) == {"AudA", "AudB"}

at2.number_input(key="target_value_Media_Cost").set_value(800.0)
at2.run()
preview_button(at2).click()
at2.run()
assert not at2.exception, f"unexpected exception: {at2.exception}"
pr2 = at2.session_state["preview_result"]
assert pr2 is not None, f"errors: {[e.value for e in at2.error]}"
assert pr2["rows"] == 20, f"all 4 partner/audience combos = 20 rows, got {pr2['rows']}"
assert pr2["subtype"] == SUBTYPE_RESERVE
print("TEST 6 OK: Reserve multi-selects default to all and select every matching row")

# narrowing to one partner really narrows the subset
at2.multiselect(reserve_key("partners")).set_value(["PEACOCK"])
at2.run()
preview_button(at2).click()
at2.run()
assert not at2.exception
pr2b = at2.session_state["preview_result"]
assert pr2b is not None and pr2b["rows"] == 10, f"expected 10 PEACOCK rows, got {pr2b}"
print("TEST 7 OK: narrowing a multi-select narrows the subset")

# ===========================================================================
# TEST 8 — even allocation writes the same value on every row
# ===========================================================================
at2.selectbox(key="operation_selector_Media_Cost").select("MC_EVEN")
at2.run()
at2.number_input(key="target_value_Media_Cost").set_value(500.0)
preview_button(at2).click()
at2.run()
assert not at2.exception
pr_even = at2.session_state["preview_result"]
assert pr_even is not None and pr_even["operation"] == "MC_EVEN"
assert abs(pr_even["resulting_sum"] - 500.0) < 0.01

click(at2, "Add to queue")
click(at2, "Run full queue (1)")
result_df = at2.session_state["df"]
touched = result_df[(result_df["Raw_Partner"] == "PEACOCK")]
assert len(touched) == 10
assert abs(touched["Media_Cost"].sum() - 500.0) < 0.01
assert touched["Media_Cost"].nunique() == 1, "even allocation must put the same value on each row"
assert abs(touched["Media_Cost"].iloc[0] - 50.0) < 0.01
print("TEST 8 OK: even allocation executed, every row got target/n")

# the log records the operation, and the applied rows are tracked for the lock
log = at2.session_state["log"]
assert len(log) == 1
assert log[0]["Operation"] == "Even allocation across rows"
assert log[0]["Type"] == SUBTYPE_RESERVE
assert log[0]["Field"] == "Media_Cost"
assert len(at2.session_state["applied_indices"]) == 1
print("TEST 9 OK: the log carries Operation/Type, and applied rows are recorded")

# ===========================================================================
# TEST 10 — the lock also blocks rows already APPLIED (not just queued)
# ===========================================================================
preview_button(at2).click()
at2.run()
assert at2.session_state["preview_result"] is None
assert any("already applied" in e.value for e in at2.error), [e.value for e in at2.error]
print("TEST 10 OK: rows already applied this session are locked too")

# ===========================================================================
# TEST 11 — Programmatic: copy Impressions from Weighted Planned Units
# ===========================================================================
at3 = fresh_app()
at3.run()
at3.radio(key="subtype_selector").set_value(SUBTYPE_PROGRAMMATIC)
at3.run()
assert not at3.exception, f"unexpected exception: {at3.exception}"

prog_kw = {"subtype": SUBTYPE_PROGRAMMATIC, "select_by": "None"}
fill(at3, [("months", "June 2026"), ("campaigns", "CampA"), ("partners", "YOUTUBE.COM")],
     **prog_kw)

channels = at3.multiselect(fkey("channels", **prog_kw))
assert set(channels.value) == {"Digital Video", "Digital Display"}
fill(at3, [("packages", "PKG_PROG")], **prog_kw)

at3.radio(key="field_selector").set_value("Impressions")
at3.run()
at3.selectbox(key="operation_selector_Impressions").select("IMPR_COPY_WPU")
at3.run()
assert not at3.exception, f"unexpected exception: {at3.exception}"
assert not at3.number_input, "the copy operation needs no target"

preview_button(at3).click()
at3.run()
assert not at3.exception, f"unexpected exception: {at3.exception}"
pr3 = at3.session_state["preview_result"]
assert pr3 is not None, f"errors: {[e.value for e in at3.error]}"
assert pr3["target_field"] == "Impressions"
assert pr3["target_value"] is None
assert pr3["rows"] == 12
expected_sum = float(df[df["Package_Placement_Name"] == "PL_PROG_UUT"]["Weighted Planned Units"].sum())
assert abs(pr3["resulting_sum"] - expected_sum) < 1, (
    f"expected the WPU total {expected_sum}, got {pr3['resulting_sum']}"
)

click(at3, "Add to queue")
click(at3, "Run full queue (1)")
prog_rows = at3.session_state["df"]
prog_rows = prog_rows[prog_rows["Package_Placement_Name"] == "PL_PROG_UUT"]
assert abs(prog_rows["Impressions"].sum() - expected_sum) < 1
assert (prog_rows["Impressions"] == prog_rows["Impressions"].round()).all(), (
    "copied impressions must still be whole numbers"
)
assert at3.session_state["log"][0]["Operation"] == "Copy from Weighted Planned Units"
print("TEST 11 OK: Programmatic Impressions copy executed and rounded, logged with its operation")

# ===========================================================================
# TEST 12 — Social by placement targets exactly one placement
# ===========================================================================
at4 = fresh_app()
at4.run()
at4.radio(key="social_select_by").set_value("Placement")
at4.run()
assert not at4.exception, f"unexpected exception: {at4.exception}"
fill(at4, [("months", "June 2026"), ("campaigns", "CampA"), ("partners", "PINTEREST")],
     select_by="Placement")
placement_select = at4.selectbox(fkey("placements", select_by="Placement"))
assert placement_select.label == "4 · Placement", placement_select.label
assert set(placement_select.options) == {
    "PL_SOCIAL_A_UNE", "PL_SOCIAL_B_UNE", "PL_SOCIAL_C_UNE"
}, placement_select.options
placement_select.select("PL_SOCIAL_B_UNE")
at4.run()
at4.number_input(key="target_value_Media_Cost").set_value(400.0)
at4.run()
preview_button(at4).click()
at4.run()
assert not at4.exception, f"unexpected exception: {at4.exception}"
pr4 = at4.session_state["preview_result"]
assert pr4 is not None, f"errors: {[e.value for e in at4.error]}"
assert pr4["rows"] == 10
assert "Placement" in pr4["filters"]
assert pr4["filters"]["Placement"] == "PL_SOCIAL_B_UNE"
print("TEST 12 OK: Social/Placement path selects a single placement's rows")

# ===========================================================================
# TEST 13 — TV keeps working
# ===========================================================================
at5 = fresh_app()
at5.run()
at5.radio(key="mode_selector").set_value("TV")
at5.run()
assert not at5.exception, f"unexpected exception: {at5.exception}"
fill(at5, [("months", "June 2026"), ("brands", "NEXXUS"), ("audiences", "General"),
           ("dayparts", "Primetime"), ("networks", "COMCAST")],
     mode="TV", subtype="None", select_by="None")
at5.number_input(key="target_value_Media_Cost").set_value(1200.0)
at5.run()
preview_button(at5).click()
at5.run()
assert not at5.exception, f"unexpected exception: {at5.exception}"
pr5 = at5.session_state["preview_result"]
assert pr5 is not None, f"errors: {[e.value for e in at5.error]}"
assert pr5["mode"] == "TV" and pr5["subtype"] is None
assert pr5["rows"] == 6
assert abs(pr5["resulting_sum"] - 1200.0) < 0.01
click(at5, "Add to queue")
click(at5, "Run full queue (1)")
tv_after = at5.session_state["df"]
tv_after = tv_after[tv_after["Channel"] == "TV"]
assert abs(tv_after["Media_Cost"].sum() - 1200.0) < 0.01
assert at5.session_state["log"][0]["Mode"] == "TV"
assert at5.session_state["log"][0]["Operation"] == "Weighted by impressions"
print("TEST 13 OK: TV mode still previews, queues, executes and logs its operation")

# ===========================================================================
# TEST 14 — Digital accepts a target of exactly 0 through the real widgets (this is
# the bug report this round of fixes addresses: typing 0 used to hit "The target
# must be a positive number." before the preview was even computed)
# ===========================================================================
at6 = fresh_app()
at6.run()
fill(at6, [("months", "June 2026"), ("campaigns", "CampA"), ("partners", "PINTEREST"),
           ("packages", "PKG_SOCIAL2"), ("ccd_jtbds", "Consideration"),
           ("audiences", "AudZ"), ("breakouts", "Brand Say")])
at6.number_input(key="target_value_Media_Cost").set_value(0.0)
at6.run()
preview_button(at6).click()
at6.run()
assert not at6.exception, f"unexpected exception: {at6.exception}"
assert not at6.error, f"a target of 0 must not be rejected on Digital: {[e.value for e in at6.error]}"
pr6 = at6.session_state["preview_result"]
assert pr6 is not None, "expected a successful preview for target=0 on Digital"
assert pr6["target_value"] == 0.0
assert pr6["resulting_sum"] == 0.0
print("TEST 14 OK: Digital accepts a target of 0 via the real widgets, no longer blocked")

print("ALL APPTEST FLOW TESTS PASSED")
