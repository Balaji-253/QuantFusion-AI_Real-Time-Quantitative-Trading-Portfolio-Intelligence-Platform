import pytest
from pydantic import ValidationError

from app.config import Settings


def test_rejects_invalid_environment():
    with pytest.raises(ValidationError):
        Settings(app_env="production-ish")


def test_rejects_zero_simulator_interval():
    with pytest.raises(ValidationError):
        Settings(simulator_interval_seconds=0)


def test_rejects_nonpositive_order_limit():
    with pytest.raises(ValidationError):
        Settings(max_order_notional=0)


def test_rejects_nonpositive_position_limit():
    with pytest.raises(ValidationError):
        Settings(max_position_quantity=0)


def test_accepts_valid_production_settings():
    settings = Settings(
        app_env="production",
        log_level="WARNING",
        simulator_interval_seconds=1.0,
        max_order_notional=5000,
        max_position_quantity=50,
    )
    assert settings.app_env == "production"
    assert settings.max_order_notional == 5000
