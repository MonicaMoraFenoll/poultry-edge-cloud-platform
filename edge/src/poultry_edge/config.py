from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class FarmConfig:
    """Configuration identifying the farm assigned to the edge."""

    id: str


@dataclass(frozen=True)
class ImagesConfig:
    """Configuration for the input images."""

    root_directory: Path


@dataclass(frozen=True)
class OutputsConfig:
    """Configuration for the inference outputs."""

    root_directory: Path


@dataclass(frozen=True)
class ModelConfig:
    """Configuration for the MLflow model assigned to the edge."""

    registered_name: str
    alias: str
    local_root_directory: Path


@dataclass(frozen=True)
class InferenceConfig:
    """Configuration controlling image inference."""

    supported_extensions: tuple[str, ...]


@dataclass(frozen=True)
class EdgeConfig:
    """Complete configuration assigned to one edge device."""

    farm: FarmConfig
    images: ImagesConfig
    outputs: OutputsConfig
    model: ModelConfig
    inference: InferenceConfig


def _require_mapping(
    data: dict[str, Any],
    key: str,
) -> dict[str, Any]:
    """Return a required YAML section as a dictionary."""

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
    """Return a required non-empty string value."""

    value = data.get(key)

    if not isinstance(value, str):
        raise ValueError(
            f"Configuration field '{field_path}' must be a string."
        )

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
    """Return a required filesystem path."""

    value = _require_string(
        data=data,
        key=key,
        field_path=field_path,
    )

    return Path(value).expanduser()


def _parse_supported_extensions(
    inference: dict[str, Any],
) -> tuple[str, ...]:
    """Validate and normalize the supported image extensions."""

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
    """Load and validate the configuration assigned to one edge."""

    if not config_path.is_file():
        raise FileNotFoundError(
            f"Edge configuration not found: '{config_path}'."
        )

    try:
        with config_path.open(encoding="utf-8") as config_file:
            raw_config = yaml.safe_load(config_file)

    except yaml.YAMLError as error:
        raise ValueError(
            f"Invalid YAML configuration in '{config_path}'."
        ) from error

    if not isinstance(raw_config, dict):
        raise ValueError(
            "The edge configuration must contain a YAML mapping."
        )

    farm = _require_mapping(raw_config, "farm")
    images = _require_mapping(raw_config, "images")
    outputs = _require_mapping(raw_config, "outputs")
    model = _require_mapping(raw_config, "model")
    inference = _require_mapping(raw_config, "inference")

    farm_id = _require_string(
        data=farm,
        key="id",
        field_path="farm.id",
    )

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

    registered_model_name = _require_string(
        data=model,
        key="registered_name",
        field_path="model.registered_name",
    )

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

    supported_extensions = _parse_supported_extensions(
        inference=inference
    )

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
        model=ModelConfig(
            registered_name=registered_model_name,
            alias=model_alias,
            local_root_directory=local_model_root_directory,
        ),
        inference=InferenceConfig(
            supported_extensions=supported_extensions,
        ),
    )