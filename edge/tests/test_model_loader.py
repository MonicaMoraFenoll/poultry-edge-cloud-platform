import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from poultry_edge.config import ModelConfig
from poultry_edge.model_loader import (
    LocalModel,
    _download_model_version,
    load_yolo_model,
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


def test_read_current_model_fails_when_current_json_is_missing(
    tmp_path,
):
    model_config = build_model_config(tmp_path)

    with pytest.raises(
        FileNotFoundError,
        match="Current model metadata not found",
    ):
        read_current_model(
            model_config
        )


def test_read_current_model_fails_with_invalid_json(
    tmp_path,
):
    model_config = build_model_config(tmp_path)

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
        "{invalid json",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Invalid JSON",
    ):
        read_current_model(
            model_config
        )


def test_read_current_model_fails_when_json_is_not_object(
    tmp_path,
):
    model_config = build_model_config(tmp_path)

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
        '["model", "version"]',
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="must contain a JSON object",
    ):
        read_current_model(
            model_config
        )


def test_read_current_model_fails_when_required_field_is_missing(
    tmp_path,
):
    model_config = build_model_config(tmp_path)

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
                "model_path": "some/path",
                "synchronized_at": "2026-08-15T08:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="missing fields",
    ):
        read_current_model(
            model_config
        )


def test_read_current_model_fails_when_registered_name_does_not_match(
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

    (
        version_directory
        / "best.pt"
    ).write_text(
        "fake model",
        encoding="utf-8",
    )

    current_file = (
        model_config.local_root_directory
        / model_config.registered_name
        / "current.json"
    )

    current_file.write_text(
        json.dumps(
            {
                "registered_name": "another_model",
                "version": ACTIVE_VERSION,
                "alias": MODEL_ALIAS,
                "model_path": str(version_directory),
                "synchronized_at": "2026-08-15T08:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        read_current_model(
            model_config
        )


def test_read_current_model_fails_when_model_path_does_not_match(
    tmp_path,
):
    model_config = build_model_config(tmp_path)

    wrong_directory = (
        tmp_path
        / "wrong_model_directory"
    )

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
                "model_path": str(wrong_directory),
                "synchronized_at": "2026-08-15T08:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="model path in current.json does not match",
    ):
        read_current_model(
            model_config
        )


def test_download_model_version_success(
    tmp_path,
    monkeypatch,
):
    destination_directory = (
        tmp_path
        / "models"
        / MODEL_NAME
        / "versions"
        / ACTIVE_VERSION
    )

    def fake_download_artifacts(
        artifact_uri,
        dst_path,
    ):
        assert (
            artifact_uri
            == f"models:/{MODEL_NAME}/{ACTIVE_VERSION}"
        )

        downloaded_directory = (
            Path(dst_path)
            / "downloaded_model"
        )

        downloaded_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        (
            downloaded_directory
            / "best.pt"
        ).write_text(
            "fake YOLO weights",
            encoding="utf-8",
        )

        return str(downloaded_directory)

    monkeypatch.setattr(
        "poultry_edge.model_loader.mlflow.artifacts.download_artifacts",
        fake_download_artifacts,
    )

    _download_model_version(
        model_uri=(
            f"models:/{MODEL_NAME}/{ACTIVE_VERSION}"
        ),
        destination_directory=destination_directory,
    )

    assert destination_directory.is_dir()

    assert (
        destination_directory
        / "best.pt"
    ).is_file()


def test_download_model_version_fails_when_best_pt_is_missing(
    tmp_path,
    monkeypatch,
):
    destination_directory = (
        tmp_path
        / "models"
        / MODEL_NAME
        / "versions"
        / ACTIVE_VERSION
    )

    def fake_download_artifacts(
        artifact_uri,
        dst_path,
    ):
        downloaded_directory = (
            Path(dst_path)
            / "downloaded_model"
        )

        downloaded_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        return str(downloaded_directory)

    monkeypatch.setattr(
        "poultry_edge.model_loader.mlflow.artifacts.download_artifacts",
        fake_download_artifacts,
    )

    with pytest.raises(
        RuntimeError,
        match="downloaded model is not valid",
    ):
        _download_model_version(
            model_uri=(
                f"models:/{MODEL_NAME}/{ACTIVE_VERSION}"
            ),
            destination_directory=destination_directory,
        )

    assert not destination_directory.exists()


def test_load_yolo_model_success(
    tmp_path,
    monkeypatch,
):
    model_directory = (
        tmp_path
        / "model"
    )

    model_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    weights_path = (
        model_directory
        / "best.pt"
    )

    weights_path.write_text(
        "fake weights",
        encoding="utf-8",
    )

    local_model = LocalModel(
        registered_name=MODEL_NAME,
        version=ACTIVE_VERSION,
        alias=MODEL_ALIAS,
        model_path=model_directory,
        synchronized_at="2026-08-15T08:00:00+00:00",
    )

    fake_yolo_model = object()

    def fake_yolo(path):
        assert path == str(weights_path)

        return fake_yolo_model

    monkeypatch.setattr(
        "poultry_edge.model_loader.YOLO",
        fake_yolo,
    )

    model = load_yolo_model(
        local_model
    )

    assert model is fake_yolo_model


def test_load_yolo_model_fails_when_model_directory_is_invalid(
    tmp_path,
):
    model_directory = (
        tmp_path
        / "model"
    )

    model_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    local_model = LocalModel(
        registered_name=MODEL_NAME,
        version=ACTIVE_VERSION,
        alias=MODEL_ALIAS,
        model_path=model_directory,
        synchronized_at="2026-08-15T08:00:00+00:00",
    )

    with pytest.raises(
        RuntimeError,
        match="Cannot load an invalid local model directory",
    ):
        load_yolo_model(
            local_model
        )


def test_load_yolo_model_fails_when_yolo_cannot_load_weights(
    tmp_path,
    monkeypatch,
):
    model_directory = (
        tmp_path
        / "model"
    )

    model_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        model_directory
        / "best.pt"
    ).write_text(
        "fake weights",
        encoding="utf-8",
    )

    local_model = LocalModel(
        registered_name=MODEL_NAME,
        version=ACTIVE_VERSION,
        alias=MODEL_ALIAS,
        model_path=model_directory,
        synchronized_at="2026-08-15T08:00:00+00:00",
    )

    def failing_yolo(path):
        raise RuntimeError(
            "Invalid weights"
        )

    monkeypatch.setattr(
        "poultry_edge.model_loader.YOLO",
        failing_yolo,
    )

    with pytest.raises(
        RuntimeError,
        match="Could not load YOLO weights",
    ):
        load_yolo_model(
            local_model
        )