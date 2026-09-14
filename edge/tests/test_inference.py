from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from poultry_edge.inference import run_daily_inference
from poultry_edge.inference import (
    extract_image_identifiers,
    extract_yolo_prediction,
    get_image_size_bytes,
    predict_image,
    run_single_image_inference,
    validate_yolo_model,
)


def test_validate_yolo_model_valid():
    """Verify that a YOLO model containing only the egg class is accepted."""

    model = MagicMock()
    model.names = {0: "egg"}

    validate_yolo_model(model)


def test_validate_yolo_model_invalid_class():
    """Verify that a YOLO model with a non-egg class is rejected."""

    model = MagicMock()
    model.names = {0: "hen"}

    with pytest.raises(
        ValueError,
        match="exactly one class named 'egg'",
    ):
        validate_yolo_model(model)


def test_validate_yolo_model_multiple_classes():
    """Verify that a multi-class YOLO model is rejected."""

    model = MagicMock()
    model.names = {
        0: "egg",
        1: "hen",
    }

    with pytest.raises(ValueError):
        validate_yolo_model(model)


def test_extract_image_identifiers(tmp_path):
    """Verify that house and cage identifiers are extracted from the image path."""

    images_root = tmp_path / "images"

    image_path = (
        images_root
        / "house_01"
        / "2026"
        / "06"
        / "01"
        / "cage_001.jpg"
    )

    image_path.parent.mkdir(parents=True)
    image_path.touch()

    house_id, cage_id = extract_image_identifiers(
        image_path=image_path,
        images_root=images_root,
    )

    assert house_id == "house_01"
    assert cage_id == "cage_001"


def test_extract_image_identifiers_outside_root(tmp_path):
    """Verify that images outside the configured root directory are rejected."""

    images_root = tmp_path / "images"

    image_path = (
        tmp_path
        / "other"
        / "house_01"
        / "2026"
        / "06"
        / "01"
        / "cage_001.jpg"
    )

    with pytest.raises(
        ValueError,
        match="is not inside the images root",
    ):
        extract_image_identifiers(
            image_path=image_path,
            images_root=images_root,
        )


def test_extract_image_identifiers_invalid_structure(tmp_path):
    """Verify that an unexpected image directory structure is rejected."""

    images_root = tmp_path / "images"

    image_path = (
        images_root
        / "house_01"
        / "cage_001.jpg"
    )

    with pytest.raises(
        ValueError,
        match="Unexpected image path structure",
    ):
        extract_image_identifiers(
            image_path=image_path,
            images_root=images_root,
        )


def test_extract_yolo_prediction_with_detections():
    """Verify egg count and mean confidence when detections are available."""

    boxes = MagicMock()

    # Simulate two YOLO detections.
    boxes.__len__.return_value = 2

    confidences = MagicMock()
    confidences.detach.return_value.cpu.return_value.tolist.return_value = [
        0.8,
        0.6,
    ]

    boxes.conf = confidences

    model_output = MagicMock()
    model_output.boxes = boxes

    egg_count, confidence = extract_yolo_prediction(
        model_output,
    )

    assert egg_count == 2
    assert confidence == 0.7


def test_extract_yolo_prediction_without_detections():
    """Verify that zero detections return an egg count of zero."""

    boxes = MagicMock()
    boxes.__len__.return_value = 0

    model_output = MagicMock()
    model_output.boxes = boxes

    egg_count, confidence = extract_yolo_prediction(
        model_output,
    )

    assert egg_count == 0
    assert confidence is None


def test_extract_yolo_prediction_without_boxes():
    """Verify that missing YOLO boxes are interpreted as zero detections."""

    model_output = MagicMock()
    model_output.boxes = None

    egg_count, confidence = extract_yolo_prediction(
        model_output,
    )

    assert egg_count == 0
    assert confidence is None


def test_predict_image():
    """Verify that YOLO inference returns the expected count and confidence."""

    model = MagicMock()

    result = MagicMock()

    boxes = MagicMock()
    boxes.__len__.return_value = 1

    confidences = MagicMock()
    confidences.detach.return_value.cpu.return_value.tolist.return_value = [
        0.9
    ]

    boxes.conf = confidences
    result.boxes = boxes

    # Simulate the result returned by Ultralytics for one input image.
    model.predict.return_value = [result]

    egg_count, confidence = predict_image(
        model=model,
        image_path=Path("cage_001.jpg"),
    )

    assert egg_count == 1
    assert confidence == 0.9

    model.predict.assert_called_once_with(
        source="cage_001.jpg",
        verbose=False,
    )


def test_predict_image_no_results():
    """Verify that an empty YOLO prediction result raises RuntimeError."""

    model = MagicMock()
    model.predict.return_value = []

    with pytest.raises(
        RuntimeError,
        match="YOLO returned no result",
    ):
        predict_image(
            model=model,
            image_path=Path("cage_001.jpg"),
        )


def test_get_image_size_bytes(tmp_path):
    """Verify that the image size is returned correctly in bytes."""

    image_path = tmp_path / "image.jpg"

    image_path.write_bytes(b"1234567890")

    size = get_image_size_bytes(image_path)

    assert size == 10


def test_run_single_image_inference_success(
    tmp_path,
    monkeypatch,
):
    """Verify the complete result generated by a successful image inference."""

    images_root = tmp_path / "images"

    image_path = (
        images_root
        / "house_01"
        / "2026"
        / "06"
        / "01"
        / "cage_001.jpg"
    )

    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"fake-image")

    model = MagicMock()

    # Minimal synchronized-model metadata required by the inference
    # result.
    local_model = SimpleNamespace(
        registered_name="egg_detector",
        version="3",
        alias="production",
        synchronized_at="2026-06-01T10:00:00+00:00",
    )

    # Replace the actual YOLO prediction with a deterministic result so
    # this test focuses on result construction rather than model execution.
    monkeypatch.setattr(
        "poultry_edge.inference.predict_image",
        lambda model, image_path: (2, 0.85),
    )

    result = run_single_image_inference(
        model=model,
        image_path=image_path,
        images_root=images_root,
        farm_id="farm_01",
        capture_date=date(2026, 6, 1),
        processing_date=date(2026, 6, 1),
        local_model=local_model,
    )

    assert result.farm_id == "farm_01"
    assert result.house_id == "house_01"
    assert result.cage_id == "cage_001"

    assert result.capture_date == "2026-06-01"
    assert result.processing_date == "2026-06-01"

    assert result.image_name == "cage_001.jpg"
    assert result.image_size_bytes == 10

    assert result.egg_count == 2
    assert result.confidence == 0.85

    assert result.registered_model_name == "egg_detector"
    assert result.model_version == "3"
    assert result.model_alias == "production"

    assert result.inference_status == "SUCCESS"
    assert result.error_message is None

    assert result.inference_duration_ms >= 0


def test_run_single_image_inference_error(
    tmp_path,
    monkeypatch,
):
    """Verify that an inference failure is recorded without stopping execution."""

    images_root = tmp_path / "images"

    image_path = (
        images_root
        / "house_01"
        / "2026"
        / "06"
        / "01"
        / "cage_001.jpg"
    )

    image_path.parent.mkdir(parents=True)
    image_path.touch()

    model = MagicMock()

    local_model = SimpleNamespace(
        registered_name="egg_detector",
        version="3",
        alias="production",
        synchronized_at="2026-06-01T10:00:00+00:00",
    )

    # Simulate a failure produced during model inference.
    def failing_prediction(model, image_path):
        raise RuntimeError("Inference failed")

    monkeypatch.setattr(
        "poultry_edge.inference.predict_image",
        failing_prediction,
    )

    result = run_single_image_inference(
        model=model,
        image_path=image_path,
        images_root=images_root,
        farm_id="farm_01",
        capture_date=date(2026, 6, 1),
        processing_date=date(2026, 6, 1),
        local_model=local_model,
    )

    assert result.house_id == "house_01"
    assert result.cage_id == "cage_001"

    assert result.egg_count is None
    assert result.confidence is None

    assert result.inference_status == "ERROR"

    assert result.error_message == (
        "RuntimeError: Inference failed"
    )


def test_run_daily_inference_success(
    tmp_path,
    monkeypatch,
):
    """Verify that daily inference processes every discovered image."""

    config = SimpleNamespace(
        farm=SimpleNamespace(
            id="farm_01",
        ),
        images=SimpleNamespace(
            root_directory=tmp_path / "images",
        ),
    )

    processing_date = date(2026, 8, 3)

    image_paths = [
        tmp_path / "images" / "house_01" / "2026" / "08" / "03" / "cage_001.jpg",
        tmp_path / "images" / "house_01" / "2026" / "08" / "03" / "cage_002.jpg",
    ]

    model = MagicMock()
    model.names = {0: "egg"}

    local_model = SimpleNamespace(
        registered_name="egg_detector",
        version="3",
        alias="production",
        synchronized_at="2026-08-03T09:00:00+00:00",
    )

    expected_results = [
        SimpleNamespace(
            inference_status="SUCCESS",
            egg_count=2,
        ),
        SimpleNamespace(
            inference_status="SUCCESS",
            egg_count=1,
        ),
    ]

    # Mock per-image inference so the test focuses on orchestration of
    # the complete daily batch.
    run_single_mock = MagicMock(
        side_effect=expected_results,
    )

    monkeypatch.setattr(
        "poultry_edge.inference.run_single_image_inference",
        run_single_mock,
    )

    results = run_daily_inference(
        config=config,
        model=model,
        local_model=local_model,
        processing_date=processing_date,
        image_paths=image_paths,
    )

    assert results == expected_results
    assert len(results) == 2

    assert run_single_mock.call_count == 2

    run_single_mock.assert_any_call(
        model=model,
        image_path=image_paths[0],
        images_root=config.images.root_directory,
        farm_id="farm_01",
        capture_date=processing_date,
        processing_date=processing_date,
        local_model=local_model,
    )

    run_single_mock.assert_any_call(
        model=model,
        image_path=image_paths[1],
        images_root=config.images.root_directory,
        farm_id="farm_01",
        capture_date=processing_date,
        processing_date=processing_date,
        local_model=local_model,
    )


def test_run_daily_inference_with_success_and_error(
    tmp_path,
    monkeypatch,
):
    """Verify that one failed image does not prevent the daily batch from continuing."""

    config = SimpleNamespace(
        farm=SimpleNamespace(
            id="farm_01",
        ),
        images=SimpleNamespace(
            root_directory=tmp_path / "images",
        ),
    )

    processing_date = date(2026, 8, 3)

    image_paths = [
        tmp_path / "image_1.jpg",
        tmp_path / "image_2.jpg",
    ]

    model = MagicMock()
    model.names = {0: "egg"}

    local_model = SimpleNamespace(
        registered_name="egg_detector",
        version="3",
        alias="production",
        synchronized_at="2026-08-03T09:00:00+00:00",
    )

    # Simulate a daily batch containing one successful inference and
    # one image-level inference error.
    expected_results = [
        SimpleNamespace(
            inference_status="SUCCESS",
            egg_count=3,
        ),
        SimpleNamespace(
            inference_status="ERROR",
            egg_count=None,
        ),
    ]

    monkeypatch.setattr(
        "poultry_edge.inference.run_single_image_inference",
        MagicMock(side_effect=expected_results),
    )

    results = run_daily_inference(
        config=config,
        model=model,
        local_model=local_model,
        processing_date=processing_date,
        image_paths=image_paths,
    )

    assert len(results) == 2

    assert results[0].inference_status == "SUCCESS"
    assert results[0].egg_count == 3

    assert results[1].inference_status == "ERROR"
    assert results[1].egg_count is None


def test_run_daily_inference_rejects_invalid_model(
    tmp_path,
):
    """Verify that daily inference rejects a model with invalid classes."""

    config = SimpleNamespace(
        farm=SimpleNamespace(
            id="farm_01",
        ),
        images=SimpleNamespace(
            root_directory=tmp_path / "images",
        ),
    )

    # The inference pipeline requires a single-class model containing
    # only the "egg" class.
    model = MagicMock()
    model.names = {
        0: "egg",
        1: "hen",
    }

    local_model = SimpleNamespace(
        registered_name="egg_detector",
        version="3",
        alias="production",
        synchronized_at="2026-08-03T09:00:00+00:00",
    )

    with pytest.raises(
        ValueError,
        match="exactly one class named 'egg'",
    ):
        run_daily_inference(
            config=config,
            model=model,
            local_model=local_model,
            processing_date=date(2026, 8, 3),
            image_paths=[
                tmp_path / "image.jpg",
            ],
        )