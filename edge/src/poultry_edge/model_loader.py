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

    The object identifies the registered model, its resolved version
    and alias, the local directory containing the model artifacts,
    and the time when the model was synchronized.

    model_path points to the complete directory of the synchronized
    model version, for example:

        /app/models/egg_detector/versions/4

    Attributes
    ----------
    registered_name:
        Name of the model registered in MLflow.

    version:
        Specific MLflow model version active on the edge.

    alias:
        MLflow alias used to resolve the model version.

    model_path:
        Local directory containing the synchronized model artifacts.

    synchronized_at:
        UTC timestamp indicating when the local model metadata was
        created or updated.
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

    Parameters
    ----------
    model_config:
        Model configuration assigned to the edge.

    version:
        MLflow model version.

    Returns
    -------
    Path
        Local directory assigned to the requested model version.

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
    """
    Check whether a local model directory contains valid YOLO weights.

    A model directory is considered valid when the directory exists
    and contains the expected best.pt file directly in its root.

    Parameters
    ----------
    model_directory:
        Local directory containing a synchronized model version.

    Returns
    -------
    bool
        True when the directory contains the expected YOLO weights.
    """

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

    Required fields are validated and normalized before creating the
    object.

    Parameters
    ----------
    data:
        Dictionary loaded from the current.json metadata file.

    Returns
    -------
    LocalModel
        Validated metadata describing the active local model.

    Raises
    ------
    ValueError
        If a required field is missing or empty.
    """

    # current.json must contain all information required to identify
    # and locate the model currently active on the edge.
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

    # Normalize metadata values before validation.
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

    Parameters
    ----------
    model_config:
        Model configuration assigned to the edge.

    Returns
    -------
    LocalModel
        Metadata describing the last valid model stored locally.

    Raises
    ------
    FileNotFoundError
        If current.json does not exist.

    ValueError
        If current.json contains invalid or inconsistent metadata.

    RuntimeError
        If the referenced local model directory is not valid.
    """

    current_file_path = _get_current_file_path(
        model_config
    )

    if not current_file_path.is_file():
        raise FileNotFoundError(
            "Current model metadata not found: "
            f"'{current_file_path}'."
        )

    # Load the metadata describing the model currently active on
    # the edge.
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

    # Ensure that current.json belongs to the registered model
    # configured for this particular edge.
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

    # Reconstruct the expected version directory instead of trusting
    # the path stored in current.json without validation.
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

    # A local fallback can only be used when the expected YOLO
    # weights are physically available.
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
    file replaces current.json only when writing has completed. This
    prevents a partially written metadata file from becoming active.

    Parameters
    ----------
    model_config:
        Model configuration assigned to the edge.

    local_model:
        Metadata describing the model version that must become active.
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

    # Persist enough metadata to identify and recover the active model
    # without requiring an MLflow connection.
    metadata = {
        "registered_name": local_model.registered_name,
        "version": local_model.version,
        "alias": local_model.alias,
        "model_path": str(local_model.model_path),
        "synchronized_at": local_model.synchronized_at,
    }

    try:
        # Write to a temporary file first so current.json is never
        # replaced by partially written metadata.
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

        # Atomically replace the previous active-model metadata.
        temporary_file_path.replace(
            current_file_path
        )

    except Exception:
        # Remove an incomplete temporary file if writing fails.
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
    the expected YOLO weights file.

    Parameters
    ----------
    model_uri:
        MLflow URI identifying the model version to download.

    destination_directory:
        Final local directory assigned to the model version.

    Raises
    ------
    RuntimeError
        If the downloaded model does not contain valid YOLO weights.
    """

    versions_directory = (
        destination_directory.parent
    )

    versions_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Use a temporary directory inside the versions directory so an
    # incomplete download never becomes an active model version.
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
        # Download all artifacts associated with the selected MLflow
        # model version.
        downloaded_path = Path(
            mlflow.artifacts.download_artifacts(
                artifact_uri=model_uri,
                dst_path=str(temporary_root),
            )
        )

        # Validate the downloaded artifacts before moving them to
        # their permanent location.
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
            # Keep an existing valid copy instead of replacing it.
            if _validate_model_directory(
                destination_directory
            ):
                logger.info(
                    "Model version is already valid at '%s'.",
                    destination_directory,
                )
                return

            # Remove an existing invalid directory before installing
            # the newly downloaded version.
            shutil.rmtree(
                destination_directory
            )

        # Move the validated model from the temporary location to its
        # permanent version directory.
        shutil.move(
            str(downloaded_path),
            str(destination_directory),
        )

        # Validate again after the move to ensure that the final local
        # model directory is usable.
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
        # Temporary download files are removed regardless of whether
        # synchronization succeeds or fails.
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

    Parameters
    ----------
    model_config:
        Model configuration assigned to the edge.

    version:
        MLflow model version resolved from the configured alias.

    Returns
    -------
    LocalModel
        Metadata describing the model version and its expected local
        storage location.
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

    1. Configure the MLflow tracking and registry endpoints.
    2. Resolve the version assigned to the configured alias.
    3. Check whether that version is already available locally.
    4. Download the version only when necessary.
    5. Update current.json.
    6. Return the active LocalModel.

    If MLflow is unavailable and local fallback is enabled, the model
    referenced by current.json is returned. This allows inference to
    continue during temporary connectivity problems.

    Parameters
    ----------
    model_config:
        Model configuration assigned to the edge.

    tracking_uri:
        Optional MLflow tracking server URI.

    registry_uri:
        Optional MLflow Model Registry URI.

    allow_local_fallback:
        Whether the last valid local model can be used when
        synchronization with MLflow fails.

    Returns
    -------
    LocalModel
        Metadata describing the model that should be used for
        inference.

    Raises
    ------
    RuntimeError
        If synchronization fails and no valid local fallback is
        available.
    """

    # Configure MLflow endpoints only when explicit values have been
    # provided by the execution environment.
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

        # Resolve the configured alias (for example, "production") to
        # the concrete immutable model version assigned in MLflow.
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

        # Build the metadata and expected local location for the
        # version currently assigned by MLflow.
        local_model = _build_local_model(
            model_config=model_config,
            version=version,
        )

        # Avoid downloading the model again when the selected version
        # is already stored locally and contains valid YOLO weights.
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
            # Build the MLflow model URI for the resolved version.
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

        # Mark the synchronized version as the model currently active
        # on this edge device.
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

        # MLflow synchronization failure does not stop inference when
        # a previously synchronized and valid model is available.
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

    Parameters
    ----------
    local_model:
        Metadata describing the synchronized model version.

    Returns
    -------
    YOLO
        Loaded Ultralytics YOLO model ready for inference.

    Raises
    ------
    RuntimeError
        If the local model directory is invalid or the YOLO weights
        cannot be loaded.
    """

    # Do not attempt to initialize YOLO unless the expected local
    # model structure has already been validated.
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
        # Load the synchronized best.pt weights using Ultralytics.
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