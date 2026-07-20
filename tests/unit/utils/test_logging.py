"""Tests for logging bootstrap."""

from __future__ import annotations

import json
import logging
import logging.handlers
import tempfile
from pathlib import Path

import pytest

from gaming_hub.config.models import Settings
from gaming_hub.utils.logging import configure_logging


@pytest.fixture(autouse=True)
def _reset_root_logger() -> None:
    """Reset root logger handlers before and after each test."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    root.setLevel(logging.WARNING)
    yield
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    root.setLevel(logging.WARNING)


@pytest.mark.unit
def test_configure_logging_sets_level() -> None:
    """configure_logging should set the root logger to the configured level."""
    settings = Settings(_env_file=None, log_level="DEBUG")
    configure_logging(settings)
    root = logging.getLogger()
    assert root.level == logging.DEBUG


@pytest.mark.unit
def test_colored_output_format(capsys: pytest.CaptureFixture) -> None:
    """With log_json=False, output should contain the expected format."""
    settings = Settings(_env_file=None, log_level="INFO", log_json=False)
    configure_logging(settings)
    logging.getLogger("test_colored").info("hello world")
    captured = capsys.readouterr()
    assert "hello world" in captured.out
    assert "test_colored" in captured.out


@pytest.mark.unit
def test_json_output_format(capsys: pytest.CaptureFixture) -> None:
    """With log_json=True, output should be valid JSON with expected keys."""
    settings = Settings(_env_file=None, log_level="INFO", log_json=True)
    configure_logging(settings)
    logging.getLogger("test_json").info("hello world")
    captured = capsys.readouterr()
    record = json.loads(captured.out.strip())
    assert record["level"] == "INFO"
    assert record["logger"] == "test_json"
    assert record["message"] == "hello world"
    assert "timestamp" in record


@pytest.mark.unit
def test_warning_level_default() -> None:
    """With default log_level=INFO, DEBUG messages should not appear."""
    settings = Settings(_env_file=None, log_level="INFO")
    configure_logging(settings)
    root = logging.getLogger()
    assert root.level == logging.INFO


@pytest.mark.unit
def test_file_output() -> None:
    """With log_file_path set, output should be written to the file."""
    with tempfile.NamedTemporaryFile(mode="r", suffix=".log", delete=False) as tmp:
        filepath = tmp.name
    try:
        settings = Settings(_env_file=None, log_file_path=filepath)
        configure_logging(settings)
        logging.getLogger("test_file").info("written to file")
        content = Path(filepath).read_text()
        assert "written to file" in content
        assert "test_file" in content
    finally:
        Path(filepath).unlink(missing_ok=True)


@pytest.mark.unit
def test_file_rotation_handler() -> None:
    """With log_rotation=True, a RotatingFileHandler with 5MB/3 backups should be used."""
    max_bytes = 5_000_000
    backup_count = 3
    with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as tmp:
        filepath = tmp.name
    try:
        settings = Settings(_env_file=None, log_file_path=filepath, log_rotation=True)
        configure_logging(settings)
        root = logging.getLogger()
        rotator = next(
            (h for h in root.handlers if isinstance(h, logging.handlers.RotatingFileHandler)),
            None,
        )
        assert rotator is not None, "Expected a RotatingFileHandler"
        assert rotator.maxBytes == max_bytes
        assert rotator.backupCount == backup_count
    finally:
        Path(filepath).unlink(missing_ok=True)


@pytest.mark.unit
def test_third_party_loggers_silenced() -> None:
    """Third-party loggers should default to WARNING level."""
    settings = Settings(_env_file=None)
    configure_logging(settings)
    assert logging.getLogger("discord").level == logging.WARNING
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("urllib3").level == logging.WARNING


@pytest.mark.unit
def test_reconfigure_replaces_handlers() -> None:
    """Calling configure_logging twice should replace the first config."""
    settings_a = Settings(_env_file=None, log_level="DEBUG")
    configure_logging(settings_a)
    root = logging.getLogger()
    initial_handlers = list(root.handlers)
    settings_b = Settings(_env_file=None, log_level="WARNING")
    configure_logging(settings_b)
    assert root.level == logging.WARNING
    assert root.handlers != initial_handlers
