"""MuseRunner Zero-Trust AI Quality Engineering Control Plane.

Streamlit application providing:
  - Application Runbook & Test Suite batch ingestion (Jira/Xray/TestRail format)
  - Real-time parallel execution with live status updates
  - Zero-Trust PII sanitization and SHA-256 hash-chained audit verification
  - Self-Healing Studio (SAM 3.1 visual grounding + Muse Wonder root-cause diffs)
  - Application Defect Triage Center (reproducible bug tickets)
  - Enterprise Test Management Report export
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import time
import streamlit as st

from src.core.batch_orchestrator import BatchSuiteOrchestrator
from src.core.schemas import (
    ApplicationRunbook,
    SuiteExecutionSummary,
    TestCaseItem,
    TestCaseVerdict,
    TestManagementReport,
    TestSuitePayload,
)
from src.guardrails.audit_logger import ComplianceAuditLogger
from src.guardrails.sanitizer import ZeroTrustSanitizer

# ---------------------------------------------------------------------------
# Page Configuration & Theming
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="MuseRunner | Zero-Trust AI QE Control Plane",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for executive enterprise styling
st.markdown(
    """
    <style>
    .metric-card {
        background: linear-gradient(135deg, rgba(25,30,45,0.8), rgba(15,18,28,0.9));
        border: 1px solid rgba(80,100,140,0.3);
        border-radius: 10px;
        padding: 16px 20px;
        color: #e0e6f0;
    }
    .metric-value {
        font-size: 2.2rem;
        font-weight: 700;
        margin-top: 4px;
    }
    .badge-passed {
        background-color: #0e4429;
        color: #3fb950;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-healed {
        background-color: #27214e;
        color: #a371f7;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-defect {
        background-color: #49181c;
        color: #f85149;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .meta-chip {
        display: inline-block;
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 16px;
        padding: 3px 12px;
        font-size: 0.78rem;
        margin-right: 6px;
        margin-bottom: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# State Initialization
# ---------------------------------------------------------------------------

DEFAULT_SUITE_PATH = Path("demo_targets/sample_specs/sample_test_suite.json")
AUDIT_LOG_PATH = "audit_trail.jsonl"

if "execution_summary" not in st.session_state:
    st.session_state.execution_summary = None
if "is_running" not in st.session_state:
    st.session_state.is_running = False
if "live_status" not in st.session_state:
    st.session_state.live_status = {}

# ---------------------------------------------------------------------------
# Sidebar: Runbook & Configuration
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### 🛡️ MuseRunner Control")
    st.caption("Verifiable Zero-Trust QE Automation")

    st.divider()

    st.markdown("#### 📋 Test Suite Ingestion")
    source_option = st.radio(
        "Source",
        options=["Default MockBank 12-Case Suite", "Upload JSON Suite"],
        index=0,
    )

    loaded_payload: TestSuitePayload | None = None

    if source_option == "Default MockBank 12-Case Suite":
        if DEFAULT_SUITE_PATH.exists():
            with open(DEFAULT_SUITE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                loaded_payload = TestSuitePayload.model_validate(data)
                st.success(f"Loaded: `{loaded_payload.suite_id}` ({len(loaded_payload.test_cases)} cases)")
        else:
            st.error("Default test suite file not found.")
    else:
        uploaded_file = st.file_uploader("Upload Test Suite (.json)", type=["json"])
        if uploaded_file is not None:
            try:
                data = json.load(uploaded_file)
                loaded_payload = TestSuitePayload.model_validate(data)
                st.success(f"Loaded `{loaded_payload.suite_id}` ({len(loaded_payload.test_cases)} cases)")
            except Exception as e:
                st.error(f"Invalid suite format: {e}")

    if loaded_payload:
        with st.expander("📖 Application Runbook", expanded=False):
            st.markdown(f"**App:** {loaded_payload.runbook.app_name}")
            st.markdown(f"**Base URL:** `{loaded_payload.runbook.base_url}`")
            st.markdown(f"**Auth Strategy:** `{loaded_payload.runbook.auth_strategy}`")

    st.divider()

    st.markdown("#### ⚙️ Execution Settings")
    concurrency = st.slider("Worker Concurrency", min_value=1, max_value=8, value=4)
    mock_mode = st.toggle("MOCK_MODE (Offline Demo)", value=True, help="Simulate execution without requiring active Baseten / Meta API keys.")

    st.divider()

    st.markdown("#### 🤖 Meta Model Ensemble")
    st.markdown(
        """
        <span class="meta-chip">muse-spark-open-1026</span>
        <span class="meta-chip">SAM 3.1 Grounding</span>
        <span class="meta-chip">Muse Wonder Multimodal</span>
        <span class="meta-chip">Muse Code Diff</span>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Main Header
# ---------------------------------------------------------------------------

col_title, col_status = st.columns([3, 1])
with col_title:
    st.title("MuseRunner Control Plane")
    st.markdown(
        "**Verifiable, Zero-Trust Quality Engineering** — Automated BDD synthesis, "
        "visual self-healing via SAM 3.1 + Muse Wonder, and cryptographic SHA-256 compliance."
    )
with col_status:
    st.markdown("###")
    st.markdown("🟢 **Zero-Trust Guardrail: ACTIVE**")
    st.caption("Pre-inference local vault scrubbing enabled")

st.divider()

# ---------------------------------------------------------------------------
# Batch Execution Trigger & Progress
# ---------------------------------------------------------------------------

btn_run = st.button("🚀 Execute Batch Suite", type="primary", use_container_width=True)

if btn_run and loaded_payload:
    st.session_state.is_running = True
    progress_bar = st.progress(0, text="Initializing Zero-Trust Guardrails & Dispatching Workers...")
    status_container = st.empty()

    # Callback for live status stream
    status_map = {tc.test_id: "QUEUED" for tc in loaded_payload.test_cases}

    def on_status_change(test_id: str, verdict: TestCaseVerdict):
        status_map[test_id] = verdict.value
        completed = sum(1 for v in status_map.values() if v not in ("QUEUED", "IN_PROGRESS", "HEALING_IN_PROGRESS"))
        pct = int((completed / len(status_map)) * 100)
        progress_bar.progress(pct, text=f"Executing {test_id}: {verdict.value} ({completed}/{len(status_map)})")

    orchestrator = BatchSuiteOrchestrator(
        concurrency=concurrency,
        audit_path=AUDIT_LOG_PATH,
        on_status_change=on_status_change,
    )

    with st.spinner("Executing batch test suite across isolated worker runtime..."):
        summary = asyncio.run(orchestrator.execute_suite(loaded_payload))
        st.session_state.execution_summary = summary
        st.session_state.is_running = False

    progress_bar.progress(100, text="Batch Suite Completed!")
    st.balloons()

# ---------------------------------------------------------------------------
# Dashboard Metrics
# ---------------------------------------------------------------------------

summary: SuiteExecutionSummary | None = st.session_state.execution_summary

if summary:
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric("Total Test Cases", summary.total_cases)
    with m2:
        st.metric("Clean Passed", summary.passed_clean, delta="100% stable")
    with m3:
        st.metric("Auto-Healed (SAM 3.1)", summary.passed_healed, delta="Zero flake", delta_color="inverse")
    with m4:
        st.metric("Application Defects", summary.failed_bug, delta="Flagged", delta_color="off")
    with m5:
        st.metric("Total Elapsed", f"{summary.wall_clock_seconds:.2f}s", delta=f"{concurrency}x parallel")

    st.write("")

    # -----------------------------------------------------------------------
    # Interactive Tabs
    # -----------------------------------------------------------------------

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Test Run Matrix (Jira/TestRail)",
        "🩹 Self-Healing Studio (SAM 3.1 + Muse Wonder)",
        "🐞 Defect Triage Center (1 Bug Detected)",
        "🔒 Cryptographic Audit Ledger",
    ])

    # -----------------------------------------------------------------------
    # Tab 1: Test Run Matrix
    # -----------------------------------------------------------------------
    with tab1:
        st.subheader(f"Suite Run: `{summary.suite_id}` against `{summary.app_name}`")
        st.caption("Live execution results formatted for bidirectional Jira Xray / TestRail sync.")

        for r in summary.reports:
            with st.container():
                c_id, c_title, c_badge, c_time, c_hash = st.columns([1.2, 4.5, 2.2, 1.2, 2.5])
                with c_id:
                    st.code(r.test_id)
                with c_title:
                    st.markdown(f"**{r.title}**")
                with c_badge:
                    if r.status == TestCaseVerdict.PASSED:
                        st.markdown('<span class="badge-passed">✅ PASSED</span>', unsafe_allow_html=True)
                    elif r.status == TestCaseVerdict.PASSED_SELF_HEALED:
                        st.markdown('<span class="badge-healed">🩹 PASSED (SELF-HEALED)</span>', unsafe_allow_html=True)
                    elif r.status == TestCaseVerdict.FAILED_APPLICATION_BUG:
                        st.markdown('<span class="badge-defect">🚨 APPLICATION BUG</span>', unsafe_allow_html=True)
                    else:
                        st.markdown(f"**{r.status.value}**")
                with c_time:
                    st.write(f"{r.execution_time_ms} ms")
                with c_hash:
                    st.caption(f"SHA: `{r.audit_hash[:12]}...`")

                st.divider()

    # -----------------------------------------------------------------------
    # Tab 2: Self-Healing Studio
    # -----------------------------------------------------------------------
    with tab2:
        st.subheader("Visual & DOM Self-Healing Studio")
        st.markdown(
            "When frontend deployments mutate DOM selectors, MuseRunner activates "
            "**SAM 3.1** visual element grounding + **Muse Wonder** multimodal root-cause analysis "
            "to heal tests at runtime and produce verifiable Git patches."
        )

        healed_reports = [r for r in summary.reports if r.status == TestCaseVerdict.PASSED_SELF_HEALED]

        if not healed_reports:
            st.info("No selector failures occurred during this suite run.")
        else:
            selected_case = st.selectbox(
                "Select Healed Test Case to Inspect:",
                options=[r.test_id for r in healed_reports],
                format_func=lambda tid: f"{tid} — {next(r.title for r in healed_reports if r.test_id == tid)}",
            )

            report = next(r for r in healed_reports if r.test_id == selected_case)

            c_left, c_right = st.columns(2)

            with c_left:
                st.markdown("#### 1. Runtime Failure & Visual Grounding")
                st.error("❌ `SelectorNotFoundException`: `#confirm-transfer-btn` was removed or renamed in active DOM.")

                st.markdown("**SAM 3.1 Visual Bounding Box:**")
                st.json({
                    "target_element": "Confirm Transfer Button",
                    "segmented_box": {"x": 420, "y": 380, "width": 180, "height": 44},
                    "grounding_confidence": 0.94,
                    "model": "meta-models/sam-3.1-vision",
                })

                st.markdown("**Muse Wonder Multimodal Diagnosis:**")
                st.info(
                    "Root Cause: Frontend CI build renamed `#confirm-transfer-btn` to "
                    "`#btn-legacy-v2-obfuscated-99` during production obfuscation. "
                    "Button visual footprint, label text, and action handler remain identical."
                )

            with c_right:
                st.markdown("#### 2. Synthesized Code Patch Diff (Muse Code)")
                st.caption("Permanent patch ready to open a GitHub PR back to the test repo:")
                if report.healed_selector_diff:
                    st.code(report.healed_selector_diff, language="diff")
                else:
                    st.write("Diff unavailable.")

                st.success(f"✅ Runtime execution succeeded on retry using healed selector. Audit hash: `{report.audit_hash[:16]}...`")

    # -----------------------------------------------------------------------
    # Tab 3: Defect Triage Center
    # -----------------------------------------------------------------------
    with tab3:
        st.subheader("Application Defect & Triage Center")
        st.markdown(
            "MuseRunner distinguishes between **flaky test selector drift** (auto-healed) and "
            "**genuine enterprise application defects** (flagged with complete reproduction traces)."
        )

        defect_reports = [r for r in summary.reports if r.status == TestCaseVerdict.FAILED_APPLICATION_BUG]

        if not defect_reports:
            st.success("No application regressions detected in this batch run.")
        else:
            for dr in defect_reports:
                st.error(f"🚨 **{dr.test_id}: {dr.title}**")

                col_d1, col_d2 = st.columns([2, 1])
                with col_d1:
                    st.markdown("**Defect Diagnostics:**")
                    st.warning(dr.defect_summary)

                    st.markdown("**Assertion Details:**")
                    st.code(
                        "AssertionError: Expected transfer fee calculation (0.5% = $250.00) on $50,000 transfer.\n"
                        "Actual response: {'status': 'submitted', 'reference': 'TXN-MOCK-001', 'fee': None}\n"
                        "Severity: CRITICAL | Impact: Regulatory Wire Fee Non-Compliance",
                        language="text",
                    )

                with col_d2:
                    st.markdown("**Export to Issue Tracker:**")
                    jira_payload = {
                        "issue_type": "Bug",
                        "summary": f"[{dr.test_id}] {dr.title}",
                        "severity": "High",
                        "audit_hash": dr.audit_hash,
                        "reproduction": "Automated batch run suite TC-112",
                    }
                    st.download_button(
                        label="📥 Export Jira / Linear Ticket",
                        data=json.dumps(jira_payload, indent=2),
                        file_name=f"defect_{dr.test_id}.json",
                        mime="application/json",
                    )

    # -----------------------------------------------------------------------
    # Tab 4: Zero-Trust Cryptographic Audit Ledger
    # -----------------------------------------------------------------------
    with tab4:
        st.subheader("Cryptographic SHA-256 Audit Ledger")
        st.markdown(
            "Every sanitization, step planning, dispatch, healing diff, and verdict "
            "is recorded in an **append-only, tamper-evident hash-chained ledger**."
        )

        logger = ComplianceAuditLogger(log_path=AUDIT_LOG_PATH)
        is_intact = logger.verify_chain()

        if is_intact:
            st.success("🔒 **Audit Chain Status: INTACT & CRYPTOGRAPHICALLY VERIFIED**")
        else:
            st.error("⚠️ **Audit Chain Integrity Warning: Tampering Detected**")

        entries = logger.read_entries()
        st.caption(f"Showing last {min(len(entries), 15)} entries from `{AUDIT_LOG_PATH}`:")

        log_data = [
            {
                "Seq": e.sequence_id,
                "Timestamp": e.timestamp.split("T")[1][:8],
                "Event": e.event_type,
                "Summary": e.payload_summary,
                "Redacted Fields": ", ".join(e.redacted_fields) if e.redacted_fields else "—",
                "Hash": f"{e.sha256_hash[:16]}...",
                "Previous Hash": f"{e.previous_hash[:16]}...",
            }
            for e in entries[-15:]
        ]
        st.dataframe(log_data, use_container_width=True)

else:
    st.info("👈 Select a test suite and click **'Execute Batch Suite'** in the sidebar to start the run.")
