from __future__ import annotations

from app.settings import load_settings


def test_load_settings_reads_dart_api_key(monkeypatch) -> None:
    monkeypatch.setenv("DART_API_KEY", "test-dart-key")

    settings = load_settings()

    assert settings.dart_api_key == "test-dart-key"
