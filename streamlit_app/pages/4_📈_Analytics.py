"""
streamlit_app/pages/4_📈_Analytics.py
Visualization and analytics page using Plotly charts.
"""
import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

st.set_page_config(page_title="Analytics | SQL Optimizer", page_icon="📈", layout="wide")

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from streamlit_app.components import inject_global_css, render_page_header
from streamlit_app.utils import load_evaluation_results

inject_global_css()

PLOTLY_TEMPLATE = dict(
    layout=dict(
        paper_bgcolor="#0d1117",
        plot_bgcolor="#161b22",
        font=dict(color="#c9d1d9", family="Inter, sans-serif"),
        xaxis=dict(gridcolor="#21262d", linecolor="#30363d"),
        yaxis=dict(gridcolor="#21262d", linecolor="#30363d"),
    )
)

render_page_header(
    "Analytics",
    "Visual performance analysis — speedup distribution, latency improvements, and accuracy comparison",
    "📈",
)

eval_data = load_evaluation_results()

if not eval_data:
    st.warning("No evaluation results found. Run the **Benchmark** page first to generate data.")
    st.stop()

comparison = eval_data.get("comparison_table", [])
if not comparison:
    st.warning("No comparison data available.")
    st.stop()

# Build dataframe
rows = []
for item in comparison:
    agent = item.get("agent", {})
    baseline = item.get("baseline", {})
    rows.append({
        "query_id": item["query_id"],
        "anti_pattern": item.get("anti_pattern", "")[:45] + "…",
        "orig_ms": agent.get("original_latency_ms") or 0,
        "opt_ms": agent.get("optimized_latency_ms") or 0,
        "baseline_ms": baseline.get("optimized_latency_ms") or 0,
        "agent_speedup": agent.get("speedup_ratio") or 1.0,
        "baseline_speedup": baseline.get("speedup_ratio") or 1.0,
        "agent_valid": agent.get("is_valid", False),
        "baseline_valid": baseline.get("is_valid", False),
        "indexes": agent.get("applied_indexes_count", 0),
        "retries": agent.get("retries_needed", 1),
    })
df = pd.DataFrame(rows)

# ── Row 1: Speedup Comparison + Latency Bar ───────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    st.markdown("#### Speedup Factor by Query")
    fig_speedup = go.Figure()
    fig_speedup.add_trace(go.Bar(
        x=df["query_id"], y=df["baseline_speedup"],
        name="Zero-Shot Baseline", marker_color="#f59e0b", opacity=0.8,
    ))
    fig_speedup.add_trace(go.Bar(
        x=df["query_id"], y=df["agent_speedup"],
        name="Multi-Agent Optimizer", marker_color="#58a6ff",
    ))
    fig_speedup.add_hline(y=1.0, line_dash="dot", line_color="#6b7280", annotation_text="1x (no gain)")
    fig_speedup.update_layout(
        **PLOTLY_TEMPLATE["layout"],
        barmode="group",
        legend=dict(orientation="h", y=1.12),
        height=340,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis_title="Query ID",
        yaxis_title="Speedup (x)",
    )
    st.plotly_chart(fig_speedup, use_container_width=True)

with col2:
    st.markdown("#### Latency Before vs After (ms)")
    fig_lat = go.Figure()
    fig_lat.add_trace(go.Bar(
        x=df["query_id"], y=df["orig_ms"],
        name="Original", marker_color="#f85149", opacity=0.85,
    ))
    fig_lat.add_trace(go.Bar(
        x=df["query_id"], y=df["opt_ms"],
        name="Optimized", marker_color="#3fb950",
    ))
    fig_lat.update_layout(
        **PLOTLY_TEMPLATE["layout"],
        barmode="group",
        legend=dict(orientation="h", y=1.12),
        height=340,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis_title="Query ID",
        yaxis_title="Latency (ms)",
    )
    st.plotly_chart(fig_lat, use_container_width=True)

# ── Row 2: Accuracy Pie + Indexes Bar ─────────────────────────────────────────
st.markdown("---")
col3, col4 = st.columns(2)

with col3:
    st.markdown("#### Accuracy: Baseline vs Agent")
    b_sum = eval_data.get("summary", {}).get("baseline", {})
    a_sum = eval_data.get("summary", {}).get("agent_optimizer", {})
    total = eval_data.get("total_queries", 10)

    fig_pie = go.Figure()
    fig_pie.add_trace(go.Pie(
        labels=["Baseline Pass", "Baseline Fail", "Agent Pass", "Agent Fail"],
        values=[
            b_sum.get("successful_cases", 0),
            total - b_sum.get("successful_cases", 0),
            a_sum.get("successful_cases", 0),
            total - a_sum.get("successful_cases", 0),
        ],
        hole=0.45,
        marker_colors=["#f59e0b", "#6b7280", "#3fb950", "#f85149"],
        textinfo="label+percent",
    ))
    fig_pie.update_layout(
        **PLOTLY_TEMPLATE["layout"],
        height=320,
        margin=dict(l=0, r=0, t=10, b=0),
        showlegend=False,
    )
    st.plotly_chart(fig_pie, use_container_width=True)

with col4:
    st.markdown("#### Indexes Synthesized per Query")
    fig_idx = go.Figure(go.Bar(
        x=df["query_id"], y=df["indexes"],
        marker_color="#a5d6ff",
        text=df["indexes"],
        textposition="auto",
    ))
    fig_idx.update_layout(
        **PLOTLY_TEMPLATE["layout"],
        height=320,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis_title="Query ID",
        yaxis_title="Number of Indexes",
    )
    st.plotly_chart(fig_idx, use_container_width=True)

# ── Row 3: Speedup scatter with anti-pattern labels ───────────────────────────
st.markdown("---")
st.markdown("#### Speedup Distribution — Original Latency vs Speedup Factor")
fig_scatter = px.scatter(
    df,
    x="orig_ms", y="agent_speedup",
    text="query_id",
    size="indexes",
    color="agent_speedup",
    color_continuous_scale=["#f85149", "#f59e0b", "#3fb950"],
    hover_data={"anti_pattern": True, "orig_ms": ":.2f", "opt_ms": ":.2f", "agent_speedup": ":.2f"},
    labels={"orig_ms": "Original Latency (ms)", "agent_speedup": "Speedup Factor"},
)
fig_scatter.update_traces(textposition="top center", marker=dict(line=dict(width=1, color="#21262d")))
fig_scatter.add_hline(y=1.0, line_dash="dot", line_color="#6b7280")
fig_scatter.update_layout(
    **PLOTLY_TEMPLATE["layout"],
    height=400,
    coloraxis_showscale=False,
    margin=dict(l=0, r=0, t=10, b=0),
)
st.plotly_chart(fig_scatter, use_container_width=True)

# Summary stats table
st.markdown("---")
st.markdown("#### Summary Statistics")
summary_df = pd.DataFrame([{
    "Metric": "Zero-Shot Baseline Accuracy",
    "Value": f"{b_sum.get('success_rate_pct', 0):.1f}%",
}, {
    "Metric": "Multi-Agent Optimizer Accuracy",
    "Value": f"{a_sum.get('success_rate_pct', 0):.1f}%",
}, {
    "Metric": "Baseline Average Speedup",
    "Value": f"{b_sum.get('average_speedup', 0):.2f}x",
}, {
    "Metric": "Agent Average Speedup",
    "Value": f"{a_sum.get('average_speedup', 0):.2f}x",
}, {
    "Metric": "Agent Max Speedup",
    "Value": f"{a_sum.get('max_speedup', 0):.2f}x",
}, {
    "Metric": "Total Indexes Synthesized",
    "Value": str(a_sum.get("total_indexes_created", 0)),
}, {
    "Metric": "Total Iteration Attempts",
    "Value": str(a_sum.get("total_iteration_attempts", 0)),
}])
st.dataframe(summary_df, use_container_width=True, hide_index=True)
