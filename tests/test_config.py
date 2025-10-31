from pathlib import Path

from grader import config


def test_settings_load_from_env(monkeypatch, tmp_path: Path):
    creds_file = tmp_path / "creds.json"
    creds_file.write_text("{}", encoding="utf-8")

    monkeypatch.setenv("UNK_THRESHOLD", "75")
    monkeypatch.setenv("MAX_CONCURRENCY", "5")
    monkeypatch.setenv("XAI_API_KEY", "test-xai")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(creds_file))
    monkeypatch.setenv("VISION_LANGUAGE_HINTS", "en, es")

    config.get_settings.cache_clear()
    settings = config.get_settings()

    assert settings.unk_threshold == 75
    assert settings.max_concurrency == 5
    assert settings.xai.api_key == "test-xai"
    assert settings.google.credentials_path == creds_file
    assert settings.google.language_hints == ["en", "es"]

    config.get_settings.cache_clear()
