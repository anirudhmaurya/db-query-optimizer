"""
streamlit_app/app.py
Home page / entrypoint for the Multi-Agent SQL Query Optimizer Streamlit app.
"""
import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

st.set_page_config(
    page_title="SQL Query Optimizer",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

from streamlit_app.components import inject_global_css, render_page_header, render_metric_card
from streamlit_app.utils import (
    load_evaluation_results,
    load_test_cases,
    DB_PATH,
    PROVIDER_MODELS,
    get_env_api_key,
)

inject_global_css()

# ── Sidebar: global settings stored in session_state ─────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding:1rem 0 1.5rem 0; border-bottom:1px solid #21262d; margin-bottom:1rem;">
        <div style="font-size:1.1rem;font-weight:700;color:#e6edf3;">⚡ SQL Optimizer</div>
        <div style="font-size:0.72rem;color:#8b949e;margin-top:2px;">Multi-Agent AI Pipeline</div>
    </div>
    """, unsafe_allow_html=True)

    provider = st.selectbox("LLM Provider", list(PROVIDER_MODELS.keys()),
                            index=0, key="global_provider")
    model_list = PROVIDER_MODELS[provider]
    model = st.selectbox("Model", model_list, key="global_model")

    auto_key = get_env_api_key(provider) if provider != "mock" else None
    api_key_input = st.text_input(
        "API Key",
        value=auto_key or "",
        type="password",
        placeholder="Leave blank to use .env",
        key="global_api_key",
    )
    st.session_state["api_key"] = api_key_input or auto_key or None

    st.slider("Max Retries", 1, 5, 3, key="global_max_retries")
    st.slider("Timeout (sec)", 5.0, 60.0, 10.0, step=5.0, key="global_timeout")

    st.markdown("---")
    st.caption("Navigate using the pages above ↑")

# ── Main content ─────────────────────────────────────────────────────────────
render_page_header(
    "Multi-Agent SQL Query Optimizer",
    "Execution-guided AI pipeline: Profiler → IndexArchitect → Developer → Verifier",
    "⚡",
)

# Hero section
st.markdown("""
<div style="background:linear-gradient(135deg,#161b22 0%,#0d1117 100%);
            border:1px solid #21262d;border-radius:16px;padding:2rem;margin-bottom:2rem;
            box-shadow:0 4px 24px rgba(0,0,0,0.4);">
    <div style="display:flex;gap:1.5rem;flex-wrap:wrap;align-items:flex-start;">
        <div style="flex:1;min-width:280px;">
            <h2 style="margin:0 0 0.5rem 0;font-size:1.3rem;color:#e6edf3;">How It Works</h2>
            <p style="color:#8b949e;font-size:0.88rem;line-height:1.6;margin:0;">
                A four-agent pipeline eliminates SQL performance bottlenecks through closed-loop, 
                execution-guided optimization with deterministic sandbox verification.
            </p>
        </div>
        <div style="display:flex;gap:0.75rem;flex-wrap:wrap;">
            <div style="background:#0d2b3d;border:1px solid #1f6feb33;border-radius:10px;padding:0.75rem 1rem;min-width:120px;text-align:center;">
                <div style="font-size:1.4rem;">🔍</div>
                <div style="color:#58a6ff;font-size:0.8rem;font-weight:600;margin-top:4px;">Profiler</div>
                <div style="color:#8b949e;font-size:0.7rem;">EXPLAIN analysis</div>
            </div>
            <div style="background:#0d2b3d;border:1px solid #1f6feb33;border-radius:10px;padding:0.75rem 1rem;min-width:120px;text-align:center;">
                <div style="font-size:1.4rem;">🏗️</div>
                <div style="color:#58a6ff;font-size:0.8rem;font-weight:600;margin-top:4px;">IndexArchitect</div>
                <div style="color:#8b949e;font-size:0.7rem;">DDL index synthesis</div>
            </div>
            <div style="background:#0d2b3d;border:1px solid #1f6feb33;border-radius:10px;padding:0.75rem 1rem;min-width:120px;text-align:center;">
                <div style="font-size:1.4rem;">✏️</div>
                <div style="color:#58a6ff;font-size:0.8rem;font-weight:600;margin-top:4px;">Developer</div>
                <div style="color:#8b949e;font-size:0.7rem;">SQL rewriting</div>
            </div>
            <div style="background:#0d2b3d;border:1px solid #1f6feb33;border-radius:10px;padding:0.75rem 1rem;min-width:120px;text-align:center;">
                <div style="font-size:1.4rem;">✅</div>
                <div style="color:#58a6ff;font-size:0.8rem;font-weight:600;margin-top:4px;">Verifier</div>
                <div style="color:#8b949e;font-size:0.7rem;">Equivalence check</div>
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Stats from existing evaluation results
eval_data = load_evaluation_results()
db_exists = DB_PATH.exists()
test_cases = load_test_cases()

col1, col2, col3, col4 = st.columns(4)
with col1:
    render_metric_card("Database", "✅ Ready" if db_exists else "⚠️ Missing", color="#3fb950" if db_exists else "#f85149")
with col2:
    render_metric_card("Test Cases", str(len(test_cases)), color="#58a6ff")
with col3:
    if eval_data:
        agent_summary = eval_data.get("summary", {}).get("agent_optimizer", {})
        render_metric_card("Agent Accuracy", f"{agent_summary.get('success_rate_pct', 0):.0f}%", color="#3fb950")
    else:
        render_metric_card("Agent Accuracy", "—", "Run benchmark first", color="#8b949e")
with col4:
    if eval_data:
        agent_summary = eval_data.get("summary", {}).get("agent_optimizer", {})
        render_metric_card("Max Speedup", f"{agent_summary.get('max_speedup', 0):.2f}x", color="#f59e0b")
    else:
        render_metric_card("Max Speedup", "—", color="#8b949e")

st.markdown("<br>", unsafe_allow_html=True)

# Quick-action cards
col_a, col_b = st.columns(2)
with col_a:
    st.markdown("""
    <div style="background:#161b22;border:1px solid #21262d;border-radius:12px;padding:1.5rem;height:160px;">
        <div style="font-size:1.5rem;margin-bottom:0.5rem;">⚡</div>
        <div style="color:#e6edf3;font-weight:600;font-size:1rem;">Optimize a Query</div>
        <div style="color:#8b949e;font-size:0.82rem;margin-top:4px;">Paste any SQL query and watch the 4-agent pipeline optimize it in real time.</div>
    </div>
    """, unsafe_allow_html=True)
    st.page_link("pages/1_⚡_Optimizer.py", label="Open Optimizer →", icon="⚡")

with col_b:
    st.markdown("""
    <div style="background:#161b22;border:1px solid #21262d;border-radius:12px;padding:1.5rem;height:160px;">
        <div style="font-size:1.5rem;margin-bottom:0.5rem;">📊</div>
        <div style="color:#e6edf3;font-weight:600;font-size:1rem;">Run Full Benchmark</div>
        <div style="color:#8b949e;font-size:0.82rem;margin-top:4px;">Evaluate all 10 benchmark queries comparing Zero-Shot Baseline vs Multi-Agent Optimizer.</div>
    </div>
    """, unsafe_allow_html=True)
    st.page_link("pages/2_📊_Benchmark.py", label="Open Benchmark →", icon="📊")

# Recent results preview
if eval_data:
    st.markdown("---")
    st.markdown("### 📋 Last Evaluation Results")
    st.caption(f"Timestamp: {eval_data.get('timestamp', 'N/A')}  |  Model: {eval_data.get('model', 'N/A')}")

    from streamlit_app.components import render_benchmark_table
    comparison = eval_data.get("comparison_table", [])
    if comparison:
        render_benchmark_table(comparison)
else:
    st.markdown("---")
    st.info("No evaluation results found. Run the **Benchmark** page to generate results.")
