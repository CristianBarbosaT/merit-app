import pandas as pd
from streamlit.testing.v1 import AppTest

from app import prepare_dataframe, build_dropdown_options_digital, build_dropdown_options_tv

digital_rows = []
for i in range(50):
    digital_rows.append((
        "2026-06-01", "Digital Social", "CampA_Secondary", "PINTEREST", "P3GHJCX_UNE_NEX_038",
        "Awareness", "Crystallizer Queen", "Brand Say", 1000 + i, 0.0, None, None, None,
    ))
tv_rows = []
for i in range(6):
    tv_rows.append((
        "2026-06-01", "TV", None, None, None, None, "General", None,
        71200 + i * 1000, 600.0 + i * 10, "NEXXUS", "Primetime", "COMCAST CORPORATION",
    ))

df = pd.DataFrame(digital_rows + tv_rows, columns=[
    "Date", "Channel", "Prisma_Campaign_Secondary", "Raw_Partner", "Package Name",
    "CCD JTBD", "Audience", "Breakout", "Impressions", "Media_Cost", "Brand",
    "Daypart", "Network_Name",
])
df = prepare_dataframe(df)


def fresh_app():
    at = AppTest.from_file("app.py")
    at.session_state["df"] = df.copy()
    at.session_state["filename"] = "test.xlsx"
    at.session_state["sheet_name"] = "Raw"
    at.session_state["dropdown_options"] = {
        "DIGITAL": build_dropdown_options_digital(df),
        "TV": build_dropdown_options_tv(df),
    }
    at.session_state["missing_columns"] = {"DIGITAL": [], "TV": []}
    at.session_state["log"] = []
    at.session_state["queue"] = []
    at.session_state["queue_next_id"] = 1
    at.session_state["last_execution_results"] = None
    at.session_state["output_basename"] = "test_backfilled"
    at.session_state["data_version"] = 0
    at.session_state["preview_result"] = None
    return at


def add_to_queue(at):
    add_btn = next(b for b in at.button if b.label == "Add to queue")
    add_btn.click()
    at.run()
    assert not at.exception, f"unexpected exception adding to queue: {at.exception}"


# --- Digital flow still works exactly as before (regression check) ---
at = fresh_app()
at.run()
assert not at.exception

at.number_input[0].set_value(1000.0)
at.button[1].click()
at.run()
assert not at.exception, f"unexpected exception: {at.exception}"
pr = at.session_state["preview_result"]
assert pr is not None and pr["mode"] == "DIGITAL" and pr["target_field"] == "Media_Cost"
assert pr["rows"] == 50
add_to_queue(at)
assert len(at.session_state["queue"]) == 1
assert at.session_state["queue"][0]["mode"] == "DIGITAL"
print("TEST 1 OK: Digital flow unchanged, item queued with mode=DIGITAL")

# --- Switch to TV mode, preview an Impressions backfill ---
at.radio(key="mode_selector").set_value("TV")
at.run()
assert not at.exception, f"unexpected exception switching to TV: {at.exception}"

at.selectbox[5].select("Impressions")  # "Field to backfill"
at.run()
at.number_input[0].set_value(800000.0)
at.button[1].click()
at.run()
assert not at.exception, f"unexpected exception on TV preview: {at.exception}"
pr = at.session_state["preview_result"]
assert pr is not None, "TV preview should have succeeded"
assert pr["mode"] == "TV"
assert pr["target_field"] == "Impressions"
assert pr["weight_field"] == "Media_Cost"
assert pr["rows"] == 6
print("TEST 2 OK: TV preview (Impressions target) computed correctly")

add_to_queue(at)
assert len(at.session_state["queue"]) == 2
tv_item = at.session_state["queue"][1]
assert tv_item["mode"] == "TV" and tv_item["target_field"] == "Impressions"
print("TEST 3 OK: TV item queued alongside the Digital item")

# --- Lock: trying to queue Media_Cost on the SAME TV subset must be blocked ---
at.selectbox[5].select("Media_Cost")
at.run()
at.number_input[0].set_value(12000.0)
at.button[1].click()
at.run()
assert not at.exception, f"unexpected exception: {at.exception}"
assert at.session_state["preview_result"] is None, "locked subset must not produce a preview"
assert len(at.error) >= 1
assert any("already has a" in e.value for e in at.error), (
    f"expected a lock error message, got: {[e.value for e in at.error]}"
)
print("TEST 4 OK: same TV subset with a different field is blocked by the one-backfill-per-subset lock")

# --- A DIFFERENT TV subset (different Daypart) must NOT be locked ---
# add a second, distinct TV subset to the dataframe so we can prove it's independent
distinct_rows = []
for i in range(3):
    distinct_rows.append((
        "2026-06-01", "TV", None, None, None, None, "General", None,
        10000 + i, 0.0, "NEXXUS", "Daytime", "COMCAST CORPORATION",
    ))
df2 = pd.concat([df, pd.DataFrame(distinct_rows, columns=df.columns.drop(["Month_Label", "Parent_PCODE"]))], ignore_index=True)
df2 = prepare_dataframe(df2)
at.session_state["df"] = df2
at.session_state["dropdown_options"] = {
    "DIGITAL": build_dropdown_options_digital(df2),
    "TV": build_dropdown_options_tv(df2),
}
at.run()
assert not at.exception

at.selectbox[3].select("Daytime")  # Daypart
at.run()
at.selectbox[5].select("Media_Cost")
at.run()
at.number_input[0].set_value(500.0)
at.button[1].click()
at.run()
assert not at.exception, f"unexpected exception: {at.exception}"
assert at.session_state["preview_result"] is not None, "a distinct TV subset (different Daypart) must not be locked"
print("TEST 5 OK: a different TV subset (different Daypart) is unaffected by the lock")

add_to_queue(at)
assert len(at.session_state["queue"]) == 3
print("TEST 6 OK: third (distinct) item queued successfully")

# --- Removal by qid still works with mixed Digital/TV items ---
qids = [item["qid"] for item in at.session_state["queue"]]
assert qids == [1, 2, 3]
remove_selectbox = at.selectbox(key="qid_to_remove")
remove_selectbox.select(2)  # remove the TV Impressions item
at.run()
remove_btn = next(b for b in at.button if b.label == "Remove selected")
remove_btn.click()
at.run()
assert not at.exception, f"unexpected exception: {at.exception}"
remaining_qids = [item["qid"] for item in at.session_state["queue"]]
assert remaining_qids == [1, 3], f"expected [1, 3], got {remaining_qids}"
print("TEST 7 OK: 'Remove from queue' removes exactly the selected mixed-mode item")

# --- Execute the remaining mixed queue (Digital Media_Cost + TV Media_Cost/Daytime) ---
exec_btn = next(b for b in at.button if "Run full queue" in b.label)
exec_btn.click()
at.run()
assert not at.exception, f"unexpected exception executing queue: {at.exception}"
assert at.session_state["queue"] == []
assert len(at.session_state["log"]) == 2
modes_in_log = sorted(entry["Mode"] for entry in at.session_state["log"])
assert modes_in_log == ["DIGITAL", "TV"], f"expected both modes logged, got {modes_in_log}"
fields_in_log = sorted(entry["Field"] for entry in at.session_state["log"])
assert fields_in_log == ["Media_Cost", "Media_Cost"]

digital_total = at.session_state["df"][at.session_state["df"]["Channel"] != "TV"]["Media_Cost"].sum()
assert abs(digital_total - 1000.0) < 0.01, f"expected Digital Media_Cost total 1000.0, got {digital_total}"

tv_daytime_mask = (at.session_state["df"]["Channel"] == "TV") & (at.session_state["df"]["Daypart"] == "Daytime")
tv_daytime_total = at.session_state["df"].loc[tv_daytime_mask, "Media_Cost"].sum()
assert abs(tv_daytime_total - 500.0) < 0.01, f"expected TV/Daytime Media_Cost total 500.0, got {tv_daytime_total}"

# the TV Impressions item was removed from the queue before execution, so the original
# Primetime TV subset's Impressions must remain untouched (still the raw seeded values)
tv_primetime_mask = (at.session_state["df"]["Channel"] == "TV") & (at.session_state["df"]["Daypart"] == "Primetime")
tv_primetime_impressions = at.session_state["df"].loc[tv_primetime_mask, "Impressions"].tolist()
assert tv_primetime_impressions == [71200, 72200, 73200, 74200, 75200, 76200], (
    f"unexecuted/removed TV Impressions item must not have modified data: {tv_primetime_impressions}"
)
print("TEST 8 OK: mixed queue execution wrote Media_Cost for both Digital and TV correctly; "
      "removed item never touched the data")

# --- TV-only rule: 0 Impressions + target 0 -> Media_Cost backfilled to 0 (through the real UI) ---
zero_tv_rows = [
    ("2026-06-01", "TV", None, None, None, None, "General", None, 0, 45.0, "GHOSTBRAND", "Overnight", "GHOST NETWORK"),
    ("2026-06-02", "TV", None, None, None, None, "General", None, 0, 12.0, "GHOSTBRAND", "Overnight", "GHOST NETWORK"),
]
df3 = pd.concat(
    [df, pd.DataFrame(zero_tv_rows, columns=df.columns.drop(["Month_Label", "Parent_PCODE"]))],
    ignore_index=True,
)
df3 = prepare_dataframe(df3)

at2 = fresh_app()
at2.session_state["df"] = df3
at2.session_state["dropdown_options"] = {
    "DIGITAL": build_dropdown_options_digital(df3),
    "TV": build_dropdown_options_tv(df3),
}
at2.run()  # first render registers the "mode_selector" widget key (defaults to "Digital")
assert not at2.exception, f"unexpected exception: {at2.exception}"

at2.radio(key="mode_selector").set_value("TV")
at2.run()
assert not at2.exception, f"unexpected exception: {at2.exception}"

at2.selectbox[1].select("GHOSTBRAND")  # Brand
at2.run()
at2.selectbox[3].select("Overnight")  # Daypart
at2.run()
at2.selectbox[4].select("GHOST NETWORK")  # Network_Name
at2.run()
at2.selectbox[5].select("Media_Cost")  # Field to backfill
at2.run()
at2.number_input[0].set_value(0.0)  # target = 0, via the real widget (min_value=0.0 already allows this)
at2.button[1].click()
at2.run()
assert not at2.exception, f"unexpected exception: {at2.exception}"

pr2 = at2.session_state["preview_result"]
assert pr2 is not None, (
    f"expected TV target=0 with 0 impressions to succeed, got errors: {[e.value for e in at2.error]}"
)
assert pr2["rows"] == 2
assert pr2["target_value"] == 0
print("TEST 9 OK: TV target=0 on a 0-impressions subset previews successfully via the real widgets")

add_btn2 = next(b for b in at2.button if b.label == "Add to queue")
add_btn2.click()
at2.run()
exec_btn2 = next(b for b in at2.button if "Run full queue" in b.label)
exec_btn2.click()
at2.run()
assert not at2.exception, f"unexpected exception executing zero-target queue: {at2.exception}"

ghost_mask = at2.session_state["df"]["Network_Name"] == "GHOST NETWORK"
ghost_media_cost = at2.session_state["df"].loc[ghost_mask, "Media_Cost"].tolist()
assert ghost_media_cost == [0.0, 0.0], f"expected both rows backfilled to 0.0, got {ghost_media_cost}"
assert at2.session_state["log"][-1]["Field"] == "Media_Cost"
assert at2.session_state["log"][-1]["Target_Value"] == 0
print("TEST 10 OK: executing the queue actually wrote Media_Cost=0 for the 0-impressions TV subset")

# --- Regression: typing a target value, then switching "Field to backfill" before
# submitting, must NOT reset the typed value back to 0. The number_input's label
# changes with target_field ("Target Media_Cost" -> "Target Impressions"); without a
# stable explicit key, Streamlit treats the relabeled widget as brand new and silently
# drops whatever the user typed under the old label. ---
at3 = fresh_app()
at3.run()
at3.radio(key="mode_selector").set_value("TV")
at3.run()
assert not at3.exception, f"unexpected exception: {at3.exception}"
assert at3.selectbox[5].value == "Media_Cost", "should default to Media_Cost"

# user types a target value while the field is still Media_Cost...
at3.number_input[0].set_value(500.0)
# ...then switches the field to Impressions before ever clicking Preview
at3.selectbox[5].select("Impressions")
at3.run()
assert not at3.exception, f"unexpected exception: {at3.exception}"
assert at3.number_input[0].label == "Target Impressions"
assert at3.number_input[0].value == 500.0, (
    f"switching 'Field to backfill' must not reset the typed target value, "
    f"got {at3.number_input[0].value}"
)

# and the very first Preview click (not a second one) must use that value
at3.button[1].click()
at3.run()
assert not at3.exception, f"unexpected exception: {at3.exception}"
pr3 = at3.session_state["preview_result"]
assert pr3 is not None, f"expected preview to succeed on the first click, got errors: {[e.value for e in at3.error]}"
assert pr3["target_value"] == 500.0, f"expected target_value 500.0 on first Preview click, got {pr3['target_value']}"
print("TEST 11 OK: switching 'Field to backfill' preserves the typed target; first Preview click works")

print("ALL APPTEST FLOW TESTS PASSED")
