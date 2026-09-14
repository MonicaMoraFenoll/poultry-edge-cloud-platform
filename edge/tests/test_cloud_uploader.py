from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from poultry_edge.cloud_uploader import (
    upload_file_to_adls,
)


def test_upload_file_to_adls_success(
    tmp_path,
):
    """Verify that a valid local file is uploaded successfully."""

    local_path = (
        tmp_path / "egg_prediction.csv"
    )

    local_path.write_bytes(
        b"mock csv content"
    )

    local_size = local_path.stat().st_size

    # Mock the remote file metadata so its size matches the local file.
    file_client = MagicMock()

    file_client.get_file_properties.return_value = (
        SimpleNamespace(
            size=local_size,
        )
    )

    file_system_client = MagicMock()

    file_system_client.get_file_client.return_value = (
        file_client
    )

    service_client = MagicMock()

    service_client.get_file_system_client.return_value = (
        file_system_client
    )

    remote_path = (
        "farm_01/2026/08/01/"
        "egg_prediction.csv"
    )

    upload_file_to_adls(
        service_client=service_client,
        file_system_name="landing",
        local_path=local_path,
        remote_path=remote_path,
    )

    service_client.get_file_system_client.assert_called_once_with(
        "landing"
    )

    file_system_client.get_file_client.assert_called_once_with(
        remote_path
    )

    file_client.upload_data.assert_called_once()

    file_client.get_file_properties.assert_called_once()


def test_upload_file_to_adls_fails_when_local_file_does_not_exist(
    tmp_path,
):
    """Verify that a missing local file raises FileNotFoundError."""

    local_path = (
        tmp_path / "missing.csv"
    )

    service_client = MagicMock()

    with pytest.raises(
        FileNotFoundError,
        match="Local file not found",
    ):
        upload_file_to_adls(
            service_client=service_client,
            file_system_name="landing",
            local_path=local_path,
            remote_path=(
                "farm_01/2026/08/01/"
                "egg_prediction.csv"
            ),
        )

    # No Azure operation should be attempted when the source file
    # does not exist locally.
    service_client.get_file_system_client.assert_not_called()


def test_upload_file_to_adls_fails_when_remote_size_is_different(
    tmp_path,
):
    """Verify that a remote size mismatch is treated as an upload failure."""

    local_path = (
        tmp_path / "egg_prediction.csv"
    )

    local_path.write_bytes(
        b"mock csv content"
    )

    local_size = local_path.stat().st_size

    file_client = MagicMock()

    # Simulate an incorrect remote file size after the upload.
    file_client.get_file_properties.return_value = (
        SimpleNamespace(
            size=local_size + 100,
        )
    )

    file_system_client = MagicMock()

    file_system_client.get_file_client.return_value = (
        file_client
    )

    service_client = MagicMock()

    service_client.get_file_system_client.return_value = (
        file_system_client
    )

    with pytest.raises(
        RuntimeError,
        match="Uploaded file size does not match",
    ):
        upload_file_to_adls(
            service_client=service_client,
            file_system_name="landing",
            local_path=local_path,
            remote_path=(
                "farm_01/2026/08/01/"
                "egg_prediction.csv"
            ),
        )


def test_upload_file_to_adls_passes_overwrite_false(
    tmp_path,
):
    """Verify that overwrite=False is forwarded to the Azure client."""

    local_path = (
        tmp_path / "egg_prediction.csv"
    )

    local_path.write_bytes(
        b"mock csv content"
    )

    file_client = MagicMock()

    file_client.get_file_properties.return_value = (
        SimpleNamespace(
            size=local_path.stat().st_size,
        )
    )

    file_system_client = MagicMock()

    file_system_client.get_file_client.return_value = (
        file_client
    )

    service_client = MagicMock()

    service_client.get_file_system_client.return_value = (
        file_system_client
    )

    upload_file_to_adls(
        service_client=service_client,
        file_system_name="landing",
        local_path=local_path,
        remote_path=(
            "farm_01/2026/08/01/"
            "egg_prediction.csv"
        ),
        overwrite=False,
    )

    # Inspect the arguments forwarded to the mocked Azure upload call.
    _, kwargs = (
        file_client.upload_data.call_args
    )

    assert kwargs["overwrite"] is False