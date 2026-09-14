from pathlib import Path

from unittest.mock import MagicMock, patch

from poultry_edge.upload_manager import (
    process_pending_uploads,
)
from poultry_edge.upload_state import (
    get_pending_uploads,
    initialize_upload_database,
    register_pending_upload,
)


def test_process_pending_uploads_continues_after_failure(
    tmp_path: Path,
):
    """Verify that one failed upload does not stop the remaining transfers."""

    database_path = tmp_path / "upload_state.db"

    initialize_upload_database(
        database_path
    )

    files = [
        (
            tmp_path / "file_01.csv",
            "farm_01/2026/08/01/egg_prediction.csv",
        ),
        (
            tmp_path / "file_02.csv",
            "farm_01/2026/08/02/egg_prediction.csv",
        ),
        (
            tmp_path / "file_03.csv",
            "farm_01/2026/08/03/egg_prediction.csv",
        ),
    ]

    # Create the local files and register them as PENDING.
    for local_path, remote_path in files:
        local_path.write_text(
            "mock data",
            encoding="utf-8",
        )

        register_pending_upload(
            database_path=database_path,
            local_path=local_path,
            remote_path=remote_path,
        )

    service_client = MagicMock()

    # Simulate a batch where:
    # - the first upload succeeds,
    # - the second upload fails,
    # - the third upload succeeds.
    with patch(
        "poultry_edge.upload_manager.upload_file_to_adls"
    ) as mock_upload:
        mock_upload.side_effect = [
            None,
            ConnectionError(
                "Azure unavailable"
            ),
            None,
        ]

        successful, failed = (
            process_pending_uploads(
                database_path=database_path,
                service_client=service_client,
                file_system_name="landing",
            )
        )

    assert successful == 2
    assert failed == 1

    # All files must be attempted even if one upload fails.
    assert mock_upload.call_count == 3

    # Only the failed file should remain available for retry.
    pending = get_pending_uploads(
        database_path
    )

    assert len(pending) == 1

    assert pending[0]["local_path"] == str(
        files[1][0]
    )

    assert pending[0]["remote_path"] == (
        files[1][1]
    )

    assert pending[0]["status"] == "FAILED"
    assert pending[0]["attempts"] == 1

    assert (
        "Azure unavailable"
        in pending[0]["last_error"]
    )