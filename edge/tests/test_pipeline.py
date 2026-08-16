from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from poultry_edge.pipeline import run_daily_pipeline


def make_config(tmp_path):
    return SimpleNamespace(
        farm=SimpleNamespace(
            id="farm_01",
        ),
        images=SimpleNamespace(
            root_directory=tmp_path / "images",
        ),
        inference=SimpleNamespace(
            supported_extensions=(".jpg", ".png"),
        ),
        model=SimpleNamespace(),
        outputs=SimpleNamespace(
            root_directory=tmp_path / "outputs",
        ),
    )


def make_local_model(tmp_path):
    return SimpleNamespace(
        registered_name="egg_detector",
        version="3",
        alias="production",
        model_path=tmp_path / "models" / "best.pt",
        synchronized_at="2026-08-03T09:00:00+00:00",
    )


def make_result(
    egg_count=2,
    inference_status="SUCCESS",
):
    return SimpleNamespace(
        egg_count=egg_count,
        inference_status=inference_status,
    )


def test_pipeline_returns_none_when_no_images(
    tmp_path,
    monkeypatch,
):
    config = make_config(tmp_path)

    synchronize_model = MagicMock()
    load_yolo_model = MagicMock()
    run_daily_inference = MagicMock()
    write_inference_results = MagicMock()

    monkeypatch.setattr(
        "poultry_edge.pipeline.find_daily_images",
        lambda **kwargs: [],
    )

    monkeypatch.setattr(
        "poultry_edge.pipeline.synchronize_model",
        synchronize_model,
    )

    monkeypatch.setattr(
        "poultry_edge.pipeline.load_yolo_model",
        load_yolo_model,
    )

    monkeypatch.setattr(
        "poultry_edge.pipeline.run_daily_inference",
        run_daily_inference,
    )

    monkeypatch.setattr(
        "poultry_edge.pipeline.write_inference_results",
        write_inference_results,
    )

    result = run_daily_pipeline(
        config=config,
        processing_date=date(2026, 8, 3),
    )

    assert result is None

    synchronize_model.assert_not_called()
    load_yolo_model.assert_not_called()
    run_daily_inference.assert_not_called()
    write_inference_results.assert_not_called()


def test_pipeline_runs_complete_workflow(
    tmp_path,
    monkeypatch,
):
    config = make_config(tmp_path)

    processing_date = date(2026, 8, 3)

    image_paths = [
        tmp_path
        / "images"
        / "house_01"
        / "2026"
        / "08"
        / "03"
        / "cage_001.jpg",
        tmp_path
        / "images"
        / "house_01"
        / "2026"
        / "08"
        / "03"
        / "cage_002.jpg",
    ]

    local_model = make_local_model(tmp_path)

    model = MagicMock()

    results = [
        make_result(
            egg_count=2,
            inference_status="SUCCESS",
        ),
        make_result(
            egg_count=1,
            inference_status="SUCCESS",
        ),
    ]

    expected_output = (
        tmp_path
        / "outputs"
        / "2026"
        / "08"
        / "03"
        / "egg_prediction.csv"
    )

    find_daily_images = MagicMock(
        return_value=image_paths,
    )

    synchronize_model = MagicMock(
        return_value=local_model,
    )

    load_yolo_model = MagicMock(
        return_value=model,
    )

    run_daily_inference = MagicMock(
        return_value=results,
    )

    write_inference_results = MagicMock(
        return_value=expected_output,
    )

    monkeypatch.setattr(
        "poultry_edge.pipeline.find_daily_images",
        find_daily_images,
    )

    monkeypatch.setattr(
        "poultry_edge.pipeline.synchronize_model",
        synchronize_model,
    )

    monkeypatch.setattr(
        "poultry_edge.pipeline.load_yolo_model",
        load_yolo_model,
    )

    monkeypatch.setattr(
        "poultry_edge.pipeline.run_daily_inference",
        run_daily_inference,
    )

    monkeypatch.setattr(
        "poultry_edge.pipeline.write_inference_results",
        write_inference_results,
    )

    output_file = run_daily_pipeline(
        config=config,
        processing_date=processing_date,
        tracking_uri="http://mlflow:5000",
        registry_uri="http://mlflow:5000",
        overwrite=True,
    )

    assert output_file == expected_output

    find_daily_images.assert_called_once_with(
        images_root=config.images.root_directory,
        processing_date=processing_date,
        supported_extensions=config.inference.supported_extensions,
    )

    synchronize_model.assert_called_once_with(
        model_config=config.model,
        tracking_uri="http://mlflow:5000",
        registry_uri="http://mlflow:5000",
        allow_local_fallback=True,
    )

    load_yolo_model.assert_called_once_with(
        local_model=local_model,
    )

    run_daily_inference.assert_called_once_with(
        config=config,
        model=model,
        local_model=local_model,
        processing_date=processing_date,
        image_paths=image_paths,
    )

    write_inference_results.assert_called_once_with(
        results=results,
        outputs_root_directory=config.outputs.root_directory,
        farm_id="farm_01",
        processing_date=processing_date,
        overwrite=True,
    )


def test_pipeline_returns_none_when_writer_returns_none(
    tmp_path,
    monkeypatch,
):
    config = make_config(tmp_path)

    processing_date = date(2026, 8, 3)

    image_paths = [
        tmp_path
        / "images"
        / "house_01"
        / "2026"
        / "08"
        / "03"
        / "cage_001.jpg",
    ]

    local_model = make_local_model(tmp_path)

    model = MagicMock()

    monkeypatch.setattr(
        "poultry_edge.pipeline.find_daily_images",
        MagicMock(return_value=image_paths),
    )

    monkeypatch.setattr(
        "poultry_edge.pipeline.synchronize_model",
        MagicMock(return_value=local_model),
    )

    monkeypatch.setattr(
        "poultry_edge.pipeline.load_yolo_model",
        MagicMock(return_value=model),
    )

    monkeypatch.setattr(
        "poultry_edge.pipeline.run_daily_inference",
        MagicMock(return_value=[]),
    )

    monkeypatch.setattr(
        "poultry_edge.pipeline.write_inference_results",
        MagicMock(return_value=None),
    )

    output_file = run_daily_pipeline(
        config=config,
        processing_date=processing_date,
    )

    assert output_file is None


def test_pipeline_passes_overwrite_false(
    tmp_path,
    monkeypatch,
):
    config = make_config(tmp_path)

    processing_date = date(2026, 8, 3)

    image_paths = [
        tmp_path / "image.jpg",
    ]

    local_model = make_local_model(tmp_path)

    model = MagicMock()

    results = [
        make_result(),
    ]

    expected_output = tmp_path / "egg_prediction.csv"

    monkeypatch.setattr(
        "poultry_edge.pipeline.find_daily_images",
        MagicMock(return_value=image_paths),
    )

    monkeypatch.setattr(
        "poultry_edge.pipeline.synchronize_model",
        MagicMock(return_value=local_model),
    )

    monkeypatch.setattr(
        "poultry_edge.pipeline.load_yolo_model",
        MagicMock(return_value=model),
    )

    monkeypatch.setattr(
        "poultry_edge.pipeline.run_daily_inference",
        MagicMock(return_value=results),
    )

    write_results_mock = MagicMock(
        return_value=expected_output,
    )

    monkeypatch.setattr(
        "poultry_edge.pipeline.write_inference_results",
        write_results_mock,
    )

    output_file = run_daily_pipeline(
        config=config,
        processing_date=processing_date,
        overwrite=False,
    )

    assert output_file == expected_output

    write_results_mock.assert_called_once_with(
        results=results,
        outputs_root_directory=config.outputs.root_directory,
        farm_id=config.farm.id,
        processing_date=processing_date,
        overwrite=False,
    )