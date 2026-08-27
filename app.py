"""M.E.R.I.T. APP — Media Evaluation, Reconciliation & Integrity Tool.

Shell that shows a home menu and mounts whichever tool the user picks. Each tool lives
in its own module under tools/ with its own render()/init_state(), so session-state keys
never collide between tools and new tools can be added without touching this file's
logic beyond registering them in TOOLS below.
"""
import streamlit as st

from tools import (
    data_caveats, merit_deliver, merit_inspect, rroi_backfill, tv_standardization,
)

st.set_page_config(page_title="M.E.R.I.T. APP", layout="wide")

TOOLS = {
    "inspect": {
        "label": "1. Merit Inspect",
        "icon": "🔍",
        "description": (
            "Monthly QA pass: row-level rule checks, spend-vs-delivery analysis "
            "per unit, and a brand/category/channel coverage checklist."
        ),
        "render": merit_inspect.render,
    },
    "tv": {
        "label": "2. TV Data Standardization",
        "icon": "📺",
        "description": (
            "Upload the TV team's raw spot-level files and get back a standardized "
            "version — AFFID DATE converted to a real date, networks and dayparts mapped."
        ),
        "render": tv_standardization.render,
    },
    "backfill": {
        "label": "3. RROI Manual Backfill",
        "icon": "🧩",
        "description": (
            "Fill in missing Media Cost or Impressions on Digital (Social / Reserve / "
            "Programmatic) or TV rows — weighted, evenly, or copied from another column."
        ),
        "render": rroi_backfill.render,
    },
    "deliver": {
        "label": "4. Merit Deliver",
        "icon": "📦",
        "description": (
            "Build the client-facing deliverable, reconcile it against the source, "
            "and flag visual duplicates before you send anything out."
        ),
        "render": merit_deliver.render,
    },
    "caveats": {
        "label": "5. Data Caveats Generator",
        "icon": "⚠️",
        "description": (
            "Upload delivery files and generate one Data Caveat Log per brand, flagging "
            "rows with cost but no impressions (or the reverse)."
        ),
        "render": data_caveats.render,
    },
}

CARDS_PER_ROW = 3

if "active_tool" not in st.session_state:
    st.session_state.active_tool = None


def render_home():
    st.markdown(
        """
        <style>
        /* Oculta el ícono de anclaje que Streamlit agrega a los headers */
        h1 a, h2 a, h3 a, h4 a { display: none !important; }
        /* Tarjetas de altura pareja: la descripción ocupa un alto fijo y el
           botón queda anclado abajo, sin importar cuántas líneas tenga el texto. */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            min-height: 260px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='text-align:center; padding: 48px 0 8px;'>"
        "<h1 style='font-size:56px; margin-bottom:0;'>M.E.R.I.T. APP</h1>"
        "<p style='font-size:18px; color:gray; margin-top:4px;'>"
        "Media Evaluation, Reconciliation &amp; Integrity Tool</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.divider()
    st.subheader("What do you want to do?")

    items = list(TOOLS.items())
    for row_start in range(0, len(items), CARDS_PER_ROW):
        row_items = items[row_start:row_start + CARDS_PER_ROW]
        columns = st.columns(CARDS_PER_ROW)
        for column, (key, tool) in zip(columns, row_items):
            with column:
                with st.container(border=True):
                    st.markdown(f"#### {tool['icon']}&nbsp;&nbsp;{tool['label']}")
                    st.caption(tool["description"])
                    if st.button("Open", key=f"open_{key}", type="primary", use_container_width=True):
                        st.session_state.active_tool = key
                        st.rerun()


active = st.session_state.active_tool
if active is None:
    render_home()
else:
    TOOLS[active]["render"]()
