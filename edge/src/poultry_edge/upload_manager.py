from __future__ import annotations

import logging
from pathlib import Path

from azure.storage.filedatalake import DataLakeServiceClient

from .cloud_uploader import upload_file_to_adls
from .upload_state import (
    get_pending_uploads,
    mark_upload_failed,
    mark_upload_successful,
)


logger = logging.getLogger(__name__)


def process_pending_uploads(
    database_path: Path,
    service_client: DataLakeServiceClient,
    file_system_name: str,
) -> tuple[int, int]:
    """
    Upload all files currently marked as PENDING or FAILED.

    Files are processed independently so that one failed upload does
    not prevent the remaining files from being attempted.

    The upload state stored in the local SQLite database is updated
    after every attempt. Successful files are marked as UPLOADED,
    while failed files remain available for future retries.

    Parameters
    ----------
    database_path:
        Path to the local SQLite database containing upload state.

    service_client:
        Authenticated Azure Data Lake service client.

    file_system_name:
        Name of the ADLS file system where result files are uploaded.

    Returns
    -------
    tuple[int, int]
        Number of successful and failed uploads, respectively.
    """

    # Retrieve both new files waiting to be uploaded and previously
    # failed files that must be retried.
    pending_uploads = get_pending_uploads(
        database_path=database_path,
    )

    logger.info(
        "Found %d pending upload(s).",
        len(pending_uploads),
    )

    successful_uploads = 0
    failed_uploads = 0

    # Process each file independently so a single transfer failure does
    # not interrupt the rest of the upload batch.
    for upload in pending_uploads:
        local_path = Path(
            upload["local_path"]
        )

        remote_path = upload["remote_path"]

        try:
            # Upload the file and validate the remote copy using the
            # checks implemented by upload_file_to_adls().
            upload_file_to_adls(
                service_client=service_client,
                file_system_name=file_system_name,
                local_path=local_path,
                remote_path=remote_path,
                overwrite=True,
            )

        except Exception as error:
            # Preserve the error type and message in SQLite so the
            # failed attempt can be inspected and retried later.
            error_message = (
                f"{type(error).__name__}: {error}"
            )

            mark_upload_failed(
                database_path=database_path,
                local_path=local_path,
                error_message=error_message,
            )

            failed_uploads += 1

            logger.exception(
                "Upload failed for '%s'.",
                local_path,
            )

            # Continue processing the remaining files in the batch.
            continue

        # Update the local state only after the upload has completed
        # successfully.
        mark_upload_successful(
            database_path=database_path,
            local_path=local_path,
        )

        successful_uploads += 1

        logger.info(
            "Upload completed for '%s'.",
            local_path,
        )

    # Log a compact summary of the complete upload batch.
    logger.info(
        "Upload batch finished. "
        "Total=%d, successful=%d, failed=%d.",
        len(pending_uploads),
        successful_uploads,
        failed_uploads,
    )

    return (
        successful_uploads,
        failed_uploads,
    )