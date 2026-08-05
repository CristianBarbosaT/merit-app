import time
import pandas as pd
from io import BytesIO
from streamlit.testing.v1 import AppTest

from tools.rroi_backfill import prepare_dataframe, build_dropdown_options_subtype, DIGITAL_SUBTYPES

rows = []
for i in range(3000):
    rows.append((
        "2026-06-01", "Digital Social", "CampA_Secondary", "PINTEREST", "P3GHJCX_UNE_NEX_038",
        "P3GHJCX_UNE_NEX_038_PINTEREST_1x1", "Awareness", "Crystallizer Queen", "Brand Say",
        1000 + i, 0.0,
    ))

df = pd.DataFrame(rows, columns=[
    "Date", "Channel", "Prisma_Campaign_Secondary", "Raw_Partner", "Package Name",
    "Package_Placement_Name", "CCD JTBD", "Audience", "Breakout", "Impressions", "Media_Cost",
])
df = prepare_dataframe(df)

at = AppTest.from_file("app.py")
at.session_state["active_tool"] = "backfill"
at.session_state["df"] = df.copy()
at.session_state["filename"] = "test.xlsx"
at.session_state["sheet_name"] = "Raw"
dropdown_options = {s: build_dropdown_options_subtype(df, s) for s in DIGITAL_SUBTYPES}
dropdown_options["TV"] = None
at.session_state["dropdown_options"] = dropdown_options
at.session_state["missing_columns"] = {"DIGITAL": [], "TV": ["Brand", "Daypart", "Network_Name"]}
at.session_state["log"] = []
at.session_state["applied_indices"] = []
at.session_state["queue"] = []
at.session_state["queue_next_id"] = 1
at.session_state["last_execution_results"] = None
at.session_state["output_basename"] = "test_backfilled"
at.session_state["data_version"] = 0
at.session_state["preview_result"] = None

at.run()
assert not at.exception, f"unexpected exception: {at.exception}"

# first render already generated the excel once (data_version=0). Re-run several times
# WITHOUT changing data_version (simulating unrelated interactions, e.g. typing in the
# filename box) and confirm it's cheap (cache hit), then bump version and confirm the
# output actually changes to reflect new Media_Cost values.

t0 = time.perf_counter()
for _ in range(5):
    at.run()
    assert not at.exception, f"unexpected exception on repeat rerun: {at.exception}"
t1 = time.perf_counter()
print(f"5 reruns with unchanged data_version took {t1 - t0:.3f}s total (should be fast, cache hits)")

from tools.rroi_backfill import build_excel_bytes, build_log_csv_bytes

bytes_v0_a = build_excel_bytes(at.session_state["df"], at.session_state["data_version"], at.session_state["sheet_name"])
bytes_v0_b = build_excel_bytes(at.session_state["df"], at.session_state["data_version"], at.session_state["sheet_name"])
assert bytes_v0_a == bytes_v0_b, "identical version should produce byte-identical cached output"
print("TEST OK: same data_version returns identical cached bytes")

# now mutate Media_Cost directly (simulating what queue execution does) and bump version
at.session_state["df"].loc[at.session_state["df"].index[:10], "Media_Cost"] = 999.0
at.session_state["data_version"] += 1

bytes_v1 = build_excel_bytes(at.session_state["df"], at.session_state["data_version"], at.session_state["sheet_name"])
assert bytes_v1 != bytes_v0_a, "bumping data_version after a real data change should invalidate the cache"

# confirm the new bytes actually reflect the mutated Media_Cost values
readback = pd.read_excel(BytesIO(bytes_v1), sheet_name="Raw")
assert (readback["Media_Cost"].iloc[:10] == 999.0).all(), "exported file should reflect the updated Media_Cost"
print("TEST OK: bumping data_version regenerates the file and reflects the real data change")

# CSV log cache: mirror the real app, where a log append always happens in the same
# code path as a data_version bump (inside "Ejecutar cola completa"), so using
# data_version as the cache key for the log export is consistent with actual usage.
log_v_before = build_log_csv_bytes(at.session_state["log"], at.session_state["data_version"])
at.session_state["log"].append({"Timestamp": "t", "Filas_Afectadas": 10})
at.session_state["data_version"] += 1
log_v_after = build_log_csv_bytes(at.session_state["log"], at.session_state["data_version"])
assert log_v_before != log_v_after, "log export should change after a log append + version bump"
readback_log = pd.read_csv(BytesIO(log_v_after))
assert len(readback_log) == 1 and readback_log["Filas_Afectadas"].iloc[0] == 10
print("TEST OK: log CSV export reflects appended entries when data_version is bumped")

print("ALL CACHE TESTS PASSED")
