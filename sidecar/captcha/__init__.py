"""Mimicry Captcha solver module.

Provides a three-phase (Detect→Solve→Apply) captcha solver framework.

Currently supports:
- CloudflareSolver — click-based Turnstile / Interstitial solver
- captcha.detect_cloudflare — detect-only, returns whether challenge is present
- captcha.solve_cloudflare — click-based solver (no external API)

API solvers (2captcha, etc.) and reCAPTCHA are intentionally out of scope
for this MVP.
"""
from .base import CaptchaSolver
from .cloudflare import (
    CaptchaApplyingError,
    CaptchaDetectionError,
    CaptchaSolvingError,
    CloudflareSolver,
    detect_cloudflare_challenge,
    solve_cloudflare_by_click,
)

__all__ = [
    "CaptchaSolver",
    "CaptchaApplyingError",
    "CaptchaDetectionError",
    "CaptchaSolvingError",
    "CloudflareSolver",
    "detect_cloudflare_challenge",
    "solve_cloudflare_by_click",
]
