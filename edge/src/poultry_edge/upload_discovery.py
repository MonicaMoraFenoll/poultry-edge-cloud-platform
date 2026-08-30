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
    Discover local inference result files and register them
    for upload.

    Expected local structure:
        output_root/YYYY/MM/DD/egg_prediction.csv

    Remote structure:
        farm_id/YYYY/MM/DD/egg_prediction.csv

    Existing records are not duplicated.

    Returns
    -------
    int
        Number of result files discovered.
    """

    if not output_root.exists():
        return 0

    result_files = sorted(
        output_root.rglob(RESULT_FILE_NAME)
    )

    for local_path in result_files:
        relative_path = local_path.relative_to(
            output_root
        )

        remote_path = (
            Path(farm_id)
            / relative_path
        ).as_posix()

        register_pending_upload(
            database_path=database_path,
            local_path=local_path,
            remote_path=remote_path,
        )

    return len(result_files)