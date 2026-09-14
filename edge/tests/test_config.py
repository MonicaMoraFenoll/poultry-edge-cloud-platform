from pathlib import Path

import pytest

from poultry_edge.config import load_edge_config


def write_config(
    tmp_path: Path,
    content: str,
) -> Path:
    """
    Write a temporary Edge YAML configuration file for testing.

    Parameters
    ----------
    tmp_path:
        Temporary directory provided by pytest.

    content:
        YAML content to write into the configuration file.

    Returns
    -------
    Path
        Path of the generated temporary configuration file.
    """

    config_path = tmp_path / "farm_01.yml"

    config_path.write_text(
        content,
        encoding="utf-8",
    )

    return config_path


def test_load_valid_edge_config(
    tmp_path,
):
    """Verify that a valid YAML configuration is loaded correctly."""

    config_path = write_config(
        tmp_path,
        """
farm:
  id: farm_01

images:
  root_directory: /app/data/images

outputs:
  root_directory: /app/data/outputs

upload:
  state_database: /app/data/state/upload_state.db

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

    config = load_edge_config(
        config_path
    )

    assert config.farm.id == "farm_01"

    assert config.images.root_directory == Path(
        "/app/data/images"
    )

    assert config.outputs.root_directory == Path(
        "/app/data/outputs"
    )

    assert config.upload.state_database == Path(
        "/app/data/state/upload_state.db"
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
    """Verify that image extensions are normalized and deduplicated."""

    config_path = write_config(
        tmp_path,
        """
farm:
  id: farm_01

images:
  root_directory: /app/data/images

outputs:
  root_directory: /app/data/outputs

upload:
  state_database: /app/data/state/upload_state.db

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

    config = load_edge_config(
        config_path
    )

    assert config.inference.supported_extensions == (
        ".jpg",
        ".jpeg",
        ".png",
    )


def test_model_alias_defaults_to_production(
    tmp_path,
):
    """Verify that the model alias defaults to 'production'."""

    config_path = write_config(
        tmp_path,
        """
farm:
  id: farm_01

images:
  root_directory: /app/data/images

outputs:
  root_directory: /app/data/outputs

upload:
  state_database: /app/data/state/upload_state.db

model:
  registered_name: egg_counter_farm_01
  local_root_directory: /app/models

inference:
  supported_extensions:
    - .jpg
""",
    )

    config = load_edge_config(
        config_path
    )

    assert config.model.alias == "production"


def test_missing_config_file_raises_error(
    tmp_path,
):
    """Verify that a missing configuration file raises FileNotFoundError."""

    config_path = (
        tmp_path
        / "missing.yml"
    )

    with pytest.raises(
        FileNotFoundError,
        match="Edge configuration not found",
    ):
        load_edge_config(
            config_path
        )


def test_missing_required_section_raises_error(
    tmp_path,
):
    """Verify that a missing required configuration section raises an error."""

    config_path = write_config(
        tmp_path,
        """
farm:
  id: farm_01

images:
  root_directory: /app/data/images

outputs:
  root_directory: /app/data/outputs

upload:
  state_database: /app/data/state/upload_state.db

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
        load_edge_config(
            config_path
        )


def test_empty_supported_extensions_raises_error(
    tmp_path,
):
    """Verify that an empty supported-extensions list is rejected."""

    config_path = write_config(
        tmp_path,
        """
farm:
  id: farm_01

images:
  root_directory: /app/data/images

outputs:
  root_directory: /app/data/outputs

upload:
  state_database: /app/data/state/upload_state.db

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
        load_edge_config(
            config_path
        )


def test_missing_upload_section_raises_error(
    tmp_path,
):
    """Verify that the upload configuration section is required."""

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
""",
    )

    with pytest.raises(
        ValueError,
        match=(
            "Configuration section 'upload' "
            "is missing or invalid"
        ),
    ):
        load_edge_config(
            config_path
        )


def test_empty_upload_state_database_raises_error(
    tmp_path,
):
    """Verify that upload.state_database cannot be empty."""

    config_path = write_config(
        tmp_path,
        """
farm:
  id: farm_01

images:
  root_directory: /app/data/images

outputs:
  root_directory: /app/data/outputs

upload:
  state_database: ""

model:
  registered_name: egg_counter_farm_01
  alias: production
  local_root_directory: /app/models

inference:
  supported_extensions:
    - .jpg
""",
    )

    with pytest.raises(
        ValueError,
        match=(
            "Configuration field "
            "'upload.state_database' "
            "cannot be empty"
        ),
    ):
        load_edge_config(
            config_path
        )