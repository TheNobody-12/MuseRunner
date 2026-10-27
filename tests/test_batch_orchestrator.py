"""Tests for the Batch Suite Orchestrator and enterprise schemas.

Validates that:
1. TestSuitePayload can be loaded from the sample JSON file
2. ApplicationRunbook and TestCaseItem models validate correctly
3. The BatchSuiteOrchestrator executes all 12 test cases in mock mode
4. The expected 9-passed / 2-healed / 1-defect outcome pattern holds
5. Audit trail entries are created for suite start, PII redaction, and completion
6. Concurrent execution actually runs faster than sequential
7. Status change callbacks are fired correctly
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest

from src.core.schemas import (
    ApplicationRunbook,
    SuiteExecutionSummary,
    TestCaseItem,
    TestCaseVerdict,
    TestManagementReport,
    TestSuitePayload,
)
from src.core.batch_orchestrator import BatchSuiteOrchestrator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_SUITE_PATH = Path(__file__).parent.parent / "demo_targets" / "sample_specs" / "sample_test_suite.json"


@pytest.fixture
def sample_suite() -> TestSuitePayload:
    """Load the sample test suite JSON into a validated Pydantic model."""
    raw = json.loads(SAMPLE_SUITE_PATH.read_text())
    return TestSuitePayload.model_validate(raw)


@pytest.fixture
def audit_path(tmp_path: Path) -> str:
    """Provide a temporary audit trail path."""
    return str(tmp_path / "audit_trail.jsonl")


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------

class TestEnterpriseSchemas:
    """Tests for the new enterprise batch schemas."""

    def test_load_sample_suite_json(self, sample_suite: TestSuitePayload) -> None:
        assert sample_suite.suite_id == "SUITE-RUN-20261026-001"
        assert len(sample_suite.test_cases) == 12
        assert sample_suite.runbook.app_name == "MockBank Enterprise Portal"
        assert sample_suite.runbook.base_url == "http://localhost:8080"

    def test_test_case_ids_sequential(self, sample_suite: TestSuitePayload) -> None:
        ids = [tc.test_id for tc in sample_suite.test_cases]
        expected = [f"TC-{i}" for i in range(101, 113)]
        assert ids == expected

    def test_runbook_model_standalone(self) -> None:
        runbook = ApplicationRunbook(
            app_name="TestApp",
            base_url="http://localhost:3000",
            auth_strategy="Login with admin/admin",
            environment="dev",
        )
        assert runbook.app_name == "TestApp"
        assert runbook.environment == "dev"

    def test_test_case_model_defaults(self) -> None:
        tc = TestCaseItem(
            test_id="TC-999",
            title="Test defaults",
            raw_steps=["Step 1"],
            expected_result="Pass",
        )
        assert tc.suite_category == "web_playwright"
        assert tc.priority == "medium"
        assert tc.preconditions == ""

    def test_test_case_verdicts(self) -> None:
        assert TestCaseVerdict.PASSED.value == "PASSED"
        assert TestCaseVerdict.PASSED_SELF_HEALED.value == "PASSED_SELF_HEALED"
        assert TestCaseVerdict.FAILED_APPLICATION_BUG.value == "FAILED_APPLICATION_BUG"
        assert TestCaseVerdict.HEALING_IN_PROGRESS.value == "HEALING_IN_PROGRESS"

    def test_suite_payload_with_custom_cases(self) -> None:
        payload = TestSuitePayload(
            suite_id="CUSTOM-001",
            runbook=ApplicationRunbook(
                app_name="CustomApp",
                base_url="http://localhost:5000",
            ),
            test_cases=[
                TestCaseItem(
                    test_id="TC-001",
                    title="Custom test",
                    raw_steps=["Go to homepage", "Click button"],
                    expected_result="Button click succeeds",
                ),
            ],
        )
        assert payload.suite_id == "CUSTOM-001"
        assert len(payload.test_cases) == 1


# ---------------------------------------------------------------------------
# Batch Orchestrator tests
# ---------------------------------------------------------------------------

class TestBatchSuiteOrchestrator:
    """Tests for the mock-mode batch orchestrator."""

    @pytest.mark.asyncio
    async def test_execute_suite_returns_12_reports(
        self, sample_suite: TestSuitePayload, audit_path: str,
    ) -> None:
        orchestrator = BatchSuiteOrchestrator(
            concurrency=4, audit_path=audit_path,
        )
        summary = await orchestrator.execute_suite(sample_suite)

        assert summary.suite_id == "SUITE-RUN-20261026-001"
        assert summary.total_cases == 12
        assert len(summary.reports) == 12

    @pytest.mark.asyncio
    async def test_expected_outcome_pattern(
        self, sample_suite: TestSuitePayload, audit_path: str,
    ) -> None:
        """Verify the 9-passed / 2-healed / 1-defect pattern."""
        orchestrator = BatchSuiteOrchestrator(
            concurrency=12, audit_path=audit_path,
        )
        summary = await orchestrator.execute_suite(sample_suite)

        assert summary.passed == 9, f"Expected 9 passed, got {summary.passed}"
        assert summary.self_healed == 2, f"Expected 2 healed, got {summary.self_healed}"
        assert summary.failed_bugs == 1, f"Expected 1 bug, got {summary.failed_bugs}"
        assert summary.failed_infra == 0
        assert summary.skipped == 0

    @pytest.mark.asyncio
    async def test_healed_cases_have_diffs(
        self, sample_suite: TestSuitePayload, audit_path: str,
    ) -> None:
        orchestrator = BatchSuiteOrchestrator(
            concurrency=12, audit_path=audit_path,
        )
        summary = await orchestrator.execute_suite(sample_suite)

        healed = [r for r in summary.reports if r.status == TestCaseVerdict.PASSED_SELF_HEALED]
        assert len(healed) == 2
        for report in healed:
            assert report.healed_selector_diff is not None
            assert "#confirm-transfer-btn" in report.healed_selector_diff
            assert "#btn-legacy-v2-obfuscated-99" in report.healed_selector_diff

    @pytest.mark.asyncio
    async def test_defect_case_has_summary(
        self, sample_suite: TestSuitePayload, audit_path: str,
    ) -> None:
        orchestrator = BatchSuiteOrchestrator(
            concurrency=12, audit_path=audit_path,
        )
        summary = await orchestrator.execute_suite(sample_suite)

        defects = [r for r in summary.reports if r.status == TestCaseVerdict.FAILED_APPLICATION_BUG]
        assert len(defects) == 1
        assert defects[0].test_id == "TC-112"
        assert defects[0].defect_summary is not None
        assert "fee" in defects[0].defect_summary.lower()

    @pytest.mark.asyncio
    async def test_all_reports_have_audit_hashes(
        self, sample_suite: TestSuitePayload, audit_path: str,
    ) -> None:
        orchestrator = BatchSuiteOrchestrator(
            concurrency=12, audit_path=audit_path,
        )
        summary = await orchestrator.execute_suite(sample_suite)

        for report in summary.reports:
            assert len(report.audit_hash) == 64, (
                f"{report.test_id} missing audit hash"
            )

    @pytest.mark.asyncio
    async def test_audit_trail_has_entries(
        self, sample_suite: TestSuitePayload, audit_path: str,
    ) -> None:
        orchestrator = BatchSuiteOrchestrator(
            concurrency=12, audit_path=audit_path,
        )
        await orchestrator.execute_suite(sample_suite)

        # Read the audit trail
        lines = Path(audit_path).read_text().strip().split("\n")
        # Should have: 1 suite_start + N pii_redactions + 12 test_case_complete + 1 suite_complete
        assert len(lines) >= 14  # at minimum

        # Verify chain
        from src.guardrails.audit_logger import ComplianceAuditLogger
        verifier = ComplianceAuditLogger(log_path=audit_path)
        assert verifier.verify_chain() is True

    @pytest.mark.asyncio
    async def test_status_change_callback_fires(
        self, sample_suite: TestSuitePayload, audit_path: str,
    ) -> None:
        """Verify the on_status_change callback is invoked."""
        status_log: list[tuple[str, TestCaseVerdict]] = []

        def on_change(test_id: str, status: TestCaseVerdict) -> None:
            status_log.append((test_id, status))

        orchestrator = BatchSuiteOrchestrator(
            concurrency=12,
            audit_path=audit_path,
            on_status_change=on_change,
        )
        await orchestrator.execute_suite(sample_suite)

        # Every test case should fire at least IN_PROGRESS + final status
        test_ids_seen = {tid for tid, _ in status_log}
        expected_ids = {tc.test_id for tc in sample_suite.test_cases}
        assert test_ids_seen == expected_ids

        # TC-110 and TC-111 should also fire HEALING_IN_PROGRESS
        healing_events = [
            (tid, s) for tid, s in status_log
            if s == TestCaseVerdict.HEALING_IN_PROGRESS
        ]
        healing_ids = {tid for tid, _ in healing_events}
        assert "TC-110" in healing_ids
        assert "TC-111" in healing_ids

    @pytest.mark.asyncio
    async def test_concurrent_execution_is_faster(
        self, sample_suite: TestSuitePayload, audit_path: str,
    ) -> None:
        """Concurrent execution with 12 workers should be faster than sequential."""
        # Concurrent (all 12 at once)
        orchestrator = BatchSuiteOrchestrator(
            concurrency=12, audit_path=audit_path,
        )
        start = time.monotonic()
        await orchestrator.execute_suite(sample_suite)
        concurrent_time = time.monotonic() - start

        # The 12 mock tests each sleep 0.2-0.8s, so sequential would be ~6s
        # Concurrent should be ~0.8s (bounded by the slowest single test)
        # We just verify it's under 4s to avoid flaky timing
        assert concurrent_time < 4.0, (
            f"Concurrent execution took {concurrent_time:.1f}s, expected < 4s"
        )

    def test_sync_wrapper(
        self, sample_suite: TestSuitePayload, audit_path: str,
    ) -> None:
        """Verify the synchronous wrapper works for non-async callers."""
        orchestrator = BatchSuiteOrchestrator(
            concurrency=4, audit_path=audit_path,
        )
        summary = orchestrator.execute_suite_sync(sample_suite)
        assert summary.total_cases == 12
        assert summary.passed + summary.self_healed + summary.failed_bugs == 12
