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


# Fixed schema used for every daily inference output file.
# Keeping an explicit column order makes the generated CSVs consistent
# across executions and Edge devices.
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

    Results are organized hierarchically by year, month, and day.

    Parameters
    ----------
    outputs_root_directory:
        Root directory configured for inference outputs.

    processing_date:
        Date associated with the daily pipeline execution.

    Returns
    -------
    Path
        Directory where the results for the selected date are stored.

    Example
    -------
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

    Parameters
    ----------
    outputs_root_directory:
        Root directory configured for inference outputs.

    processing_date:
        Date associated with the daily pipeline execution.

    Returns
    -------
    Path
        Complete path of the daily egg_prediction.csv file.

    Example
    -------
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

    The fields contained in the result are checked against the expected
    CSV schema before the row is written. This prevents silent schema
    inconsistencies between the inference and output modules.

    Parameters
    ----------
    result:
        Inference result generated for one image.

    Returns
    -------
    dict[str, object]
        Dictionary containing the CSV fields in the expected order.

    Raises
    ------
    ValueError
        If the inference result contains missing or unexpected fields.
    """

    # Convert the immutable dataclass into a standard dictionary.
    row = asdict(result)

    expected_fields = set(CSV_FIELD_NAMES)
    result_fields = set(row)

    # Ensure that all fields required by the CSV schema are present.
    missing_fields = expected_fields.difference(result_fields)

    if missing_fields:
        raise ValueError(
            "InferenceResult is missing required CSV fields: "
            f"{sorted(missing_fields)}"
        )

    # Prevent additional fields from being written silently if the
    # InferenceResult schema changes in the future.
    unexpected_fields = result_fields.difference(expected_fields)

    if unexpected_fields:
        raise ValueError(
            "InferenceResult contains fields not defined in the CSV "
            f"schema: {sorted(unexpected_fields)}"
        )

    # Rebuild the dictionary following the explicit CSV column order.
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

    This validation prevents results from different executions or model
    versions from being combined into the same daily output file.

    Parameters
    ----------
    results:
        Inference results that will be written to the CSV.

    farm_id:
        Identifier of the farm assigned to this edge.

    processing_date:
        Date associated with the current daily pipeline execution.

    Raises
    ------
    ValueError
        If the farm identifier is empty or if any result is inconsistent
        with the expected daily execution.
    """

    # An empty result collection does not require consistency checks.
    if not results:
        return

    normalized_farm_id = farm_id.strip()

    if not normalized_farm_id:
        raise ValueError("farm_id cannot be empty.")

    expected_processing_date = processing_date.isoformat()

    # The first result establishes the model metadata expected for all
    # remaining rows in the same daily output.
    expected_model_name = results[0].registered_model_name
    expected_model_version = results[0].model_version
    expected_model_alias = results[0].model_alias

    for position, result in enumerate(results):
        # Every row must belong to the farm configured for this Edge.
        if result.farm_id != normalized_farm_id:
            raise ValueError(
                "All inference results must belong to the configured "
                "farm. "
                f"Result at position {position} has farm_id="
                f"'{result.farm_id}', expected "
                f"'{normalized_farm_id}'."
            )

        # A daily CSV must only contain results associated with the
        # requested processing date.
        if result.processing_date != expected_processing_date:
            raise ValueError(
                "All inference results must belong to the requested "
                "processing date. "
                f"Result at position {position} has processing_date="
                f"'{result.processing_date}', expected "
                f"'{expected_processing_date}'."
            )

        # All rows must be generated using the same registered model.
        if result.registered_model_name != expected_model_name:
            raise ValueError(
                "All inference results must use the same registered "
                "model. "
                f"Result at position {position} uses "
                f"'{result.registered_model_name}', expected "
                f"'{expected_model_name}'."
            )

        # Mixing model versions in one daily file would make model
        # provenance ambiguous, so the version must remain constant.
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

    This strategy prevents an incomplete or partially written CSV from
    being exposed as the final daily result if the writing process fails.

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

    Raises
    ------
    FileExistsError
        If the final CSV already exists and overwrite is disabled.

    ValueError
        If the inference results are not consistent with the expected
        daily execution or CSV schema.
    """

    # Do not create an empty daily CSV when no inference results were
    # generated.
    if not results:
        logger.warning(
            "No inference results to write for farm='%s', date='%s'.",
            farm_id,
            processing_date.isoformat(),
        )
        return None

    # Validate execution-level consistency before creating any output.
    _validate_results(
        results=results,
        farm_id=farm_id,
        processing_date=processing_date,
    )

    output_file = build_daily_output_file(
        outputs_root_directory=outputs_root_directory,
        processing_date=processing_date,
    )

    # Create the YYYY/MM/DD output hierarchy when necessary.
    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if output_file.exists() and not overwrite:
        raise FileExistsError(
            f"The output file already exists: '{output_file}'."
        )

    # Write to a temporary file first so a failed execution cannot
    # leave a partially written egg_prediction.csv.
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

            # Write the fixed schema as the first row of the CSV.
            writer.writeheader()

            # Each InferenceResult corresponds to one processed image.
            for result in results:
                writer.writerow(
                    _result_to_csv_row(result)
                )

            csv_file.flush()

        # Replace the final CSV only after the complete temporary file
        # has been written successfully.
        temporary_file.replace(output_file)

    except Exception:
        # Remove incomplete temporary output if any step fails.
        temporary_file.unlink(missing_ok=True)
        raise

    # Generate a concise execution summary for operational monitoring.
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