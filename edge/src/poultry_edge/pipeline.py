from __future__ import annotations

import logging
import time
from datetime import date, datetime, timezone
from pathlib import Path

from .config import EdgeConfig
from .inference import run_daily_inference
from .model_loader import (
    load_yolo_model,
    synchronize_model,
)
from .output_writer import write_inference_results


logger = logging.getLogger(__name__)


def run_daily_pipeline(
    config: EdgeConfig,
    processing_date: date,
    tracking_uri: str | None = None,
    registry_uri: str | None = None,
    overwrite: bool = True,
) -> Path | None:
    """
    Run the complete daily inference pipeline for one edge.

    Workflow:

    1. Synchronize the model assigned to the edge.
    2. Load the synchronized YOLO model.
    3. Discover and process the images for the selected date.
    4. Write the daily inference CSV.
    5. Log execution statistics.

    Parameters
    ----------
    config:
        Configuration assigned to the edge.

    processing_date:
        Date whose images must be processed.

    tracking_uri:
        Optional MLflow Tracking Server URI.

    registry_uri:
        Optional MLflow Model Registry URI.

    overwrite:
        If True, replace an existing daily output CSV.

    Returns
    -------
    Path | None
        Path of the generated CSV.

        None is returned when no images are found for the selected date.
    """

    pipeline_started_at = datetime.now(timezone.utc)
    pipeline_start_time = time.perf_counter()

    logger.info(
        "Starting daily edge pipeline. "
        "Farm='%s', date='%s'.",
        config.farm.id,
        processing_date.isoformat(),
    )

    # Resolve the model version assigned to this edge and make sure that
    # it is available locally. If MLflow is unavailable, the last valid
    # local model may be used.
    local_model = synchronize_model(
        model_config=config.model,
        tracking_uri=tracking_uri,
        registry_uri=registry_uri,
        allow_local_fallback=True,
    )

    logger.info(
        "Synchronized model ready. "
        "Name='%s', version='%s', alias='%s', path='%s'.",
        local_model.registered_name,
        local_model.version,
        local_model.alias,
        local_model.model_path,
    )

    # Load best.pt into memory as an Ultralytics YOLO model.
    model = load_yolo_model(
        local_model=local_model,
    )

    # Discover the daily images and process each one.
    results = run_daily_inference(
        config=config,
        model=model,
        local_model=local_model,
        processing_date=processing_date,
    )

    # Write one CSV inside outputs/YYYY/MM/DD/.
    output_file = write_inference_results(
        results=results,
        outputs_root_directory=config.outputs.root_directory,
        farm_id=config.farm.id,
        processing_date=processing_date,
        overwrite=overwrite,
    )

    pipeline_duration_seconds = (
        time.perf_counter() - pipeline_start_time
    )

    successful_inferences = sum(
        result.inference_status == "SUCCESS"
        for result in results
    )

    failed_inferences = sum(
        result.inference_status == "ERROR"
        for result in results
    )

    total_eggs = sum(
        result.egg_count or 0
        for result in results
        if result.inference_status == "SUCCESS"
    )

    if output_file is None:
        logger.warning(
            "Daily edge pipeline finished without an output file. "
            "Farm='%s', date='%s', total_images=0, "
            "model='%s', version='%s', started_at='%s', "
            "duration_seconds=%.3f.",
            config.farm.id,
            processing_date.isoformat(),
            local_model.registered_name,
            local_model.version,
            pipeline_started_at.isoformat(),
            pipeline_duration_seconds,
        )

        return None

    logger.info(
        "Daily edge pipeline finished successfully. "
        "Farm='%s', date='%s', total_images=%d, "
        "successful=%d, failed=%d, total_eggs=%d, "
        "model='%s', version='%s', started_at='%s', "
        "duration_seconds=%.3f, output='%s'.",
        config.farm.id,
        processing_date.isoformat(),
        len(results),
        successful_inferences,
        failed_inferences,
        total_eggs,
        local_model.registered_name,
        local_model.version,
        pipeline_started_at.isoformat(),
        pipeline_duration_seconds,
        output_file,
    )

    return output_file