"""Unit tests for logging configuration."""

import importlib
import logging as py_logging

import allure
import pytest

from src.database import database as db_module
from src.utils import logging as logging_module


FEATURE = "Logging"
STORY = "Logging configuration"


@allure.feature(FEATURE)
@allure.story(STORY)
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
def test_setup_logging_is_idempotent(monkeypatch, tmp_path):
    """Ensure setup_logging only configures handlers once."""
    monkeypatch.chdir(tmp_path)

    # Reload module to reset cached state
    mod = importlib.reload(logging_module)

    logger_first = mod.setup_logging()
    root_logger = py_logging.getLogger()
    handler_ids = tuple(id(handler) for handler in root_logger.handlers)

    # Expect console + file handler
    assert len(handler_ids) == 2

    logger_second = mod.setup_logging()
    handler_ids_second = tuple(id(handler) for handler in root_logger.handlers)

    assert handler_ids_second == handler_ids
    assert logger_first is logger_second

    # Cleanup handlers so other tests can reconfigure logging
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        if isinstance(handler, py_logging.FileHandler):
            handler.close()
    mod._logging_configured = False


@allure.feature(FEATURE)
@allure.story(STORY)
@allure.severity(allure.severity_level.MINOR)
@pytest.mark.unit
def test_alembic_does_not_configure_logging(tmp_path):
    """Ensure Alembic logging configuration stays disabled."""
    ini_path = tmp_path / "alembic.ini"
    ini_path.write_text("[alembic]\nscript_location = migrations\n")
    (tmp_path / "migrations").mkdir()

    config = db_module._build_alembic_config(
        ini_path=ini_path, script_location=tmp_path / "migrations"
    )

    assert config.attributes.get("configure_logger") is False
