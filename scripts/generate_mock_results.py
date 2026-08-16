from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

OUTPUT_ROOT = Path("data\outputs")

START_DATE = date(2026, 8, 1)
NUMBER_OF_DAYS = 5

RANDOM_SEED = 42


# ============================================================
# MODEL METADATA
# ============================================================

REGISTERED_MODEL_NAME = "egg_counter"
MODEL_VERSION = "4"
MODEL_ALIAS = "production"

MODEL_SYNCHRONIZED_AT = "2026-08-01T08:00:00+00:00"


# ============================================================
# ANOMALY CONFIGURATION
# ============================================================
# Simulated anomaly:
#
# farm_02
# house 2
# battery 4
# final 10% of the battery
#
# All cages in this zone will return egg_count = 0
# during all five days.

ANOMALY_FARM = "farm_02"
ANOMALY_HOUSE = 2
ANOMALY_BATTERY = 4
ANOMALY_END_FRACTION = 0.10


# ============================================================
# OUTPUT SCHEMA
# ============================================================

CSV_FIELD_NAMES = [
    "farm_id",
    "house_id",
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


# ============================================================
# MASTER DATA STRUCTURE
#
# This structure must match the sample master data stored
# in the relational database.
# ============================================================

FARMS = {
    "farm_01": {
        "houses": {
            1: {
                1: {
                    "levels": 2,
                    "cages_per_side": 250,
                },
                2: {
                    "levels": 3,
                    "cages_per_side": 300,
                },
                3: {
                    "levels": 4,
                    "cages_per_side": 400,
                },
                4: {
                    "levels": 3,
                    "cages_per_side": 500,
                },
            },
            2: {
                1: {
                    "levels": 2,
                    "cages_per_side": 300,
                },
                2: {
                    "levels": 3,
                    "cages_per_side": 400,
                },
                3: {
                    "levels": 4,
                    "cages_per_side": 500,
                },
            },
        },
    },

    "farm_02": {
        "houses": {
            1: {
                1: {
                    "levels": 3,
                    "cages_per_side": 250,
                },
                2: {
                    "levels": 4,
                    "cages_per_side": 350,
                },
                3: {
                    "levels": 2,
                    "cages_per_side": 500,
                },
            },
            2: {
                1: {
                    "levels": 2,
                    "cages_per_side": 250,
                },
                2: {
                    "levels": 3,
                    "cages_per_side": 350,
                },
                3: {
                    "levels": 4,
                    "cages_per_side": 450,
                },
                4: {
                    "levels": 2,
                    "cages_per_side": 500,
                },
            },
        },
    },

    "farm_03": {
        "houses": {
            1: {
                1: {
                    "levels": 4,
                    "cages_per_side": 250,
                },
                2: {
                    "levels": 3,
                    "cages_per_side": 300,
                },
                3: {
                    "levels": 2,
                    "cages_per_side": 400,
                },
                4: {
                    "levels": 4,
                    "cages_per_side": 500,
                },
            },
            2: {
                1: {
                    "levels": 2,
                    "cages_per_side": 300,
                },
                2: {
                    "levels": 3,
                    "cages_per_side": 400,
                },
                3: {
                    "levels": 4,
                    "cages_per_side": 500,
                },
            },
        },
    },
}


# ============================================================
# MASTER DATA GENERATION
# ============================================================

def generate_all_cages() -> list[dict]:
    """
    Generate the physical cage structure.

    cage_id starts at 1000 for every house and continues
    sequentially across all batteries of that house.

    Therefore:
        - cage_id is unique inside one house;
        - cage_id may be repeated in another house.
    """

    cages: list[dict] = []

    for farm_id, farm_data in FARMS.items():

        for house_id, batteries in farm_data["houses"].items():

            next_cage_id = 1000

            for battery_number in sorted(batteries):

                battery = batteries[battery_number]

                number_of_levels = battery["levels"]
                cages_per_side = battery["cages_per_side"]

                for level in range(
                    1,
                    number_of_levels + 1,
                ):

                    for side in (
                        "FRONT",
                        "BACK",
                    ):

                        for position in range(
                            1,
                            cages_per_side + 1,
                        ):

                            cages.append(
                                {
                                    "farm_id": farm_id,
                                    "house_id": house_id,
                                    "battery_number": battery_number,
                                    "cage_id": next_cage_id,
                                    "level": level,
                                    "side": side,
                                    "position": position,
                                    "cages_per_side": cages_per_side,
                                }
                            )

                            next_cage_id += 1

    return cages


# ============================================================
# MASTER DATA VALIDATION
# ============================================================

def validate_cages(
    cages: list[dict],
) -> None:
    """
    Validate that cage_id is unique inside each house.
    """

    seen: set[tuple[str, int, int]] = set()

    for cage in cages:

        key = (
            cage["farm_id"],
            cage["house_id"],
            cage["cage_id"],
        )

        if key in seen:
            raise RuntimeError(
                "Duplicate cage_id detected inside a house: "
                f"{key}"
            )

        seen.add(key)


# ============================================================
# ANOMALY
# ============================================================

def is_anomalous_cage(
    cage: dict,
) -> bool:
    """
    Check whether a cage belongs to the simulated anomalous zone.

    The anomalous zone corresponds to the last 10% of positions in:

        farm_02
        house 2
        battery 4

    The anomaly affects every level and both battery sides.
    """

    if cage["farm_id"] != ANOMALY_FARM:
        return False

    if cage["house_id"] != ANOMALY_HOUSE:
        return False

    if cage["battery_number"] != ANOMALY_BATTERY:
        return False

    first_anomalous_position = (
        int(
            cage["cages_per_side"]
            * (1 - ANOMALY_END_FRACTION)
        )
        + 1
    )

    return (
        cage["position"]
        >= first_anomalous_position
    )


# ============================================================
# MOCK INFERENCE VALUES
# ============================================================

def generate_egg_count(
    anomalous: bool,
) -> int:
    """
    Generate the simulated egg count.

    Normal cages mostly contain one egg.
    The anomalous zone always returns zero.
    """

    if anomalous:
        return 0

    return random.choices(
        population=[
            0,
            1,
            2,
        ],
        weights=[
            0.05,
            0.90,
            0.05,
        ],
        k=1,
    )[0]


def generate_confidence(
    egg_count: int,
) -> float | None:
    """
    Generate a mock mean detection confidence.

    Confidence is None when no egg is detected.
    """

    if egg_count == 0:
        return None

    return round(
        random.uniform(
            0.80,
            0.99,
        ),
        6,
    )


# ============================================================
# OUTPUT PATH
# ============================================================

def build_output_file(
    farm_id: str,
    processing_date: date,
) -> Path:
    """
    Build the daily output path.

    Example:

        /data/outputs/
        └── farm_01/
            └── 2026/
                └── 08/
                    └── 16/
                        └── egg_prediction.csv
    """

    return (
        OUTPUT_ROOT
        / farm_id
        / f"{processing_date.year:04d}"
        / f"{processing_date.month:02d}"
        / f"{processing_date.day:02d}"
        / "egg_prediction.csv"
    )


# ============================================================
# DAILY MOCK INFERENCE
# ============================================================

def generate_daily_results(
    cages: list[dict],
    farm_id: str,
    processing_date: date,
) -> pd.DataFrame:
    """
    Generate one mock inference result per cage for one farm and day.
    """

    rows: list[dict] = []

    farm_cages = [
        cage
        for cage in cages
        if cage["farm_id"] == farm_id
    ]

    for index, cage in enumerate(
        farm_cages
    ):

        anomalous = is_anomalous_cage(
            cage
        )

        egg_count = generate_egg_count(
            anomalous=anomalous
        )

        confidence = generate_confidence(
            egg_count=egg_count
        )

        image_name = (
            f"cage_{cage['cage_id']}.jpg"
        )

        image_path = (
            f"/data/images/"
            f"{farm_id}/"
            f"house_{cage['house_id']:02d}/"
            f"{processing_date.year:04d}/"
            f"{processing_date.month:02d}/"
            f"{processing_date.day:02d}/"
            f"{image_name}"
        )

        inference_started_at = datetime(
            processing_date.year,
            processing_date.month,
            processing_date.day,
            11,
            0,
            tzinfo=timezone.utc,
        )

        inference_started_at += timedelta(
            milliseconds=index * 50
        )

        rows.append(
            {
                "farm_id": farm_id,
                "house_id": str(
                    cage["house_id"]
                ),
                "cage_id": str(
                    cage["cage_id"]
                ),
                "capture_date": (
                    processing_date.isoformat()
                ),
                "processing_date": (
                    processing_date.isoformat()
                ),
                "image_name": image_name,
                "image_path": image_path,
                "image_size_bytes": random.randint(
                    100_000,
                    500_000,
                ),
                "egg_count": egg_count,
                "confidence": confidence,
                "registered_model_name": (
                    REGISTERED_MODEL_NAME
                ),
                "model_version": (
                    MODEL_VERSION
                ),
                "model_alias": (
                    MODEL_ALIAS
                ),
                "model_synchronized_at": (
                    MODEL_SYNCHRONIZED_AT
                ),
                "inference_started_at": (
                    inference_started_at.isoformat()
                ),
                "inference_duration_ms": round(
                    random.uniform(
                        15.0,
                        80.0,
                    ),
                    3,
                ),
                "inference_status": "SUCCESS",
                "error_message": None,
            }
        )

    return pd.DataFrame(
        rows,
        columns=CSV_FIELD_NAMES,
    )


# ============================================================
# VALIDATE GENERATED RESULTS
# ============================================================

def validate_daily_results(
    results: pd.DataFrame,
    expected_cages: int,
    farm_id: str,
    processing_date: date,
) -> None:
    """
    Validate the generated mock inference file.
    """

    if list(results.columns) != CSV_FIELD_NAMES:
        raise RuntimeError(
            "The generated CSV schema does not match "
            "CSV_FIELD_NAMES."
        )

    if len(results) != expected_cages:
        raise RuntimeError(
            f"Unexpected number of rows for {farm_id}. "
            f"Expected {expected_cages}, "
            f"generated {len(results)}."
        )

    if not (
        results["farm_id"] == farm_id
    ).all():
        raise RuntimeError(
            "Results contain rows from another farm."
        )

    expected_date = (
        processing_date.isoformat()
    )

    if not (
        results["processing_date"]
        == expected_date
    ).all():
        raise RuntimeError(
            "Invalid processing_date detected."
        )


# ============================================================
# SUMMARY
# ============================================================

def print_master_data_summary(
    cages: list[dict],
) -> None:

    print()
    print("MASTER DATA SUMMARY")
    print("=" * 60)

    for farm_id in FARMS:

        farm_cages = [
            cage
            for cage in cages
            if cage["farm_id"] == farm_id
        ]

        print(
            f"{farm_id}: "
            f"{len(farm_cages):,} cages"
        )

        house_ids = sorted(
            {
                cage["house_id"]
                for cage in farm_cages
            }
        )

        for house_id in house_ids:

            house_cages = [
                cage
                for cage in farm_cages
                if cage["house_id"]
                == house_id
            ]

            print(
                f"  house {house_id}: "
                f"{len(house_cages):,} cages"
            )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    random.seed(
        RANDOM_SEED
    )

    cages = generate_all_cages()

    validate_cages(
        cages
    )

    print_master_data_summary(
        cages
    )

    print()
    print("GENERATING MOCK INFERENCE RESULTS")
    print("=" * 60)

    for day_offset in range(
        NUMBER_OF_DAYS
    ):

        processing_date = (
            START_DATE
            + timedelta(
                days=day_offset
            )
        )

        for farm_id in FARMS:

            farm_cages = [
                cage
                for cage in cages
                if cage["farm_id"]
                == farm_id
            ]

            daily_results = (
                generate_daily_results(
                    cages=cages,
                    farm_id=farm_id,
                    processing_date=processing_date,
                )
            )

            validate_daily_results(
                results=daily_results,
                expected_cages=len(
                    farm_cages
                ),
                farm_id=farm_id,
                processing_date=processing_date,
            )

            output_file = (
                build_output_file(
                    farm_id=farm_id,
                    processing_date=processing_date,
                )
            )

            output_file.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            daily_results.to_csv(
                output_file,
                index=False,
            )

            print(
                f"{farm_id} | "
                f"{processing_date} | "
                f"{len(daily_results):,} rows | "
                f"{output_file}"
            )

    # Validate anomaly definition.
    anomalous_cages = [
        cage
        for cage in cages
        if is_anomalous_cage(cage)
    ]

    print()
    print("SIMULATED ANOMALY")
    print("=" * 60)

    print(
        f"Farm: {ANOMALY_FARM}"
    )

    print(
        f"House: {ANOMALY_HOUSE}"
    )

    print(
        f"Battery: {ANOMALY_BATTERY}"
    )

    print(
        "Zone: final 10% "
        "of the battery"
    )

    print(
        f"Affected cages per day: "
        f"{len(anomalous_cages):,}"
    )


if __name__ == "__main__":
    main()