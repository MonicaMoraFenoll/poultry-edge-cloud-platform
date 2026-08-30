from pathlib import Path

from poultry_edge.upload_state import (
    STATUS_FAILED,
    STATUS_PENDING,
    initialize_upload_database,
    get_pending_uploads,
    mark_upload_failed,
    mark_upload_successful,
    register_pending_upload,
)


def test_register_pending_upload(
    tmp_path: Path,
):
    database_path = tmp_path / "upload_state.db"
    local_path = tmp_path / "egg_prediction.csv"
    remote_path = (
        "farm_01/2026/08/01/egg_prediction.csv"
    )

    initialize_upload_database(
        database_path
    )

    register_pending_upload(
        database_path=database_path,
        local_path=local_path,
        remote_path=remote_path,
    )

    pending = get_pending_uploads(
        database_path
    )

    assert len(pending) == 1
    assert pending[0]["local_path"] == str(local_path)
    assert pending[0]["remote_path"] == remote_path
    assert pending[0]["status"] == STATUS_PENDING
    assert pending[0]["attempts"] == 0


def test_failed_upload_is_retried(
    tmp_path: Path,
):
    database_path = tmp_path / "upload_state.db"
    local_path = tmp_path / "egg_prediction.csv"
    remote_path = (
        "farm_01/2026/08/01/egg_prediction.csv"
    )

    initialize_upload_database(
        database_path
    )

    register_pending_upload(
        database_path=database_path,
        local_path=local_path,
        remote_path=remote_path,
    )

    mark_upload_failed(
        database_path=database_path,
        local_path=local_path,
        error_message="Azure unavailable",
    )

    pending = get_pending_uploads(
        database_path
    )

    assert len(pending) == 1
    assert pending[0]["status"] == STATUS_FAILED
    assert pending[0]["attempts"] == 1
    assert pending[0]["last_error"] == "Azure unavailable"
    assert pending[0]["last_attempt_at"] is not None


def test_successful_upload_is_not_pending(
    tmp_path: Path,
):
    database_path = tmp_path / "upload_state.db"
    local_path = tmp_path / "egg_prediction.csv"
    remote_path = (
        "farm_01/2026/08/01/egg_prediction.csv"
    )

    initialize_upload_database(
        database_path
    )

    register_pending_upload(
        database_path=database_path,
        local_path=local_path,
        remote_path=remote_path,
    )

    mark_upload_successful(
        database_path=database_path,
        local_path=local_path,
    )

    pending = get_pending_uploads(
        database_path
    )

    assert pending == []


def test_existing_upload_is_not_registered_twice(
    tmp_path: Path,
):
    database_path = tmp_path / "upload_state.db"
    local_path = tmp_path / "egg_prediction.csv"
    remote_path = (
        "farm_01/2026/08/01/egg_prediction.csv"
    )

    initialize_upload_database(
        database_path
    )

    register_pending_upload(
        database_path=database_path,
        local_path=local_path,
        remote_path=remote_path,
    )

    register_pending_upload(
        database_path=database_path,
        local_path=local_path,
        remote_path=remote_path,
    )

    pending = get_pending_uploads(
        database_path
    )

    assert len(pending) == 1