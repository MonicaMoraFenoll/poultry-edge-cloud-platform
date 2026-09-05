from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import poultry_edge.upload_results as upload_results


def test_parse_args_default_config(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        ["poultry-edge-upload"],
    )

    args = upload_results.parse_args()

    assert args.config == upload_results.DEFAULT_CONFIG_PATH


def test_main_runs_complete_upload_flow(monkeypatch, tmp_path):
    state_db = tmp_path / "uploads.db"
    output_dir = tmp_path / "outputs"

    fake_config = SimpleNamespace(
        farm=SimpleNamespace(
            id="farm_01",
        ),
        outputs=SimpleNamespace(
            root_directory=output_dir,
        ),
        upload=SimpleNamespace(
            state_database=state_db,
        ),
    )

    fake_service_client = object()

    calls = {}

    monkeypatch.setattr(
        upload_results,
        "parse_args",
        lambda: Namespace(
            config=Path("fake_edge.yaml"),
        ),
    )

    monkeypatch.setattr(
        upload_results,
        "load_edge_config",
        lambda path: fake_config,
    )

    def fake_initialize_upload_database(database_path):
        calls["database_path"] = database_path

    monkeypatch.setattr(
        upload_results,
        "initialize_upload_database",
        fake_initialize_upload_database,
    )

    def fake_discover_and_register_uploads(
        output_root,
        farm_id,
        database_path,
    ):
        calls["output_root"] = output_root
        calls["farm_id"] = farm_id
        calls["discovery_database_path"] = database_path
        return 3

    monkeypatch.setattr(
        upload_results,
        "discover_and_register_uploads",
        fake_discover_and_register_uploads,
    )

    def fake_create_datalake_service_client(
        storage_account_name,
    ):
        calls["storage_account_name"] = storage_account_name
        return fake_service_client

    monkeypatch.setattr(
        upload_results,
        "create_datalake_service_client",
        fake_create_datalake_service_client,
    )

    def fake_process_pending_uploads(
        database_path,
        service_client,
        file_system_name,
    ):
        calls["process_database_path"] = database_path
        calls["service_client"] = service_client
        calls["file_system_name"] = file_system_name
        return 3, 0

    monkeypatch.setattr(
        upload_results,
        "process_pending_uploads",
        fake_process_pending_uploads,
    )

    upload_results.main()

    assert calls["database_path"] == state_db
    assert calls["output_root"] == output_dir
    assert calls["farm_id"] == "farm_01"
    assert calls["discovery_database_path"] == state_db

    assert (
        calls["storage_account_name"]
        == upload_results.STORAGE_ACCOUNT_NAME
    )

    assert calls["process_database_path"] == state_db
    assert calls["service_client"] is fake_service_client
    assert (
        calls["file_system_name"]
        == upload_results.FILE_SYSTEM_NAME
    )


def test_main_handles_failed_uploads(monkeypatch, tmp_path):
    state_db = tmp_path / "uploads.db"
    output_dir = tmp_path / "outputs"

    fake_config = SimpleNamespace(
        farm=SimpleNamespace(
            id="farm_02",
        ),
        outputs=SimpleNamespace(
            root_directory=output_dir,
        ),
        upload=SimpleNamespace(
            state_database=state_db,
        ),
    )

    monkeypatch.setattr(
        upload_results,
        "parse_args",
        lambda: Namespace(
            config=Path("fake_edge.yaml"),
        ),
    )

    monkeypatch.setattr(
        upload_results,
        "load_edge_config",
        lambda path: fake_config,
    )

    monkeypatch.setattr(
        upload_results,
        "initialize_upload_database",
        lambda database_path: None,
    )

    monkeypatch.setattr(
        upload_results,
        "discover_and_register_uploads",
        lambda **kwargs: 2,
    )

    monkeypatch.setattr(
        upload_results,
        "create_datalake_service_client",
        lambda **kwargs: object(),
    )

    monkeypatch.setattr(
        upload_results,
        "process_pending_uploads",
        lambda **kwargs: (1, 1),
    )

    upload_results.main()