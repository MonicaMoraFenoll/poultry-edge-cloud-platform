from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


# Possible states of a file during the upload lifecycle.
STATUS_PENDING = "PENDING"
STATUS_FAILED = "FAILED"
STATUS_UPLOADED = "UPLOADED"


def initialize_upload_database(
    database_path: Path,
) -> None:
    """
    Create the local upload-state database if it does not exist.

    The database persists the state of every discovered result file,
    allowing upload attempts to survive process restarts or temporary
    connectivity failures.

    Parameters
    ----------
    database_path:
        Path to the SQLite database used to persist upload state.
    """

    # Ensure that the directory containing the SQLite database exists.
    database_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with sqlite3.connect(database_path) as connection:
        # local_path uniquely identifies each result file so the same
        # file cannot be registered more than once.
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


def register_pending_upload(
    database_path: Path,
    local_path: Path,
    remote_path: str,
) -> None:
    """
    Register a local result file as pending upload.

    Existing records are preserved so their current status, previous
    attempts, timestamps, and error information are not overwritten.

    Parameters
    ----------
    database_path:
        Path to the SQLite upload-state database.

    local_path:
        Path of the local result file to register.

    remote_path:
        Destination path assigned to the file in cloud storage.
    """

    with sqlite3.connect(database_path) as connection:
        # INSERT OR IGNORE makes file discovery idempotent. Repeated
        # discovery executions do not reset already registered files.
        connection.execute(
            """
            INSERT OR IGNORE INTO uploads (
                local_path,
                remote_path,
                status
            )
            VALUES (?, ?, ?)
            """,
            (
                str(local_path),
                remote_path,
                STATUS_PENDING,
            ),
        )

        connection.commit()


def mark_upload_failed(
    database_path: Path,
    local_path: Path,
    error_message: str,
) -> None:
    """
    Mark an upload attempt as failed.

    The attempt counter is incremented and the error information is
    preserved so the failure can be inspected and the file retried in
    a later execution.

    Parameters
    ----------
    database_path:
        Path to the SQLite upload-state database.

    local_path:
        Path of the local file whose upload failed.

    error_message:
        Error information associated with the failed upload attempt.
    """

    # Store timestamps in UTC to keep execution records consistent
    # across Edge devices deployed in different locations.
    now = datetime.now(
        timezone.utc
    ).isoformat()

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            UPDATE uploads
            SET
                status = ?,
                attempts = attempts + 1,
                last_attempt_at = ?,
                last_error = ?
            WHERE local_path = ?
            """,
            (
                STATUS_FAILED,
                now,
                error_message,
                str(local_path),
            ),
        )

        connection.commit()


def mark_upload_successful(
    database_path: Path,
    local_path: Path,
) -> None:
    """
    Mark a file as successfully uploaded.

    The attempt counter and timestamps are updated, and any error
    recorded during a previous failed attempt is cleared.

    Parameters
    ----------
    database_path:
        Path to the SQLite upload-state database.

    local_path:
        Path of the local file that was uploaded successfully.
    """

    now = datetime.now(
        timezone.utc
    ).isoformat()

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            UPDATE uploads
            SET
                status = ?,
                attempts = attempts + 1,
                last_attempt_at = ?,
                uploaded_at = ?,
                last_error = NULL
            WHERE local_path = ?
            """,
            (
                STATUS_UPLOADED,
                now,
                now,
                str(local_path),
            ),
        )

        connection.commit()


def get_pending_uploads(
    database_path: Path,
) -> list[dict]:
    """
    Return files that still need to be uploaded.

    Both newly discovered PENDING files and files from previous FAILED
    attempts are returned, allowing temporary upload failures to be
    retried automatically.

    Parameters
    ----------
    database_path:
        Path to the SQLite upload-state database.

    Returns
    -------
    list[dict]
        Upload records whose status is PENDING or FAILED, ordered by
        local file path.
    """

    with sqlite3.connect(database_path) as connection:
        # Return rows with column names so they can be converted
        # directly into dictionaries for the upload manager.
        connection.row_factory = sqlite3.Row

        # UPLOADED records are intentionally excluded because they
        # have already completed the transfer lifecycle successfully.
        rows = connection.execute(
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
            WHERE status IN (?, ?)
            ORDER BY local_path
            """,
            (
                STATUS_PENDING,
                STATUS_FAILED,
            ),
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]