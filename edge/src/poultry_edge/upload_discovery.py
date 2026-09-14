from __future__ import annotations

from pathlib import Path

from .upload_state import register_pending_upload


RESULT_FILE_NAME = "egg_prediction.csv"


def discover_and_register_uploads(
    output_root: Path,
    farm_id: str,
    database_path: Path,
) -> int:
    """
    Discover local inference result files and register them for upload.

    The output directory is searched recursively for daily inference
    CSV files. For each discovered file, the corresponding remote path
    is built by prefixing the local relative path with the farm
    identifier.

    Expected local structure:

        output_root/YYYY/MM/DD/egg_prediction.csv

    Remote structure:

        farm_id/YYYY/MM/DD/egg_prediction.csv

    Existing records are not duplicated because registration is
    handled by the local upload-state database.

    Parameters
    ----------
    output_root:
        Root directory containing the daily inference output files.

    farm_id:
        Identifier of the farm assigned to the edge. It is used as
        the first component of the remote storage path.

    database_path:
        Path to the local SQLite database used to track upload state.

    Returns
    -------
    int
        Number of result files discovered locally.
    """

    # If the output directory has not been created yet, there are no
    # result files available for registration.
    if not output_root.exists():
        return 0

    # Search recursively because daily results are organized under
    # the YYYY/MM/DD directory hierarchy.
    result_files = sorted(
        output_root.rglob(RESULT_FILE_NAME)
    )

    for local_path in result_files:
        # Preserve the YYYY/MM/DD/file structure relative to the
        # configured output root.
        relative_path = local_path.relative_to(
            output_root
        )

        # Prefix the relative result path with the farm identifier to
        # create the destination path used in cloud storage.
        remote_path = (
            Path(farm_id)
            / relative_path
        ).as_posix()

        # Register the file in the local upload-state database.
        # Existing records are preserved by register_pending_upload().
        register_pending_upload(
            database_path=database_path,
            local_path=local_path,
            remote_path=remote_path,
        )

    return len(result_files)