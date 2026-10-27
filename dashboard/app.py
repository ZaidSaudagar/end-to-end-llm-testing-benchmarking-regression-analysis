from __future__ import annotations

import os
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

from dashboard.api_client import APIClient, DashboardAPIError

load_dotenv()

BACKEND_URL = os.getenv("DASHBOARD_API_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="End to End LLM Testing Benchmarking and Regression Analysis",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root { color-scheme: dark; }
    .stApp { background: #0b1020; color: #edf1ff; }
    [data-testid="stSidebar"] { background: #10172a; border-right: 1px solid #26314d; }
    [data-testid="stMetric"] { background: #111a30; border: 1px solid #26314d;
        padding: 16px 18px; border-radius: 14px; }
    [data-testid="stMetricValue"] { color: #b5a4ff; }
    .block-container { padding-top: 2rem; }
    div[data-testid="stTabs"] button { font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _run_label(run: dict[str, Any]) -> str:
    short_id = str(run["id"])[:8]
    return f"{run['model_id']} · {run['dataset_name']} · {run['status']} · {short_id}"


def _analysis_label(analysis: dict[str, Any]) -> str:
    regressions = analysis.get("regressions_detected", 0)
    return f"{analysis['created_at']} · {regressions} regression(s) · {analysis['id'][:8]}"


def _render_run_detail(api: APIClient, run_id: str) -> None:
    try:
        detail = api.get_run(run_id)
    except DashboardAPIError as exc:
        st.error(str(exc))
        return

    st.subheader(f"Run · {detail['model_id']}")
    cols = st.columns(5)
    cols[0].metric("Status", detail["status"])
    cols[1].metric("Cases completed", f"{detail['completed_cases']} / {detail['total_cases']}")
    cols[2].metric("Deterministic passes", detail["passed_cases"])
    cols[3].metric("Case errors", detail["errored_cases"])
    cols[4].metric("Latency", f"{detail['total_latency_ms'] / 1000:.1f} s")
    st.caption(
        f"{detail['dataset_name']} v{detail['dataset_version']} · "
        f"{detail['provider']} / {detail['model_id']} · "
        f"SHA-256 `{detail['dataset_sha256'][:16]}…`"
    )
    if detail.get("total_estimated_cost_usd") is not None:
        st.caption(f"Estimated provider cost: ${detail['total_estimated_cost_usd']:.6f}")

    rows = []
    for case in detail.get("cases", []):
        deterministic = case.get("deterministic_result") or {}
        semantic = case.get("semantic_result") or {}
        judge = case.get("judge_result") or {}
        aggregate = judge.get("aggregate") or {}
        rows.append(
            {
                "Case": case["test_case_id"],
                "Method": case["evaluation_method"],
                "Status": case["status"],
                "Passed": deterministic.get("passed"),
                "Semantic similarity": semantic.get("similarity"),
                "Judge mean": aggregate.get("overall_mean"),
                "Latency (ms)": case.get("latency_ms"),
                "Error": case.get("error_category") or case.get("evaluation_error"),
            }
        )
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        with st.expander("Inspect generated responses and evaluation details"):
            for case in detail.get("cases", []):
                st.markdown(f"**{case['test_case_id']}** · {case['evaluation_method']}")
                if case.get("candidate_text"):
                    st.code(case["candidate_text"])
                if case.get("deterministic_result"):
                    st.json(case["deterministic_result"])
                if case.get("semantic_result"):
                    st.json(case["semantic_result"])
                if case.get("judge_result"):
                    st.json(case["judge_result"])
                if case.get("error_message") or case.get("evaluation_error"):
                    st.warning(case.get("error_message") or case.get("evaluation_error"))
                st.divider()
    else:
        st.info("This run has no case results yet.")


def _render_analysis(result: dict[str, Any], *, widget_suffix: str) -> None:
    st.markdown(
        f"Baseline `{result['baseline_run_id'][:8]}` → "
        f"candidate `{result['candidate_run_id'][:8]}` · "
        f"{result['dataset_name']} v{result['dataset_version']}"
    )
    metrics = result.get("metrics", [])
    if not metrics:
        st.info("There are no paired metrics to display.")
        return
    frame = pd.DataFrame(metrics)
    columns = [
        "metric",
        "paired_cases",
        "baseline_mean",
        "candidate_mean",
        "mean_delta",
        "confidence_interval_95",
        "adjusted_p_value",
        "regression_detected",
    ]
    st.dataframe(frame[columns], use_container_width=True, hide_index=True)
    flagged = frame[frame["regression_detected"]]
    if flagged.empty:
        st.success("No statistically supported regressions were flagged in this comparison.")
    else:
        st.error("Regression signal detected: " + ", ".join(flagged["metric"].tolist()))
    st.caption(
        f"Paired cases only · {result['multiple_testing_correction']} · "
        f"95% {result['confidence_interval_method']} intervals · alpha={result['alpha']}"
    )
    selected_metric = st.selectbox(
        "Metric to chart",
        options=frame["metric"].tolist(),
        key=(
            f"metric_chart_{widget_suffix}_{result['baseline_run_id']}_"
            f"{result['candidate_run_id']}"
        ),
    )
    selected = frame[frame["metric"] == selected_metric].iloc[0]
    chart = pd.DataFrame(
        {
            "Run": ["Baseline", "Candidate"],
            "Mean score": [selected["baseline_mean"], selected["candidate_mean"]],
        }
    )
    figure = px.bar(
        chart,
        x="Run",
        y="Mean score",
        color="Run",
        color_discrete_sequence=["#8871ec", "#42c8b7"],
        title=selected_metric.replace("_", " ").title(),
    )
    figure.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    st.plotly_chart(figure, use_container_width=True)


st.title("🧪 End-to-End LLM Testing, Benchmarking & Regression Analysis")
st.caption(
    "Run reproducible model evaluations, inspect case-level outputs, and compare regressions."
)

with st.sidebar:
    st.markdown("### Workspace")
    st.caption("LLM testing · benchmarking · regression analysis")
    st.text_input("Backend URL", value=BACKEND_URL, key="backend_url")
    if st.button("Refresh data", use_container_width=True):
        st.rerun()
    st.divider()
    st.caption("Provider credentials stay in the backend environment.")

backend_url = st.session_state.get("backend_url", BACKEND_URL).strip().rstrip("/")
try:
    with APIClient(backend_url) as api:
        health = api.health()
        overview = api.overview()
        provider_info = api.provider_status()
        datasets = api.list_datasets()
        runs = api.list_runs(limit=100)
        analyses = api.list_analyses(limit=100)
except DashboardAPIError as exc:
    st.error(str(exc))
    st.info("Start the FastAPI backend, then refresh this page.")
    st.stop()

providers = provider_info.get("providers", {})
configured_providers = [name for name, info in providers.items() if info.get("configured")]
judge_enabled = bool(provider_info.get("judge_enabled"))

st.success(f"Backend connected · {health.get('environment', 'unknown')} environment")
overview_metrics = overview.get("metrics", {})
kpis = st.columns(4)
kpis[0].metric("Saved runs", overview_metrics.get("total_runs", 0))
kpis[1].metric("Models evaluated", overview_metrics.get("models_evaluated", 0))
kpis[2].metric("Cases completed", overview_metrics.get("test_cases_executed", 0))
kpis[3].metric("Saved comparisons", len(analyses))

overview_tab, new_run_tab, history_tab, compare_tab = st.tabs(
    ["Overview", "New evaluation", "Run history", "Regression analysis"]
)

with overview_tab:
    st.subheader("Recent activity")
    if runs:
        activity = pd.DataFrame(
            [
                {
                    "Started": run["started_at"],
                    "Dataset": run["dataset_name"],
                    "Provider": run["provider"],
                    "Model": run["model_id"],
                    "Status": run["status"],
                    "Cases": f"{run['completed_cases']}/{run['total_cases']}",
                    "Passes": run["passed_cases"],
                    "Errors": run["errored_cases"],
                }
                for run in runs[:10]
            ]
        )
        st.dataframe(activity, use_container_width=True, hide_index=True)
    else:
        st.info("No saved runs yet. Start an evaluation from the New evaluation tab.")
    if analyses:
        st.subheader("Latest regression comparison")
        try:
            with APIClient(backend_url) as api:
                latest = api.get_analysis(analyses[0]["id"])
            _render_analysis(latest["result"], widget_suffix="home")
        except DashboardAPIError as exc:
            st.warning(str(exc))

with new_run_tab:
    st.subheader("Start an evaluation")
    dataset_files = [dataset["dataset_file"] for dataset in datasets]
    if not dataset_files:
        st.warning("The backend did not find any valid CSV or JSON datasets.")
    elif not configured_providers:
        st.warning("No provider API key is configured. Add one to `.env` and restart the backend.")
    else:
        with st.form("new_run_form"):
            left, right = st.columns(2)
            dataset_file = left.selectbox(
                "Dataset",
                dataset_files,
                format_func=lambda filename: next(
                    (
                        f"{dataset['dataset_name']} · v{dataset['dataset_version']} · "
                        f"{dataset['case_count']} cases"
                        for dataset in datasets
                        if dataset["dataset_file"] == filename
                    ),
                    filename,
                ),
            )
            provider = right.selectbox("Provider", configured_providers)
            model_id = st.text_input("Model ID override", placeholder="Use provider default")
            include_judge = st.checkbox(
                "Include LLM judge scores",
                value=False,
                disabled=not judge_enabled,
                help="Requires JUDGE_ENABLED=true and configured judge credentials in the backend.",
            )
            start_run = st.form_submit_button("Start evaluation", type="primary")
        if start_run:
            payload: dict[str, Any] = {
                "dataset_file": dataset_file,
                "provider": provider,
                "include_judge": include_judge,
            }
            if model_id.strip():
                payload["model_id"] = model_id.strip()
            try:
                with st.spinner(
                    "Running dataset cases sequentially. This can take a while for larger datasets…"
                ):
                    with APIClient(backend_url) as api:
                        created = api.create_run(payload)
                st.session_state["selected_run_id"] = created["id"]
                st.success(
                    f"Run finished with status **{created['status']}** · "
                    f"{created['completed_cases']}/{created['total_cases']} cases completed."
                )
            except DashboardAPIError as exc:
                st.error(str(exc))

with history_tab:
    st.subheader("Saved run history")
    if not runs:
        st.info("No evaluation runs have been saved yet.")
    else:
        labels = {_run_label(run): run["id"] for run in runs}
        label_values = list(labels)
        current_id = st.session_state.get("selected_run_id")
        default_index = next(
            (index for index, label in enumerate(label_values) if labels[label] == current_id),
            0,
        )
        selected_label = st.selectbox("Choose a run", label_values, index=default_index)
        with APIClient(backend_url) as api:
            _render_run_detail(api, labels[selected_label])

with compare_tab:
    st.subheader("Compare baseline and candidate")
    completed_runs = [run for run in runs if run.get("status") != "running"]
    if len(completed_runs) < 2:
        st.info("Complete at least two runs on the same dataset before comparing them.")
    else:
        labels = {_run_label(run): run for run in completed_runs}
        choices = list(labels)
        left, right = st.columns(2)
        baseline_label = left.selectbox("Baseline run", choices, index=min(1, len(choices) - 1))
        candidate_label = right.selectbox("Candidate run", choices, index=0)
        baseline = labels[baseline_label]
        candidate = labels[candidate_label]
        if baseline["id"] == candidate["id"]:
            st.warning("Choose two different runs.")
        elif baseline["dataset_sha256"] != candidate["dataset_sha256"]:
            st.warning(
                "These runs use different dataset files. Select runs with the same fingerprint."
            )
        else:
            minimum_drop = st.number_input(
                "Minimum drop required to flag a regression",
                min_value=0.0,
                value=0.0,
                step=0.01,
                help=(
                    "Uses each metric's native scale; for pass rate, 0.05 is five "
                    "percentage points."
                ),
            )
            if st.button("Run paired comparison", type="primary"):
                try:
                    with APIClient(backend_url) as api:
                        comparison = api.compare_runs(
                            {
                                "baseline_run_id": baseline["id"],
                                "candidate_run_id": candidate["id"],
                                "alpha": 0.05,
                                "minimum_regression_drop": minimum_drop,
                            }
                        )
                    st.session_state["selected_analysis_id"] = comparison["id"]
                    st.success("Comparison saved.")
                    _render_analysis(comparison["result"], widget_suffix="created")
                except DashboardAPIError as exc:
                    st.error(str(exc))

        if analyses:
            st.subheader("Saved comparisons")
            analysis_labels = {_analysis_label(analysis): analysis["id"] for analysis in analyses}
            chosen_analysis = st.selectbox("Open a saved comparison", list(analysis_labels))
            try:
                with APIClient(backend_url) as api:
                    saved = api.get_analysis(analysis_labels[chosen_analysis])
                _render_analysis(saved["result"], widget_suffix=analysis_labels[chosen_analysis])
            except DashboardAPIError as exc:
                st.error(str(exc))