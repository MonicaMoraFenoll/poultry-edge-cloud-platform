from __future__ import annotations

import logging
from datetime import date
from pathlib import Path


logger = logging.getLogger(__name__)


def build_date_path(processing_date: date) -> Path:
    """Build a YYYY/MM/DD relative path."""

    return Path(
        f"{processing_date.year:04d}",
        f"{processing_date.month:02d}",
        f"{processing_date.day:02d}",
    )


def find_daily_images(
    images_root: Path,
    processing_date: date,
    supported_extensions: tuple[str, ...],
) -> list[Path]:
    """
    Find all images belonging to the selected date.

    Expected directory structure:

        images_root/
        ├── house_01/
        │   └── YYYY/MM/DD/
        │       ├── cage_001.jpg
        │       └── cage_002.jpg
        └── house_02/
            └── YYYY/MM/DD/
                └── cage_001.jpg
    """

    if not images_root.is_dir():
        raise FileNotFoundError(
            f"Images root directory not found: '{images_root}'."
        )

    if not supported_extensions:
        raise ValueError(
            "supported_extensions cannot be empty."
        )

    date_path = build_date_path(processing_date)
    daily_images: list[Path] = []

    for house_directory in sorted(images_root.glob("house_*")):
        if not house_directory.is_dir():
            continue

        day_directory = house_directory / date_path

        if not day_directory.is_dir():
            continue

        for image_path in sorted(day_directory.iterdir()):
            if (
                image_path.is_file()
                and image_path.suffix.lower() in supported_extensions
            ):
                daily_images.append(image_path)

    logger.info(
        "Discovered %d image(s) for date='%s' in '%s'.",
        len(daily_images),
        processing_date.isoformat(),
        images_root,
    )

    return daily_images