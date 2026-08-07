from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from ultralytics import YOLO
from ultralytics.engine.results import Results

from .config import EdgeConfig
from .image_discovery import find_daily_images
from .model_loader import LocalModel


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InferenceResult:
    """
    Result produced after processing one image.

    confidence contains the mean confidence of all egg detections in
    the image. It is None when no eggs are detected or inference fails.
    """

    farm_id: str
    house_id: str
    cage_id: str

    capture_date: str
    processing_date: str

    image_name: str
    image_path: str
    image_size_bytes: int

    egg_count: int | None
    confidence: float | None

    registered_model_name: str
    model_version: str
    model_alias: str
    model_synchronized_at: str

    inference_started_at: str
    inference_duration_ms: float

    inference_status: str
    error_message: str | None


def validate_yolo_model(model: YOLO) -> None:
    """Validate that the YOLO model contains only the egg class."""

    class_names = model.names

    if isinstance(class_names, dict):
        normalized_names = [
            str(class_names[index]).strip().lower()
            for index in sorted(class_names)
        ]
    else:
        normalized_names = [
            str(name).strip().lower()
            for name in class_names
        ]

    if normalized_names != ["egg"]:
        raise ValueError(
            "The YOLO model must contain exactly one class named "
            f"'egg'. Found: {normalized_names}."
        )


def extract_image_identifiers(
    image_path: Path,
    images_root: Path,
) -> tuple[str, str]:
    """
    Extract the house and cage identifiers from an image path.

    Expected structure:

        images_root/
        └── house_01/
            └── YYYY/MM/DD/
                └── cage_001.jpg
    """

    try:
        relative_path = image_path.relative_to(images_root)
    except ValueError as error:
        raise ValueError(
            f"Image '{image_path}' is not inside the images root "
            f"directory '{images_root}'."
        ) from error

    if len(relative_path.parts) != 5:
        raise ValueError(
            f"Unexpected image path structure: '{image_path}'. "
            "Expected: "
            "images_root/house_id/YYYY/MM/DD/cage_id.extension"
        )

    house_id = relative_path.parts[0].strip()
    cage_id = image_path.stem.strip()

    if not house_id:
        raise ValueError(
            f"Could not extract house_id from '{image_path}'."
        )

    if not cage_id:
        raise ValueError(
            f"Could not extract cage_id from '{image_path}'."
        )

    return house_id, cage_id


def extract_yolo_prediction(
    model_output: Results,
) -> tuple[int, float | None]:
    """
    Extract the egg count and mean confidence from one YOLO result.

    The model contains one class named egg. Therefore, every bounding
    box represents one detected egg.
    """

    boxes = model_output.boxes

    if boxes is None or len(boxes) == 0:
        return 0, None

    egg_count = len(boxes)

    if boxes.conf is None:
        return egg_count, None

    confidences = boxes.conf.detach().cpu().tolist()

    if not confidences:
        return egg_count, None

    mean_confidence = sum(
        float(confidence)
        for confidence in confidences
    ) / len(confidences)

    return egg_count, round(mean_confidence, 6)


def predict_image(
    model: YOLO,
    image_path: Path,
) -> tuple[int, float | None]:
    """Run YOLO inference on one image."""

    prediction_results = model.predict(
        source=str(image_path),
        verbose=False,
    )

    if not prediction_results:
        raise RuntimeError(
            f"YOLO returned no result for image '{image_path}'."
        )

    if len(prediction_results) != 1:
        raise RuntimeError(
            "Expected one YOLO result for one image, but received "
            f"{len(prediction_results)} results."
        )

    return extract_yolo_prediction(
        model_output=prediction_results[0],
    )


def get_image_size_bytes(image_path: Path) -> int:
    """Return the image size in bytes."""

    try:
        return image_path.stat().st_size
    except OSError as error:
        logger.warning(
            "Could not read the size of image '%s': %s.",
            image_path,
            error,
        )
        return 0


def run_single_image_inference(
    model: YOLO,
    image_path: Path,
    images_root: Path,
    farm_id: str,
    capture_date: date,
    processing_date: date,
    local_model: LocalModel,
) -> InferenceResult:
    """
    Run YOLO inference on one image.

    Errors are handled independently so that one invalid image does not
    stop the processing of the remaining daily images.
    """

    inference_started_at = datetime.now(timezone.utc)
    inference_start_time = time.perf_counter()

    house_id = ""
    cage_id = image_path.stem.strip()

    egg_count: int | None = None
    confidence: float | None = None

    inference_status = "SUCCESS"
    error_message: str | None = None

    try:
        house_id, cage_id = extract_image_identifiers(
            image_path=image_path,
            images_root=images_root,
        )

        egg_count, confidence = predict_image(
            model=model,
            image_path=image_path,
        )

    except Exception as error:
        inference_status = "ERROR"
        error_message = f"{type(error).__name__}: {error}"

        logger.exception(
            "Inference failed for image '%s'.",
            image_path,
        )

    inference_duration_ms = (
        time.perf_counter() - inference_start_time
    ) * 1_000

    return InferenceResult(
        farm_id=farm_id,
        house_id=house_id,
        cage_id=cage_id,
        capture_date=capture_date.isoformat(),
        processing_date=processing_date.isoformat(),
        image_name=image_path.name,
        image_path=str(image_path),
        image_size_bytes=get_image_size_bytes(image_path),
        egg_count=egg_count,
        confidence=confidence,
        registered_model_name=local_model.registered_name,
        model_version=local_model.version,
        model_alias=local_model.alias,
        model_synchronized_at=local_model.synchronized_at,
        inference_started_at=inference_started_at.isoformat(),
        inference_duration_ms=round(
            inference_duration_ms,
            3,
        ),
        inference_status=inference_status,
        error_message=error_message,
    )


def run_daily_inference(
    config: EdgeConfig,
    model: YOLO,
    local_model: LocalModel,
    processing_date: date,
) -> list[InferenceResult]:
    """Run YOLO inference on all images belonging to one date."""

    validate_yolo_model(model)

    image_paths = find_daily_images(
        images_root=config.images.root_directory,
        processing_date=processing_date,
        supported_extensions=(
            config.inference.supported_extensions
        ),
    )

    if not image_paths:
        logger.warning(
            "No images found for farm='%s', date='%s'.",
            config.farm.id,
            processing_date.isoformat(),
        )
        return []

    logger.info(
        "Starting inference for %d image(s). "
        "Farm='%s', date='%s', model='%s', version='%s'.",
        len(image_paths),
        config.farm.id,
        processing_date.isoformat(),
        local_model.registered_name,
        local_model.version,
    )

    results = [
        run_single_image_inference(
            model=model,
            image_path=image_path,
            images_root=config.images.root_directory,
            farm_id=config.farm.id,
            capture_date=processing_date,
            processing_date=processing_date,
            local_model=local_model,
        )
        for image_path in image_paths
    ]

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

    logger.info(
        "Daily inference finished. "
        "Farm='%s', date='%s', total_images=%d, "
        "successful=%d, failed=%d, total_eggs=%d.",
        config.farm.id,
        processing_date.isoformat(),
        len(results),
        successful_inferences,
        failed_inferences,
        total_eggs,
    )

    return results