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

    Parameters
    ----------
    storage_account_name:
        Name of the Azure Storage account to connect to.

    Returns
    -------
    DataLakeServiceClient
        Authenticated client used to interact with Azure Data Lake
        Storage.
    """

    # DefaultAzureCredential automatically selects an available
    # authentication method depending on the execution environment.
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

    Parameters
    ----------
    service_client:
        Authenticated Azure Data Lake service client.

    file_system_name:
        Name of the destination file system (container) in ADLS.

    local_path:
        Path of the local file to upload.

    remote_path:
        Destination path of the file within the ADLS file system.

    overwrite:
        Whether an existing remote file can be replaced.

    Raises
    ------
    FileNotFoundError
        If the local file does not exist.

    RuntimeError
        If the uploaded file size differs from the local file size.
    """

    # Validate the local file before starting any remote operation.
    if not local_path.is_file():
        raise FileNotFoundError(
            f"Local file not found: '{local_path}'."
        )

    # Store the local size so it can be compared with the uploaded
    # file after the transfer.
    local_size = local_path.stat().st_size

    # Access the configured ADLS file system (container).
    file_system_client = (
        service_client.get_file_system_client(
            file_system_name
        )
    )

    # Create a client pointing to the destination file in ADLS.
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

    # Stream the local file to ADLS in binary mode.
    with local_path.open("rb") as local_file:
        file_client.upload_data(
            local_file,
            overwrite=overwrite,
        )

    # Retrieve the remote metadata after the upload to verify that
    # the transferred file has the expected size.
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