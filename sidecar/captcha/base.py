"""Abstract base class for captcha solvers — Detect → Solve → Apply pipeline."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from loguru import logger
from playwright.sync_api import Page


class CaptchaSolver(ABC):
    """Three-phase captcha solver base class.

    Subclasses implement detect/solve/apply for a specific captcha type.
    """

    @abstractmethod
    def detect(self, page: Page, **kwargs: Any) -> dict:
        """Check if this captcha type is present on the page.

        Returns dict with at least {"detected": bool}.
        """

    @abstractmethod
    def solve(self, page: Page, detection: dict, **kwargs: Any) -> dict:
        """Attempt to solve the detected captcha.

        Returns dict with at least {"solved": bool}.
        """

    @abstractmethod
    def apply(self, page: Page, solution: dict, **kwargs: Any) -> dict:
        """Apply / verify the solution.

        Returns dict with at least {"applied": bool}.
        """

    def run(self, page: Page, **kwargs: Any) -> dict:
        """Execute the full Detect → Solve → Apply pipeline."""
        detection = self.detect(page, **kwargs)
        if not detection.get("detected"):
            logger.debug(f"{self.__class__.__name__}: no captcha detected")
            return {"status": "no_captcha", **detection}

        solution = self.solve(page, detection, **kwargs)
        if not solution.get("solved"):
            logger.warning(f"{self.__class__.__name__}: solve failed")
            return {"status": "solve_failed", **solution}

        result = self.apply(page, solution, **kwargs)
        if not result.get("applied"):
            logger.warning(f"{self.__class__.__name__}: apply failed")
            return {"status": "apply_failed", **result}

        logger.info(f"{self.__class__.__name__}: captcha resolved successfully")
        return {"status": "success", **result}
