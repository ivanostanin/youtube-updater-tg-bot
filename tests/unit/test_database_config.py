from __future__ import annotations

import logging

import allure
import pytest
from alembic.config import Config

from src.database.database import _build_alembic_config
from src.utils.config import settings


@allure.feature("Database")
@allure.story("Alembic configuration")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
def test_build_config_uses_existing_ini(tmp_path) -> None:
    ini_path = tmp_path / "alembic.ini"
    ini_path.write_text(
        "[alembic]\n"
        "script_location = should_be_overridden\n"
        "sqlalchemy.url = sqlite:///ignored.db\n",
        encoding="utf-8",
    )
    script_location = tmp_path / "migrations"
    script_location.mkdir()

    config = _build_alembic_config(
        ini_path=ini_path,
        script_location=script_location,
    )

    assert isinstance(config, Config)
    assert config.get_main_option("script_location") == str(script_location)
    assert config.get_main_option("sqlalchemy.url") == settings.database_url
    assert config.attributes["db_url"] == settings.database_url


@allure.feature("Database")
@allure.story("Alembic configuration")
@allure.severity(allure.severity_level.MINOR)
@pytest.mark.unit
def test_build_config_without_ini_logs_warning(tmp_path, caplog) -> None:
    missing_ini = tmp_path / "alembic.ini"
    script_location = tmp_path / "migrations"
    script_location.mkdir()

    caplog.set_level(logging.WARNING, logger="src.database.database")

    config = _build_alembic_config(
        ini_path=missing_ini,
        script_location=script_location,
    )

    assert config.get_main_option("script_location") == str(script_location)
    assert config.get_main_option("sqlalchemy.url") == settings.database_url
    assert config.attributes["db_url"] == settings.database_url
    assert "Alembic configuration file missing" in caplog.text
