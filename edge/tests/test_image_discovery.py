from datetime import date
from pathlib import Path

import pytest

from poultry_edge.image_discovery import (
    build_date_path,
    find_daily_images,
)


PROCESSING_DATE = date(2026, 6, 15)


def create_file(path: Path, content: str = "mock") -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        content,
        encoding="utf-8",
    )


def test_build_date_path():
    result = build_date_path(
        PROCESSING_DATE
    )

    assert result == Path(
        "2026",
        "06",
        "15",
    )


def test_find_daily_images_returns_images_from_all_houses(
    tmp_path,
):
    images_root = tmp_path / "images"

    image_1 = (
        images_root
        / "house_01"
        / "2026"
        / "06"
        / "15"
        / "cage_001.jpg"
    )

    image_2 = (
        images_root
        / "house_02"
        / "2026"
        / "06"
        / "15"
        / "cage_002.png"
    )

    create_file(image_1)
    create_file(image_2)

    result = find_daily_images(
        images_root=images_root,
        processing_date=PROCESSING_DATE,
        supported_extensions=(
            ".jpg",
            ".jpeg",
            ".png",
        ),
    )

    assert result == [
        image_1,
        image_2,
    ]


def test_find_daily_images_ignores_other_dates(
    tmp_path,
):
    images_root = tmp_path / "images"

    expected_image = (
        images_root
        / "house_01"
        / "2026"
        / "06"
        / "15"
        / "cage_001.jpg"
    )

    other_date_image = (
        images_root
        / "house_01"
        / "2026"
        / "06"
        / "16"
        / "cage_002.jpg"
    )

    create_file(expected_image)
    create_file(other_date_image)

    result = find_daily_images(
        images_root=images_root,
        processing_date=PROCESSING_DATE,
        supported_extensions=(".jpg",),
    )

    assert result == [
        expected_image
    ]


def test_find_daily_images_ignores_unsupported_extensions(
    tmp_path,
):
    images_root = tmp_path / "images"

    expected_image = (
        images_root
        / "house_01"
        / "2026"
        / "06"
        / "15"
        / "cage_001.jpg"
    )

    unsupported_file = (
        images_root
        / "house_01"
        / "2026"
        / "06"
        / "15"
        / "metadata.txt"
    )

    create_file(expected_image)
    create_file(unsupported_file)

    result = find_daily_images(
        images_root=images_root,
        processing_date=PROCESSING_DATE,
        supported_extensions=(".jpg",),
    )

    assert result == [
        expected_image
    ]


def test_find_daily_images_returns_empty_list_when_day_has_no_images(
    tmp_path,
):
    images_root = tmp_path / "images"

    images_root.mkdir()

    result = find_daily_images(
        images_root=images_root,
        processing_date=PROCESSING_DATE,
        supported_extensions=(".jpg",),
    )

    assert result == []


def test_find_daily_images_raises_error_when_root_does_not_exist(
    tmp_path,
):
    images_root = tmp_path / "missing"

    with pytest.raises(
        FileNotFoundError,
        match="Images root directory not found",
    ):
        find_daily_images(
            images_root=images_root,
            processing_date=PROCESSING_DATE,
            supported_extensions=(".jpg",),
        )


def test_find_daily_images_raises_error_when_extensions_are_empty(
    tmp_path,
):
    images_root = tmp_path / "images"

    images_root.mkdir()

    with pytest.raises(
        ValueError,
        match="supported_extensions cannot be empty",
    ):
        find_daily_images(
            images_root=images_root,
            processing_date=PROCESSING_DATE,
            supported_extensions=(),
        )