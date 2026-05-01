"""Mimicry Captcha solver module.

Provides Cloudflare Turnstile / Interstitial click-based solving by accessing
the active session's Playwright page through SessionManager.

Currently supports:
- captcha.detect_cloudflare — detect-only, returns whether challenge is present
- captcha.solve_cloudflare — click-based solver (no external API)

API solvers (2captcha, etc.) and reCAPTCHA are intentionally out of scope
for this MVP.
"""
from .cloudflare import (
    CaptchaApplyingError,
    CaptchaDetectionError,
    CaptchaSolvingError,
    detect_cloudflare_challenge,
    solve_cloudflare_by_click,
)

__all__ = [
    "CaptchaApplyingError",
    "CaptchaDetectionError",
    "CaptchaSolvingError",
    "detect_cloudflare_challenge",
    "solve_cloudflare_by_click",
]
