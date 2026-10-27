"""Batch Suite Orchestrator for MuseRunner.

Consumes a ``TestSuitePayload`` (runbook + test cases) and dispatches
each test case to the appropriate worker, optionally in parallel via
``asyncio``.  When API keys arrive, the parallel execution path can
be upgraded to Modal Sandboxes for isolated, ephemeral containers.

In MOCK_MODE, the orchestrator simulates realistic execution with
deterministic timing and pre-scripted outcomes:
  - TC-101..TC-109: PASSED
  - TC-110, TC-111: PASSED_SELF_HEALED
  - TC-112: FAILED_APPLICATION_BUG
"""

from __future__ import annotations

import asyncio
import hashlib
import random
import time
from typing import Callable, Optional

from src.core.schemas import (
    ApplicationRunbook,
    AtomicQEStep,
    HealingDiagnosis,
    SuiteExecutionSummary,
    TestCaseItem,
    TestCaseVerdict,
    TestManagementReport,
    TestSuitePayload,
)
from src.core.meta_client import MetaOrchestratorClient, MOCK_MODE
from src.guardrails.sanitizer import ZeroTrustSanitizer
from src.guardrails.audit_logger import ComplianceAuditLogger


# ---------------------------------------------------------------------------
# Batch Orchestrator
# ---------------------------------------------------------------------------

class BatchSuiteOrchestrator:
    """Executes a full test suite with sanitization, orchestration, and audit.

    Parameters
    ----------
    concurrency : int
        Maximum number of test cases to execute in parallel.
    audit_path : str
        Path to the audit trail JSONL file.
    on_status_change : callable, optional
        Callback invoked whenever a test case's status changes,
        signature: ``(test_id: str, status: TestCaseVerdict) -> None``.
        Useful for live Streamlit dashboard updates.
    """

    def __init__(
        self,
        concurrency: int = 4,
        audit_path: str = "audit_trail.jsonl",
        on_status_change: Optional[Callable[[str, TestCaseVerdict], None]] = None,
    ) -> None:
        self._concurrency = concurrency
        self._sanitizer = ZeroTrustSanitizer()
        self._audit = ComplianceAuditLogger(log_path=audit_path)
        self._client = MetaOrchestratorClient()
        self._on_status_change = on_status_change

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute_suite(self, payload: TestSuitePayload) -> SuiteExecutionSummary:
        """Execute all test cases in the suite, respecting concurrency limits.

        Returns a ``SuiteExecutionSummary`` with per-case reports.
        """
        # Log suite start
        self._audit.log(
            event_type="suite_start",
            payload_summary=(
                f"Starting suite '{payload.suite_id}' with "
                f"{len(payload.test_cases)} test cases against "
                f"'{payload.runbook.app_name}' at {payload.runbook.base_url}"
            ),
        )

        # Sanitize the runbook
        sanitized_auth, auth_tokens = self._sanitizer.sanitize(
            payload.runbook.auth_strategy
        )
        if auth_tokens:
            self._audit.log(
                event_type="pii_redaction",
                payload_summary=f"Redacted {len(auth_tokens)} fields from runbook auth strategy",
                redacted_fields=[t.category for t in auth_tokens],
            )

        # Execute test cases with bounded concurrency
        semaphore = asyncio.Semaphore(self._concurrency)
        tasks = [
            self._execute_with_semaphore(semaphore, tc, payload.runbook)
            for tc in payload.test_cases
        ]
        reports = await asyncio.gather(*tasks)

        # Build summary
        summary = self._build_summary(payload.suite_id, reports)

        # Log suite completion
        self._audit.log(
            event_type="suite_complete",
            payload_summary=(
                f"Suite '{payload.suite_id}' complete: "
                f"{summary.passed} passed, {summary.self_healed} healed, "
                f"{summary.failed_bugs} bugs, {summary.failed_infra} infra failures"
            ),
        )

        return summary

    def execute_suite_sync(self, payload: TestSuitePayload) -> SuiteExecutionSummary:
        """Synchronous wrapper around ``execute_suite`` for non-async callers."""
        return asyncio.run(self.execute_suite(payload))

    # ------------------------------------------------------------------
    # Private: execution pipeline
    # ------------------------------------------------------------------

    async def _execute_with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        test_case: TestCaseItem,
        runbook: ApplicationRunbook,
    ) -> TestManagementReport:
        """Acquire the semaphore, then execute a single test case."""
        async with semaphore:
            return await self._execute_single(test_case, runbook)

    async def _execute_single(
        self,
        test_case: TestCaseItem,
        runbook: ApplicationRunbook,
    ) -> TestManagementReport:
        """Execute a single test case through the full pipeline."""
        self._notify(test_case.test_id, TestCaseVerdict.IN_PROGRESS)

        start = time.monotonic()

        # Step 1: Sanitize raw steps
        sanitized_steps: list[str] = []
        all_tokens = []
        for step in test_case.raw_steps:
            clean, tokens = self._sanitizer.sanitize(step)
            sanitized_steps.append(clean)
            all_tokens.extend(tokens)

        if all_tokens:
            self._audit.log(
                event_type="pii_redaction",
                payload_summary=(
                    f"[{test_case.test_id}] Redacted {len(all_tokens)} fields "
                    f"from test steps"
                ),
                redacted_fields=[t.category for t in all_tokens],
            )

        if MOCK_MODE:
            report = await self._mock_execute(test_case, sanitized_steps, start)
        else:
            # Real execution path (to be implemented with actual workers)
            report = await self._real_execute(test_case, sanitized_steps, runbook, start)

        # Log result
        audit_entry = self._audit.log(
            event_type="test_case_complete",
            payload_summary=(
                f"[{test_case.test_id}] {test_case.title} → "
                f"{report.status.value} in {report.execution_time_ms}ms"
            ),
        )

        # Attach audit hash
        report.audit_hash = audit_entry.sha256_hash

        self._notify(test_case.test_id, report.status)
        return report

    # ------------------------------------------------------------------
    # Mock execution (MOCK_MODE=true)
    # ------------------------------------------------------------------

    async def _mock_execute(
        self,
        test_case: TestCaseItem,
        sanitized_steps: list[str],
        start: float,
    ) -> TestManagementReport:
        """Simulate test execution with deterministic outcomes."""

        # Simulate realistic execution time (200-800ms per test)
        delay = random.uniform(0.2, 0.8)
        await asyncio.sleep(delay)

        steps_total = len(sanitized_steps)

        # Determine outcome based on test_id
        if test_case.test_id in ("TC-110", "TC-111"):
            # Self-healing scenario
            self._notify(test_case.test_id, TestCaseVerdict.HEALING_IN_PROGRESS)
            await asyncio.sleep(random.uniform(0.3, 0.6))  # healing delay

            diagnosis = self._client.diagnose_failure(
                failed_step=AtomicQEStep(
                    step_id="step_005",
                    action="Click Confirm Transfer",
                    target_selector="#confirm-transfer-btn",
                ),
                error_message="Element '#confirm-transfer-btn' not found in DOM",
            )

            elapsed_ms = int((time.monotonic() - start) * 1000)
            return TestManagementReport(
                test_id=test_case.test_id,
                title=test_case.title,
                status=TestCaseVerdict.PASSED_SELF_HEALED,
                execution_time_ms=elapsed_ms,
                healed_selector_diff=diagnosis.patch_diff,
                screenshot_path=f"screenshots/{test_case.test_id}_healed.png",
                audit_hash="",  # filled in after audit log
                steps_executed=steps_total,
                steps_total=steps_total,
            )

        elif test_case.test_id == "TC-112":
            # Application bug scenario
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return TestManagementReport(
                test_id=test_case.test_id,
                title=test_case.title,
                status=TestCaseVerdict.FAILED_APPLICATION_BUG,
                execution_time_ms=elapsed_ms,
                defect_summary=(
                    "DEFECT: Wire transfer fee calculation missing. "
                    "Expected 0.5% fee ($250.00) on $50,000 transfer, "
                    "but no fee field exists in the response. "
                    "Application returns only {status, reference, account, amount}."
                ),
                screenshot_path=f"screenshots/{test_case.test_id}_defect.png",
                audit_hash="",
                steps_executed=steps_total - 1,
                steps_total=steps_total,
            )

        else:
            # Clean pass
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return TestManagementReport(
                test_id=test_case.test_id,
                title=test_case.title,
                status=TestCaseVerdict.PASSED,
                execution_time_ms=elapsed_ms,
                screenshot_path=f"screenshots/{test_case.test_id}_passed.png",
                audit_hash="",
                steps_executed=steps_total,
                steps_total=steps_total,
            )

    # ------------------------------------------------------------------
    # Real execution (MOCK_MODE=false) — placeholder
    # ------------------------------------------------------------------

    async def _real_execute(
        self,
        test_case: TestCaseItem,
        sanitized_steps: list[str],
        runbook: ApplicationRunbook,
        start: float,
    ) -> TestManagementReport:
        """Real execution using Playwright/Robot/Pywinauto workers.

        To be implemented when API keys and worker integrations are ready.
        """
        raise NotImplementedError(
            f"Real execution for {test_case.test_id} not yet implemented. "
            "Set MOCK_MODE=true."
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _notify(self, test_id: str, status: TestCaseVerdict) -> None:
        """Fire the status change callback if registered."""
        if self._on_status_change:
            self._on_status_change(test_id, status)

    @staticmethod
    def _build_summary(
        suite_id: str,
        reports: list[TestManagementReport],
    ) -> SuiteExecutionSummary:
        """Aggregate individual reports into a suite-level summary."""
        return SuiteExecutionSummary(
            suite_id=suite_id,
            total_cases=len(reports),
            passed=sum(1 for r in reports if r.status == TestCaseVerdict.PASSED),
            self_healed=sum(
                1 for r in reports if r.status == TestCaseVerdict.PASSED_SELF_HEALED
            ),
            failed_bugs=sum(
                1 for r in reports if r.status == TestCaseVerdict.FAILED_APPLICATION_BUG
            ),
            failed_infra=sum(
                1 for r in reports if r.status == TestCaseVerdict.FAILED_INFRASTRUCTURE
            ),
            skipped=sum(1 for r in reports if r.status == TestCaseVerdict.SKIPPED),
            total_execution_time_ms=sum(r.execution_time_ms for r in reports),
            reports=reports,
        )
