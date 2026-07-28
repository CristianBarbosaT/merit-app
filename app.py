import re
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Weighted Backfills App", layout="wide")

REQUIRED_COLUMNS = [
    "Channel", "Date", "Brand", "Campaign", "Prisma_Campaign_Secondary",
    "Product_Line", "Category", "Raw_Partner", "Audience", "Package_Placement_Name",
    "Daypart", "Retailer", "Breakout", "Impressions", "Clicks", "Media_Cost",
    "Video_Views", "GRPs", "In Platform Spend", "Delivered Spend (Reconciled)",
    "Delivered Spend (Prisma)", "Delivered Spend (Capped)", "Even Allocated Spend",
    "Even Allocated Units", "Monitored Impressions", "Weighted Planned Units",
    "Cost Method", "Product Code", "Network_Name", "Campaign ID", "Placement ID",
    "Is Reconciled", "Package Name", "CCD JTBD", "Creative Name", "Team",
]

# "Channel" is critical for BOTH modes: Digital needs it to exclude TV rows from its
# own filtering/dropdowns (TV rows populate Raw_Partner too, so without this exclusion
# TV network names would leak into the Digital Partner dropdown).
CRITICAL_COLUMNS_DIGITAL = [
    "Channel", "Date", "Prisma_Campaign_Secondary", "Raw_Partner", "Package Name",
    "CCD JTBD", "Audience", "Breakout", "Impressions", "Media_Cost",
]
CRITICAL_COLUMNS_TV = [
    "Channel", "Date", "Brand", "Audience", "Daypart", "Network_Name",
    "Impressions", "Media_Cost",
]

PCODE_PATTERN = re.compile(r"^[A-Z0-9]{7}$")

# TV can backfill either field, weighted by the other one. Digital always uses
# Media_Cost/Impressions and never exposes this choice to the user.
FIELD_PAIRS = {"Media_Cost": "Impressions", "Impressions": "Media_Cost"}


def init_state():
    defaults = {
        "df": None,
        "log": [],
        "filename": None,
        "sheet_name": None,
        "preview_result": None,
        "queue": [],
        "queue_next_id": 1,
        "last_execution_results": None,
        "output_basename": None,
        "dropdown_options": None,
        "missing_columns": {},
        "data_version": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_all():
    st.session_state.df = None
    st.session_state.log = []
    st.session_state.filename = None
    st.session_state.sheet_name = None
    st.session_state.preview_result = None
    st.session_state.queue = []
    st.session_state.queue_next_id = 1
    st.session_state.last_execution_results = None
    st.session_state.output_basename = None
    st.session_state.dropdown_options = None
    st.session_state.missing_columns = {}
    st.session_state.data_version = 0
    st.session_state.mode_selector = "Digital"


def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Month_Label"] = df["Date"].dt.strftime("%B %Y")
    if "Package Name" in df.columns:
        df["Parent_PCODE"] = df["Package Name"].astype(str).str[:7]
    else:
        df["Parent_PCODE"] = ""
    # Force float64 on both backfillable columns. If the source sheet had no blank
    # cells in Impressions or Media_Cost, pandas reads them as int64; a proportional
    # backfill always produces fractional values, and pandas refuses to write floats
    # into an int64 column in place, so without this cast "Run full queue" crashes.
    df["Media_Cost"] = pd.to_numeric(df["Media_Cost"], errors="coerce").astype("float64")
    df["Impressions"] = pd.to_numeric(df["Impressions"], errors="coerce").astype("float64")
    return df


def sorted_month_labels(df: pd.DataFrame) -> list:
    """Month_Label values ("June 2026") sorted chronologically. Plain alphabetical
    sorting would put "April 2026" before "December 2026" before "February 2026" —
    wrong order — so this sorts by the underlying Date instead of the label text."""
    pairs = df[["Month_Label", "Date"]].dropna(subset=["Month_Label", "Date"])
    pairs = pairs.drop_duplicates("Month_Label").sort_values("Date")
    return pairs["Month_Label"].tolist()


def build_dropdown_options_digital(df: pd.DataFrame) -> dict:
    digital_df = df[df["Channel"] != "TV"]
    return {
        "months": sorted_month_labels(digital_df),
        "campaigns": sorted(digital_df["Prisma_Campaign_Secondary"].dropna().unique()),
        "partners": sorted(digital_df["Raw_Partner"].dropna().unique()),
        "pcodes": sorted(
            p for p in digital_df["Parent_PCODE"].dropna().unique() if PCODE_PATTERN.match(p)
        ),
        "ccd_jtbds": sorted(digital_df["CCD JTBD"].dropna().unique()),
        "audiences": sorted(digital_df["Audience"].dropna().unique()),
        "breakouts": sorted(digital_df["Breakout"].dropna().unique()),
    }


def build_dropdown_options_tv(df: pd.DataFrame) -> dict:
    tv_df = df[df["Channel"] == "TV"]
    return {
        "months": sorted_month_labels(tv_df),
        "brands": sorted(tv_df["Brand"].dropna().unique()),
        "audiences": sorted(tv_df["Audience"].dropna().unique()),
        "dayparts": sorted(tv_df["Daypart"].dropna().unique()),
        "networks": sorted(tv_df["Network_Name"].dropna().unique()),
    }


def missing_critical_columns(df: pd.DataFrame, required: list):
    return [c for c in required if c not in df.columns]


def compute_subset_digital(df, month_label, campaign, partner, pcode, ccd_jtbd, audience, breakout):
    mask = (
        (df["Channel"] != "TV")
        & (df["Month_Label"] == month_label)
        & (df["Prisma_Campaign_Secondary"] == campaign)
        & (df["Raw_Partner"] == partner)
        & (df["Parent_PCODE"] == pcode)
        & (df["CCD JTBD"] == ccd_jtbd)
        & (df["Audience"] == audience)
        & (df["Breakout"] == breakout)
    )
    return df[mask]


def compute_subset_tv(df, month_label, brand, audience, daypart, network_name):
    mask = (
        (df["Channel"] == "TV")
        & (df["Month_Label"] == month_label)
        & (df["Brand"] == brand)
        & (df["Audience"] == audience)
        & (df["Daypart"] == daypart)
        & (df["Network_Name"] == network_name)
    )
    return df[mask]


def compute_backfill(subset: pd.DataFrame, target_value: float, target_field: str, weight_field: str):
    weights_raw = subset[weight_field].fillna(0)
    total_weight = weights_raw.sum()
    if total_weight == 0:
        return None, total_weight
    weights = weights_raw / total_weight
    new_values = weights * target_value
    return new_values, total_weight


def round_preserving_sum(values: pd.Series, target_value: float) -> pd.Series:
    """Rounds every value to a whole number while keeping the sum exactly equal to
    round(target_value), using the largest-remainder method (a.k.a. Hare-Niemeyer
    apportionment) — so rounding never invents or loses impressions overall."""
    floor_values = values.astype("int64")
    remainder = values - floor_values
    target_int = int(round(target_value))
    deficit = target_int - int(floor_values.sum())
    result = floor_values.astype("float64").copy()
    if deficit > 0:
        bump = remainder.sort_values(ascending=False).index[:deficit]
        result.loc[bump] += 1
    elif deficit < 0:
        bump = remainder.sort_values(ascending=True).index[:(-deficit)]
        result.loc[bump] -= 1
    return result


def resolve_new_values(mode: str, target_value: float, target_field: str, weight_field: str,
                        subset: pd.DataFrame):
    """Wraps compute_backfill with two rules on top of the raw proportional split:
    1. TV-only: when the weight basis is entirely 0 (e.g. all rows have Impressions=0)
       but the target is also exactly 0, there's nothing ambiguous about the
       distribution — every row simply gets 0. Digital keeps the strict original
       behavior (always blocked when the weight basis is 0).
    2. Impressions are always whole numbers — a backfilled Impressions value is
       rounded (sum-preserving) regardless of mode, since fractional impressions
       don't mean anything."""
    new_values, total_weight = compute_backfill(subset, target_value, target_field, weight_field)
    if new_values is None:
        if mode == "TV" and target_value == 0:
            new_values = pd.Series(0.0, index=subset.index)
        else:
            return None
    if target_field == "Impressions":
        new_values = round_preserving_sum(new_values, target_value)
    return new_values


def subset_key(mode: str, filters: dict):
    """Canonical identity of a subset, independent of which field gets backfilled.
    Used by the one-backfill-per-subset lock: a Media_Cost and an Impressions
    backfill on the same TV subset are still considered the same subset."""
    if mode == "DIGITAL":
        return (
            "DIGITAL", filters["Month"], filters["Campaign"], filters["Partner"],
            filters["Package (PCODE)"], filters["CCD JTBD"], filters["Audience"],
            filters["Breakout"],
        )
    return (
        "TV", filters["Month"], filters["Brand"], filters["Audience"],
        filters["Daypart"], filters["Network_Name"],
    )


def find_lock_conflict_field(mode: str, filters: dict, queue: list, log: list):
    """Returns the target_field already occupying this subset (queued or applied),
    or None if the subset is free."""
    key = subset_key(mode, filters)
    for item in queue:
        if subset_key(item["mode"], item["filters"]) == key:
            return item["target_field"]
    for entry in log:
        if subset_key(entry["Mode"], entry) == key:
            return entry["Field"]
    return None


def build_preview(mode: str, filters: dict, target_value: float, target_field: str,
                   weight_field: str, subset: pd.DataFrame, queue: list, log: list):
    """Runs all four preview-time validations and returns (preview_dict, None) on
    success or (None, error_message) on failure. Order: cheapest/most obviously
    wrong checks first."""
    if mode == "TV":
        if target_value < 0:
            return None, "The target must be a number greater than or equal to 0."
    elif target_value <= 0:
        return None, "The target must be a positive number."
    if len(subset) == 0:
        return None, "0 rows match these filters. The backfill cannot be applied."
    conflict_field = find_lock_conflict_field(mode, filters, queue, log)
    if conflict_field is not None:
        return None, (
            f"This subset already has a {conflict_field} backfill pending or applied in this "
            "session. To apply a new adjustment to this subset, start a new session and apply "
            "it on top of the file resulting from the current session."
        )
    new_values = resolve_new_values(mode, target_value, target_field, weight_field, subset)
    if new_values is None:
        return None, (
            f"The rows in this subset have 0 total {weight_field}. There is no basis to "
            "distribute the value. The backfill cannot be applied."
        )
    current_sum = subset[target_field].fillna(0).sum()
    preview = {
        "mode": mode,
        "filters": filters,
        "target_value": target_value,
        "target_field": target_field,
        "weight_field": weight_field,
        "rows": len(subset),
        "current_sum": current_sum,
        "delta": target_value - current_sum,
    }
    return preview, None


def format_field_value(field: str, value: float) -> str:
    if field == "Media_Cost":
        return f"${value:,.2f}"
    return f"{value:,.0f}"


@st.cache_data(show_spinner="Generating Excel file...")
def build_excel_bytes(_df: pd.DataFrame, version: int, sheet_name: str) -> bytes:
    # The leading underscore on _df tells Streamlit's cache not to hash the dataframe
    # (which would cost O(n) on every rerun); `version` alone drives cache invalidation,
    # bumped only when Media_Cost/Impressions actually change.
    export_df = _df.drop(columns=["Month_Label", "Parent_PCODE"], errors="ignore")
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        export_df.to_excel(writer, sheet_name=sheet_name, index=False)
    return output.getvalue()


@st.cache_data(show_spinner=False)
def build_log_csv_bytes(_log: list, version: int) -> bytes:
    log_df = pd.DataFrame(_log)
    output = BytesIO()
    log_df.to_csv(output, index=False)
    return output.getvalue()


def sanitize_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[^A-Za-z0-9 _\-\.]", "_", name)
    return name or "backfilled"


init_state()

st.title("Weighted Backfills App")

# --- Step 1 and 2: upload and sheet selection ---
if st.session_state.df is None:
    uploaded_file = st.file_uploader("Upload the .xlsx file", type=["xlsx"])

    if uploaded_file is not None:
        try:
            excel_file = pd.ExcelFile(uploaded_file, engine="openpyxl")
        except Exception as e:
            st.error(f"Could not read the file: {e}")
            st.stop()

        sheet_names = excel_file.sheet_names

        if len(sheet_names) > 1:
            sheet_choice = st.selectbox("Which sheet is the working sheet (Raw)?", sheet_names)
        else:
            sheet_choice = sheet_names[0]
            st.info(f"Using the only available sheet: {sheet_choice}")

        if st.button("Load sheet"):
            raw_df = excel_file.parse(sheet_choice)

            missing_digital = missing_critical_columns(raw_df, CRITICAL_COLUMNS_DIGITAL)
            missing_tv = missing_critical_columns(raw_df, CRITICAL_COLUMNS_TV)

            if missing_digital and missing_tv:
                st.error(
                    "This file does not have the columns required for either mode. "
                    f"Missing for Digital: {', '.join(missing_digital)}. "
                    f"Missing for TV: {', '.join(missing_tv)}."
                )
                st.stop()

            df = prepare_dataframe(raw_df)

            dropdown_options = {
                "DIGITAL": build_dropdown_options_digital(df) if not missing_digital else None,
                "TV": build_dropdown_options_tv(df) if not missing_tv else None,
            }

            st.session_state.df = df
            st.session_state.filename = uploaded_file.name
            st.session_state.sheet_name = sheet_choice
            st.session_state.preview_result = None
            st.session_state.queue = []
            st.session_state.queue_next_id = 1
            st.session_state.last_execution_results = None
            st.session_state.dropdown_options = dropdown_options
            st.session_state.missing_columns = {"DIGITAL": missing_digital, "TV": missing_tv}
            st.session_state.data_version = 0
            st.session_state.mode_selector = "Digital"
            base_name = re.sub(r"\.xlsx$", "", uploaded_file.name, flags=re.IGNORECASE)
            st.session_state.output_basename = f"{base_name}_backfilled"
            st.rerun()

else:
    df = st.session_state.df

    st.success(
        f"File loaded: {st.session_state.filename} — sheet: {st.session_state.sheet_name} "
        f"({len(df)} rows)"
    )

    missing_cols = st.session_state.missing_columns or {}
    if missing_cols.get("DIGITAL"):
        st.warning(
            f"Digital mode is not available for this file: missing columns "
            f"{', '.join(missing_cols['DIGITAL'])}."
        )
    if missing_cols.get("TV"):
        st.warning(
            f"TV mode is not available for this file: missing columns "
            f"{', '.join(missing_cols['TV'])}."
        )

    if st.button("Start over with another file (reset)"):
        reset_all()
        st.rerun()

    st.divider()
    st.subheader("Backfill filters")

    mode_label = st.radio("Mode", ["Digital", "TV"], horizontal=True, key="mode_selector")
    mode = mode_label.upper()

    options = st.session_state.dropdown_options.get(mode)

    if options is None:
        missing = missing_cols.get(mode, [])
        st.error(
            f"{mode_label} mode is not available for this file: missing critical columns "
            f"({', '.join(missing)}). You can keep using the other mode."
        )
    else:
        st.caption(
            "Choose the filters and the target, then click **Preview**. "
            "The app only recalculates when you confirm — changing a dropdown does not "
            "trigger a reload."
        )

        if mode == "DIGITAL":
            with st.form("filters_form_digital"):
                col1, col2 = st.columns(2)
                with col1:
                    f_month = st.selectbox("Month", options["months"])
                    f_campaign = st.selectbox("Campaign", options["campaigns"])
                    f_partner = st.selectbox("Partner", options["partners"])
                    f_pcode = st.selectbox("Package (PCODE)", options["pcodes"])
                with col2:
                    f_ccd = st.selectbox("CCD JTBD", options["ccd_jtbds"])
                    f_audience = st.selectbox("Audience", options["audiences"])
                    f_breakout = st.selectbox("Breakout", options["breakouts"])

                target_value = st.number_input(
                    "Target Media Cost ($)", min_value=0.0, step=0.01, format="%.2f"
                )
                submitted = st.form_submit_button(
                    "Preview", type="primary", use_container_width=True
                )

            if submitted:
                filters = {
                    "Month": f_month, "Campaign": f_campaign, "Partner": f_partner,
                    "Package (PCODE)": f_pcode, "CCD JTBD": f_ccd, "Audience": f_audience,
                    "Breakout": f_breakout,
                }
                subset = compute_subset_digital(
                    df, f_month, f_campaign, f_partner, f_pcode, f_ccd, f_audience, f_breakout
                )
                preview, error = build_preview(
                    mode="DIGITAL", filters=filters, target_value=target_value,
                    target_field="Media_Cost", weight_field="Impressions", subset=subset,
                    queue=st.session_state.queue, log=st.session_state.log,
                )
                if error:
                    st.error(error)
                    st.session_state.preview_result = None
                else:
                    st.session_state.preview_result = preview

        else:  # TV
            with st.form("filters_form_tv"):
                col1, col2 = st.columns(2)
                with col1:
                    f_month = st.selectbox("Month", options["months"])
                    f_brand = st.selectbox("Brand", options["brands"])
                    f_audience = st.selectbox("Audience", options["audiences"])
                with col2:
                    f_daypart = st.selectbox("Daypart", options["dayparts"])
                    f_network = st.selectbox("Network_Name", options["networks"])

                target_field = st.selectbox("Field to backfill", ["Media_Cost", "Impressions"])
                weight_field = FIELD_PAIRS[target_field]
                # Fixed key (not derived from the label): the label changes with
                # target_field, and without an explicit key Streamlit treats a
                # relabeled widget as brand new, silently resetting it to 0.
                target_value = st.number_input(
                    f"Target {target_field}", min_value=0.0, step=0.01, format="%.2f",
                    key="tv_target_value",
                )
                submitted = st.form_submit_button(
                    "Preview", type="primary", use_container_width=True
                )

            if submitted:
                filters = {
                    "Month": f_month, "Brand": f_brand, "Audience": f_audience,
                    "Daypart": f_daypart, "Network_Name": f_network,
                }
                subset = compute_subset_tv(df, f_month, f_brand, f_audience, f_daypart, f_network)
                preview, error = build_preview(
                    mode="TV", filters=filters, target_value=target_value,
                    target_field=target_field, weight_field=weight_field, subset=subset,
                    queue=st.session_state.queue, log=st.session_state.log,
                )
                if error:
                    st.error(error)
                    st.session_state.preview_result = None
                else:
                    st.session_state.preview_result = preview

    preview = st.session_state.preview_result

    if preview is not None:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Rows in subset", preview["rows"])
        m2.metric(
            f"Current {preview['target_field']} sum",
            format_field_value(preview["target_field"], preview["current_sum"]),
        )
        m3.metric("Target sum", format_field_value(preview["target_field"], preview["target_value"]))
        m4.metric("Delta", format_field_value(preview["target_field"], preview["delta"]))

        if st.button("Add to queue", type="primary"):
            st.session_state.queue.append(
                {
                    "qid": st.session_state.queue_next_id,
                    "mode": preview["mode"],
                    "filters": preview["filters"],
                    "target_value": preview["target_value"],
                    "target_field": preview["target_field"],
                    "weight_field": preview["weight_field"],
                    "rows": preview["rows"],
                    "current_sum": preview["current_sum"],
                    "delta": preview["delta"],
                }
            )
            st.session_state.queue_next_id += 1
            st.session_state.preview_result = None
            st.success("Added to queue.")
            st.rerun()

    st.divider()
    st.subheader(f"Backfill queue ({len(st.session_state.queue)})")

    if st.session_state.queue:
        queue_rows = []
        for item in st.session_state.queue:
            f = item["filters"]
            queue_rows.append(
                {
                    "#": item["qid"],
                    "Mode": item["mode"],
                    "Field": item["target_field"],
                    "Month": f.get("Month"),
                    "Campaign": f.get("Campaign"),
                    "Partner": f.get("Partner"),
                    "Package": f.get("Package (PCODE)"),
                    "CCD JTBD": f.get("CCD JTBD"),
                    "Brand": f.get("Brand"),
                    "Daypart": f.get("Daypart"),
                    "Network": f.get("Network_Name"),
                    "Audience": f.get("Audience"),
                    "Breakout": f.get("Breakout"),
                    "Rows": item["rows"],
                    "Current Sum": round(item["current_sum"], 2),
                    "Target": round(item["target_value"], 2),
                    "Delta": round(item["delta"], 2),
                }
            )
        st.dataframe(pd.DataFrame(queue_rows), use_container_width=True, hide_index=True)

        remove_col, clear_col, exec_col = st.columns([2, 1, 2])
        with remove_col:
            qid_to_remove = st.selectbox(
                "Remove from queue",
                options=[item["qid"] for item in st.session_state.queue],
                format_func=lambda qid: f"#{qid}",
                key="qid_to_remove",
            )
            if st.button("Remove selected"):
                before_count = len(st.session_state.queue)
                st.session_state.queue = [
                    item for item in st.session_state.queue if item["qid"] != qid_to_remove
                ]
                after_count = len(st.session_state.queue)
                if after_count < before_count:
                    st.success(f"Removed #{qid_to_remove} from the queue.")
                else:
                    st.warning(f"Could not find #{qid_to_remove} in the queue.")
                st.rerun()
        with clear_col:
            if st.button("Clear queue"):
                st.session_state.queue = []
                st.rerun()
        with exec_col:
            if st.button(
                f"Run full queue ({len(st.session_state.queue)})",
                type="primary",
                use_container_width=True,
            ):
                results = []
                any_applied = False
                for item in st.session_state.queue:
                    f = item["filters"]
                    if item["mode"] == "DIGITAL":
                        subset = compute_subset_digital(
                            st.session_state.df,
                            f["Month"], f["Campaign"], f["Partner"], f["Package (PCODE)"],
                            f["CCD JTBD"], f["Audience"], f["Breakout"],
                        )
                    else:
                        subset = compute_subset_tv(
                            st.session_state.df,
                            f["Month"], f["Brand"], f["Audience"], f["Daypart"], f["Network_Name"],
                        )
                    base_result = {"Mode": item["mode"], "Field": item["target_field"], **f}
                    if len(subset) == 0:
                        results.append({**base_result, "Status": "Skipped — 0 rows at execution time"})
                        continue
                    new_values = resolve_new_values(
                        item["mode"], item["target_value"], item["target_field"],
                        item["weight_field"], subset,
                    )
                    if new_values is None:
                        results.append(
                            {
                                **base_result,
                                "Status": f"Skipped — 0 {item['weight_field']} at execution time",
                            }
                        )
                        continue
                    current_sum = subset[item["target_field"]].fillna(0).sum()
                    st.session_state.df.loc[subset.index, item["target_field"]] = new_values
                    new_sum = st.session_state.df.loc[subset.index, item["target_field"]].sum()
                    any_applied = True
                    st.session_state.log.append(
                        {
                            "Timestamp": datetime.now().isoformat(timespec="seconds"),
                            "Mode": item["mode"],
                            "Field": item["target_field"],
                            **f,
                            "Target_Value": item["target_value"],
                            "Rows_Affected": len(subset),
                            "Sum_Before": current_sum,
                            "Sum_After": new_sum,
                        }
                    )
                    results.append(
                        {
                            **base_result,
                            "Status": (
                                f"Applied — {len(subset)} rows, "
                                f"{format_field_value(item['target_field'], new_sum)}"
                            ),
                        }
                    )
                st.session_state.queue = []
                st.session_state.last_execution_results = results
                if any_applied:
                    st.session_state.data_version += 1
                st.rerun()
    else:
        st.caption("The queue is empty. Set filters above and use 'Add to queue'.")

    if st.session_state.last_execution_results:
        st.subheader("Result of the last queue run")
        st.dataframe(
            pd.DataFrame(st.session_state.last_execution_results),
            use_container_width=True,
            hide_index=True,
        )

    st.divider()
    st.subheader("Downloads")

    default_basename = st.session_state.output_basename or "backfilled"
    output_basename = st.text_input(
        "Download file name (without extension)", value=default_basename
    )
    safe_basename = sanitize_filename(output_basename)

    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        st.download_button(
            "Download resulting file (.xlsx)",
            data=build_excel_bytes(
                st.session_state.df, st.session_state.data_version, st.session_state.sheet_name
            ),
            file_name=f"{safe_basename}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    with dl_col2:
        if st.session_state.log:
            st.download_button(
                "Download backfill log (.csv)",
                data=build_log_csv_bytes(st.session_state.log, st.session_state.data_version),
                file_name=f"{safe_basename}_log.csv",
                mime="text/csv",
            )
        else:
            st.caption("No backfills have been applied in this session yet.")

    if st.session_state.log:
        st.subheader("Backfills applied in this session (log)")
        st.dataframe(pd.DataFrame(st.session_state.log), use_container_width=True)
