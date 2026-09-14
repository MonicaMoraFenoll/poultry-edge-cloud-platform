from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class FarmConfig:
    """
    Configuration identifying the farm assigned to the edge.

    Attributes
    ----------
    id:
        Unique identifier of the farm where the edge device is deployed.
    """

    id: str


@dataclass(frozen=True)
class ImagesConfig:
    """
    Configuration for the input images.

    Attributes
    ----------
    root_directory:
        Root directory containing the images to be processed.
    """

    root_directory: Path


@dataclass(frozen=True)
class OutputsConfig:
    """
    Configuration for the inference outputs.

    Attributes
    ----------
    root_directory:
        Root directory where inference results are stored.
    """

    root_directory: Path


@dataclass(frozen=True)
class UploadConfig:
    """
    Configuration for the local cloud-upload state.

    Attributes
    ----------
    state_database:
        Path to the local SQLite database used to track the status
        of files waiting to be uploaded to the cloud.
    """

    state_database: Path


@dataclass(frozen=True)
class ModelConfig:
    """
    Configuration for the MLflow model assigned to the edge.

    Attributes
    ----------
    registered_name:
        Name of the model registered in MLflow.

    alias:
        MLflow alias used to identify the model version assigned
        to the edge.

    local_root_directory:
        Root directory where synchronized model artifacts are stored
        locally.
    """

    registered_name: str
    alias: str
    local_root_directory: Path


@dataclass(frozen=True)
class InferenceConfig:
    """
    Configuration controlling image inference.

    Attributes
    ----------
    supported_extensions:
        Image file extensions accepted by the inference pipeline.
    """

    supported_extensions: tuple[str, ...]


@dataclass(frozen=True)
class EdgeConfig:
    """
    Complete configuration assigned to one edge device.

    The configuration groups all settings required by the local
    pipeline, including farm identification, image and output paths,
    upload state, model information, and inference parameters.
    """

    farm: FarmConfig
    images: ImagesConfig
    outputs: OutputsConfig
    upload: UploadConfig
    model: ModelConfig
    inference: InferenceConfig


def _require_mapping(
    data: dict[str, Any],
    key: str,
) -> dict[str, Any]:
    """
    Return a required YAML section as a dictionary.

    Parameters
    ----------
    data:
        Configuration dictionary containing the requested section.

    key:
        Name of the required YAML section.

    Returns
    -------
    dict[str, Any]
        Validated configuration section.

    Raises
    ------
    ValueError
        If the section does not exist or is not a YAML mapping.
    """

    value = data.get(key)

    if not isinstance(value, dict):
        raise ValueError(
            f"Configuration section '{key}' is missing or invalid."
        )

    return value


def _require_string(
    data: dict[str, Any],
    key: str,
    field_path: str,
) -> str:
    """
    Return a required non-empty string value.

    Leading and trailing whitespace is removed before returning the
    validated value.

    Parameters
    ----------
    data:
        Configuration dictionary containing the field.

    key:
        Name of the field to retrieve.

    field_path:
        Full YAML path used to provide descriptive validation errors.

    Returns
    -------
    str
        Normalized non-empty string value.

    Raises
    ------
    ValueError
        If the field is missing, is not a string, or is empty.
    """

    value = data.get(key)

    if not isinstance(value, str):
        raise ValueError(
            f"Configuration field '{field_path}' must be a string."
        )

    # Normalize surrounding whitespace before validating the value.
    normalized_value = value.strip()

    if not normalized_value:
        raise ValueError(
            f"Configuration field '{field_path}' cannot be empty."
        )

    return normalized_value


def _require_path(
    data: dict[str, Any],
    key: str,
    field_path: str,
) -> Path:
    """
    Return a required filesystem path.

    User-home references such as '~' are expanded before the path
    is returned.

    Parameters
    ----------
    data:
        Configuration dictionary containing the path.

    key:
        Name of the path field.

    field_path:
        Full YAML path used to provide descriptive validation errors.

    Returns
    -------
    Path
        Normalized filesystem path.
    """

    value = _require_string(
        data=data,
        key=key,
        field_path=field_path,
    )

    # Expand '~' so paths relative to the current user's home directory
    # can be used in the configuration file.
    return Path(value).expanduser()


def _parse_supported_extensions(
    inference: dict[str, Any],
) -> tuple[str, ...]:
    """
    Validate and normalize the supported image extensions.

    Extensions are converted to lowercase and normalized so that
    every value starts with a dot. Duplicated extensions are removed
    while preserving their original order.

    Parameters
    ----------
    inference:
        YAML inference configuration section.

    Returns
    -------
    tuple[str, ...]
        Normalized supported image extensions.

    Raises
    ------
    ValueError
        If the extensions are missing, invalid, or empty.
    """

    raw_extensions = inference.get("supported_extensions")

    if not isinstance(raw_extensions, list):
        raise ValueError(
            "'inference.supported_extensions' must be a YAML list."
        )

    normalized_extensions: list[str] = []

    for extension in raw_extensions:
        if not isinstance(extension, str):
            raise ValueError(
                "Every value in 'inference.supported_extensions' "
                "must be a string."
            )

        # Normalize extension values to make later comparisons
        # independent of capitalization or whether '.' was provided.
        normalized_extension = extension.strip().lower()

        if not normalized_extension:
            raise ValueError(
                "'inference.supported_extensions' cannot contain "
                "empty values."
            )

        if not normalized_extension.startswith("."):
            normalized_extension = f".{normalized_extension}"

        normalized_extensions.append(normalized_extension)

    if not normalized_extensions:
        raise ValueError(
            "'inference.supported_extensions' cannot be empty."
        )

    # Remove duplicated extensions while preserving their original order.
    return tuple(dict.fromkeys(normalized_extensions))


def load_edge_config(config_path: Path) -> EdgeConfig:
    """
    Load and validate the configuration assigned to one edge.

    The YAML file is parsed, all required sections and fields are
    validated, and the resulting values are converted into immutable
    configuration objects used by the rest of the application.

    Parameters
    ----------
    config_path:
        Path to the YAML configuration file assigned to the edge.

    Returns
    -------
    EdgeConfig
        Fully validated edge configuration.

    Raises
    ------
    FileNotFoundError
        If the configuration file does not exist.

    ValueError
        If the YAML syntax or any required configuration value is
        invalid.
    """

    # Fail immediately if the configuration assigned to the device
    # cannot be found.
    if not config_path.is_file():
        raise FileNotFoundError(
            f"Edge configuration not found: '{config_path}'."
        )

    # Parse the YAML file using safe_load to avoid constructing
    # arbitrary Python objects from configuration content.
    try:
        with config_path.open(encoding="utf-8") as config_file:
            raw_config = yaml.safe_load(config_file)

    except yaml.YAMLError as error:
        raise ValueError(
            f"Invalid YAML configuration in '{config_path}'."
        ) from error

    # The root of the configuration must be a YAML mapping.
    if not isinstance(raw_config, dict):
        raise ValueError(
            "The edge configuration must contain a YAML mapping."
        )

    # Retrieve and validate the required top-level sections.
    farm = _require_mapping(raw_config, "farm")
    images = _require_mapping(raw_config, "images")
    outputs = _require_mapping(raw_config, "outputs")
    model = _require_mapping(raw_config, "model")
    inference = _require_mapping(raw_config, "inference")
    upload = _require_mapping(raw_config, "upload")

    # Farm identification.
    farm_id = _require_string(
        data=farm,
        key="id",
        field_path="farm.id",
    )

    # Local directories used by the inference pipeline.
    images_root_directory = _require_path(
        data=images,
        key="root_directory",
        field_path="images.root_directory",
    )

    outputs_root_directory = _require_path(
        data=outputs,
        key="root_directory",
        field_path="outputs.root_directory",
    )

    # SQLite database used to persist cloud-upload state.
    upload_state_database = _require_path(
        data=upload,
        key="state_database",
        field_path="upload.state_database",
    )

    # MLflow model assigned to this edge device.
    registered_model_name = _require_string(
        data=model,
        key="registered_name",
        field_path="model.registered_name",
    )

    # Use the production alias when no explicit alias is configured.
    raw_alias = model.get("alias", "production")

    if not isinstance(raw_alias, str) or not raw_alias.strip():
        raise ValueError(
            "Configuration field 'model.alias' must be a "
            "non-empty string."
        )

    model_alias = raw_alias.strip()

    local_model_root_directory = _require_path(
        data=model,
        key="local_root_directory",
        field_path="model.local_root_directory",
    )

    # Normalize the image extensions accepted by the discovery process.
    supported_extensions = _parse_supported_extensions(
        inference=inference
    )

    # Convert the validated YAML values into immutable configuration
    # objects consumed by the rest of the application.
    return EdgeConfig(
        farm=FarmConfig(
            id=farm_id,
        ),
        images=ImagesConfig(
            root_directory=images_root_directory,
        ),
        outputs=OutputsConfig(
            root_directory=outputs_root_directory,
        ),
        upload=UploadConfig(
            state_database=upload_state_database,
        ),
        model=ModelConfig(
            registered_name=registered_model_name,
            alias=model_alias,
            local_root_directory=local_model_root_directory,
        ),
        inference=InferenceConfig(
            supported_extensions=supported_extensions,
        ),
    )