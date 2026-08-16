from pathlib import Path

import pytest

from poultry_edge.config import load_edge_config


def write_config(
    tmp_path: Path,
    content: str,
) -> Path:
    config_path = tmp_path / "farm_01.yml"
    config_path.write_text(
        content,
        encoding="utf-8",
    )
    return config_path


def test_load_valid_edge_config(tmp_path):
    config_path = write_config(
        tmp_path,
        """
farm:
  id: farm_01

images:
  root_directory: /app/data/images

outputs:
  root_directory: /app/data/outputs

model:
  registered_name: egg_counter_farm_01
  alias: production
  local_root_directory: /app/models

inference:
  supported_extensions:
    - .jpg
    - .jpeg
    - .png
""",
    )

    config = load_edge_config(config_path)

    assert config.farm.id == "farm_01"

    assert config.images.root_directory == Path(
        "/app/data/images"
    )

    assert config.outputs.root_directory == Path(
        "/app/data/outputs"
    )

    assert (
        config.model.registered_name
        == "egg_counter_farm_01"
    )

    assert config.model.alias == "production"

    assert config.model.local_root_directory == Path(
        "/app/models"
    )

    assert config.inference.supported_extensions == (
        ".jpg",
        ".jpeg",
        ".png",
    )


def test_supported_extensions_are_normalized(
    tmp_path,
):
    config_path = write_config(
        tmp_path,
        """
farm:
  id: farm_01

images:
  root_directory: /app/data/images

outputs:
  root_directory: /app/data/outputs

model:
  registered_name: egg_counter_farm_01
  alias: production
  local_root_directory: /app/models

inference:
  supported_extensions:
    - JPG
    - .jpeg
    - PNG
    - jpg
""",
    )

    config = load_edge_config(config_path)

    assert config.inference.supported_extensions == (
        ".jpg",
        ".jpeg",
        ".png",
    )


def test_model_alias_defaults_to_production(
    tmp_path,
):
    config_path = write_config(
        tmp_path,
        """
farm:
  id: farm_01

images:
  root_directory: /app/data/images

outputs:
  root_directory: /app/data/outputs

model:
  registered_name: egg_counter_farm_01
  local_root_directory: /app/models

inference:
  supported_extensions:
    - .jpg
""",
    )

    config = load_edge_config(config_path)

    assert config.model.alias == "production"


def test_missing_config_file_raises_error(
    tmp_path,
):
    config_path = tmp_path / "missing.yml"

    with pytest.raises(
        FileNotFoundError,
        match="Edge configuration not found",
    ):
        load_edge_config(config_path)


def test_missing_required_section_raises_error(
    tmp_path,
):
    config_path = write_config(
        tmp_path,
        """
farm:
  id: farm_01

images:
  root_directory: /app/data/images

outputs:
  root_directory: /app/data/outputs

model:
  registered_name: egg_counter_farm_01
  local_root_directory: /app/models
""",
    )

    with pytest.raises(
        ValueError,
        match=(
            "Configuration section 'inference' "
            "is missing or invalid"
        ),
    ):
        load_edge_config(config_path)


def test_empty_supported_extensions_raises_error(
    tmp_path,
):
    config_path = write_config(
        tmp_path,
        """
farm:
  id: farm_01

images:
  root_directory: /app/data/images

outputs:
  root_directory: /app/data/outputs

model:
  registered_name: egg_counter_farm_01
  alias: production
  local_root_directory: /app/models

inference:
  supported_extensions: []
""",
    )

    with pytest.raises(
        ValueError,
        match=(
            "'inference.supported_extensions' "
            "cannot be empty"
        ),
    ):
        load_edge_config(config_path)