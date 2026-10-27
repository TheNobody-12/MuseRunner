"""Tests for the LangGraph Self-Healing Agent Workflow.

Validates that:
1. Normal test cases pass cleanly (PLAN -> EXEC -> FINALIZE).
2. Broken selector test cases trigger self-healing (PLAN -> EXEC -> HEAL -> EXEC -> FINALIZE)
   and return PASSED_SELF_HEALED with unified patch diffs.
3. Business logic assertion failures trigger bug triage (PLAN -> EXEC -> TRIAGE -> FINALIZE)
   and return FAILED_APPLICATION_BUG with defect summaries.
4. Zero-Trust PII sanitization operates before planning.
5. Every execution produces a verifiable audit hash.
"""

from __future__ import annotations

import pytest

from src.core.schemas import TestCaseItem, TestCaseVerdict
from src.graph.healing_agent import QEHealingWorkflow
from src.guardrails.audit_logger import ComplianceAuditLogger
from src.guardrails.sanitizer import ZeroTrustSanitizer


@pytest.fixture
def workflow(tmp_path) -> QEHealingWorkflow:
    audit_file = str(tmp_path / "test_audit.jsonl")
    return QEHealingWorkflow(
        sanitizer=ZeroTrustSanitizer(),
        audit_logger=ComplianceAuditLogger(log_path=audit_file),
    )


@pytest.fixture
def clean_test_case() -> TestCaseItem:
    return TestCaseItem(
        test_id="TC-101",
        title="Domestic Checking Wire Transfer",
        priority="critical",
        raw_steps=[
            "Navigate to wire transfer page",
            "Fill account number with 9876543210",
            "Fill amount with 2500",
            "Click confirm transfer",
        ],
        expected_result="Confirmation reference displayed with status submitted",
    )


@pytest.fixture
def healing_test_case() -> TestCaseItem:
    return TestCaseItem(
        test_id="TC-110",
        title="High-Value Commercial Wire Transfer with Custom Memo",
        priority="high",
        raw_steps=[
            "Navigate to wire transfer page",
            "Fill account number with 5544332211",
            "Fill SSN with 123-45-6789",
            "Fill amount with 45000",
            "Click confirm transfer",
        ],
        expected_result="Wire transfer submitted with memo preserved",
    )


@pytest.fixture
def bug_test_case() -> TestCaseItem:
    return TestCaseItem(
        test_id="TC-112",
        title="Daily Transfer Limit Boundary Exceeded",
        priority="critical",
        raw_steps=[
            "Navigate to wire transfer page",
            "Fill account number with 1122334455",
            "Fill amount with 75000",
            "Click confirm transfer",
        ],
        expected_result="Transfer blocked with user error daily limit exceeded",
    )


@pytest.mark.asyncio
async def test_clean_case_passes(workflow: QEHealingWorkflow, clean_test_case: TestCaseItem):
    report = await workflow.run(clean_test_case)
    assert report.test_id == "TC-101"
    assert report.status == TestCaseVerdict.PASSED
    assert report.healed_selector_diff is None
    assert report.defect_summary is None
    assert len(report.audit_hash) == 64


@pytest.mark.asyncio
async def test_healed_case_produces_diff(workflow: QEHealingWorkflow, healing_test_case: TestCaseItem):
    report = await workflow.run(healing_test_case)
    assert report.test_id == "TC-110"
    assert report.status == TestCaseVerdict.PASSED_SELF_HEALED
    assert report.healed_selector_diff is not None
    assert "--- a/selectors" in report.healed_selector_diff
    assert report.defect_summary is None
    assert len(report.audit_hash) == 64


@pytest.mark.asyncio
async def test_bug_case_produces_defect_summary(workflow: QEHealingWorkflow, bug_test_case: TestCaseItem):
    report = await workflow.run(bug_test_case)
    assert report.test_id == "TC-112"
    assert report.status == TestCaseVerdict.FAILED_APPLICATION_BUG
    assert report.defect_summary is not None
    assert "DEFECT [TC-112]" in report.defect_summary
    assert "AssertionError" in report.defect_summary
    assert report.healed_selector_diff is None
    assert len(report.audit_hash) == 64


@pytest.mark.asyncio
async def test_pii_sanitization_in_workflow(workflow: QEHealingWorkflow):
    case = TestCaseItem(
        test_id="TC-PII",
        title="PII Scrub Test",
        priority="medium",
        raw_steps=[
            "Enter SSN 999-88-7766 and email secret@example.com",
            "Submit form",
        ],
        expected_result="Form submitted",
    )
    report = await workflow.run(case)
    assert report.status == TestCaseVerdict.PASSED
    # Check that audit logged the PII redaction event
    entries = workflow.audit.read_entries()
    pii_events = [e for e in entries if e.event_type == "pii_redaction"]
    assert len(pii_events) > 0
    assert "SSN" in pii_events[0].redacted_fields or "EMAIL" in pii_events[0].redacted_fields
