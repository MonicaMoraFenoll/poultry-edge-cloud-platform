from __future__ import annotations

import json
import logging
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import mlflow
from mlflow import MlflowClient
from ultralytics import YOLO

from .config import ModelConfig


logger = logging.getLogger(__name__)


CURRENT_MODEL_FILE_NAME = "current.json"
YOLO_WEIGHTS_FILE_NAME = "best.pt"


@dataclass(frozen=True)
class LocalModel:
    """
    Metadata describing the model version currently active on the edge.

    model_path points to the complete directory of the synchronized
    model version, for example:

        /data/models/egg_counter/versions/4
    """

    registered_name: str
    version: str
    alias: str
    model_path: Path
    synchronized_at: str


def _get_registered_model_directory(
    model_config: ModelConfig,
) -> Path:
    """
    Return the local directory assigned to one registered model.

    Example:

        /data/models/egg_counter
    """

    return (
        model_config.local_root_directory
        / model_config.registered_name
    )


def _get_versions_directory(
    model_config: ModelConfig,
) -> Path:
    """
    Return the directory containing all locally stored versions.

    Example:

        /data/models/egg_counter/versions
    """

    return (
        _get_registered_model_directory(model_config)
        / "versions"
    )


def _get_version_directory(
    model_config: ModelConfig,
    version: str,
) -> Path:
    """
    Return the local directory assigned to one model version.

    Example:

        /data/models/egg_counter/versions/4
    """

    return (
        _get_versions_directory(model_config)
        / version
    )


def _get_current_file_path(
    model_config: ModelConfig,
) -> Path:
    """
    Return the path of the metadata file describing the active model.

    Example:

        /data/models/egg_counter/current.json
    """

    return (
        _get_registered_model_directory(model_config)
        / CURRENT_MODEL_FILE_NAME
    )


def _get_yolo_weights_path(
    model_directory: Path,
) -> Path:
    """
    Return the expected YOLO weights path.

    Every registered model version must contain best.pt directly
    inside its root directory.
    """

    return model_directory / YOLO_WEIGHTS_FILE_NAME


def _validate_model_directory(
    model_directory: Path,
) -> bool:
    """Check whether a directory contains valid YOLO weights."""

    return (
        model_directory.is_dir()
        and _get_yolo_weights_path(
            model_directory
        ).is_file()
    )


def _local_model_from_dict(
    data: dict[str, Any],
) -> LocalModel:
    """
    Convert current.json contents into a LocalModel instance.

    Required fields are validated before creating the object.
    """

    required_fields = {
        "registered_name",
        "version",
        "alias",
        "model_path",
        "synchronized_at",
    }

    missing_fields = required_fields.difference(data)

    if missing_fields:
        raise ValueError(
            "The current model metadata is missing fields: "
            f"{sorted(missing_fields)}"
        )

    registered_name = str(
        data["registered_name"]
    ).strip()

    version = str(
        data["version"]
    ).strip()

    alias = str(
        data["alias"]
    ).strip()

    model_path_value = str(
        data["model_path"]
    ).strip()

    synchronized_at = str(
        data["synchronized_at"]
    ).strip()

    if not registered_name:
        raise ValueError(
            "'registered_name' cannot be empty in current.json."
        )

    if not version:
        raise ValueError(
            "'version' cannot be empty in current.json."
        )

    if not alias:
        raise ValueError(
            "'alias' cannot be empty in current.json."
        )

    if not model_path_value:
        raise ValueError(
            "'model_path' cannot be empty in current.json."
        )

    if not synchronized_at:
        raise ValueError(
            "'synchronized_at' cannot be empty in current.json."
        )

    return LocalModel(
        registered_name=registered_name,
        version=version,
        alias=alias,
        model_path=Path(model_path_value),
        synchronized_at=synchronized_at,
    )


def read_current_model(
    model_config: ModelConfig,
) -> LocalModel:
    """
    Read current.json and return the active local model.

    This function does not connect to MLflow. It allows the edge to
    continue operating when MLflow is unavailable, provided that a
    valid model version is already stored locally.
    """

    current_file_path = _get_current_file_path(
        model_config
    )

    if not current_file_path.is_file():
        raise FileNotFoundError(
            "Current model metadata not found: "
            f"'{current_file_path}'."
        )

    try:
        with current_file_path.open(
            encoding="utf-8",
        ) as current_file:
            raw_data = json.load(current_file)

    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid JSON in '{current_file_path}'."
        ) from error

    if not isinstance(raw_data, dict):
        raise ValueError(
            f"'{current_file_path}' must contain a JSON object."
        )

    local_model = _local_model_from_dict(raw_data)

    if (
        local_model.registered_name
        != model_config.registered_name
    ):
        raise ValueError(
            "The registered model in current.json does not match "
            "the model configured for this edge. "
            f"Expected '{model_config.registered_name}', "
            f"found '{local_model.registered_name}'."
        )

    expected_model_path = _get_version_directory(
        model_config=model_config,
        version=local_model.version,
    )

    if local_model.model_path != expected_model_path:
        raise ValueError(
            "The model path in current.json does not match the "
            "configured model version. "
            f"Expected '{expected_model_path}', "
            f"found '{local_model.model_path}'."
        )

    if not _validate_model_directory(
        local_model.model_path
    ):
        raise RuntimeError(
            "The current model directory is missing or invalid: "
            f"'{local_model.model_path}'."
        )

    return local_model


def _write_current_model(
    model_config: ModelConfig,
    local_model: LocalModel,
) -> None:
    """
    Write current.json atomically.

    The metadata is first written into a temporary file. The temporary
    file replaces current.json only when writing has completed.
    """

    current_file_path = _get_current_file_path(
        model_config
    )

    temporary_file_path = (
        current_file_path.with_suffix(".json.tmp")
    )

    current_file_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    metadata = {
        "registered_name": local_model.registered_name,
        "version": local_model.version,
        "alias": local_model.alias,
        "model_path": str(local_model.model_path),
        "synchronized_at": local_model.synchronized_at,
    }

    try:
        with temporary_file_path.open(
            mode="w",
            encoding="utf-8",
        ) as temporary_file:
            json.dump(
                metadata,
                temporary_file,
                indent=2,
                ensure_ascii=False,
            )

            temporary_file.flush()

        temporary_file_path.replace(
            current_file_path
        )

    except Exception:
        temporary_file_path.unlink(
            missing_ok=True
        )
        raise

    logger.info(
        "Current model updated in '%s': "
        "model='%s', version='%s'.",
        current_file_path,
        local_model.registered_name,
        local_model.version,
    )


def _download_model_version(
    model_uri: str,
    destination_directory: Path,
) -> None:
    """
    Download one registered model version safely.

    The model is downloaded into a temporary directory first. It is
    moved to its final location only after checking that it contains
    best.pt.
    """

    versions_directory = (
        destination_directory.parent
    )

    versions_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_root = Path(
        tempfile.mkdtemp(
            prefix=f".{destination_directory.name}_",
            dir=versions_directory,
        )
    )

    logger.info(
        "Downloading model '%s' into temporary directory '%s'.",
        model_uri,
        temporary_root,
    )

    try:
        downloaded_path = Path(
            mlflow.artifacts.download_artifacts(
                artifact_uri=model_uri,
                dst_path=str(temporary_root),
            )
        )

        if not _validate_model_directory(
            downloaded_path
        ):
            raise RuntimeError(
                "The downloaded model is not valid for edge "
                "inference. The model directory must contain "
                f"'{YOLO_WEIGHTS_FILE_NAME}' directly in its root. "
                f"Downloaded directory: '{downloaded_path}'."
            )

        if destination_directory.exists():
            if _validate_model_directory(
                destination_directory
            ):
                logger.info(
                    "Model version is already valid at '%s'.",
                    destination_directory,
                )
                return

            shutil.rmtree(
                destination_directory
            )

        shutil.move(
            str(downloaded_path),
            str(destination_directory),
        )

        if not _validate_model_directory(
            destination_directory
        ):
            raise RuntimeError(
                "The model was moved to its final location, "
                "but validation failed: "
                f"'{destination_directory}'."
            )

        logger.info(
            "Model downloaded successfully to '%s'.",
            destination_directory,
        )

    finally:
        shutil.rmtree(
            temporary_root,
            ignore_errors=True,
        )


def _build_local_model(
    model_config: ModelConfig,
    version: str,
) -> LocalModel:
    """
    Build the local metadata for one registered model version.
    """

    return LocalModel(
        registered_name=model_config.registered_name,
        version=version,
        alias=model_config.alias,
        model_path=_get_version_directory(
            model_config=model_config,
            version=version,
        ),
        synchronized_at=datetime.now(
            timezone.utc
        ).isoformat(),
    )


def synchronize_model(
    model_config: ModelConfig,
    tracking_uri: str | None = None,
    registry_uri: str | None = None,
    allow_local_fallback: bool = True,
) -> LocalModel:
    """
    Synchronize the edge model with MLflow Model Registry.

    Workflow:

    1. Resolve the version assigned to the configured alias.
    2. Check whether that version is already available locally.
    3. Download the version only when necessary.
    4. Update current.json.
    5. Return the active LocalModel.

    If MLflow is unavailable and local fallback is enabled, the model
    referenced by current.json is returned.
    """

    if tracking_uri:
        mlflow.set_tracking_uri(
            tracking_uri
        )

    if registry_uri:
        mlflow.set_registry_uri(
            registry_uri
        )

    try:
        client = MlflowClient()

        logger.info(
            "Resolving alias '%s' for registered model '%s'.",
            model_config.alias,
            model_config.registered_name,
        )

        model_version = (
            client.get_model_version_by_alias(
                name=model_config.registered_name,
                alias=model_config.alias,
            )
        )

        version = str(
            model_version.version
        )

        logger.info(
            "Alias '%s' points to version '%s' "
            "of model '%s'.",
            model_config.alias,
            version,
            model_config.registered_name,
        )

        local_model = _build_local_model(
            model_config=model_config,
            version=version,
        )

        if _validate_model_directory(
            local_model.model_path
        ):
            logger.info(
                "Model '%s' version '%s' is already "
                "available locally.",
                local_model.registered_name,
                local_model.version,
            )

        else:
            model_uri = (
                f"models:/"
                f"{model_config.registered_name}/"
                f"{version}"
            )

            _download_model_version(
                model_uri=model_uri,
                destination_directory=(
                    local_model.model_path
                ),
            )

        _write_current_model(
            model_config=model_config,
            local_model=local_model,
        )

        return local_model

    except Exception:
        logger.exception(
            "Could not synchronize model '%s' "
            "using alias '%s'.",
            model_config.registered_name,
            model_config.alias,
        )

        if not allow_local_fallback:
            raise

        logger.warning(
            "Trying to use the last valid model stored locally."
        )

        try:
            local_model = read_current_model(
                model_config
            )

        except Exception as fallback_error:
            raise RuntimeError(
                "The model could not be synchronized with MLflow "
                "and no valid local YOLO model is available."
            ) from fallback_error

        logger.warning(
            "Using local fallback: model='%s', "
            "version='%s', path='%s'.",
            local_model.registered_name,
            local_model.version,
            local_model.model_path,
        )

        return local_model


def load_yolo_model(
    local_model: LocalModel,
) -> YOLO:
    """
    Load the synchronized YOLO weights into memory.

    The model directory must contain best.pt directly in its root.
    """

    if not _validate_model_directory(
        local_model.model_path
    ):
        raise RuntimeError(
            "Cannot load an invalid local model directory: "
            f"'{local_model.model_path}'."
        )

    weights_path = _get_yolo_weights_path(
        local_model.model_path
    )

    logger.info(
        "Loading YOLO model '%s', version='%s', weights='%s'.",
        local_model.registered_name,
        local_model.version,
        weights_path,
    )

    try:
        model = YOLO(
            str(weights_path)
        )

    except Exception as error:
        raise RuntimeError(
            "Could not load YOLO weights from "
            f"'{weights_path}'."
        ) from error

    logger.info(
        "YOLO model loaded successfully. "
        "Model='%s', version='%s'.",
        local_model.registered_name,
        local_model.version,
    )

    return model