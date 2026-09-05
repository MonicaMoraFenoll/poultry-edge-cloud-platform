from __future__ import annotations

import csv
import logging
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Sequence

from .inference import InferenceResult


logger = logging.getLogger(__name__)


OUTPUT_FILE_NAME = "egg_prediction.csv"
TEMPORARY_FILE_SUFFIX = ".tmp"


CSV_FIELD_NAMES = [
    "farm_id",
    "house_number",
    "cage_id",
    "capture_date",
    "processing_date",
    "image_name",
    "image_path",
    "image_size_bytes",
    "egg_count",
    "confidence",
    "registered_model_name",
    "model_version",
    "model_alias",
    "model_synchronized_at",
    "inference_started_at",
    "inference_duration_ms",
    "inference_status",
    "error_message",
]


def build_daily_output_directory(
    outputs_root_directory: Path,
    processing_date: date,
) -> Path:
    """
    Build the output directory for one processing date.

    Example:

        outputs_root_directory = /data/outputs
        processing_date = 2026-08-03

    Result:

        /data/outputs/2026/08/03
    """

    return (
        outputs_root_directory
        / f"{processing_date.year:04d}"
        / f"{processing_date.month:02d}"
        / f"{processing_date.day:02d}"
    )


def build_daily_output_file(
    outputs_root_directory: Path,
    processing_date: date,
) -> Path:
    """
    Build the complete path of the daily inference CSV.

    Example:

        /data/outputs/2026/08/03/egg_prediction.csv
    """

    output_directory = build_daily_output_directory(
        outputs_root_directory=outputs_root_directory,
        processing_date=processing_date,
    )

    return output_directory / OUTPUT_FILE_NAME


def _result_to_csv_row(
    result: InferenceResult,
) -> dict[str, object]:
    """
    Convert one InferenceResult into a CSV row.
    """

    row = asdict(result)

    expected_fields = set(CSV_FIELD_NAMES)
    result_fields = set(row)

    missing_fields = expected_fields.difference(result_fields)

    if missing_fields:
        raise ValueError(
            "InferenceResult is missing required CSV fields: "
            f"{sorted(missing_fields)}"
        )

    unexpected_fields = result_fields.difference(expected_fields)

    if unexpected_fields:
        raise ValueError(
            "InferenceResult contains fields not defined in the CSV "
            f"schema: {sorted(unexpected_fields)}"
        )

    return {
        field_name: row[field_name]
        for field_name in CSV_FIELD_NAMES
    }


def _validate_results(
    results: Sequence[InferenceResult],
    farm_id: str,
    processing_date: date,
) -> None:
    """
    Validate that all results belong to the same daily execution.

    All rows must belong to:

    - the configured farm;
    - the requested processing date;
    - the same registered model;
    - the same model version;
    - the same model alias.
    """

    if not results:
        return

    normalized_farm_id = farm_id.strip()

    if not normalized_farm_id:
        raise ValueError("farm_id cannot be empty.")

    expected_processing_date = processing_date.isoformat()

    expected_model_name = results[0].registered_model_name
    expected_model_version = results[0].model_version
    expected_model_alias = results[0].model_alias

    for position, result in enumerate(results):
        if result.farm_id != normalized_farm_id:
            raise ValueError(
                "All inference results must belong to the configured "
                "farm. "
                f"Result at position {position} has farm_id="
                f"'{result.farm_id}', expected "
                f"'{normalized_farm_id}'."
            )

        if result.processing_date != expected_processing_date:
            raise ValueError(
                "All inference results must belong to the requested "
                "processing date. "
                f"Result at position {position} has processing_date="
                f"'{result.processing_date}', expected "
                f"'{expected_processing_date}'."
            )

        if result.registered_model_name != expected_model_name:
            raise ValueError(
                "All inference results must use the same registered "
                "model. "
                f"Result at position {position} uses "
                f"'{result.registered_model_name}', expected "
                f"'{expected_model_name}'."
            )

        if result.model_version != expected_model_version:
            raise ValueError(
                "All inference results must use the same model "
                "version. "
                f"Result at position {position} uses version "
                f"'{result.model_version}', expected "
                f"'{expected_model_version}'."
            )

        if result.model_alias != expected_model_alias:
            raise ValueError(
                "All inference results must use the same model alias. "
                f"Result at position {position} uses alias "
                f"'{result.model_alias}', expected "
                f"'{expected_model_alias}'."
            )


def write_inference_results(
    results: Sequence[InferenceResult],
    outputs_root_directory: Path,
    farm_id: str,
    processing_date: date,
    overwrite: bool = True,
) -> Path | None:
    """
    Write the daily inference results to a CSV file.

    The file is written atomically:

    1. All rows are written to a temporary file.
    2. The temporary file replaces the final CSV only after writing
       has completed successfully.

    Parameters
    ----------
    results:
        Results generated by run_daily_inference().

    outputs_root_directory:
        Root directory configured for inference outputs.

    farm_id:
        Identifier of the farm assigned to this edge.

    processing_date:
        Date processed by the daily pipeline.

    overwrite:
        If True, replace an existing daily CSV.
        If False and the file already exists, raise FileExistsError.

    Returns
    -------
    Path | None
        Path of the generated CSV.

        None is returned when there are no inference results.
    """

    if not results:
        logger.warning(
            "No inference results to write for farm='%s', date='%s'.",
            farm_id,
            processing_date.isoformat(),
        )
        return None

    _validate_results(
        results=results,
        farm_id=farm_id,
        processing_date=processing_date,
    )

    output_file = build_daily_output_file(
        outputs_root_directory=outputs_root_directory,
        processing_date=processing_date,
    )

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if output_file.exists() and not overwrite:
        raise FileExistsError(
            f"The output file already exists: '{output_file}'."
        )

    temporary_file = output_file.with_suffix(
        output_file.suffix + TEMPORARY_FILE_SUFFIX
    )

    try:
        with temporary_file.open(
            mode="w",
            encoding="utf-8",
            newline="",
        ) as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=CSV_FIELD_NAMES,
                extrasaction="raise",
            )

            writer.writeheader()

            for result in results:
                writer.writerow(
                    _result_to_csv_row(result)
                )

            csv_file.flush()

        temporary_file.replace(output_file)

    except Exception:
        temporary_file.unlink(missing_ok=True)
        raise

    successful_inferences = sum(
        result.inference_status == "SUCCESS"
        for result in results
    )

    failed_inferences = sum(
        result.inference_status == "ERROR"
        for result in results
    )

    logger.info(
        "Inference results written successfully to '%s'. "
        "Farm='%s', total=%d, successful=%d, failed=%d, "
        "model='%s', version='%s'.",
        output_file,
        farm_id,
        len(results),
        successful_inferences,
        failed_inferences,
        results[0].registered_model_name,
        results[0].model_version,
    )

    return output_file