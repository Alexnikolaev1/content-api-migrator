"""Auth resolution: env token preferred, else ADC."""

from __future__ import annotations

import pytest

from content_api_migrator.auth import access_token


def test_access_token_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MERCHANT_ACCESS_TOKEN", "  ya29.test  ")
    assert access_token() == "ya29.test"


def test_adc_token_when_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MERCHANT_ACCESS_TOKEN", raising=False)

    class Creds:
        valid = True
        token = "adc-token"

    import google.auth

    monkeypatch.setattr(google.auth, "default", lambda scopes=None: (Creds(), "p"))
    assert access_token() == "adc-token"


def test_adc_refreshes_invalid_creds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MERCHANT_ACCESS_TOKEN", raising=False)

    class Creds:
        valid = False
        token = "after-refresh"

        def refresh(self, _request: object) -> None:
            self.valid = True

    import google.auth

    monkeypatch.setattr(google.auth, "default", lambda scopes=None: (Creds(), None))
    assert access_token() == "after-refresh"


def test_adc_rejects_empty_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MERCHANT_ACCESS_TOKEN", raising=False)

    class Creds:
        valid = True
        token = None

    import google.auth

    monkeypatch.setattr(google.auth, "default", lambda scopes=None: (Creds(), None))
    with pytest.raises(RuntimeError, match="no access token"):
        access_token()
