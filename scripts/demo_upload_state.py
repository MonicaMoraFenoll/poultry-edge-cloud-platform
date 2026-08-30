from pathlib import Path
import sqlite3

from poultry_edge.upload_state import (
    initialize_upload_database,
    mark_upload_failed,
    mark_upload_successful,
    register_pending_upload,
)


DATABASE_PATH = Path(
    "data/state/upload_state_demo.db"
)

LOCAL_PATH = Path(
    "data/outputs/2026/08/01/egg_prediction.csv"
)

REMOTE_PATH = (
    "farm_01/2026/08/01/egg_prediction.csv"
)


def get_upload_record(
    database_path: Path,
    local_path: Path,
) -> dict:
    with sqlite3.connect(
        database_path
    ) as connection:

        connection.row_factory = sqlite3.Row

        row = connection.execute(
            """
            SELECT
                local_path,
                remote_path,
                status,
                attempts,
                last_attempt_at,
                uploaded_at,
                last_error
            FROM uploads
            WHERE local_path = ?
            """,
            (
                str(local_path),
            ),
        ).fetchone()

    if row is None:
        raise RuntimeError(
            "Upload record not found."
        )

    return dict(row)


def print_record(
    step: str,
) -> None:

    record = get_upload_record(
        database_path=DATABASE_PATH,
        local_path=LOCAL_PATH,
    )

    print()
    print(step)
    print("=" * 80)

    print(
        f"Status:          {record['status']}"
    )

    print(
        f"Attempts:        {record['attempts']}"
    )

    print(
        f"Local path:      {record['local_path']}"
    )

    print(
        f"Remote path:     {record['remote_path']}"
    )

    print(
        f"Last attempt:    {record['last_attempt_at']}"
    )

    print(
        f"Uploaded at:     {record['uploaded_at']}"
    )

    print(
        f"Last error:      {record['last_error']}"
    )


def main() -> None:

    # Reproducible demo.
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    initialize_upload_database(
        DATABASE_PATH
    )

    # --------------------------------------------------------
    # 1. File discovered
    # --------------------------------------------------------

    register_pending_upload(
        database_path=DATABASE_PATH,
        local_path=LOCAL_PATH,
        remote_path=REMOTE_PATH,
    )

    print_record(
        "1. FILE DISCOVERED"
    )

    # --------------------------------------------------------
    # 2. First attempt fails
    # --------------------------------------------------------

    mark_upload_failed(
        database_path=DATABASE_PATH,
        local_path=LOCAL_PATH,
        error_message=(
            "Cloud connection unavailable"
        ),
    )

    print_record(
        "2. FIRST UPLOAD ATTEMPT FAILED"
    )

    # --------------------------------------------------------
    # 3. Connectivity restored
    # --------------------------------------------------------

    mark_upload_successful(
        database_path=DATABASE_PATH,
        local_path=LOCAL_PATH,
    )

    print_record(
        "3. RETRY SUCCESSFUL"
    )

    print()
    print("=" * 80)
    print(
        "Upload state transition completed:"
    )
    print(
        "PENDING -> FAILED -> UPLOADED"
    )


if __name__ == "__main__":
    main()