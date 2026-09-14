from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from ultralytics import YOLO
from ultralytics.engine.results import Results

from .config import EdgeConfig
from .model_loader import LocalModel


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InferenceResult:
    """
    Result produced after processing one image.

    The object stores image metadata, model information, prediction
    results, execution timing, and the final inference status.

    The confidence field contains the mean confidence of all egg
    detections in the image. It is None when no eggs are detected
    or when inference fails.

    Attributes
    ----------
    farm_id:
        Identifier of the farm where the image was captured.

    house_number:
        Identifier of the house extracted from the image path.

    cage_id:
        Identifier of the cage extracted from the image filename.

    capture_date:
        Date when the image belongs to the acquisition dataset.

    processing_date:
        Date associated with the pipeline execution.

    image_name:
        Original image filename.

    image_path:
        Full path of the processed image.

    image_size_bytes:
        Size of the input image in bytes.

    egg_count:
        Number of egg detections returned by YOLO.

    confidence:
        Mean confidence of all detected eggs.

    registered_model_name:
        Name of the model registered in MLflow.

    model_version:
        Version of the synchronized model used for inference.

    model_alias:
        MLflow alias associated with the model.

    model_synchronized_at:
        Timestamp indicating when the local model was synchronized.

    inference_started_at:
        UTC timestamp marking the start of image processing.

    inference_duration_ms:
        Total inference duration for the image in milliseconds.

    inference_status:
        Final status of the image inference.

    error_message:
        Error information when inference fails.
    """

    farm_id: str
    house_number: str
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
    """
    Validate that the YOLO model contains only the egg class.

    The edge pipeline expects a single-class object detection model.
    Any model containing additional classes, or a different class name,
    is rejected before daily inference starts.

    Parameters
    ----------
    model:
        Loaded Ultralytics YOLO model.

    Raises
    ------
    ValueError
        If the model does not contain exactly one class named "egg".
    """

    class_names = model.names

    # Ultralytics may expose model class names either as a dictionary
    # or as an ordered sequence depending on the loaded model.
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

    # The counting logic assumes that every detected bounding box
    # represents one egg.
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

    The house identifier is obtained from the first directory below
    the configured images root. The cage identifier is obtained from
    the image filename without its extension.

    Expected structure:

        images_root/
        └── house_01/
            └── YYYY/MM/DD/
                └── cage_001.jpg

    Parameters
    ----------
    image_path:
        Path of the image being processed.

    images_root:
        Configured root directory containing all house images.

    Returns
    -------
    tuple[str, str]
        House identifier and cage identifier.

    Raises
    ------
    ValueError
        If the image is outside the configured root directory, the
        path structure is invalid, or an identifier cannot be extracted.
    """

    # Convert the image path into a path relative to the configured
    # image root so identifiers can be extracted consistently.
    try:
        relative_path = image_path.relative_to(images_root)
    except ValueError as error:
        raise ValueError(
            f"Image '{image_path}' is not inside the images root "
            f"directory '{images_root}'."
        ) from error

    # The expected relative structure is:
    # house_number / YYYY / MM / DD / cage_id.extension
    if len(relative_path.parts) != 5:
        raise ValueError(
            f"Unexpected image path structure: '{image_path}'. "
            "Expected: "
            "images_root/house_number/YYYY/MM/DD/cage_id.extension"
        )

    house_number = relative_path.parts[0].strip()

    # The image filename acts as the cage identifier.
    cage_id = image_path.stem.strip()

    if not house_number:
        raise ValueError(
            f"Could not extract house_number from '{image_path}'."
        )

    if not cage_id:
        raise ValueError(
            f"Could not extract cage_id from '{image_path}'."
        )

    return house_number, cage_id


def extract_yolo_prediction(
    model_output: Results,
) -> tuple[int, float | None]:
    """
    Extract the egg count and mean confidence from one YOLO result.

    The model contains one class named egg. Therefore, every bounding
    box represents one detected egg.

    Parameters
    ----------
    model_output:
        Ultralytics result produced for one image.

    Returns
    -------
    tuple[int, float | None]
        Number of detected eggs and mean detection confidence.

        When no bounding boxes are detected, the egg count is zero
        and confidence is None.
    """

    boxes = model_output.boxes

    # A successful inference with no detected bounding boxes represents
    # a valid count of zero eggs.
    if boxes is None or len(boxes) == 0:
        return 0, None

    # Since the model has exactly one class, each bounding box
    # corresponds to one detected egg.
    egg_count = len(boxes)

    if boxes.conf is None:
        return egg_count, None

    # Move confidence values to CPU memory before converting them into
    # standard Python values.
    confidences = boxes.conf.detach().cpu().tolist()

    if not confidences:
        return egg_count, None

    # Store a single confidence value per image using the mean
    # confidence of all egg detections.
    mean_confidence = sum(
        float(confidence)
        for confidence in confidences
    ) / len(confidences)

    return egg_count, round(mean_confidence, 6)


def predict_image(
    model: YOLO,
    image_path: Path,
) -> tuple[int, float | None]:
    """
    Run YOLO inference on one image.

    Parameters
    ----------
    model:
        Loaded YOLO model used for prediction.

    image_path:
        Path of the image to process.

    Returns
    -------
    tuple[int, float | None]
        Egg count and mean detection confidence.

    Raises
    ------
    RuntimeError
        If YOLO returns no result or more than one result for the
        input image.
    """

    prediction_results = model.predict(
        source=str(image_path),
        verbose=False,
    )

    if not prediction_results:
        raise RuntimeError(
            f"YOLO returned no result for image '{image_path}'."
        )

    # One input image must produce exactly one Ultralytics Results
    # object.
    if len(prediction_results) != 1:
        raise RuntimeError(
            "Expected one YOLO result for one image, but received "
            f"{len(prediction_results)} results."
        )

    return extract_yolo_prediction(
        model_output=prediction_results[0],
    )


def get_image_size_bytes(image_path: Path) -> int:
    """
    Return the image size in bytes.

    If the file metadata cannot be accessed, the error is logged and
    zero is returned so the remaining inference result can still be
    persisted.

    Parameters
    ----------
    image_path:
        Path of the processed image.

    Returns
    -------
    int
        File size in bytes, or zero if it cannot be read.
    """

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
    stop the processing of the remaining daily images. Both successful
    and failed executions are returned as InferenceResult objects.

    Parameters
    ----------
    model:
        Loaded YOLO model.

    image_path:
        Path of the image to process.

    images_root:
        Root directory used to derive house and cage identifiers.

    farm_id:
        Identifier of the farm assigned to the edge.

    capture_date:
        Date associated with the input image.

    processing_date:
        Date associated with the pipeline execution.

    local_model:
        Metadata describing the synchronized local model.

    Returns
    -------
    InferenceResult
        Complete result for the processed image, including metadata,
        prediction values, timing information, and execution status.
    """

    # Record both a UTC timestamp and a high-resolution timer. The
    # timestamp is persisted, while perf_counter is used to measure
    # execution duration accurately.
    inference_started_at = datetime.now(timezone.utc)
    inference_start_time = time.perf_counter()

    # Default identifiers and prediction values allow an error result
    # to be created even if processing fails before inference starts.
    house_number = ""
    cage_id = image_path.stem.strip()

    egg_count: int | None = None
    confidence: float | None = None

    inference_status = "SUCCESS"
    error_message: str | None = None

    try:
        # Derive farm-context identifiers from the image location.
        house_number, cage_id = extract_image_identifiers(
            image_path=image_path,
            images_root=images_root,
        )

        # Run the detector and extract the image-level prediction.
        egg_count, confidence = predict_image(
            model=model,
            image_path=image_path,
        )

    except Exception as error:
        # Processing errors are stored in the result instead of stopping
        # the complete daily pipeline.
        inference_status = "ERROR"
        error_message = f"{type(error).__name__}: {error}"

        logger.exception(
            "Inference failed for image '%s'.",
            image_path,
        )

    inference_duration_ms = (
        time.perf_counter() - inference_start_time
    ) * 1_000

    # Combine image metadata, prediction values, model provenance,
    # execution timing, and status into one persistent result object.
    return InferenceResult(
        farm_id=farm_id,
        house_number=house_number,
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
    image_paths: list[Path],
) -> list[InferenceResult]:
    """
    Run YOLO inference on all images belonging to one date.

    The model is validated before processing starts. Each image is then
    processed independently and the complete list of results is
    returned, including both successful and failed inferences.

    Parameters
    ----------
    config:
        Validated configuration assigned to the edge device.

    model:
        Loaded YOLO model used for inference.

    local_model:
        Metadata describing the synchronized model version.

    processing_date:
        Date being processed by the daily pipeline.

    image_paths:
        Images discovered for the selected date.

    Returns
    -------
    list[InferenceResult]
        Inference results generated for all input images.

    Raises
    ------
    ValueError
        If the loaded YOLO model does not contain exactly one class
        named "egg".
    """

    # Validate the model before processing any daily images so an
    # incompatible model fails immediately.
    validate_yolo_model(model)

    logger.info(
        "Starting inference for %d image(s). "
        "Farm='%s', date='%s', model='%s', version='%s'.",
        len(image_paths),
        config.farm.id,
        processing_date.isoformat(),
        local_model.registered_name,
        local_model.version,
    )

    # Process every discovered image independently. A failure in one
    # image is captured inside its result and does not interrupt the
    # remaining daily execution.
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

    # Build execution statistics for operational logging.
    successful_inferences = sum(
        result.inference_status == "SUCCESS"
        for result in results
    )

    failed_inferences = sum(
        result.inference_status == "ERROR"
        for result in results
    )

    # Only successful results contribute to the daily egg total.
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