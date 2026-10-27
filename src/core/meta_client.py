"""Baseten (muse-spark-open-1026) & Meta Model API client with MOCK_MODE fallback.

When MOCK_MODE is enabled (the default until API keys arrive), all calls
return deterministic hardcoded responses so the full pipeline can be
developed and tested end-to-end without network access.
"""

from __future__ import annotations

import os

from src.core.schemas import AtomicQEStep, HealingDiagnosis, BoundingBox, WorkerRuntime

MOCK_MODE: bool = os.getenv("MOCK_MODE", "true").lower() == "true"


class MetaOrchestratorClient:
    """Client for muse-spark-open-1026 structured output on Baseten.

    Translates sanitized BDD specs into deterministic AtomicQEStep plans.
    """

    def __init__(self) -> None:
        self._baseten_api_key = os.getenv("BASETEN_API_KEY", "")
        self._model_id = os.getenv("BASETEN_MODEL_ID", "meta-models/muse-spark-open-1026")

    def plan_steps(self, sanitized_spec: str) -> list[AtomicQEStep]:
        """Generate an ordered list of atomic QE steps from a BDD spec.

        Parameters
        ----------
        sanitized_spec : str
            The Gherkin/BDD text *after* PII redaction by ZeroTrustSanitizer.

        Returns
        -------
        list[AtomicQEStep]
        """
        if MOCK_MODE:
            return self._mock_plan()

        # Real Baseten inference — to be implemented when API keys arrive
        raise NotImplementedError(
            "Real inference not yet available. "
            "Set MOCK_MODE=true or provide BASETEN_API_KEY."
        )

    def diagnose_failure(
        self,
        failed_step: AtomicQEStep,
        error_message: str,
        dom_snapshot: str | None = None,
    ) -> HealingDiagnosis:
        """Invoke Muse Wonder + SAM 3.1 to diagnose a selector failure.

        Parameters
        ----------
        failed_step : AtomicQEStep
            The step that raised a selector/timeout exception.
        error_message : str
            The runtime error message.
        dom_snapshot : str | None
            Optional sanitized DOM snapshot for context.

        Returns
        -------
        HealingDiagnosis
        """
        if MOCK_MODE:
            return self._mock_diagnosis(failed_step)

        raise NotImplementedError(
            "Real inference not yet available. "
            "Set MOCK_MODE=true or provide BASETEN_API_KEY."
        )

    # ------------------------------------------------------------------
    # Mock responses
    # ------------------------------------------------------------------

    @staticmethod
    def _mock_plan() -> list[AtomicQEStep]:
        """Return a deterministic 4-step wire-transfer test plan."""
        return [
            AtomicQEStep(
                step_id="step_001",
                action="Navigate to wire transfer page",
                target_selector="#nav-transfers",
                runtime=WorkerRuntime.PLAYWRIGHT,
            ),
            AtomicQEStep(
                step_id="step_002",
                action="Fill account number",
                target_selector="#account-number",
                input_value="{{REDACTED_SSN_1}}",
                runtime=WorkerRuntime.PLAYWRIGHT,
            ),
            AtomicQEStep(
                step_id="step_003",
                action="Fill transfer amount",
                target_selector="#amount",
                input_value="5000",
                runtime=WorkerRuntime.PLAYWRIGHT,
            ),
            AtomicQEStep(
                step_id="step_004",
                action="Click confirm transfer",
                target_selector="#confirm-transfer-btn",
                runtime=WorkerRuntime.PLAYWRIGHT,
                assertion="text='submitted'",
            ),
        ]

    @staticmethod
    def _mock_diagnosis(failed_step: AtomicQEStep) -> HealingDiagnosis:
        """Return a mock healing diagnosis for a broken selector."""
        return HealingDiagnosis(
            original_selector=failed_step.target_selector,
            failure_reason=(
                f"Selector '{failed_step.target_selector}' not found in DOM. "
                "Likely renamed during a frontend deployment."
            ),
            healed_selector="#btn-legacy-v2-obfuscated-99",
            visual_bounding_box=BoundingBox(
                x=420, y=380, width=180, height=44, confidence=0.94,
            ),
            confidence=0.92,
            patch_diff=(
                f"--- a/selectors\n"
                f"+++ b/selectors\n"
                f"-  target_selector: {failed_step.target_selector}\n"
                f"+  target_selector: #btn-legacy-v2-obfuscated-99\n"
            ),
            model_used="muse-spark-open-1026 (MOCK)",
        )
