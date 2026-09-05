import csv
from datetime import date
from pathlib import Path

import pytest

from poultry_edge.inference import InferenceResult
from poultry_edge.output_writer import (
    CSV_FIELD_NAMES,
    OUTPUT_FILE_NAME,
    _result_to_csv_row,
    _validate_results,
    build_daily_output_directory,
    build_daily_output_file,
    write_inference_results,
)


def make_result(
    farm_id: str = "farm_01",
    processing_date: str = "2026-08-03",
    model_name: str = "egg_detector",
    model_version: str = "3",
    model_alias: str = "production",
) -> InferenceResult:
    return InferenceResult(
        farm_id=farm_id,
        house_number="house_01",
        cage_id="cage_001",
        capture_date="2026-08-03",
        processing_date=processing_date,
        image_name="cage_001.jpg",
        image_path="/data/images/house_01/2026/08/03/cage_001.jpg",
        image_size_bytes=1024,
        egg_count=2,
        confidence=0.87,
        registered_model_name=model_name,
        model_version=model_version,
        model_alias=model_alias,
        model_synchronized_at="2026-08-03T09:00:00+00:00",
        inference_started_at="2026-08-03T11:00:00+00:00",
        inference_duration_ms=12.5,
        inference_status="SUCCESS",
        error_message=None,
    )


def test_build_daily_output_directory(tmp_path):
    processing_date = date(2026, 8, 3)

    output_directory = build_daily_output_directory(
        outputs_root_directory=tmp_path,
        processing_date=processing_date,
    )

    assert output_directory == (
        tmp_path
        / "2026"
        / "08"
        / "03"
    )


def test_build_daily_output_file(tmp_path):
    processing_date = date(2026, 8, 3)

    output_file = build_daily_output_file(
        outputs_root_directory=tmp_path,
        processing_date=processing_date,
    )

    assert output_file == (
        tmp_path
        / "2026"
        / "08"
        / "03"
        / OUTPUT_FILE_NAME
    )


def test_result_to_csv_row():
    result = make_result()

    row = _result_to_csv_row(result)

    assert list(row.keys()) == CSV_FIELD_NAMES

    assert row["farm_id"] == "farm_01"
    assert row["house_number"] == "house_01"
    assert row["cage_id"] == "cage_001"

    assert row["egg_count"] == 2
    assert row["confidence"] == 0.87

    assert row["inference_status"] == "SUCCESS"
    assert row["error_message"] is None


def test_validate_results_valid():
    results = [
        make_result(),
        make_result(),
    ]

    _validate_results(
        results=results,
        farm_id="farm_01",
        processing_date=date(2026, 8, 3),
    )


def test_validate_results_wrong_farm():
    results = [
        make_result(),
        make_result(farm_id="farm_02"),
    ]

    with pytest.raises(
        ValueError,
        match="configured farm",
    ):
        _validate_results(
            results=results,
            farm_id="farm_01",
            processing_date=date(2026, 8, 3),
        )


def test_validate_results_wrong_processing_date():
    results = [
        make_result(),
        make_result(processing_date="2026-08-04"),
    ]

    with pytest.raises(
        ValueError,
        match="requested processing date",
    ):
        _validate_results(
            results=results,
            farm_id="farm_01",
            processing_date=date(2026, 8, 3),
        )


def test_validate_results_different_model_name():
    results = [
        make_result(),
        make_result(model_name="other_model"),
    ]

    with pytest.raises(
        ValueError,
        match="same registered model",
    ):
        _validate_results(
            results=results,
            farm_id="farm_01",
            processing_date=date(2026, 8, 3),
        )


def test_validate_results_different_model_version():
    results = [
        make_result(),
        make_result(model_version="4"),
    ]

    with pytest.raises(
        ValueError,
        match="same model version",
    ):
        _validate_results(
            results=results,
            farm_id="farm_01",
            processing_date=date(2026, 8, 3),
        )


def test_validate_results_different_model_alias():
    results = [
        make_result(),
        make_result(model_alias="staging"),
    ]

    with pytest.raises(
        ValueError,
        match="same model alias",
    ):
        _validate_results(
            results=results,
            farm_id="farm_01",
            processing_date=date(2026, 8, 3),
        )


def test_write_inference_results(tmp_path):
    results = [
        make_result(),
        make_result(),
    ]

    output_file = write_inference_results(
        results=results,
        outputs_root_directory=tmp_path,
        farm_id="farm_01",
        processing_date=date(2026, 8, 3),
    )

    expected_file = (
        tmp_path
        / "2026"
        / "08"
        / "03"
        / "egg_prediction.csv"
    )

    assert output_file == expected_file
    assert output_file.exists()

    with output_file.open(
        mode="r",
        encoding="utf-8",
        newline="",
    ) as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)

    assert reader.fieldnames == CSV_FIELD_NAMES
    assert len(rows) == 2

    assert rows[0]["farm_id"] == "farm_01"
    assert rows[0]["house_number"] == "house_01"
    assert rows[0]["cage_id"] == "cage_001"

    assert rows[0]["egg_count"] == "2"
    assert rows[0]["confidence"] == "0.87"

    assert rows[0]["registered_model_name"] == "egg_detector"
    assert rows[0]["model_version"] == "3"
    assert rows[0]["model_alias"] == "production"

    assert rows[0]["inference_status"] == "SUCCESS"


def test_write_inference_results_creates_directories(tmp_path):
    results = [make_result()]

    output_file = write_inference_results(
        results=results,
        outputs_root_directory=tmp_path,
        farm_id="farm_01",
        processing_date=date(2026, 8, 3),
    )

    assert output_file is not None
    assert output_file.parent.exists()
    assert output_file.exists()


def test_write_inference_results_empty_results(tmp_path):
    output_file = write_inference_results(
        results=[],
        outputs_root_directory=tmp_path,
        farm_id="farm_01",
        processing_date=date(2026, 8, 3),
    )

    assert output_file is None


def test_write_inference_results_existing_file_without_overwrite(
    tmp_path,
):
    results = [make_result()]

    output_file = write_inference_results(
        results=results,
        outputs_root_directory=tmp_path,
        farm_id="farm_01",
        processing_date=date(2026, 8, 3),
    )

    assert output_file is not None
    assert output_file.exists()

    with pytest.raises(
        FileExistsError,
        match="already exists",
    ):
        write_inference_results(
            results=results,
            outputs_root_directory=tmp_path,
            farm_id="farm_01",
            processing_date=date(2026, 8, 3),
            overwrite=False,
        )


def test_write_inference_results_overwrites_existing_file(
    tmp_path,
):
    first_result = make_result()

    output_file = write_inference_results(
        results=[first_result],
        outputs_root_directory=tmp_path,
        farm_id="farm_01",
        processing_date=date(2026, 8, 3),
    )

    second_result = make_result()

    output_file_again = write_inference_results(
        results=[second_result],
        outputs_root_directory=tmp_path,
        farm_id="farm_01",
        processing_date=date(2026, 8, 3),
        overwrite=True,
    )

    assert output_file_again == output_file
    assert output_file.exists()


def test_temporary_file_is_removed_after_success(tmp_path):
    results = [make_result()]

    output_file = write_inference_results(
        results=results,
        outputs_root_directory=tmp_path,
        farm_id="farm_01",
        processing_date=date(2026, 8, 3),
    )

    temporary_file = output_file.with_suffix(
        output_file.suffix + ".tmp"
    )

    assert output_file.exists()
    assert not temporary_file.exists()