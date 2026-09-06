from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from azure.identity import AzureCliCredential
from azure.storage.filedatalake import DataLakeServiceClient


# ============================================================
# CONFIGURATION
# ============================================================

STORAGE_ACCOUNT_NAME = "mastermmf001sta"
FILE_SYSTEM_NAME = "landing"

OUTPUT_ROOT = Path("data") / "outputs"

STATE_DIR = Path("data") / "state"
DATABASE_PATH = STATE_DIR / "uploads.db"


# ============================================================
# DATABASE
# ============================================================

def initialize_database() -> None:
    """
    Create the local SQLite database used to track file transfers.
    """

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS uploads (
                local_path TEXT PRIMARY KEY,
                remote_path TEXT NOT NULL,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_attempt_at TEXT,
                uploaded_at TEXT,
                last_error TEXT
            )
            """
        )

        connection.commit()


def register_file(
    local_path: Path,
    remote_path: str,
) -> None:
    """
    Register a file as PENDING if it has not been registered before.
    """

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO uploads (
                local_path,
                remote_path,
                status,
                attempts
            )
            VALUES (?, ?, 'PENDING', 0)
            """,
            (
                str(local_path.resolve()),
                remote_path,
            ),
        )

        connection.commit()


def get_files_to_upload() -> list[tuple[str, str]]:
    """
    Return files that are pending or previously failed.
    """

    with sqlite3.connect(DATABASE_PATH) as connection:
        cursor = connection.execute(
            """
            SELECT
                local_path,
                remote_path
            FROM uploads
            WHERE status IN ('PENDING', 'FAILED')
            ORDER BY local_path
            """
        )

        return cursor.fetchall()


def mark_upload_success(
    local_path: Path,
) -> None:
    """
    Mark a file as successfully uploaded.
    """

    timestamp = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            """
            UPDATE uploads
            SET
                status = 'UPLOADED',
                attempts = attempts + 1,
                last_attempt_at = ?,
                uploaded_at = ?,
                last_error = NULL
            WHERE local_path = ?
            """,
            (
                timestamp,
                timestamp,
                str(local_path.resolve()),
            ),
        )

        connection.commit()


def mark_upload_failed(
    local_path: Path,
    error: str,
) -> None:
    """
    Mark a file as failed so that it can be retried later.
    """

    timestamp = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            """
            UPDATE uploads
            SET
                status = 'FAILED',
                attempts = attempts + 1,
                last_attempt_at = ?,
                last_error = ?
            WHERE local_path = ?
            """,
            (
                timestamp,
                error,
                str(local_path.resolve()),
            ),
        )

        connection.commit()


# ============================================================
# FILE DISCOVERY
# ============================================================

def discover_output_files() -> list[Path]:
    """
    Find all simulated Edge output CSV files.
    """

    return sorted(
        OUTPUT_ROOT.rglob("egg_prediction.csv")
    )


def build_remote_path(
    local_path: Path,
) -> str:
    """
    Preserve the Edge directory structure in ADLS.

    Example:

    data/outputs/farm_01/2026/08/01/egg_prediction.csv

    becomes:

    farm_01/2026/08/01/egg_prediction.csv
    """

    relative_path = local_path.relative_to(
        OUTPUT_ROOT
    )

    return relative_path.as_posix()


# ============================================================
# AZURE
# ============================================================

def create_service_client() -> DataLakeServiceClient:
    """
    Authenticate using the current Azure CLI session.
    """

    credential = AzureCliCredential()

    return DataLakeServiceClient(
        account_url=(
            f"https://{STORAGE_ACCOUNT_NAME}"
            ".dfs.core.windows.net"
        ),
        credential=credential,
    )


def upload_file(
    service_client: DataLakeServiceClient,
    local_path: Path,
    remote_path: str,
) -> None:
    """
    Upload one file and verify that the remote size matches
    the local file size.
    """

    if not local_path.is_file():
        raise FileNotFoundError(
            f"Local file not found: {local_path}"
        )

    local_size = local_path.stat().st_size

    file_system_client = (
        service_client.get_file_system_client(
            FILE_SYSTEM_NAME
        )
    )

    file_client = (
        file_system_client.get_file_client(
            remote_path
        )
    )

    with local_path.open("rb") as local_file:
        file_client.upload_data(
            local_file,
            overwrite=True,
        )

    remote_properties = (
        file_client.get_file_properties()
    )

    remote_size = remote_properties.size

    if remote_size != local_size:
        raise RuntimeError(
            "Uploaded file size does not match local file. "
            f"Local size={local_size}, "
            f"remote size={remote_size}."
        )


# ============================================================
# SUMMARY
# ============================================================

def print_summary() -> None:
    """
    Print transfer statistics stored in SQLite.
    """

    with sqlite3.connect(DATABASE_PATH) as connection:

        total = connection.execute(
            """
            SELECT COUNT(*)
            FROM uploads
            """
        ).fetchone()[0]

        uploaded = connection.execute(
            """
            SELECT COUNT(*)
            FROM uploads
            WHERE status = 'UPLOADED'
            """
        ).fetchone()[0]

        failed = connection.execute(
            """
            SELECT COUNT(*)
            FROM uploads
            WHERE status = 'FAILED'
            """
        ).fetchone()[0]

        pending = connection.execute(
            """
            SELECT COUNT(*)
            FROM uploads
            WHERE status = 'PENDING'
            """
        ).fetchone()[0]

    success_rate = (
        uploaded / total * 100
        if total > 0
        else 0
    )

    print()
    print("========================================")
    print("TRANSFER SUMMARY")
    print("========================================")
    print(f"Total files:       {total}")
    print(f"Uploaded:          {uploaded}")
    print(f"Failed:            {failed}")
    print(f"Pending:           {pending}")
    print(f"Success rate:      {success_rate:.2f} %")
    print("========================================")


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    # --------------------------------------------------------
    # Initialize transfer state
    # --------------------------------------------------------

    initialize_database()

    # --------------------------------------------------------
    # Discover simulated Edge outputs
    # --------------------------------------------------------

    output_files = discover_output_files()

    if not output_files:
        raise FileNotFoundError(
            f"No output files found in '{OUTPUT_ROOT.resolve()}'."
        )

    print(
        f"Found {len(output_files)} output files."
    )

    # --------------------------------------------------------
    # Register files
    # --------------------------------------------------------

    for local_path in output_files:

        remote_path = build_remote_path(
            local_path
        )

        register_file(
            local_path=local_path,
            remote_path=remote_path,
        )

    # --------------------------------------------------------
    # Get pending / failed files
    # --------------------------------------------------------

    files_to_upload = get_files_to_upload()

    print(
        f"Files to upload: {len(files_to_upload)}"
    )

    if not files_to_upload:
        print("No files require upload.")
        print_summary()
        return

    # --------------------------------------------------------
    # Connect to Azure
    # --------------------------------------------------------

    service_client = create_service_client()

    # --------------------------------------------------------
    # Upload
    # --------------------------------------------------------

    for local_path_str, remote_path in files_to_upload:

        local_path = Path(local_path_str)

        print()
        print(f"Uploading: {local_path}")
        print(f"Remote:    {remote_path}")

        try:

            upload_file(
                service_client=service_client,
                local_path=local_path,
                remote_path=remote_path,
            )

            mark_upload_success(
                local_path
            )

            print("Status: UPLOADED")

        except Exception as exc:

            mark_upload_failed(
                local_path=local_path,
                error=str(exc),
            )

            print("Status: FAILED")
            print(f"Error: {exc}")

    # --------------------------------------------------------
    # Final metrics
    # --------------------------------------------------------

    print_summary()


if __name__ == "__main__":
    main()