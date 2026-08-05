"""RROI Manual Backfill — weighted/even/copy backfills for Digital (Social/Reserve/
Programmatic) and TV rows in an RROI delivery file. See estado_actual_app.md for the
full design history; this module is mounted by the M.E.R.I.T. shell (app.py)."""
import re
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st

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
    "Package_Placement_Name", "CCD JTBD", "Audience", "Breakout", "Impressions", "Media_Cost",
]
CRITICAL_COLUMNS_TV = [
    "Channel", "Date", "Brand", "Audience", "Daypart", "Network_Name",
    "Impressions", "Media_Cost",
]

PCODE_PATTERN = re.compile(r"^[A-Z0-9]{7}$")

# TV can backfill either field; Digital's field choice is now driven by the operation
# picked (see OPERATIONS), not by this pairing.
FIELD_PAIRS = {"Media_Cost": "Impressions", "Impressions": "Media_Cost"}

# --- Digital sub-type taxonomy -------------------------------------------------
# A Digital row's sub-type is decided by the token in its Package_Placement_Name plus,
# for the "UNE" ones, whether the partner is a social platform:
#   Package_Placement_Name contains "UUT"                    -> Programmatic
#   contains "UNE" and Raw_Partner is a social platform      -> Social
#   contains "UNE" and it is not                             -> Reserve
#   neither token                                            -> Unclassified (bonus /
#       added-value lines whose placement is free text, e.g. "Awareness AV BONUS $4,608.39").
#       Verified against the real file: 0 rows contain BOTH tokens, 312 contain neither.
SOCIAL_PARTNERS = {
    "FACEBOOK.COM", "TIKTOK", "REDDIT.COM", "PINTEREST", "SNAP INC FK SNAPCHAT",
}
# Matched case-insensitively on purpose: the file contains both "CNBC.COM - X CORP" and
# "FOXSPORTS.COM - X Corp", and a case-sensitive match would silently drop the latter.
SOCIAL_PARTNER_CONTAINS = "X CORP"

SUBTYPE_SOCIAL = "Social"
SUBTYPE_RESERVE = "Reserve"
SUBTYPE_PROGRAMMATIC = "Programmatic"
SUBTYPE_UNCLASSIFIED = "Unclassified"
DIGITAL_SUBTYPES = [SUBTYPE_SOCIAL, SUBTYPE_RESERVE, SUBTYPE_PROGRAMMATIC]

# --- Backfill operations -------------------------------------------------------
# Each operation says which column it writes, whether the user must supply a target
# total, and (for the copy operations) which column the values are read from.
OPERATIONS = {
    "MC_WEIGHTED": {
        "field": "Media_Cost",
        "label": "Weighted by impressions",
        "needs_target": True,
        "help": "Splits the target across rows in proportion to each row's Impressions.",
    },
    "MC_EVEN": {
        "field": "Media_Cost",
        "label": "Even allocation across rows",
        "needs_target": True,
        "help": "Divides the target equally across every row in the subset.",
    },
    "MC_COPY_RECONCILED": {
        "field": "Media_Cost",
        "label": "Copy from Delivered Spend (Reconciled)",
        "needs_target": False,
        "source": "Delivered Spend (Reconciled)",
        "help": "Overwrites Media_Cost row by row with Delivered Spend (Reconciled).",
    },
    "MC_COPY_PRISMA": {
        "field": "Media_Cost",
        "label": "Copy from Delivered Spend (Prisma)",
        "needs_target": False,
        "source": "Delivered Spend (Prisma)",
        "help": "Overwrites Media_Cost row by row with Delivered Spend (Prisma).",
    },
    "IMPR_WEIGHTED": {
        "field": "Impressions",
        "label": "Weighted (by impressions, falls back to cost)",
        "needs_target": True,
        "help": (
            "Splits the target in proportion to each row's current Impressions, so the "
            "daily delivery curve is preserved. If the subset has no impressions at all, "
            "it falls back to weighting by Media_Cost."
        ),
    },
    "IMPR_COPY_WPU": {
        "field": "Impressions",
        "label": "Copy from Weighted Planned Units",
        "needs_target": False,
        "source": "Weighted Planned Units",
        "help": "Overwrites Impressions row by row with Weighted Planned Units.",
    },
}
OPERATIONS_BY_FIELD = {
    "Media_Cost": ["MC_WEIGHTED", "MC_EVEN", "MC_COPY_RECONCILED", "MC_COPY_PRISMA"],
    "Impressions": ["IMPR_WEIGHTED", "IMPR_COPY_WPU"],
}

# --- Filter definitions per Digital sub-type -----------------------------------
# (label, dataframe column, options key, multi?) — "multi" filters let the analyst pick
# one, several, or all values; single ones are exactly one value.
SOCIAL_SELECT_BY_PACKAGE = "Package"
SOCIAL_SELECT_BY_PLACEMENT = "Placement"

FILTER_SPECS = {
    SUBTYPE_SOCIAL: {
        SOCIAL_SELECT_BY_PACKAGE: [
            ("Month", "Month_Label", "months", False),
            ("Campaign", "Prisma_Campaign_Secondary", "campaigns", False),
            ("Partner", "Raw_Partner", "partners", False),
            ("Package", "Package Name", "packages", False),
            ("CCD JTBD", "CCD JTBD", "ccd_jtbds", False),
            ("Audience", "Audience", "audiences", False),
            ("Breakout", "Breakout", "breakouts", False),
        ],
        SOCIAL_SELECT_BY_PLACEMENT: [
            ("Month", "Month_Label", "months", False),
            ("Campaign", "Prisma_Campaign_Secondary", "campaigns", False),
            ("Partner", "Raw_Partner", "partners", False),
            ("Placement", "Package_Placement_Name", "placements", False),
        ],
    },
    SUBTYPE_RESERVE: [
        ("Month", "Month_Label", "months", False),
        ("Campaign", "Prisma_Campaign_Secondary", "campaigns", False),
        ("Partner", "Raw_Partner", "partners", True),
        ("Audience", "Audience", "audiences", True),
    ],
    SUBTYPE_PROGRAMMATIC: [
        ("Month", "Month_Label", "months", False),
        ("Campaign", "Prisma_Campaign_Secondary", "campaigns", False),
        ("Partner", "Raw_Partner", "partners", False),
        ("Channel", "Channel", "channels", True),
        ("Package", "Package Name", "packages", False),
        ("CCD JTBD", "CCD JTBD", "ccd_jtbds", True),
        ("Audience", "Audience", "audiences", True),
    ],
}

TV_FILTER_SPEC = [
    ("Month", "Month_Label", "months", False),
    ("Brand", "Brand", "brands", False),
    ("Audience", "Audience", "audiences", False),
    ("Daypart", "Daypart", "dayparts", False),
    ("Network_Name", "Network_Name", "networks", False),
]


def init_state():
    defaults = {
        "df": None,
        "log": [],
        "applied_indices": [],
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
    st.session_state.applied_indices = []
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


def classify_digital_subtype(df: pd.DataFrame) -> pd.Series:
    """Labels every row Social / Reserve / Programmatic / Unclassified (TV rows get
    Unclassified too — the sub-type only means anything for Digital)."""
    placement = df.get("Package_Placement_Name")
    if placement is None:
        return pd.Series(SUBTYPE_UNCLASSIFIED, index=df.index)
    placement = placement.fillna("").astype(str)
    partner = df.get("Raw_Partner")
    partner = partner.fillna("").astype(str) if partner is not None else pd.Series("", index=df.index)

    has_uut = placement.str.contains("UUT", regex=False)
    has_une = placement.str.contains("UNE", regex=False)
    is_social_partner = (
        partner.isin(SOCIAL_PARTNERS)
        | partner.str.upper().str.contains(SOCIAL_PARTNER_CONTAINS, regex=False)
    )
    is_digital = df["Channel"] != "TV" if "Channel" in df.columns else pd.Series(True, index=df.index)

    subtype = pd.Series(SUBTYPE_UNCLASSIFIED, index=df.index, dtype="object")
    subtype[is_digital & has_uut] = SUBTYPE_PROGRAMMATIC
    subtype[is_digital & has_une & ~has_uut & is_social_partner] = SUBTYPE_SOCIAL
    subtype[is_digital & has_une & ~has_uut & ~is_social_partner] = SUBTYPE_RESERVE
    return subtype


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
    df["Digital_Subtype"] = classify_digital_subtype(df)
    return df


def sorted_month_labels(df: pd.DataFrame) -> list:
    """Month_Label values ("June 2026") sorted chronologically. Plain alphabetical
    sorting would put "April 2026" before "December 2026" before "February 2026" —
    wrong order — so this sorts by the underlying Date instead of the label text."""
    pairs = df[["Month_Label", "Date"]].dropna(subset=["Month_Label", "Date"])
    pairs = pairs.drop_duplicates("Month_Label").sort_values("Date")
    return pairs["Month_Label"].tolist()


def subtype_frame(df: pd.DataFrame, subtype: str) -> pd.DataFrame:
    return df[df["Digital_Subtype"] == subtype]


def build_dropdown_options_subtype(df: pd.DataFrame, subtype: str) -> dict:
    sub = subtype_frame(df, subtype)

    def uniq(col):
        return sorted(sub[col].dropna().unique()) if col in sub.columns else []

    return {
        "months": sorted_month_labels(sub),
        "campaigns": uniq("Prisma_Campaign_Secondary"),
        "partners": uniq("Raw_Partner"),
        "packages": uniq("Package Name"),
        "placements": uniq("Package_Placement_Name"),
        "ccd_jtbds": uniq("CCD JTBD"),
        "audiences": uniq("Audience"),
        "breakouts": uniq("Breakout"),
        "channels": uniq("Channel"),
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


def compute_subset(df: pd.DataFrame, base_mask: pd.Series, filters: dict, specs: list) -> pd.DataFrame:
    """Applies every filter in `specs` to the rows already selected by `base_mask`.
    A filter whose value is a list/tuple/set matches any of those values (the "pick one,
    several or all" filters); anything else must match exactly."""
    mask = base_mask.copy()
    col_by_label = {label: column for label, column, _, _ in specs}
    for label, value in filters.items():
        column = col_by_label.get(label)
        if column is None or column not in df.columns:
            continue
        if isinstance(value, (list, tuple, set)):
            mask &= df[column].isin(list(value))
        else:
            mask &= df[column] == value
    return df[mask]


def compute_subset_digital(df: pd.DataFrame, subtype: str, filters: dict, specs: list) -> pd.DataFrame:
    return compute_subset(df, df["Digital_Subtype"] == subtype, filters, specs)


def compute_subset_tv(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    return compute_subset(df, df["Channel"] == "TV", filters, TV_FILTER_SPEC)


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


def compute_new_values(subset: pd.DataFrame, operation_id: str, target_value, mode: str):
    """The single dispatcher every operation goes through. Returns (Series, None) with
    the new values for the operation's target column, or (None, error_message).

    Kept pure (no st.session_state) so both the preview and the queue execution call the
    exact same code and can never drift apart."""
    spec = OPERATIONS[operation_id]
    field = spec["field"]

    if len(subset) == 0:
        return None, "0 rows match these filters. The backfill cannot be applied."

    # --- copy operations: value comes from another column, no target involved ---
    source = spec.get("source")
    if source is not None:
        if source not in subset.columns:
            return None, f"This file has no '{source}' column, so this operation is unavailable."
        values = pd.to_numeric(subset[source], errors="coerce").fillna(0).astype("float64")
        if field == "Impressions":
            values = values.round()
        return values, None

    # --- even allocation ---
    if operation_id == "MC_EVEN":
        return pd.Series(float(target_value) / len(subset), index=subset.index), None

    # --- weighted operations ---
    if operation_id == "MC_WEIGHTED":
        weight_field = "Impressions"
    else:  # IMPR_WEIGHTED — weight by the impressions already there so the daily
        # delivery curve is preserved; only fall back to cost when there are none.
        weight_field = "Impressions" if subset["Impressions"].fillna(0).sum() > 0 else "Media_Cost"

    new_values, total_weight = compute_backfill(subset, target_value, field, weight_field)
    if new_values is None:
        # A zero target across a zero weight basis is unambiguous regardless of mode —
        # there's nothing to distribute either way, so every row simply gets 0.
        if target_value == 0:
            new_values = pd.Series(0.0, index=subset.index)
        else:
            return None, (
                f"The rows in this subset have 0 total {weight_field}. There is no basis "
                "to distribute the value. The backfill cannot be applied."
            )
    if field == "Impressions":
        new_values = round_preserving_sum(new_values, target_value)
    return new_values, None


def find_lock_conflict(indices, queue: list, applied: list):
    """One backfill per set of rows, per session. Detects conflicts by ROW OVERLAP rather
    than by comparing filter values: now that Reserve/Programmatic filters accept several
    values at once, two different-looking selections can still hit the same rows (e.g.
    partners [A,B] and [B,C]), and a filter-equality check would wave that through and
    silently double-write. Returns a description of the conflicting backfill, or None."""
    indices = set(indices)
    for item in queue:
        if indices & set(item["indices"]):
            return f"#{item['qid']} ({item['operation_label']}), still queued"
    for entry in applied:
        if indices & set(entry["indices"]):
            return f"{entry['label']}, already applied in this session"
    return None


def build_preview(mode: str, subtype, filters: dict, operation_id: str, target_value,
                   subset: pd.DataFrame, queue: list, applied: list):
    """Runs every validation in order and returns (preview_dict, None) on success or
    (None, error_message) on failure."""
    spec = OPERATIONS[operation_id]
    field = spec["field"]

    if spec["needs_target"]:
        if target_value is None:
            return None, "This operation needs a target total."
        if target_value < 0:
            return None, "The target must be a number greater than or equal to 0."

    for label, value in filters.items():
        if value is None:
            return None, f"Pick a value for {label} — the filters below it are still locked."
        if isinstance(value, (list, tuple, set)) and len(value) == 0:
            return None, f"Pick at least one value for {label}."

    if len(subset) == 0:
        return None, "0 rows match these filters. The backfill cannot be applied."

    conflict = find_lock_conflict(subset.index, queue, applied)
    if conflict is not None:
        return None, (
            f"These rows overlap a backfill that is {conflict}. Each row can only be "
            "backfilled once per session. Remove the other one from the queue, or start a "
            "new session on top of the file this one produces."
        )

    new_values, error = compute_new_values(subset, operation_id, target_value, mode)
    if error:
        return None, error

    current_sum = subset[field].fillna(0).sum()
    resulting_sum = float(new_values.sum())
    return {
        "mode": mode,
        "subtype": subtype,
        "filters": filters,
        "operation": operation_id,
        "operation_label": operation_label(mode, subtype, operation_id),
        "target_field": field,
        "target_value": target_value,
        "resulting_sum": resulting_sum,
        "rows": len(subset),
        "current_sum": current_sum,
        "delta": resulting_sum - current_sum,
        "indices": list(subset.index),
    }, None


def operation_label(mode: str, subtype, operation_id: str) -> str:
    scope = "TV" if mode == "TV" else f"Digital · {subtype}"
    return f"{scope} · {OPERATIONS[operation_id]['field']} · {OPERATIONS[operation_id]['label']}"


def format_field_value(field: str, value) -> str:
    if value is None:
        return "—"
    if field == "Media_Cost":
        return f"${value:,.2f}"
    return f"{value:,.0f}"


def format_filter_value(value) -> str:
    if isinstance(value, (list, tuple, set)):
        values = list(value)
        if len(values) > 3:
            return f"{len(values)} selected"
        return ", ".join(str(v) for v in values)
    return str(value)


@st.cache_data(show_spinner="Generating Excel file...")
def build_excel_bytes(_df: pd.DataFrame, version: int, sheet_name: str) -> bytes:
    # The leading underscore on _df tells Streamlit's cache not to hash the dataframe
    # (which would cost O(n) on every rerun); `version` alone drives cache invalidation,
    # bumped only when Media_Cost/Impressions actually change.
    export_df = _df.drop(
        columns=["Month_Label", "Parent_PCODE", "Digital_Subtype"], errors="ignore"
    )
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


def available_choices(working: pd.DataFrame, column: str) -> list:
    if column == "Month_Label":
        return sorted_month_labels(working)
    if column not in working.columns:
        return []
    return sorted(working[column].dropna().unique())


def _forget_stale_single(key: str, choices: list):
    """A cascading dropdown's options shrink when its parent changes. If what the user
    had picked is no longer offered, drop it so the widget comes back unselected instead
    of Streamlit raising on a value that isn't in its own option list."""
    if key in st.session_state and st.session_state[key] not in choices:
        del st.session_state[key]


def _reset_multi_on_new_choices(key: str, choices: list):
    """Multi-value filters mean "all of what's available". When the available set itself
    changes (because a parent filter moved), re-select everything rather than keeping the
    old intersection — otherwise newly-valid values would stay silently unselected."""
    signature_key = f"{key}__choices"
    signature = tuple(choices)
    if st.session_state.get(signature_key) != signature:
        st.session_state[signature_key] = signature
        st.session_state[key] = list(choices)


def render_cascading_filters(df: pd.DataFrame, base_mask: pd.Series, specs: list,
                              key_prefix: str) -> dict:
    """Renders the filters in order, numbered, each one offering only the values still
    available given everything chosen above it. Until a filter is answered, everything
    below it stays locked with a "pick X first" placeholder — so the dependent filters
    (CCD JTBD / Audience / Breakout) can only ever show values that really exist for the
    chosen package, instead of every value in the file.

    Returns {label: value}, with None for anything still unanswered.
    """
    filters = {}
    working = df[base_mask]
    blocked_by = None
    columns = st.columns(2)

    for i, (label, column, options_key, is_multi) in enumerate(specs):
        numbered = f"{i + 1} · {label}"
        widget_key = f"{key_prefix}_{options_key}"

        with columns[i % 2]:
            if blocked_by is not None:
                st.selectbox(
                    numbered, [], index=None, disabled=True,
                    placeholder=f"Pick {blocked_by} first",
                    key=f"{widget_key}_locked",
                )
                filters[label] = None
                continue

            choices = available_choices(working, column)
            if is_multi:
                _reset_multi_on_new_choices(widget_key, choices)
                value = st.multiselect(
                    f"{numbered} (one, several or all)", choices, key=widget_key
                )
            else:
                _forget_stale_single(widget_key, choices)
                value = st.selectbox(
                    numbered, choices, index=None,
                    placeholder=f"Select {label}…", key=widget_key,
                )
            filters[label] = value

        if value is None or (is_multi and not value):
            blocked_by = label
        elif isinstance(value, list):
            working = working[working[column].isin(value)]
        else:
            working = working[working[column] == value]

    return filters


def selection_signature(mode, subtype, select_by, operation_id, target_value, filters: dict) -> str:
    """Identifies exactly what a preview was computed for. Without a form to act as the
    submit boundary, this is what tells a stale preview from a current one."""
    return repr((mode, subtype, select_by, operation_id, target_value,
                 sorted(filters.items(), key=lambda kv: kv[0])))


def render():
    if st.button("← Back to menu"):
        st.session_state.active_tool = None
        st.rerun()

    init_state()

    st.title("RROI Manual Backfill")

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
                    "TV": build_dropdown_options_tv(df) if not missing_tv else None,
                }
                if not missing_digital:
                    for subtype in DIGITAL_SUBTYPES:
                        dropdown_options[subtype] = build_dropdown_options_subtype(df, subtype)
                else:
                    for subtype in DIGITAL_SUBTYPES:
                        dropdown_options[subtype] = None

                st.session_state.df = df
                st.session_state.filename = uploaded_file.name
                st.session_state.sheet_name = sheet_choice
                st.session_state.preview_result = None
                st.session_state.queue = []
                st.session_state.queue_next_id = 1
                st.session_state.log = []
                st.session_state.applied_indices = []
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

        unclassified = int(
            ((df["Digital_Subtype"] == SUBTYPE_UNCLASSIFIED) & (df["Channel"] != "TV")).sum()
        )
        if unclassified:
            st.info(
                f"{unclassified} Digital rows could not be classified as Social, Reserve or "
                "Programmatic (their placement name has neither 'UNE' nor 'UUT' — usually bonus "
                "or added-value lines). They cannot be backfilled through this app."
            )

        if st.button("Start over with another file (reset)"):
            reset_all()
            st.rerun()

        st.divider()
        st.subheader("What are you backfilling?")

        mode_label = st.radio("Mode", ["Digital", "TV"], horizontal=True, key="mode_selector")
        mode = mode_label.upper()

        subtype = None
        social_select_by = None
        if mode == "DIGITAL":
            subtype = st.radio(
                "Digital type", DIGITAL_SUBTYPES, horizontal=True, key="subtype_selector",
                help=(
                    "Social = placement contains 'UNE' on a social platform. "
                    "Reserve = placement contains 'UNE' on any other partner. "
                    "Programmatic = placement contains 'UUT'."
                ),
            )
            options = st.session_state.dropdown_options.get(subtype)
            specs = FILTER_SPECS[subtype]
            if subtype == SUBTYPE_SOCIAL:
                social_select_by = st.radio(
                    "Select rows by", [SOCIAL_SELECT_BY_PACKAGE, SOCIAL_SELECT_BY_PLACEMENT],
                    horizontal=True, key="social_select_by",
                    help=(
                        "Package needs CCD JTBD, Audience and Breakout as well. "
                        "Placement targets exactly one placement on its own."
                    ),
                )
                specs = specs[social_select_by]
        else:
            options = st.session_state.dropdown_options.get("TV")
            specs = TV_FILTER_SPEC

        if options is None:
            missing = missing_cols.get("DIGITAL" if mode == "DIGITAL" else "TV", [])
            st.error(
                f"{mode_label} mode is not available for this file: missing critical columns "
                f"({', '.join(missing)}). You can keep using the other mode."
            )
        elif mode == "DIGITAL" and not options.get("months"):
            st.warning(
                f"This file has no rows classified as Digital · {subtype}, so there is nothing "
                "to backfill here. Try another Digital type."
            )
        else:
            st.subheader("How should the values be calculated?")
            op_col1, op_col2 = st.columns([1, 2])
            with op_col1:
                target_field = st.radio(
                    "Field to backfill", ["Media_Cost", "Impressions"], key="field_selector"
                )
            with op_col2:
                operation_id = st.selectbox(
                    "Operation",
                    OPERATIONS_BY_FIELD[target_field],
                    format_func=lambda oid: OPERATIONS[oid]["label"],
                    key=f"operation_selector_{target_field}",
                )
            st.caption(OPERATIONS[operation_id]["help"])

            operation_spec = OPERATIONS[operation_id]
            source_column = operation_spec.get("source")
            if source_column and source_column not in df.columns:
                st.error(
                    f"This file has no '{source_column}' column, so this operation cannot be "
                    "used. Pick another operation."
                )
            else:
                st.subheader("Which rows?")
                st.caption(
                    "Fill the filters **in order** — each one only offers the values that "
                    "still exist given the ones above it, so the later filters can never "
                    "show a combination that isn't in your data."
                )

                key_prefix = f"filters_{mode}_{subtype}_{social_select_by}"
                base_mask = (
                    df["Digital_Subtype"] == subtype if mode == "DIGITAL" else df["Channel"] == "TV"
                )
                filters = render_cascading_filters(df, base_mask, specs, key_prefix)

                target_value = None
                if operation_spec["needs_target"]:
                    target_value = st.number_input(
                        f"Target {target_field} total",
                        min_value=0.0, step=0.01, format="%.2f",
                        key=f"target_value_{target_field}",
                    )
                else:
                    st.caption(
                        f"No target needed — values are copied row by row from '{source_column}'."
                    )

                signature = selection_signature(
                    mode, subtype, social_select_by, operation_id, target_value, filters
                )
                # There is no form to act as a submit boundary any more, so a preview left over
                # from an earlier selection would otherwise keep showing next to filters it no
                # longer describes. Drop it as soon as anything moves.
                if (
                    st.session_state.preview_result is not None
                    and st.session_state.preview_result.get("signature") != signature
                ):
                    st.session_state.preview_result = None

                if st.button("Preview", type="primary", use_container_width=True):
                    if mode == "DIGITAL":
                        subset = compute_subset_digital(df, subtype, filters, specs)
                    else:
                        subset = compute_subset_tv(df, filters)
                    preview, error = build_preview(
                        mode=mode, subtype=subtype, filters=filters, operation_id=operation_id,
                        target_value=target_value, subset=subset,
                        queue=st.session_state.queue, applied=st.session_state.applied_indices,
                    )
                    if error:
                        st.error(error)
                        st.session_state.preview_result = None
                    else:
                        preview["signature"] = signature
                        st.session_state.preview_result = preview

        preview = st.session_state.preview_result

        if preview is not None:
            st.divider()
            st.markdown(f"**Preview — {preview['operation_label']}**")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Rows in subset", preview["rows"])
            m2.metric(
                f"Current {preview['target_field']} sum",
                format_field_value(preview["target_field"], preview["current_sum"]),
            )
            m3.metric(
                "Resulting sum",
                format_field_value(preview["target_field"], preview["resulting_sum"]),
            )
            m4.metric("Delta", format_field_value(preview["target_field"], preview["delta"]))

            if st.button("Add to queue", type="primary"):
                st.session_state.queue.append(
                    {
                        "qid": st.session_state.queue_next_id,
                        "mode": preview["mode"],
                        "subtype": preview["subtype"],
                        "filters": preview["filters"],
                        "operation": preview["operation"],
                        "operation_label": preview["operation_label"],
                        "target_field": preview["target_field"],
                        "target_value": preview["target_value"],
                        "rows": preview["rows"],
                        "current_sum": preview["current_sum"],
                        "resulting_sum": preview["resulting_sum"],
                        "delta": preview["delta"],
                        "indices": preview["indices"],
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
                row = {
                    "#": item["qid"],
                    "Mode": item["mode"],
                    "Type": item["subtype"] or "—",
                    "Field": item["target_field"],
                    "Operation": OPERATIONS[item["operation"]]["label"],
                    "Rows": item["rows"],
                }
                for label, value in item["filters"].items():
                    row[label] = format_filter_value(value)
                row["Current Sum"] = round(item["current_sum"], 2)
                row["Target"] = (
                    round(item["target_value"], 2) if item["target_value"] is not None else None
                )
                row["Resulting Sum"] = round(item["resulting_sum"], 2)
                row["Delta"] = round(item["delta"], 2)
                queue_rows.append(row)
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
                        specs_for_item = TV_FILTER_SPEC
                        if item["mode"] == "DIGITAL":
                            spec_entry = FILTER_SPECS[item["subtype"]]
                            if isinstance(spec_entry, dict):
                                # Social: pick whichever variant matches the stored filters
                                spec_entry = (
                                    spec_entry[SOCIAL_SELECT_BY_PLACEMENT]
                                    if "Placement" in item["filters"]
                                    else spec_entry[SOCIAL_SELECT_BY_PACKAGE]
                                )
                            specs_for_item = spec_entry
                            subset = compute_subset_digital(
                                st.session_state.df, item["subtype"], item["filters"], specs_for_item
                            )
                        else:
                            subset = compute_subset_tv(st.session_state.df, item["filters"])

                        base_result = {
                            "Mode": item["mode"],
                            "Type": item["subtype"] or "—",
                            "Field": item["target_field"],
                            "Operation": OPERATIONS[item["operation"]]["label"],
                            **{k: format_filter_value(v) for k, v in item["filters"].items()},
                        }
                        new_values, error = compute_new_values(
                            subset, item["operation"], item["target_value"], item["mode"]
                        )
                        if error:
                            results.append({**base_result, "Status": f"Skipped — {error}"})
                            continue

                        current_sum = subset[item["target_field"]].fillna(0).sum()
                        st.session_state.df.loc[subset.index, item["target_field"]] = new_values
                        new_sum = st.session_state.df.loc[subset.index, item["target_field"]].sum()
                        any_applied = True
                        st.session_state.log.append(
                            {
                                "Timestamp": datetime.now().isoformat(timespec="seconds"),
                                "Mode": item["mode"],
                                "Type": item["subtype"] or "",
                                "Field": item["target_field"],
                                "Operation": OPERATIONS[item["operation"]]["label"],
                                **{k: format_filter_value(v) for k, v in item["filters"].items()},
                                "Target_Value": item["target_value"],
                                "Rows_Affected": len(subset),
                                "Sum_Before": current_sum,
                                "Sum_After": new_sum,
                            }
                        )
                        st.session_state.applied_indices.append(
                            {"label": item["operation_label"], "indices": list(subset.index)}
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
