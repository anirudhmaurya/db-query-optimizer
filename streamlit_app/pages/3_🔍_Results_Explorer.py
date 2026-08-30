"""
streamlit_app/pages/3_🔍_Results_Explorer.py
Per-query results and agent trajectory explorer.
"""
import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

st.set_page_config(page_title="Results Explorer | SQL Optimizer", page_icon="🔍", layout="wide")

from streamlit_app.components import (
    inject_global_css, render_page_header, render_sql_diff, render_speedup_gauge,
    render_bottlenecks, render_applied_indexes, render_agent_trajectory,
    render_metric_card, render_status_badge,
)
from streamlit_app.utils import load_evaluation_results, load_trajectories

inject_global_css()

render_page_header(
    "Results Explorer",
    "Deep-dive into per-query agent trajectories, SQL diffs, and verification reports",
    "🔍",
)

eval_data = load_evaluation_results()
trajectories = load_trajectories()

if not eval_data:
    st.warning("No evaluation results found. Run the **Benchmark** page first to generate results.")
    st.stop()

comparison = eval_data.get("comparison_table", [])
if not comparison:
    st.warning("No comparison data in evaluation results.")
    st.stop()

# Build trajectory lookup: {test_case_id: [steps]}
traj_lookup: dict = {}
for step in trajectories:
    tc_id = step.get("test_case_id", "")
    traj_lookup.setdefault(tc_id, []).append(step)

# Query selector
query_labels = {f"{item['query_id']}: {item['name'][:50]}": item for item in comparison}
selected_label = st.selectbox("Select Query", list(query_labels.keys()))
item = query_labels[selected_label]

tc_id = item["query_id"]
agent = item.get("agent", {})
baseline = item.get("baseline", {})

# Header row
st.markdown(f"""
<div style="background:#161b22;border:1px solid #21262d;border-radius:12px;padding:1.25rem 1.5rem;margin:1rem 0;">
    <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
        <span style="color:#58a6ff;font-size:1rem;font-weight:700;">{tc_id}</span>
        <span style="color:#8b949e;font-size:0.85rem;">{item.get('name','')}</span>
    </div>
    <div style="color:#f59e0b;font-size:0.8rem;margin-top:6px;">⚠️ Anti-Pattern: {item.get('anti_pattern','')}</div>
</div>
""", unsafe_allow_html=True)

# Metrics
m1, m2, m3, m4, m5 = st.columns(5)
with m1:
    render_metric_card("Baseline Acc", "✅ 100%" if baseline.get("is_valid") else "❌ 0%",
                       color="#3fb950" if baseline.get("is_valid") else "#f85149")
with m2:
    render_metric_card("Agent Acc", "✅ 100%" if agent.get("is_valid") else "❌ 0%",
                       color="#3fb950" if agent.get("is_valid") else "#f85149")
with m3:
    render_metric_card("Orig Latency", f"{agent.get('original_latency_ms',0):.2f} ms"
                       if agent.get("original_latency_ms") else "N/A", color="#8b949e")
with m4:
    render_metric_card("Opt Latency", f"{agent.get('optimized_latency_ms',0):.2f} ms"
                       if agent.get("optimized_latency_ms") else "N/A", color="#58a6ff")
with m5:
    render_speedup_gauge(agent.get("speedup_ratio"))

st.markdown("<br>", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["🔄 SQL Diff", "🏗️ Indexes & Techniques", "🤖 Agent Trajectory", "📄 Raw JSON"])

with tab1:
    # We need original + optimized SQL — pull from agent_results if available
    from streamlit_app.utils import load_agent_results
    agent_results = load_agent_results()
    orig_sql = optimized_sql = None
    if agent_results:
        for r in agent_results.get("results", []):
            if r.get("id") == tc_id:
                orig_sql = r.get("original_query", "")
                optimized_sql = r.get("optimized_sql", "")
                break
    if orig_sql and optimized_sql:
        render_sql_diff(orig_sql, optimized_sql)
    else:
        st.info("SQL diff not available — agent_results.json not found or query not matched.")

with tab2:
    st.markdown("**Applied Indexes**")
    render_applied_indexes(agent.get("applied_indexes", []))
    st.markdown("**Applied Techniques**")
    techs = agent.get("applied_techniques", [])
    if techs:
        for t in techs:
            st.markdown(f"- `{t}`")
    else:
        st.info("No techniques listed.")

with tab3:
    steps = traj_lookup.get(tc_id, [])
    if steps:
        render_agent_trajectory(steps)
    else:
        st.info("No trajectory data found for this query. Run the benchmark to generate trajectories.")

with tab4:
    st.json(item)
