from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


STATUS_PENDING = "PENDING"
STATUS_FAILED = "FAILED"
STATUS_UPLOADED = "UPLOADED"


def initialize_upload_database(
    database_path: Path,
) -> None:
    """
    Create the local upload-state database if it does not exist.
    """

    database_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with sqlite3.connect(database_path) as connection:
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
    Register a local file as pending.

    Existing records are preserved.
    """

    with sqlite3.connect(database_path) as connection:
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

    Both PENDING and FAILED records are retried.
    """

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row

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