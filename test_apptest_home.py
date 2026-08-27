"""End-to-end tests for the M.E.R.I.T. home menu (app.py) and, for Data Caveats, the
settings/generate/download flow through real Streamlit widgets. File upload itself can't
be simulated by streamlit.testing.v1.AppTest (same limitation noted throughout this
project), so the Data Caveats flow is exercised by seeding st.session_state.caveats_data
with what "Read files" would have produced — using the real read_delivery_file function,
not a hand-built stand-in."""
from io import BytesIO

import pandas as pd
from streamlit.testing.v1 import AppTest

from tools.data_caveats import read_delivery_file
from tools.tv_standardization import load_mappings, read_tv_file

# ---------------------------------------------------------------------------
# TEST 1 — the home menu itself
# ---------------------------------------------------------------------------
at = AppTest.from_file("app.py")
at.run()
assert not at.exception, f"unexpected exception on the home menu: {at.exception}"

markdown_text = " ".join(m.value for m in at.markdown)
assert "M.E.R.I.T. APP" in markdown_text
assert "Media Evaluation, Reconciliation" in markdown_text

open_buttons = [b for b in at.button if b.label == "Open"]
assert len(open_buttons) == 5, f"expected 5 'Open' buttons, found {len(open_buttons)}"
# the home lays the five cards out 3-per-row, numbered in the order they appear
assert [b.key for b in open_buttons] == [
    "open_inspect", "open_tv", "open_backfill", "open_deliver", "open_caveats"
], [b.key for b in open_buttons]
print("TEST 1 OK: home menu renders the title and all five tool cards, in order")

# ---------------------------------------------------------------------------
# TEST 2 — opening RROI Manual Backfill and returning home
# ---------------------------------------------------------------------------
at.button(key="open_backfill").click()
at.run()
assert not at.exception, f"unexpected exception opening the backfill tool: {at.exception}"
assert at.session_state["active_tool"] == "backfill"
assert any(t.value == "RROI Manual Backfill" for t in at.title)
assert any(b.label == "← Back to menu" for b in at.button)

next(b for b in at.button if b.label == "← Back to menu").click()
at.run()
assert not at.exception, f"unexpected exception returning to the menu: {at.exception}"
assert at.session_state["active_tool"] is None
assert any(b.label == "Open" for b in at.button)
print("TEST 2 OK: RROI Manual Backfill opens and 'Back to menu' returns home")

# ---------------------------------------------------------------------------
# TEST 3 — opening Data Caveats Generator and returning home
# ---------------------------------------------------------------------------
at2 = AppTest.from_file("app.py")
at2.run()
at2.button(key="open_caveats").click()
at2.run()
assert not at2.exception, f"unexpected exception opening Data Caveats: {at2.exception}"
assert at2.session_state["active_tool"] == "caveats"
assert any(t.value == "Data Caveats Generator" for t in at2.title)

next(b for b in at2.button if b.label == "← Back to menu").click()
at2.run()
assert not at2.exception
assert at2.session_state["active_tool"] is None
print("TEST 3 OK: Data Caveats Generator opens and 'Back to menu' returns home")

# ---------------------------------------------------------------------------
# TEST 4 — Data Caveats: settings -> generate -> download, via real widgets,
# seeding caveats_data the way "Read files" would have left it (using the real
# read_delivery_file function, not a hand-built stand-in for its output shape)
# ---------------------------------------------------------------------------
rows = [
    {"Channel": "Digital Social", "Date": "2026-06-01", "Brand": "BrandA",
     "Category": "Hair Care", "Prisma_Campaign_Secondary": "CampX", "Raw_Partner": "PINTEREST",
     "Package_Placement_Name": "PL1_UNE", "Retailer": "(all)",
     "Impressions": None, "Media_Cost": 5.0, "GRPs": None, "Video_Views": None},
    {"Channel": "Digital Social", "Date": "2026-06-02", "Brand": "BrandA",
     "Category": "Hair Care", "Prisma_Campaign_Secondary": "CampX", "Raw_Partner": "PINTEREST",
     "Package_Placement_Name": "PL1_UNE", "Retailer": "(all)",
     "Impressions": None, "Media_Cost": 7.0, "GRPs": None, "Video_Views": None},
]
buf = BytesIO()
pd.DataFrame(rows).to_excel(buf, index=False)
data_df, sheet, candidates, dropped = read_delivery_file(buf.getvalue(), "brandA.xlsx")

at3 = AppTest.from_file("app.py")
at3.session_state["active_tool"] = "caveats"
at3.session_state["caveats_data"] = data_df
at3.session_state["caveats_file_summaries"] = [
    {"File": "brandA.xlsx", "Sheet": sheet, "Rows": len(data_df), "Brand(s)": "BrandA"}
]
at3.session_state["caveats_warnings"] = []
at3.session_state["caveats_errors"] = []
at3.session_state["caveats_results"] = None
at3.run()
assert not at3.exception, f"unexpected exception rendering the settings screen: {at3.exception}"

# with only one month in the data, render() shows a caption instead of a range slider
caption_text = " ".join(c.value for c in at3.caption)
assert "Jun'26" in caption_text, f"expected the single detected month in a caption: {caption_text}"

next(b for b in at3.button if b.label == "Generate Data Caveat Logs").click()
at3.run()
assert not at3.exception, f"unexpected exception generating: {at3.exception}"

results = at3.session_state["caveats_results"]
assert results is not None and not results["stopped"]
assert results["n_files"] == 1
summary = {r["Brand"]: r for r in results["summary_rows"]}
assert summary["BrandA"]["Caveats"] == 1
assert summary["BrandA"]["Null Impr"] == 1

download_buttons = [b for b in at3.download_button if "Download all files" in b.label]
assert len(download_buttons) == 1
assert len(results["zip_bytes"]) > 0, "the generated zip must contain real bytes"
print("TEST 4 OK: Data Caveats settings -> generate -> download works through real widgets")

# ---------------------------------------------------------------------------
# TEST 5 — TV Data Standardization: normalize -> pick output format -> generate ->
# download, via real widgets, seeding tv_data the way "Standardize" would have left it
# (using the real read_tv_file function on a file shaped like a real TV pull, not a
# hand-built stand-in for its output shape)
# ---------------------------------------------------------------------------
mappings = load_mappings()
header = ["ESTIMATE NAME", "PACKAGE", "NETWORK", "QUARTER", "DAYPART", "PROGRAM NAME",
          "DATE", "MONTH", "NETWORK", "AFFID DATE", "AFFID TIME", "LEN", "UNITS",
          "ASSIGNED GROSS", "ASSIGNED NET", "P2+ ACTIMP", "P2+ ESTIMP"]
tv_raw_row = ["25/26 CABLE SPORTS", "PKG", "ACCN ACC NETWORK", "APR-JUN", "SPORTS", "PROG",
              "06/08/26", "JUN", "ACCN", "JUN10", "653P", "15", 1, 128.0, 108.8, 0.0, 3.5]
preamble = [["DETAILS OF REQUEST"] + [None] * 16 for _ in range(32)]
raw_buf = BytesIO()
pd.DataFrame(preamble + [header] + [tv_raw_row]).to_excel(raw_buf, index=False, header=False)
tv_df, _ = read_tv_file(raw_buf.getvalue(), "DHC test.xlsx", mappings)

at5 = AppTest.from_file("app.py")
at5.session_state["active_tool"] = "tv"
at5.session_state["tv_data"] = {"DHC": tv_df}
at5.session_state["tv_file_summaries"] = [
    {"File": "DHC test.xlsx", "Product Code": "DHC", "Rows": len(tv_df), "Blank AFFID DATE": 0}
]
at5.session_state["tv_warnings"] = []
at5.session_state["tv_errors"] = []
at5.session_state["tv_output"] = None
at5.run()
assert not at5.exception, f"unexpected exception rendering the TV settings screen: {at5.exception}"
assert not any("Platform export" in u.label for u in at5.file_uploader), (
    "the platform-export uploader must be gone -- this tool is normalize-only"
)

radio_options = next(r for r in at5.radio if r.key == "tv_output_format").options
assert radio_options == ["Separate files per product", "One consolidated file", "Both"], radio_options

next(b for b in at5.button if b.label == "Generate").click()
at5.run()
assert not at5.exception, f"unexpected exception generating: {at5.exception}"

tv_output = at5.session_state["tv_output"]
assert tv_output is not None and len(tv_output["bytes"]) > 0, "the generated file must have bytes"
assert tv_output["filename"].endswith(".zip"), "the default 'separate' choice must produce a zip"
assert len([b for b in at5.download_button if tv_output["filename"] in b.label]) == 1
print("TEST 5 OK: TV Data Standardization normalize -> output format -> generate -> download works")

# ---------------------------------------------------------------------------
# TEST 6 — the two tools contributed from merit_V1 mount cleanly on their own
# session-state namespaces and expose their upload entry point
# ---------------------------------------------------------------------------
for tool_key, expected_title, uploader_key in (
    ("inspect", "Merit Inspect", "inspect_back"),
    ("deliver", "Merit Deliver", "deliver_back"),
):
    at6 = AppTest.from_file("app.py")
    at6.session_state["active_tool"] = tool_key
    at6.run(timeout=120)
    assert not at6.exception, f"{tool_key}: unexpected exception: {at6.exception}"
    assert any(t.value == expected_title for t in at6.title), \
        f"{tool_key}: expected the title {expected_title!r}"
    assert any(b.key == uploader_key for b in at6.button), \
        f"{tool_key}: expected its own keyed back button ({uploader_key})"
    assert len(at6.file_uploader) >= 1, f"{tool_key}: expected at least one file uploader"
    # its results key starts empty, and is namespaced so it can't collide with another tool
    assert at6.session_state[f"{tool_key}_results"] is None
print("TEST 6 OK: Merit Inspect and Merit Deliver mount, render and namespace their state")

print("ALL HOME/DATA-CAVEATS APPTEST FLOW TESTS PASSED")
