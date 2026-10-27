"""Pydantic schemas for MuseRunner's agentic QE pipeline.

Defines the core data models used across the orchestration layer,
workers, self-healing agent, and audit ledger.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class WorkerRuntime(str, Enum):
    """Execution runtimes supported by MuseRunner workers."""
    PLAYWRIGHT = "playwright"
    ROBOT = "robot"
    PYWINAUTO = "pywinauto"


class StepVerdict(str, Enum):
    """Outcome of a single atomic QE step execution."""
    PASS = "pass"
    FAIL = "fail"
    HEALED = "healed"
    SKIPPED = "skipped"


# ---------------------------------------------------------------------------
# Orchestration schemas
# ---------------------------------------------------------------------------

class AtomicQEStep(BaseModel):
    """A single atomic QE action the orchestrator dispatches to a worker.

    Produced by muse-spark-open-1026 structured output from a BDD spec,
    consumed by the appropriate runtime worker.
    """
    step_id: str = Field(
        ...,
        description="Unique step identifier, e.g. 'step_001'",
    )
    action: str = Field(
        ...,
        description="Human-readable action description",
    )
    target_selector: str = Field(
        ...,
        description="DOM selector, Robot keyword, or Win32 control ID",
    )
    input_value: Optional[str] = Field(
        None,
        description="Value to type / select, if any",
    )
    runtime: WorkerRuntime = Field(
        default=WorkerRuntime.PLAYWRIGHT,
        description="Target execution runtime",
    )
    assertion: Optional[str] = Field(
        None,
        description="Post-action assertion expression",
    )


# ---------------------------------------------------------------------------
# Self-healing schemas
# ---------------------------------------------------------------------------

class BoundingBox(BaseModel):
    """Pixel bounding box returned by SAM 3.1 visual grounding."""
    x: int
    y: int
    width: int
    height: int
    confidence: float = Field(ge=0.0, le=1.0)


class HealingDiagnosis(BaseModel):
    """Root-cause analysis + healing patch produced by the self-healing agent.

    Generated when a worker encounters a selector failure and the visual
    healing state machine (SAM 3.1 + Muse Wonder) resolves the break.
    """
    original_selector: str = Field(
        ...,
        description="The selector that failed at runtime",
    )
    failure_reason: str = Field(
        ...,
        description="Diagnosis of why the selector broke",
    )
    healed_selector: str = Field(
        ...,
        description="Corrected selector that resolves the element",
    )
    visual_bounding_box: Optional[BoundingBox] = Field(
        None,
        description="SAM 3.1 bounding box of the target element",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Model confidence in the healing patch",
    )
    patch_diff: str = Field(
        ...,
        description="Unified diff of the selector fix",
    )
    model_used: str = Field(
        default="muse-spark-open-1026",
        description="Model that generated the healing diagnosis",
    )


# ---------------------------------------------------------------------------
# Audit schemas
# ---------------------------------------------------------------------------

class AuditEntry(BaseModel):
    """A single row in the SHA-256 hash-chained audit ledger.

    Each entry's sha256_hash covers its own payload plus the previous
    entry's hash, forming a tamper-evident append-only chain.
    """
    sequence_id: int = Field(
        ...,
        description="Monotonically increasing sequence number",
    )
    timestamp: str = Field(
        ...,
        description="ISO-8601 UTC timestamp",
    )
    event_type: str = Field(
        ...,
        description="Category of event, e.g. 'pii_redaction', 'step_executed'",
    )
    payload_summary: str = Field(
        ...,
        description="Human-readable summary of the event payload",
    )
    redacted_fields: list[str] = Field(
        default_factory=list,
        description="List of PII field types that were redacted",
    )
    sha256_hash: str = Field(
        ...,
        description="SHA-256 hash of this entry (covers payload + previous_hash)",
    )
    previous_hash: str = Field(
        ...,
        description="SHA-256 hash of the preceding entry (genesis = '0' * 64)",
    )


# ---------------------------------------------------------------------------
# Enterprise Batch Orchestration schemas
# ---------------------------------------------------------------------------

class ApplicationRunbook(BaseModel):
    """Application access guide / runbook provided alongside a test suite.

    Contains environment URLs, authentication strategy, credential
    placeholders (intercepted by ZeroTrustSanitizer), and global
    navigation notes that apply to every test case in the batch.
    """
    app_name: str = Field(
        ...,
        description="Human-readable application name, e.g. 'MockBank Portal'",
    )
    base_url: str = Field(
        ...,
        description="Root URL of the application under test",
    )
    auth_strategy: str = Field(
        default="",
        description="Steps to authenticate using vaulted credentials",
    )
    global_navigation_notes: str = Field(
        default="",
        description="Shared navigation rules applied before each test case",
    )
    environment: str = Field(
        default="staging",
        description="Target environment label, e.g. 'staging', 'production'",
    )


class TestCaseItem(BaseModel):
    """A single test case imported from a Test Management system.

    Maps to a Jira Xray, TestRail, or Zephyr export row. The
    ``raw_steps`` list is fed to muse-spark-open-1026 to synthesize
    typed ``AtomicQEStep`` tool calls.
    """
    __test__ = False
    test_id: str = Field(
        ...,
        description="External test management ID, e.g. 'XRAY-401' or 'TC-101'",
    )
    title: str = Field(
        ...,
        description="Human-readable test case title",
    )
    suite_category: Literal["web_playwright", "robot_framework", "legacy_desktop"] = Field(
        default="web_playwright",
        description="Target worker runtime for this test case",
    )
    priority: Literal["critical", "high", "medium", "low"] = Field(
        default="medium",
        description="Execution priority for scheduling",
    )
    raw_steps: list[str] = Field(
        ...,
        description="Ordered list of human-readable test steps",
    )
    expected_result: str = Field(
        ...,
        description="Expected outcome after all steps complete",
    )
    preconditions: str = Field(
        default="",
        description="Setup conditions required before execution",
    )


class TestSuitePayload(BaseModel):
    """A batch of test cases paired with an application runbook.

    This is the top-level input artifact that MuseRunner's batch
    orchestrator consumes. It replaces the single-prompt workflow
    with a production-grade test management integration.
    """
    __test__ = False
    suite_id: str = Field(
        ...,
        description="Unique suite run identifier, e.g. 'SUITE-RUN-20261026-001'",
    )
    runbook: ApplicationRunbook = Field(
        ...,
        description="Application access guide for this test run",
    )
    test_cases: list[TestCaseItem] = Field(
        ...,
        description="Ordered list of test cases to execute",
    )


class TestCaseVerdict(str, Enum):
    """Outcome of a single test case in a batch run."""
    __test__ = False
    PASSED = "PASSED"
    PASSED_SELF_HEALED = "PASSED_SELF_HEALED"
    FAILED_APPLICATION_BUG = "FAILED_APPLICATION_BUG"
    FAILED_INFRASTRUCTURE = "FAILED_INFRASTRUCTURE"
    SKIPPED = "SKIPPED"
    IN_PROGRESS = "IN_PROGRESS"
    HEALING_IN_PROGRESS = "HEALING_IN_PROGRESS"


class TestManagementReport(BaseModel):
    """Execution result for a single test case, ready for Jira/TestRail sync.

    Contains the verdict, timing, optional healing diffs, optional
    defect summaries, screenshot paths, and the audit hash linking
    this result to the tamper-evident ledger.
    """
    __test__ = False
    test_id: str = Field(
        ...,
        description="Matches TestCaseItem.test_id",
    )
    title: str = Field(
        default="",
        description="Test case title for display",
    )
    status: TestCaseVerdict = Field(
        ...,
        description="Final execution verdict",
    )
    execution_time_ms: int = Field(
        ...,
        description="Wall-clock execution time in milliseconds",
    )
    healed_selector_diff: Optional[str] = Field(
        None,
        description="Unified diff of auto-healed selectors, if any",
    )
    defect_summary: Optional[str] = Field(
        None,
        description="Bug description if a real application defect was caught",
    )
    screenshot_path: str = Field(
        default="",
        description="Path to the final-state screenshot",
    )
    audit_hash: str = Field(
        ...,
        description="SHA-256 hash from the audit ledger for this test case",
    )
    steps_executed: int = Field(
        default=0,
        description="Number of AtomicQESteps successfully executed",
    )
    steps_total: int = Field(
        default=0,
        description="Total number of AtomicQESteps planned",
    )


class SuiteExecutionSummary(BaseModel):
    """Aggregate summary of a full batch suite run.

    Designed for the Streamlit dashboard header and test management
    sync payload.
    """
    suite_id: str
    total_cases: int
    passed: int
    self_healed: int
    failed_bugs: int
    failed_infra: int
    skipped: int
    total_execution_time_ms: int
    reports: list[TestManagementReport]

