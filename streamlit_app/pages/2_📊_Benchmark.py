"""
streamlit_app/pages/2_📊_Benchmark.py
Full benchmark evaluation page.
"""
import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

st.set_page_config(page_title="Benchmark | SQL Optimizer", page_icon="📊", layout="wide")

from streamlit_app.components import (
    inject_global_css, render_page_header, render_metric_card,
    render_benchmark_table, render_status_badge,
)
from streamlit_app.utils import (
    run_benchmark, load_evaluation_results, PROVIDER_MODELS, get_env_api_key,
)

inject_global_css()

render_page_header(
    "Benchmark Evaluation",
    "Run the full 10-query suite — Zero-Shot Baseline vs Multi-Agent Optimizer",
    "📊",
)

with st.sidebar:
    st.markdown("### ⚙️ Benchmark Settings")
    provider = st.selectbox("Provider", list(PROVIDER_MODELS.keys()),
                            index=list(PROVIDER_MODELS.keys()).index(
                                st.session_state.get("global_provider", "mock")),
                            key="bench_provider")
    model = st.selectbox("Model", PROVIDER_MODELS[provider], key="bench_model")
    auto_key = get_env_api_key(provider) if provider != "mock" else None
    api_key = st.text_input("API Key", value=st.session_state.get("api_key") or auto_key or "",
                            type="password", key="bench_api_key") or auto_key
    max_retries = st.slider("Max Retries", 1, 5, st.session_state.get("global_max_retries", 3), key="bench_retries")
    timeout = st.slider("Timeout (sec)", 5.0, 120.0, 10.0, step=5.0, key="bench_timeout")

# Existing results preview
eval_data = load_evaluation_results()

run_col, _ = st.columns([2, 5])
with run_col:
    run_btn = st.button("▶ Run Full Benchmark", type="primary", use_container_width=True)

if run_btn:
    progress_bar = st.progress(0, text="Initializing benchmark...")
    status_placeholder = st.empty()

    with st.spinner("Running benchmark — this may take 1-2 minutes..."):
        try:
            result = run_benchmark(
                provider=provider,
                model=model if model != "mock-orchestrator" else None,
                api_key=api_key if api_key else None,
                max_retries=max_retries,
                timeout_sec=timeout,
            )
            progress_bar.progress(100, text="Benchmark complete!")
            eval_data = result
            st.success(f"✅ Benchmark completed! {result.get('summary', {}).get('agent_optimizer', {}).get('successful_cases', 0)}/10 queries verified.")
        except Exception as e:
            progress_bar.empty()
            st.error(f"Benchmark failed: {e}")
            st.stop()

if eval_data:
    st.markdown("---")
    # Summary timestamp / model
    ts = eval_data.get("timestamp", "N/A")
    mdl = eval_data.get("model", "N/A")
    st.caption(f"**Last run:** {ts}  |  **Model:** {mdl}")

    # Summary metrics
    b_sum = eval_data.get("summary", {}).get("baseline", {})
    a_sum = eval_data.get("summary", {}).get("agent_optimizer", {})

    st.markdown("#### Aggregate Summary")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        render_metric_card("Total Queries", str(eval_data.get("total_queries", 10)))
    with c2:
        render_metric_card("Baseline Acc", f"{b_sum.get('success_rate_pct', 0):.0f}%", color="#f59e0b")
    with c3:
        render_metric_card("Agent Acc", f"{a_sum.get('success_rate_pct', 0):.0f}%", color="#3fb950")
    with c4:
        render_metric_card("Avg Speedup", f"{a_sum.get('average_speedup', 0):.2f}x", color="#58a6ff")
    with c5:
        render_metric_card("Max Speedup", f"{a_sum.get('max_speedup', 0):.2f}x", color="#f59e0b")
    with c6:
        render_metric_card("Total Indexes", str(a_sum.get("total_indexes_created", 0)), color="#a5d6ff")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### Per-Query Comparison Table")
    comparison = eval_data.get("comparison_table", [])
    if comparison:
        render_benchmark_table(comparison)
    else:
        st.info("No comparison data available.")
else:
    st.info("No evaluation results found. Click **Run Full Benchmark** to start.")
