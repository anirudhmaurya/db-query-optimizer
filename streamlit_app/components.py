"""
streamlit_app/components.py
Reusable UI components for the Multi-Agent SQL Query Optimizer Streamlit app.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
import streamlit as st


DARK_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
    background-color: #0d1117 !important;
    color: #e6edf3 !important;
    font-family: 'Inter', sans-serif !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #161b22 0%, #0d1117 100%) !important;
    border-right: 1px solid #21262d !important;
}
[data-testid="stSidebar"] * { color: #c9d1d9 !important; }
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stTextInput label,
[data-testid="stSidebar"] .stSlider label { color: #8b949e !important; font-size: 0.78rem !important; font-weight: 500 !important; letter-spacing: 0.04em !important; text-transform: uppercase; }

/* Metric cards */
[data-testid="stMetricValue"] { color: #58a6ff !important; font-size: 2rem !important; font-weight: 700 !important; }
[data-testid="stMetricLabel"] { color: #8b949e !important; font-size: 0.75rem !important; text-transform: uppercase; letter-spacing: 0.06em; }
[data-testid="stMetricDelta"] { font-size: 0.8rem !important; }

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #1f6feb 0%, #388bfd 100%) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    padding: 0.55rem 1.4rem !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 2px 8px rgba(31,111,235,0.4) !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 16px rgba(31,111,235,0.6) !important;
}

/* Text areas */
.stTextArea textarea {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px !important;
    color: #e6edf3 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.85rem !important;
}
.stTextArea textarea:focus {
    border-color: #388bfd !important;
    box-shadow: 0 0 0 3px rgba(56,139,253,0.15) !important;
}

/* Selectbox */
.stSelectbox > div > div {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px !important;
    color: #e6edf3 !important;
}

/* Expander */
.streamlit-expanderHeader {
    background: #161b22 !important;
    border: 1px solid #21262d !important;
    border-radius: 8px !important;
    color: #c9d1d9 !important;
    font-weight: 500 !important;
}
.streamlit-expanderContent {
    background: #0d1117 !important;
    border: 1px solid #21262d !important;
    border-top: none !important;
    border-radius: 0 0 8px 8px !important;
}

/* Tabs */
[data-testid="stTab"] {
    color: #8b949e !important;
    font-weight: 500 !important;
}
[data-testid="stTab"][aria-selected="true"] {
    color: #58a6ff !important;
    border-bottom-color: #58a6ff !important;
}

/* Code blocks */
.stCode { border-radius: 8px !important; }
pre { background: #161b22 !important; border: 1px solid #30363d !important; border-radius: 8px !important; }

/* Divider */
hr { border-color: #21262d !important; }

/* Progress bar */
[data-testid="stProgress"] > div > div { background: linear-gradient(90deg, #1f6feb, #58a6ff) !important; }

/* Info/success/warning/error */
.stAlert { border-radius: 8px !important; }

/* Dataframe */
[data-testid="stDataFrame"] { border-radius: 8px !important; overflow: hidden; }

/* Spinner */
[data-testid="stSpinner"] { color: #58a6ff !important; }

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #30363d; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #484f58; }
</style>
"""


def inject_global_css() -> None:
    """Inject dark-mode CSS into the Streamlit app."""
    st.markdown(DARK_CSS, unsafe_allow_html=True)


def render_page_header(title: str, subtitle: str = "", icon: str = "") -> None:
    """Render a consistent page header."""
    st.markdown(f"""
    <div style="padding: 0.5rem 0 1.5rem 0; border-bottom: 1px solid #21262d; margin-bottom: 1.5rem;">
        <h1 style="margin:0; font-size:1.8rem; font-weight:700; color:#e6edf3; font-family:'Inter',sans-serif;">
            {icon} {title}
        </h1>
        {f'<p style="margin:0.4rem 0 0 0; color:#8b949e; font-size:0.9rem;">{subtitle}</p>' if subtitle else ''}
    </div>
    """, unsafe_allow_html=True)


def render_metric_card(label: str, value: str, delta: str = "", color: str = "#58a6ff") -> None:
    """Render a styled metric card."""
    delta_html = f'<div style="color:#3fb950;font-size:0.78rem;margin-top:2px;">{delta}</div>' if delta else ""
    st.markdown(f"""
    <div style="background:#161b22;border:1px solid #21262d;border-radius:12px;padding:1rem 1.2rem;
                box-shadow:0 2px 8px rgba(0,0,0,0.3);">
        <div style="color:#8b949e;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.08em;font-weight:600;">{label}</div>
        <div style="color:{color};font-size:1.8rem;font-weight:700;margin-top:0.3rem;font-family:'Inter',sans-serif;">{value}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)


def render_status_badge(status: str) -> str:
    """Return HTML for a colored status badge."""
    colors = {
        "SUCCESS": ("#3fb950", "#0d2b0d"),
        "PASSED":  ("#3fb950", "#0d2b0d"),
        "FAILED":  ("#f85149", "#2b0d0d"),
        "ERROR":   ("#f85149", "#2b0d0d"),
        "RUNNING": ("#d29922", "#2b200d"),
    }
    fg, bg = colors.get(status.upper(), ("#8b949e", "#21262d"))
    return f'<span style="background:{bg};color:{fg};border:1px solid {fg}33;border-radius:20px;padding:2px 10px;font-size:0.72rem;font-weight:600;letter-spacing:0.04em;">{status}</span>'


def render_sql_diff(original_sql: str, optimized_sql: str) -> None:
    """Render original vs optimized SQL side-by-side."""
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Original SQL**")
        st.code(original_sql.strip(), language="sql")
    with col2:
        st.markdown("**Optimized SQL**")
        st.code(optimized_sql.strip(), language="sql")


def render_speedup_gauge(speedup: Optional[float], label: str = "Speedup") -> None:
    """Render a compact speedup display."""
    from streamlit_app.utils import speedup_badge_color
    if speedup is None:
        return
    color = speedup_badge_color(speedup)
    st.markdown(f"""
    <div style="text-align:center;padding:1rem;background:#161b22;border:1px solid #21262d;border-radius:12px;">
        <div style="color:#8b949e;font-size:0.75rem;text-transform:uppercase;letter-spacing:0.08em;">{label}</div>
        <div style="color:{color};font-size:3rem;font-weight:800;line-height:1.1;">{speedup:.2f}<span style="font-size:1.5rem;">x</span></div>
        <div style="color:#8b949e;font-size:0.7rem;margin-top:4px;">faster than original</div>
    </div>
    """, unsafe_allow_html=True)


def render_bottlenecks(bottlenecks: List[Dict[str, Any]]) -> None:
    """Render profiler bottleneck cards."""
    severity_colors = {"HIGH": "#f85149", "MEDIUM": "#d29922", "LOW": "#3fb950"}
    if not bottlenecks:
        st.info("No bottlenecks identified.")
        return
    for b in bottlenecks:
        sev = b.get("severity", "MEDIUM")
        color = severity_colors.get(sev, "#8b949e")
        st.markdown(f"""
        <div style="background:#161b22;border-left:3px solid {color};border-radius:0 8px 8px 0;
                    padding:0.75rem 1rem;margin:0.4rem 0;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
                <span style="color:{color};font-size:0.7rem;font-weight:700;text-transform:uppercase;">{sev}</span>
                <span style="color:#c9d1d9;font-size:0.85rem;font-weight:600;">{b.get('type','')}</span>
                {f'<span style="color:#8b949e;font-size:0.75rem;">— {b.get("table","")}</span>' if b.get("table") else ''}
            </div>
            <div style="color:#8b949e;font-size:0.8rem;">{b.get('detail','')}</div>
        </div>
        """, unsafe_allow_html=True)


def render_applied_indexes(indexes: List[str]) -> None:
    """Render list of applied DDL indexes."""
    if not indexes:
        st.info("No indexes were created for this query.")
        return
    for ddl in indexes:
        st.code(ddl, language="sql")


def render_agent_trajectory(execution_steps: List[Dict[str, Any]]) -> None:
    """Render expandable agent trajectory steps."""
    agent_icons = {
        "Profiler": "🔍",
        "IndexArchitect": "🏗️",
        "Developer": "✏️",
        "OrchestratorFallback": "🛡️",
    }
    for step in execution_steps:
        agent_id = step.get("agent_id", "Agent")
        icon = agent_icons.get(agent_id, "🤖")
        retries = step.get("retries_triggered", 0)
        tool = step.get("tool_called", "")
        tool_output = step.get("tool_output", {})
        status = tool_output.get("status", "")

        title = f"{icon} {agent_id}  |  `{tool}`"
        if retries:
            title += f"  |  Retry #{retries}"
        if status:
            title += f"  |  {status}"

        with st.expander(title, expanded=False):
            tabs = st.tabs(["LLM Output", "Tool Output", "Raw Prompt"])
            with tabs[0]:
                llm_out = step.get("llm_output", {})
                if "rewritten_sql" in llm_out:
                    st.markdown("**Rewritten SQL**")
                    st.code(llm_out["rewritten_sql"], language="sql")
                if "applied_techniques" in llm_out:
                    st.markdown("**Techniques Applied**")
                    for t in llm_out["applied_techniques"]:
                        st.markdown(f"- {t}")
                if "identified_bottlenecks" in llm_out:
                    st.markdown("**Bottlenecks Identified**")
                    render_bottlenecks(llm_out["identified_bottlenecks"])
                if "recommended_indexes" in llm_out:
                    st.markdown("**Recommended Indexes**")
                    for idx in llm_out["recommended_indexes"]:
                        st.code(idx.get("ddl", ""), language="sql")
                        if idx.get("purpose"):
                            st.caption(idx["purpose"])
            with tabs[1]:
                st.json(tool_output)
            with tabs[2]:
                raw = step.get("raw_prompt", "")
                st.text_area("Prompt", value=raw[:3000] + ("..." if len(raw) > 3000 else ""),
                             height=200, disabled=True, key=f"prompt_{id(step)}")


def render_benchmark_table(comparison_table: List[Dict[str, Any]]) -> None:
    """Render styled comparison table using Streamlit columns."""
    import pandas as pd
    from streamlit_app.utils import speedup_badge_color

    rows = []
    for item in comparison_table:
        agent = item.get("agent", {})
        baseline = item.get("baseline", {})
        sp = agent.get("speedup_ratio")
        rows.append({
            "Query ID": item.get("query_id", ""),
            "Anti-Pattern": item.get("anti_pattern", "")[:55] + ("…" if len(item.get("anti_pattern","")) > 55 else ""),
            "Baseline Acc": "✅ 100%" if baseline.get("is_valid") else "❌ 0%",
            "Agent Acc": "✅ 100%" if agent.get("is_valid") else "❌ 0%",
            "Orig (ms)": f"{agent.get('original_latency_ms', 0):.2f}" if agent.get("original_latency_ms") else "N/A",
            "Opt (ms)": f"{agent.get('optimized_latency_ms', 0):.2f}" if agent.get("optimized_latency_ms") else "N/A",
            "Speedup": f"{sp:.2f}x" if sp else "—",
            "Indexes": agent.get("indexes_created", "No"),
            "Retries": str(agent.get("retries_needed", 1)),
        })

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Speedup": st.column_config.TextColumn("Speedup Factor"),
            "Orig (ms)": st.column_config.TextColumn("Orig Latency"),
            "Opt (ms)": st.column_config.TextColumn("Opt Latency"),
        }
    )
