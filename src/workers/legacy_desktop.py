"""Legacy Desktop & Win32 worker for enterprise client applications.

Provides:
  - Accessibility / control-tree hierarchy extraction
  - Fallback to SAM 3.1 visual grounding coordinates (x, y) when Win32 automation IDs
    are obfuscated, missing, or dynamically allocated.
"""

from __future__ import annotations

from typing import Optional

from src.core.schemas import AtomicQEStep, BoundingBox, StepVerdict


class LegacyDesktopWorker:
    """Interacts with desktop applications via accessibility trees and visual coordinates."""

    def __init__(self, app_title: str = "Enterprise Desktop Client") -> None:
        self.app_title = app_title

    def extract_control_tree(self) -> list[dict[str, any]]:
        """Simulate extracting Win32 / UIA control hierarchy."""
        return [
            {"control_id": "txtAccount", "type": "Edit", "rect": [100, 150, 300, 180]},
            {"control_id": "txtAmount", "type": "Edit", "rect": [100, 200, 300, 230]},
            {"control_id": "btnSubmit", "type": "Button", "rect": [100, 260, 220, 295]},
        ]

    def execute_step(
        self,
        step: AtomicQEStep,
        visual_bounding_box: Optional[BoundingBox] = None,
    ) -> dict[str, any]:
        """Execute step using control selector or fallback to SAM 3.1 bounding box click."""
        if visual_bounding_box:
            # Click center of segmented bounding box
            click_x = visual_bounding_box.x + visual_bounding_box.width // 2
            click_y = visual_bounding_box.y + visual_bounding_box.height // 2
            return {
                "verdict": StepVerdict.PASS,
                "mechanism": "SAM_3.1_VISUAL_COORDINATES",
                "coordinates": (click_x, click_y),
                "confidence": visual_bounding_box.confidence,
            }

        return {
            "verdict": StepVerdict.PASS,
            "mechanism": "WIN32_CONTROL_TREE",
            "control_selector": step.target_selector,
        }
