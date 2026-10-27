"""Pydantic schemas for MuseRunner's agentic QE pipeline.

Defines the core data models used across the orchestration layer,
workers, self-healing agent, and audit ledger.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

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
