from __future__ import annotations

import logging
from datetime import date
from pathlib import Path


logger = logging.getLogger(__name__)


def build_date_path(processing_date: date) -> Path:
    """
    Build the relative directory path for a processing date.

    The date is represented using the YYYY/MM/DD directory structure
    used to organize images on the edge device.

    Parameters
    ----------
    processing_date:
        Date for which the directory path is required.

    Returns
    -------
    Path
        Relative path following the YYYY/MM/DD structure.
    """

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
    Find all images belonging to the selected processing date.

    Images are searched across all house directories located under
    the configured images root directory.

    Expected directory structure:

        images_root/
        ├── house_01/
        │   └── YYYY/MM/DD/
        │       ├── cage_001.jpg
        │       └── cage_002.jpg
        └── house_02/
            └── YYYY/MM/DD/
                └── cage_001.jpg

    Parameters
    ----------
    images_root:
        Root directory containing the house image directories.

    processing_date:
        Date for which images must be discovered.

    supported_extensions:
        File extensions accepted as valid input images.

    Returns
    -------
    list[Path]
        Sorted list of image paths found for the selected date.

    Raises
    ------
    FileNotFoundError
        If the configured images root directory does not exist.

    ValueError
        If no supported image extensions are configured.
    """

    # The configured image root must exist before starting discovery.
    if not images_root.is_dir():
        raise FileNotFoundError(
            f"Images root directory not found: '{images_root}'."
        )

    if not supported_extensions:
        raise ValueError(
            "supported_extensions cannot be empty."
        )

    # Build the YYYY/MM/DD path shared by all houses for the
    # requested processing date.
    date_path = build_date_path(processing_date)

    daily_images: list[Path] = []

    # Search every house directory available on the edge device.
    for house_directory in sorted(images_root.glob("house_*")):
        if not house_directory.is_dir():
            continue

        day_directory = house_directory / date_path

        # A house may not contain images for the requested date.
        # In that case, simply continue with the next house.
        if not day_directory.is_dir():
            continue

        # Keep only regular files with one of the configured image
        # extensions.
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