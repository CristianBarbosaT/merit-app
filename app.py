"""M.E.R.I.T. APP — Media Evaluation, Reconciliation & Integrity Tool.

Shell that shows a home menu and mounts whichever tool the user picks. Each tool lives
in its own module under tools/ with its own render()/init_state(), so session-state keys
never collide between tools and new tools can be added without touching this file's
logic beyond registering them in TOOLS below.
"""
import streamlit as st

from tools import rroi_backfill, data_caveats

st.set_page_config(page_title="M.E.R.I.T APP", layout="wide")

TOOLS = {
    "backfill": {
        "label": "RROI Manual Backfill",
        "description": (
            "Fill in missing Media Cost or Impressions on Digital (Social / Reserve / "
            "Programmatic) or TV rows — weighted, evenly, or copied from another column."
        ),
        "render": rroi_backfill.render,
    },
    "caveats": {
        "label": "Data Caveats Generator",
        "description": (
            "Upload delivery files and generate one Data Caveat Log per brand, flagging "
            "rows with cost but no impressions (or the reverse)."
        ),
        "render": data_caveats.render,
    },
}

if "active_tool" not in st.session_state:
    st.session_state.active_tool = None


def render_home():
    st.markdown(
        "<div style='text-align:center; padding: 48px 0 8px;'>"
        "<h1 style='font-size:56px; margin-bottom:0;'>M.E.R.I.T APP</h1>"
        "<p style='font-size:18px; color:gray; margin-top:4px;'>"
        "Media Evaluation, Reconciliation &amp; Integrity Tool</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.divider()
    st.subheader("What do you want to do?")

    columns = st.columns(len(TOOLS))
    for column, (key, tool) in zip(columns, TOOLS.items()):
        with column:
            with st.container(border=True):
                st.markdown(f"#### {tool['label']}")
                st.caption(tool["description"])
                if st.button("Open", key=f"open_{key}", type="primary", use_container_width=True):
                    st.session_state.active_tool = key
                    st.rerun()


active = st.session_state.active_tool
if active is None:
    render_home()
else:
    TOOLS[active]["render"]()
