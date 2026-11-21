"""Лог игры и файл падения — в папке настроек, logs/."""
from duel import logs


def test_crash_is_written(tmp_path, monkeypatch):
    monkeypatch.setenv("DUEL_SETTINGS", str(tmp_path / "s.json"))
    try:
        raise ValueError("Invalid resolution for Surface")
    except ValueError as e:
        path = logs.crash(type(e), e, e.__traceback__)
    assert path.parent == tmp_path / "logs"
    text = path.read_text(encoding="utf-8")
    assert "Spellgunners" in text and "Invalid resolution" in text and "test_crash_is_written" in text
