from pathlib import Path

from poultry_edge.upload_discovery import (
    discover_and_register_uploads,
)
from poultry_edge.upload_state import (
    get_pending_uploads,
    initialize_upload_database,
)


def test_discover_and_register_uploads(
    tmp_path: Path,
):
    """Verify that discovered result files are registered with the expected remote paths."""

    output_root = tmp_path / "outputs"

    database_path = (
        tmp_path / "state" / "upload_state.db"
    )

    initialize_upload_database(
        database_path
    )

    result_files = [
        output_root
        / "2026"
        / "08"
        / "01"
        / "egg_prediction.csv",
        output_root
        / "2026"
        / "08"
        / "02"
        / "egg_prediction.csv",
    ]

    for result_file in result_files:
        result_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        result_file.write_text(
            "mock data",
            encoding="utf-8",
        )

    discovered = discover_and_register_uploads(
        output_root=output_root,
        farm_id="farm_01",
        database_path=database_path,
    )

    assert discovered == 2

    pending = get_pending_uploads(
        database_path
    )

    assert len(pending) == 2

    remote_paths = {
        item["remote_path"]
        for item in pending
    }

    assert remote_paths == {
        "farm_01/2026/08/01/egg_prediction.csv",
        "farm_01/2026/08/02/egg_prediction.csv",
    }


def test_discovery_does_not_duplicate_existing_records(
    tmp_path: Path,
):
    """Verify that repeated discovery does not duplicate existing upload records."""

    output_root = tmp_path / "outputs"

    database_path = (
        tmp_path / "state" / "upload_state.db"
    )

    initialize_upload_database(
        database_path
    )

    result_file = (
        output_root
        / "2026"
        / "08"
        / "01"
        / "egg_prediction.csv"
    )

    result_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result_file.write_text(
        "mock data",
        encoding="utf-8",
    )

    # Run discovery twice to verify that registration is idempotent.
    discover_and_register_uploads(
        output_root=output_root,
        farm_id="farm_01",
        database_path=database_path,
    )

    discover_and_register_uploads(
        output_root=output_root,
        farm_id="farm_01",
        database_path=database_path,
    )

    pending = get_pending_uploads(
        database_path
    )

    assert len(pending) == 1


def test_missing_output_directory_returns_zero(
    tmp_path: Path,
):
    """Verify that a missing output directory produces no registered uploads."""

    output_root = tmp_path / "missing_outputs"

    database_path = (
        tmp_path / "state" / "upload_state.db"
    )

    initialize_upload_database(
        database_path
    )

    discovered = discover_and_register_uploads(
        output_root=output_root,
        farm_id="farm_01",
        database_path=database_path,
    )

    assert discovered == 0

    assert get_pending_uploads(
        database_path
    ) == []