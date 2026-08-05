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

# ---------------------------------------------------------------------------
# TEST 1 — the home menu itself
# ---------------------------------------------------------------------------
at = AppTest.from_file("app.py")
at.run()
assert not at.exception, f"unexpected exception on the home menu: {at.exception}"

markdown_text = " ".join(m.value for m in at.markdown)
assert "M.E.R.I.T APP" in markdown_text
assert "Media Evaluation, Reconciliation" in markdown_text

open_buttons = [b for b in at.button if b.label == "Open"]
assert len(open_buttons) == 2, f"expected 2 'Open' buttons, found {len(open_buttons)}"
print("TEST 1 OK: home menu renders the title and both tool cards")

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

print("ALL HOME/DATA-CAVEATS APPTEST FLOW TESTS PASSED")
