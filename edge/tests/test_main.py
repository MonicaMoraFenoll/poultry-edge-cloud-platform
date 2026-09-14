from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

from poultry_edge.main import main


def make_config():
    """
    Build a minimal Edge configuration object for main-function tests.

    Returns
    -------
    SimpleNamespace
        Minimal configuration containing the farm identifier required
        by the application entry point.
    """

    return SimpleNamespace(
        farm=SimpleNamespace(
            id="farm_01",
        )
    )


def test_main_success(
    monkeypatch,
):
    """Verify that main returns success when the daily pipeline completes."""

    config = make_config()

    load_config_mock = MagicMock(
        return_value=config,
    )

    pipeline_mock = MagicMock()

    monkeypatch.setattr(
        "poultry_edge.main.load_edge_config",
        load_config_mock,
    )

    monkeypatch.setattr(
        "poultry_edge.main.run_daily_pipeline",
        pipeline_mock,
    )

    monkeypatch.setattr(
        "poultry_edge.main.configure_logging",
        MagicMock(),
    )

    # Provide the MLflow endpoints expected by the application.
    monkeypatch.setenv(
        "MLFLOW_TRACKING_URI",
        "http://mlflow:5000",
    )

    monkeypatch.setenv(
        "MLFLOW_REGISTRY_URI",
        "http://mlflow:5000",
    )

    result = main()

    assert result == 0

    load_config_mock.assert_called_once()

    pipeline_mock.assert_called_once_with(
        config=config,
        processing_date=date.today(),
        tracking_uri="http://mlflow:5000",
        registry_uri="http://mlflow:5000",
    )


def test_main_uses_tracking_uri_as_registry_uri_by_default(
    monkeypatch,
):
    """Verify that the tracking URI is reused when no registry URI is defined."""

    config = make_config()

    monkeypatch.setattr(
        "poultry_edge.main.load_edge_config",
        MagicMock(return_value=config),
    )

    pipeline_mock = MagicMock()

    monkeypatch.setattr(
        "poultry_edge.main.run_daily_pipeline",
        pipeline_mock,
    )

    monkeypatch.setattr(
        "poultry_edge.main.configure_logging",
        MagicMock(),
    )

    monkeypatch.setenv(
        "MLFLOW_TRACKING_URI",
        "http://mlflow:5000",
    )

    # Remove the explicit registry URI to test the fallback behavior.
    monkeypatch.delenv(
        "MLFLOW_REGISTRY_URI",
        raising=False,
    )

    result = main()

    assert result == 0

    pipeline_mock.assert_called_once_with(
        config=config,
        processing_date=date.today(),
        tracking_uri="http://mlflow:5000",
        registry_uri="http://mlflow:5000",
    )


def test_main_returns_one_when_config_loading_fails(
    monkeypatch,
):
    """Verify that main returns exit code 1 when configuration loading fails."""

    def failing_load_config(*args, **kwargs):
        # Simulate an error raised while reading or validating the configuration.
        raise RuntimeError(
            "Invalid configuration"
        )

    pipeline_mock = MagicMock()

    monkeypatch.setattr(
        "poultry_edge.main.load_edge_config",
        failing_load_config,
    )

    monkeypatch.setattr(
        "poultry_edge.main.run_daily_pipeline",
        pipeline_mock,
    )

    monkeypatch.setattr(
        "poultry_edge.main.configure_logging",
        MagicMock(),
    )

    result = main()

    assert result == 1

    # The pipeline must not start when configuration loading fails.
    pipeline_mock.assert_not_called()


def test_main_returns_one_when_pipeline_fails(
    monkeypatch,
):
    """Verify that main returns exit code 1 when the pipeline raises an error."""

    config = make_config()

    monkeypatch.setattr(
        "poultry_edge.main.load_edge_config",
        MagicMock(return_value=config),
    )

    def failing_pipeline(*args, **kwargs):
        # Simulate an unexpected failure during daily pipeline execution.
        raise RuntimeError(
            "Pipeline failed"
        )

    monkeypatch.setattr(
        "poultry_edge.main.run_daily_pipeline",
        failing_pipeline,
    )

    monkeypatch.setattr(
        "poultry_edge.main.configure_logging",
        MagicMock(),
    )

    result = main()

    assert result == 1