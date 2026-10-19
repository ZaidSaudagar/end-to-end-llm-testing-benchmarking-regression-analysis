from __future__ import annotations

import httpx
import streamlit as st

st.set_page_config(page_title="LLM Evaluation Dashboard", page_icon="📊", layout="wide")

st.markdown(
    """
    <style>
    .stApp {
        background: #0b0f1a;
        color: #f5f7ff;
    }
    div[data-testid="stMetricValue"] {
        color: #b59dff;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("End-to-End LLM Testing, Benchmarking and Regression Analysis")
st.caption("Foundation dashboard for benchmarking, evaluation, and regression monitoring.")

backend_url = "http://127.0.0.1:8000"

with st.spinner("Checking backend status..."):
    try:
        response = httpx.get(f"{backend_url}/health", timeout=5)
        backend_status = response.json() if response.is_success else {"status": "unavailable"}
    except httpx.HTTPError:
        backend_status = {"status": "unavailable"}

col1, col2, col3, col4 = st.columns(4)
col1.metric("Run count", 0)
col2.metric("Models", 0)
col3.metric("Test cases", 0)
col4.metric("Backend", backend_status.get("status", "unknown"))

st.subheader("System status")
st.json({
    "project": "End-to-End LLM Testing, Benchmarking and Regression Analysis",
    "backend": backend_status,
    "milestone": "Milestone 1: Foundation and GitHub Setup",
})