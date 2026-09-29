"""OAuth access tokens for Merchant API (scope: content)."""

from __future__ import annotations

import os

SCOPE = "https://www.googleapis.com/auth/content"


def access_token() -> str:
    """Resolve Bearer token from env or Application Default Credentials.

    Preferred for CI/scripts: MERCHANT_ACCESS_TOKEN.
    Preferred for local/service accounts: GOOGLE_APPLICATION_CREDENTIALS
    + google-auth ADC (scope content).
    """
    env_token = os.environ.get("MERCHANT_ACCESS_TOKEN", "").strip()
    if env_token:
        return env_token
    return _adc_token()


def _adc_token() -> str:
    try:
        import google.auth
        from google.auth.transport.requests import Request
    except ImportError as exc:
        raise RuntimeError(
            "Install google-auth + requests, or set MERCHANT_ACCESS_TOKEN. "
            "pip install -e ."
        ) from exc
    credentials, _project = google.auth.default(scopes=[SCOPE])  # type: ignore[attr-defined]
    if not credentials.valid:
        credentials.refresh(Request())
    token = getattr(credentials, "token", None)
    if not token:
        raise RuntimeError("ADC returned no access token for Merchant API.")
    return str(token)
