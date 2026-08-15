import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from poultry_edge.config import ModelConfig
from poultry_edge.model_loader import (
    read_current_model,
    synchronize_model,
)


MODEL_NAME = "egg_counter_farm_01"
MODEL_ALIAS = "production"
ACTIVE_VERSION = "4"


def build_model_config(tmp_path: Path) -> ModelConfig:
    return ModelConfig(
        registered_name=MODEL_NAME,
        alias=MODEL_ALIAS,
        local_root_directory=tmp_path / "models",
    )


def build_version_directory(
    model_config: ModelConfig,
    version: str,
) -> Path:
    return (
        model_config.local_root_directory
        / model_config.registered_name
        / "versions"
        / version
    )


def write_current_model(
    model_config: ModelConfig,
    version_directory: Path,
) -> None:
    """Create a valid current.json for testing."""

    current_file = (
        model_config.local_root_directory
        / model_config.registered_name
        / "current.json"
    )

    current_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    current_file.write_text(
        json.dumps(
            {
                "registered_name": MODEL_NAME,
                "version": ACTIVE_VERSION,
                "alias": MODEL_ALIAS,
                "model_path": str(version_directory),
                "synchronized_at": "2026-08-15T08:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )


def test_synchronize_model_downloads_new_version(
    tmp_path,
    monkeypatch,
):
    model_config = build_model_config(tmp_path)

    fake_model_version = SimpleNamespace(
        version=ACTIVE_VERSION,
    )

    class FakeMlflowClient:
        def get_model_version_by_alias(
            self,
            name,
            alias,
        ):
            assert name == MODEL_NAME
            assert alias == MODEL_ALIAS

            return fake_model_version

    monkeypatch.setattr(
        "poultry_edge.model_loader.MlflowClient",
        FakeMlflowClient,
    )

    def fake_download_model_version(
        model_uri,
        destination_directory,
    ):
        assert (
            model_uri
            == f"models:/{MODEL_NAME}/{ACTIVE_VERSION}"
        )

        destination_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        (
            destination_directory
            / "best.pt"
        ).write_text(
            "mock YOLO model version 4",
            encoding="utf-8",
        )

    monkeypatch.setattr(
        "poultry_edge.model_loader._download_model_version",
        fake_download_model_version,
    )

    local_model = synchronize_model(
        model_config=model_config,
        allow_local_fallback=False,
    )

    assert local_model.registered_name == MODEL_NAME
    assert local_model.alias == MODEL_ALIAS
    assert local_model.version == ACTIVE_VERSION

    assert (
        local_model.model_path
        / "best.pt"
    ).is_file()

    current_model = read_current_model(
        model_config
    )

    assert current_model.version == ACTIVE_VERSION
    assert current_model.alias == MODEL_ALIAS
    assert current_model.registered_name == MODEL_NAME


def test_synchronize_model_reuses_existing_local_version(
    tmp_path,
    monkeypatch,
):
    model_config = build_model_config(tmp_path)

    version_directory = build_version_directory(
        model_config=model_config,
        version=ACTIVE_VERSION,
    )

    version_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        version_directory
        / "best.pt"
    ).write_text(
        "existing local model version 4",
        encoding="utf-8",
    )

    fake_model_version = SimpleNamespace(
        version=ACTIVE_VERSION,
    )

    class FakeMlflowClient:
        def get_model_version_by_alias(
            self,
            name,
            alias,
        ):
            assert name == MODEL_NAME
            assert alias == MODEL_ALIAS

            return fake_model_version

    monkeypatch.setattr(
        "poultry_edge.model_loader.MlflowClient",
        FakeMlflowClient,
    )

    def should_not_download(*args, **kwargs):
        raise AssertionError(
            "The model should not be downloaded again."
        )

    monkeypatch.setattr(
        "poultry_edge.model_loader._download_model_version",
        should_not_download,
    )

    local_model = synchronize_model(
        model_config=model_config,
        allow_local_fallback=False,
    )

    assert local_model.version == ACTIVE_VERSION
    assert local_model.model_path == version_directory


def test_synchronize_model_uses_local_fallback_when_mlflow_fails(
    tmp_path,
    monkeypatch,
):
    model_config = build_model_config(tmp_path)

    version_directory = build_version_directory(
        model_config=model_config,
        version=ACTIVE_VERSION,
    )

    version_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        version_directory
        / "best.pt"
    ).write_text(
        "local fallback model version 4",
        encoding="utf-8",
    )

    write_current_model(
        model_config=model_config,
        version_directory=version_directory,
    )

    class FailingMlflowClient:
        def get_model_version_by_alias(
            self,
            name,
            alias,
        ):
            raise ConnectionError(
                "MLflow unavailable"
            )

    monkeypatch.setattr(
        "poultry_edge.model_loader.MlflowClient",
        FailingMlflowClient,
    )

    local_model = synchronize_model(
        model_config=model_config,
        allow_local_fallback=True,
    )

    assert local_model.version == ACTIVE_VERSION
    assert local_model.alias == MODEL_ALIAS
    assert local_model.model_path == version_directory


def test_synchronize_model_fails_when_mlflow_and_local_model_are_unavailable(
    tmp_path,
    monkeypatch,
):
    model_config = build_model_config(tmp_path)

    class FailingMlflowClient:
        def get_model_version_by_alias(
            self,
            name,
            alias,
        ):
            raise ConnectionError(
                "MLflow unavailable"
            )

    monkeypatch.setattr(
        "poultry_edge.model_loader.MlflowClient",
        FailingMlflowClient,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "The model could not be synchronized with MLflow "
            "and no valid local YOLO model is available"
        ),
    ):
        synchronize_model(
            model_config=model_config,
            allow_local_fallback=True,
        )


def test_read_current_model_fails_when_best_pt_is_missing(
    tmp_path,
):
    model_config = build_model_config(tmp_path)

    version_directory = build_version_directory(
        model_config=model_config,
        version=ACTIVE_VERSION,
    )

    version_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Intentionally do NOT create best.pt.

    write_current_model(
        model_config=model_config,
        version_directory=version_directory,
    )

    with pytest.raises(
        RuntimeError,
        match="current model directory is missing or invalid",
    ):
        read_current_model(
            model_config
        )