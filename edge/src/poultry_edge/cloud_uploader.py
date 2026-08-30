from __future__ import annotations

import logging
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.storage.filedatalake import DataLakeServiceClient


logger = logging.getLogger(__name__)


def create_datalake_service_client(
    storage_account_name: str,
) -> DataLakeServiceClient:
    """
    Create an authenticated Azure Data Lake service client.

    In development, DefaultAzureCredential can use the current
    Azure CLI session. In production, the same code can use a
    device-specific technical identity.
    """

    credential = DefaultAzureCredential()

    return DataLakeServiceClient(
        account_url=(
            f"https://{storage_account_name}.dfs.core.windows.net"
        ),
        credential=credential,
    )


def upload_file_to_adls(
    service_client: DataLakeServiceClient,
    file_system_name: str,
    local_path: Path,
    remote_path: str,
    overwrite: bool = True,
) -> None:
    """
    Upload one local file to Azure Data Lake Storage.

    The upload is considered successful only when the remote file
    exists and its size matches the local file size.
    """

    if not local_path.is_file():
        raise FileNotFoundError(
            f"Local file not found: '{local_path}'."
        )

    local_size = local_path.stat().st_size

    file_system_client = (
        service_client.get_file_system_client(
            file_system_name
        )
    )

    file_client = (
        file_system_client.get_file_client(
            remote_path
        )
    )

    logger.info(
        "Uploading '%s' to '%s/%s'.",
        local_path,
        file_system_name,
        remote_path,
    )

    with local_path.open("rb") as local_file:
        file_client.upload_data(
            local_file,
            overwrite=overwrite,
        )

    remote_properties = (
        file_client.get_file_properties()
    )

    remote_size = remote_properties.size

    if remote_size != local_size:
        raise RuntimeError(
            "Uploaded file size does not match the local file. "
            f"Local size={local_size}, "
            f"remote size={remote_size}, "
            f"remote_path='{remote_path}'."
        )

    logger.info(
        "Upload completed successfully. "
        "Remote path='%s', size=%d bytes.",
        remote_path,
        remote_size,
    )