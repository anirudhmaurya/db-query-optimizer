"""
streamlit_app/pages/1_⚡_Optimizer.py
Single-query optimization page.
"""
import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

st.set_page_config(page_title="Optimizer | SQL Optimizer", page_icon="⚡", layout="wide")

from streamlit_app.components import (
    inject_global_css, render_page_header, render_sql_diff,
    render_speedup_gauge, render_bottlenecks, render_applied_indexes,
    render_agent_trajectory, render_metric_card, render_status_badge,
)
from streamlit_app.utils import (
    run_single_query_optimization, load_test_cases, PROVIDER_MODELS, get_env_api_key,
)

inject_global_css()

render_page_header(
    "Query Optimizer",
    "Paste any SQL query and watch the 4-agent pipeline optimize it live",
    "⚡",
)

# Sidebar settings (mirror from home / override)
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    provider = st.selectbox("Provider", list(PROVIDER_MODELS.keys()),
                            index=list(PROVIDER_MODELS.keys()).index(
                                st.session_state.get("global_provider", "mock")),
                            key="opt_provider")
    model = st.selectbox("Model", PROVIDER_MODELS[provider], key="opt_model")
    auto_key = get_env_api_key(provider) if provider != "mock" else None
    api_key = st.text_input("API Key", value=st.session_state.get("api_key") or auto_key or "",
                            type="password", key="opt_api_key") or auto_key
    max_retries = st.slider("Max Retries", 1, 5, st.session_state.get("global_max_retries", 3), key="opt_retries")
    timeout = st.slider("Timeout (sec)", 5.0, 60.0, st.session_state.get("global_timeout", 10.0),
                        step=5.0, key="opt_timeout")

    st.markdown("---")
    st.markdown("### 📚 Load Example Query")
    test_cases = load_test_cases()
    if test_cases:
        tc_options = {f"{tc['id']}: {tc['name'][:40]}": tc for tc in test_cases}
        selected_tc_label = st.selectbox("Select test case", ["(custom)"] + list(tc_options.keys()),
                                         key="opt_tc_select")
        if selected_tc_label != "(custom)" and selected_tc_label in tc_options:
            tc = tc_options[selected_tc_label]
            st.session_state["opt_query_value"] = tc["query"]
            st.caption(f"**Anti-pattern:** {tc.get('anti_pattern', '')}")

# ── Main: SQL Editor ──────────────────────────────────────────────────────────
default_query = st.session_state.get("opt_query_value",
    "SELECT user_id, event_type, COUNT(*) AS event_count\n"
    "FROM events\n"
    "WHERE strftime('%Y', created_at) = '2025'\n"
    "GROUP BY user_id, event_type\n"
    "HAVING COUNT(*) >= 1\n"
    "ORDER BY event_count DESC\n"
    "LIMIT 25;"
)

query_input = st.text_area(
    "SQL Query",
    value=default_query,
    height=200,
    placeholder="Paste your SQL query here...",
    key="opt_query_textarea",
)

run_btn = st.button("🚀 Optimize Query", type="primary", use_container_width=False)

if run_btn:
    if not query_input.strip():
        st.error("Please enter a SQL query.")
    else:
        st.markdown("---")
        stage_placeholder = st.empty()
        progress_bar = st.progress(0)
        status_msgs = []

        stages = [
            ("profiler",   10, "🔍 ProfilerAgent: Analyzing EXPLAIN QUERY PLAN..."),
            ("architect",  40, "🏗️ IndexArchitectAgent: Designing composite indexes..."),
            ("developer",  70, "✏️ DeveloperAgent: Rewriting SQL anti-patterns..."),
            ("verifier",   90, "✅ VerifierAgent: Validating result-set equivalence..."),
        ]
        stage_iter = iter(stages)

        def on_stage(stage_name: str, message: str):
            status_msgs.append(message)
            stage_placeholder.info(message)

        with st.spinner("Running multi-agent optimization pipeline..."):
            try:
                result = run_single_query_optimization(
                    query=query_input,
                    provider=provider,
                    model=model if model != "mock-orchestrator" else None,
                    api_key=api_key if api_key else None,
                    max_retries=max_retries,
                    timeout_sec=timeout,
                    on_stage=on_stage,
                )
                progress_bar.progress(100)
                stage_placeholder.empty()
            except Exception as e:
                stage_placeholder.empty()
                progress_bar.empty()
                st.error(f"Optimization failed: {e}")
                st.stop()

        # ── Results ──────────────────────────────────────────────────────────
        is_valid = result.get("is_valid", False)
        speedup = result.get("speedup_ratio")
        orig_ms = result.get("original_execution_time_ms")
        opt_ms = result.get("optimized_execution_time_ms")
        attempts = result.get("total_attempts", 1)
        status = result.get("status", "UNKNOWN")
        applied_indexes = result.get("applied_indexes", [])
        techniques = result.get("applied_techniques", [])
        trajectory_steps = []
        for key in ["stages"]:
            pass  # trajectory is embedded in result for custom queries

        st.markdown(f"### Result: {render_status_badge('SUCCESS' if is_valid else 'FAILED')}",
                    unsafe_allow_html=True)

        # Metric cards
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            render_metric_card("Status", "✅ Verified" if is_valid else "❌ Failed",
                               color="#3fb950" if is_valid else "#f85149")
        with m2:
            render_metric_card("Original", f"{orig_ms:.2f} ms" if orig_ms else "N/A", color="#8b949e")
        with m3:
            render_metric_card("Optimized", f"{opt_ms:.2f} ms" if opt_ms else "N/A", color="#58a6ff")
        with m4:
            render_speedup_gauge(speedup)

        st.markdown("<br>", unsafe_allow_html=True)

        # Tabs
        tab1, tab2, tab3, tab4 = st.tabs(["🔄 SQL Diff", "🔍 Bottleneck Analysis", "🏗️ Applied Indexes", "📋 Techniques"])

        with tab1:
            render_sql_diff(result.get("original_query", query_input), result.get("optimized_sql", query_input))
            if result.get("fallback_triggered"):
                st.warning("⚠️ Optimization fell back to original SQL after exhausting retries. Indexes were still applied.")

        with tab2:
            stages_data = result.get("trajectory", {}).get("stages", {}) if "trajectory" in result else {}
            profiler_report = stages_data.get("profiler", {}).get("profiler_report", {})
            bottlenecks = profiler_report.get("identified_bottlenecks", [])
            strategy = profiler_report.get("optimization_strategy", "")
            if strategy:
                st.info(f"**Strategy:** {strategy}")
            render_bottlenecks(bottlenecks)

        with tab3:
            render_applied_indexes(applied_indexes)
            st.caption(f"{len(applied_indexes)} index(es) synthesized and applied to the sandbox database.")

        with tab4:
            if techniques:
                for t in techniques:
                    st.markdown(f"- `{t}`")
            else:
                st.info("No techniques listed.")
            st.markdown(f"**Attempts:** {attempts}")
            if result.get("verification_message"):
                st.caption(result["verification_message"])
