from __future__ import annotations

import hashlib
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

OUTPUT_ROOT = Path("data") / "outputs"

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
# SIMULATION CONFIGURATION
# ============================================================

# Persistent spatial anomaly:
# farm_02 / house 2 / battery 4 / final 10%.
ANOMALY_FARM = "farm_02"
ANOMALY_HOUSE = 2
ANOMALY_BATTERY = 4
ANOMALY_END_FRACTION = 0.10


# Temporary production decrease:
# farm_03 shows lower egg production on day 4.
TEMPORAL_ANOMALY_FARM = "farm_03"
TEMPORAL_ANOMALY_DATE = date(2026, 8, 4)
TEMPORAL_PRODUCTION_FACTOR = 0.65


# Small proportion of technical inference errors.
TECHNICAL_ERROR_RATE = 0.003


# Normal daily production variation.
DAILY_PRODUCTION_FACTORS = {
    date(2026, 8, 1): 1.00,
    date(2026, 8, 2): 0.98,
    date(2026, 8, 3): 1.02,
    date(2026, 8, 4): 1.00,
    date(2026, 8, 5): 1.01,
}


# ============================================================
# OUTPUT SCHEMA
# ============================================================

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


# ============================================================
# MASTER DATA STRUCTURE
# ============================================================

FARMS = {
    "farm_01": {
        "houses": {
            1: {
                1: {"levels": 2, "cages_per_side": 250},
                2: {"levels": 3, "cages_per_side": 300},
                3: {"levels": 4, "cages_per_side": 400},
                4: {"levels": 3, "cages_per_side": 500},
            },
            2: {
                1: {"levels": 2, "cages_per_side": 300},
                2: {"levels": 3, "cages_per_side": 400},
                3: {"levels": 4, "cages_per_side": 500},
            },
        },
    },

    "farm_02": {
        "houses": {
            1: {
                1: {"levels": 3, "cages_per_side": 250},
                2: {"levels": 4, "cages_per_side": 350},
                3: {"levels": 2, "cages_per_side": 500},
            },
            2: {
                1: {"levels": 2, "cages_per_side": 250},
                2: {"levels": 3, "cages_per_side": 350},
                3: {"levels": 4, "cages_per_side": 450},
                4: {"levels": 2, "cages_per_side": 500},
            },
        },
    },

    "farm_03": {
        "houses": {
            1: {
                1: {"levels": 4, "cages_per_side": 250},
                2: {"levels": 3, "cages_per_side": 300},
                3: {"levels": 2, "cages_per_side": 400},
                4: {"levels": 4, "cages_per_side": 500},
            },
            2: {
                1: {"levels": 2, "cages_per_side": 300},
                2: {"levels": 3, "cages_per_side": 400},
                3: {"levels": 4, "cages_per_side": 500},
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

    cage_id starts at 1000 in each house and continues across
    all batteries of that house.
    """

    cages: list[dict] = []

    for farm_id, farm_data in FARMS.items():

        for house_number, batteries in farm_data["houses"].items():

            next_cage_id = 1000

            for battery_number in sorted(batteries):

                battery = batteries[battery_number]

                number_of_levels = battery["levels"]
                cages_per_side = battery["cages_per_side"]

                for level in range(
                    1,
                    number_of_levels + 1,
                ):

                    for side in ("FRONT", "BACK"):

                        for position in range(
                            1,
                            cages_per_side + 1,
                        ):

                            cages.append(
                                {
                                    "farm_id": farm_id,
                                    "house_number": house_number,
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
    Validate that cage_id is unique inside every house.
    """

    seen: set[tuple[str, int, int]] = set()

    for cage in cages:

        key = (
            cage["farm_id"],
            cage["house_number"],
            cage["cage_id"],
        )

        if key in seen:
            raise RuntimeError(
                "Duplicate cage_id detected inside a house: "
                f"{key}"
            )

        seen.add(key)


# ============================================================
# DETERMINISTIC CAGE CHARACTERISTICS
# ============================================================

def stable_random_value(
    *values: object,
) -> float:
    """
    Generate a deterministic value between 0 and 1 from a key.

    This makes the same cage behave similarly across different days.
    """

    key = "|".join(
        str(value)
        for value in values
    )

    digest = hashlib.sha256(
        key.encode("utf-8")
    ).hexdigest()

    integer_value = int(
        digest[:12],
        16,
    )

    return (
        integer_value
        / int("f" * 12, 16)
    )


def get_cage_productivity(
    cage: dict,
) -> float:
    """
    Give each cage a persistent productivity factor.

    Values are approximately between 0.90 and 1.10.
    """

    value = stable_random_value(
        cage["farm_id"],
        cage["house_number"],
        cage["cage_id"],
    )

    return 0.90 + (0.20 * value)


# ============================================================
# ANOMALIES
# ============================================================

def is_spatial_anomaly(
    cage: dict,
) -> bool:
    """
    Persistent anomaly at the final 10% of one battery.
    """

    if cage["farm_id"] != ANOMALY_FARM:
        return False

    if cage["house_number"] != ANOMALY_HOUSE:
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


def get_temporal_factor(
    farm_id: str,
    processing_date: date,
) -> float:
    """
    Return the production factor associated with farm and date.
    """

    factor = DAILY_PRODUCTION_FACTORS.get(
        processing_date,
        1.0,
    )

    if (
        farm_id == TEMPORAL_ANOMALY_FARM
        and processing_date == TEMPORAL_ANOMALY_DATE
    ):
        factor *= TEMPORAL_PRODUCTION_FACTOR

    return factor


# ============================================================
# TECHNICAL ERRORS
# ============================================================

def generate_technical_error() -> str | None:
    """
    Generate occasional technical inference errors.
    """

    if random.random() >= TECHNICAL_ERROR_RATE:
        return None

    return random.choice(
        [
            "RuntimeError: YOLO inference failed",
            "OSError: Could not read image",
            "ValueError: Invalid image input",
        ]
    )


# ============================================================
# MOCK PHENOTYPE
# ============================================================

def generate_egg_count(
    cage: dict,
    processing_date: date,
) -> int:
    """
    Generate the simulated egg count.

    The result includes:
        - persistent cage variability;
        - normal day-to-day variation;
        - one temporary farm-level decrease;
        - one persistent spatial anomaly.
    """

    if is_spatial_anomaly(cage):
        return 0

    cage_productivity = get_cage_productivity(
        cage
    )

    temporal_factor = get_temporal_factor(
        farm_id=cage["farm_id"],
        processing_date=processing_date,
    )

    productivity = (
        cage_productivity
        * temporal_factor
    )

    # Base probabilities roughly centred around one egg/cage.
    probability_zero = 0.07
    probability_two = 0.07

    # Lower productivity increases the probability of zero eggs.
    if productivity < 1.0:

        difference = 1.0 - productivity

        probability_zero += (
            difference * 1.2
        )

        probability_two -= (
            difference * 0.4
        )

    # Higher productivity increases the probability of two eggs.
    elif productivity > 1.0:

        difference = productivity - 1.0

        probability_two += (
            difference * 0.8
        )

        probability_zero -= (
            difference * 0.3
        )

    probability_zero = max(
        0.01,
        min(
            probability_zero,
            0.60,
        ),
    )

    probability_two = max(
        0.01,
        min(
            probability_two,
            0.25,
        ),
    )

    probability_one = (
        1.0
        - probability_zero
        - probability_two
    )

    return random.choices(
        population=[
            0,
            1,
            2,
        ],
        weights=[
            probability_zero,
            probability_one,
            probability_two,
        ],
        k=1,
    )[0]


def generate_confidence(
    egg_count: int,
) -> float | None:
    """
    Generate mean YOLO confidence.
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
    Example:

    data/outputs/
        farm_01/
            2026/
                08/
                    01/
                        egg_prediction.csv
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

    rows: list[dict] = []

    farm_cages = [
        cage
        for cage in cages
        if cage["farm_id"] == farm_id
    ]

    for index, cage in enumerate(
        farm_cages
    ):

        technical_error = (
            generate_technical_error()
        )

        if technical_error is not None:

            egg_count = None
            confidence = None
            inference_status = "ERROR"
            error_message = technical_error

            # Failed inference is slightly slower.
            inference_duration_ms = random.randint(
                250,
                600,
            )

        else:

            egg_count = generate_egg_count(
                cage=cage,
                processing_date=processing_date,
            )

            confidence = generate_confidence(
                egg_count=egg_count
            )

            inference_status = "SUCCESS"
            error_message = None

            inference_duration_ms = random.randint(
                80,
                220,
            )

        image_name = (
            f"cage_{cage['cage_id']}.jpg"
        )

        image_path = (
            f"/data/images/"
            f"{farm_id}/"
            f"house_{cage['house_number']:02d}/"
            f"{processing_date.year:04d}/"
            f"{processing_date.month:02d}/"
            f"{processing_date.day:02d}/"
            f"{image_name}"
        )

        # Simulated image size.
        image_size_bytes = random.randint(
            120_000,
            850_000,
        )

        # Daily processing starts at 11:00 UTC.
        inference_started_at = datetime(
            processing_date.year,
            processing_date.month,
            processing_date.day,
            11,
            0,
            tzinfo=timezone.utc,
        )

        # Simulate sequential inference start times.
        inference_started_at += timedelta(
            milliseconds=index * 50
        )

        rows.append(
            {
                "farm_id": farm_id,
                "house_number": cage["house_number"],
                "cage_id": cage["cage_id"],
                "capture_date": processing_date.isoformat(),
                "processing_date": processing_date.isoformat(),
                "image_name": image_name,
                "image_path": image_path,
                "image_size_bytes": image_size_bytes,
                "egg_count": egg_count,
                "confidence": confidence,
                "registered_model_name": REGISTERED_MODEL_NAME,
                "model_version": MODEL_VERSION,
                "model_alias": MODEL_ALIAS,
                "model_synchronized_at": MODEL_SYNCHRONIZED_AT,
                "inference_started_at": inference_started_at.isoformat(),
                "inference_duration_ms": inference_duration_ms,
                "inference_status": inference_status,
                "error_message": error_message,
            }
        )

    return pd.DataFrame(
        rows,
        columns=CSV_FIELD_NAMES,
    )


# ============================================================
# SAVE DAILY RESULTS
# ============================================================

def save_daily_results(
    dataframe: pd.DataFrame,
    farm_id: str,
    processing_date: date,
) -> Path:
    """
    Save one daily inference CSV for one farm.
    """

    output_file = build_output_file(
        farm_id=farm_id,
        processing_date=processing_date,
    )

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    dataframe.to_csv(
        output_file,
        index=False,
    )

    return output_file


# ============================================================
# SUMMARY
# ============================================================

def print_daily_summary(
    dataframe: pd.DataFrame,
    farm_id: str,
    processing_date: date,
    output_file: Path,
) -> None:
    """
    Print a simple summary of each generated file.
    """

    total = len(dataframe)

    success = (
        dataframe["inference_status"]
        .eq("SUCCESS")
        .sum()
    )

    errors = (
        dataframe["inference_status"]
        .eq("ERROR")
        .sum()
    )

    success_pct = (
        success / total * 100
        if total > 0
        else 0
    )

    print(
        f"{farm_id} | "
        f"{processing_date} | "
        f"{total:,} images | "
        f"{success:,} successful "
        f"({success_pct:.2f}%) | "
        f"{errors:,} errors"
    )

    print(
        f"  -> {output_file.resolve()}"
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    # Reproducible simulation.
    random.seed(
        RANDOM_SEED
    )

    print(
        f"Output root: "
        f"{OUTPUT_ROOT.resolve()}"
    )

    # Generate master cage structure.
    cages = generate_all_cages()

    # Validate cage identifiers.
    validate_cages(
        cages
    )

    print(
        f"Generated cage structure: "
        f"{len(cages):,} cages"
    )

    print()

    # Generate one CSV per farm and day.
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

            dataframe = generate_daily_results(
                cages=cages,
                farm_id=farm_id,
                processing_date=processing_date,
            )

            output_file = save_daily_results(
                dataframe=dataframe,
                farm_id=farm_id,
                processing_date=processing_date,
            )

            print_daily_summary(
                dataframe=dataframe,
                farm_id=farm_id,
                processing_date=processing_date,
                output_file=output_file,
            )

    print()
    print(
        "Mock inference generation completed."
    )


if __name__ == "__main__":
    main()