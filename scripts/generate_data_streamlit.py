from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

LANDING_ROOT = Path("data") / "outputs"
OUTPUT_DIR = Path("data") / "dashboard"

PRODUCTION_FILE = OUTPUT_DIR / "production_dashboard.csv"
ANOMALIES_FILE = OUTPUT_DIR / "df_detected_anomalies.csv"

POSITION_GROUP_SIZE = 50


# ============================================================
# MASTER DATA
# ============================================================

# Same physical structure used to create the original mock Landing data.
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
        }
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
        }
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
        }
    },
}


def build_master_cages() -> pd.DataFrame:
    """
    Reconstruct the local master-data mapping used by the mock dataset.

    cage_id starts at 1000 for each house and increases continuously through:
        battery -> level -> side -> position
    """
    rows = []

    for farm_id, farm_cfg in FARMS.items():
        for house_number, batteries in farm_cfg["houses"].items():
            next_cage_id = 1000

            for battery_number in sorted(batteries):
                cfg = batteries[battery_number]

                for level in range(1, cfg["levels"] + 1):
                    for side in ("FRONT", "BACK"):
                        for position in range(1, cfg["cages_per_side"] + 1):
                            rows.append(
                                {
                                    "farm_id": farm_id,
                                    "house_number": house_number,
                                    "cage_id": next_cage_id,
                                    "battery_number": battery_number,
                                    "level": level,
                                    "side": side,
                                    "position": position,
                                    "cages_per_side": cfg["cages_per_side"],
                                }
                            )
                            next_cage_id += 1

    master = pd.DataFrame(rows)

    if master.duplicated(
        ["farm_id", "house_number", "cage_id"]
    ).any():
        raise RuntimeError(
            "Duplicate cage_id inside a house in master data."
        )

    # Physical groups used by the spatial Gold dataset:
    # 1-50 -> 1, 51-100 -> 51, ..., 451-500 -> 451
    master["position_group"] = (
        ((master["position"] - 1) // POSITION_GROUP_SIZE)
        * POSITION_GROUP_SIZE
        + 1
    ).astype(int)

    return master


# ============================================================
# LANDING
# ============================================================

def read_landing_files() -> pd.DataFrame:
    files = sorted(LANDING_ROOT.rglob("egg_prediction.csv"))

    if not files:
        raise FileNotFoundError(
            f"No egg_prediction.csv files found below "
            f"{LANDING_ROOT.resolve()}"
        )

    frames = []

    for file in files:
        df = pd.read_csv(file)
        df["source_file"] = str(file)
        frames.append(df)

    landing = pd.concat(frames, ignore_index=True)

    if "house_number" not in landing.columns:
        if "house_id" not in landing.columns:
            raise KeyError(
                "Landing data needs 'house_number' or 'house_id'."
            )

        landing = landing.rename(
            columns={"house_id": "house_number"}
        )

    required = {
        "farm_id",
        "house_number",
        "cage_id",
        "capture_date",
        "egg_count",
        "inference_status",
    }

    missing = required.difference(landing.columns)

    if missing:
        raise KeyError(
            f"Missing Landing columns: {sorted(missing)}"
        )

    landing["house_number"] = pd.to_numeric(
        landing["house_number"], errors="raise"
    ).astype(int)

    landing["cage_id"] = pd.to_numeric(
        landing["cage_id"], errors="raise"
    ).astype(int)

    landing["capture_date"] = pd.to_datetime(
        landing["capture_date"], errors="raise"
    ).dt.normalize()

    landing["egg_count"] = pd.to_numeric(
        landing["egg_count"], errors="coerce"
    )

    if "confidence" in landing.columns:
        landing["confidence"] = pd.to_numeric(
            landing["confidence"], errors="coerce"
        )

    print(f"Landing files found: {len(files)}")

    return landing


# ============================================================
# SILVER-LIKE ENRICHMENT
# ============================================================

def build_silver(
    landing: pd.DataFrame,
    master: pd.DataFrame,
) -> pd.DataFrame:

    # Keep SUCCESS rows with valid egg_count.
    # confidence may be null when egg_count = 0.
    silver = landing[
        (landing["inference_status"] == "SUCCESS")
        & landing["egg_count"].notna()
    ].copy()

    silver["egg_count"] = silver["egg_count"].astype(int)

    duplicate_keys = [
        col
        for col in [
            "farm_id",
            "house_number",
            "cage_id",
            "capture_date",
            "image_name",
        ]
        if col in silver.columns
    ]

    silver = silver.drop_duplicates(
        subset=duplicate_keys
    )

    enrichment = [
        "farm_id",
        "house_number",
        "cage_id",
        "battery_number",
        "level",
        "side",
        "position",
        "cages_per_side",
        "position_group",
    ]

    silver = silver.merge(
        master[enrichment],
        on=["farm_id", "house_number", "cage_id"],
        how="left",
        validate="many_to_one",
    )

    if silver["battery_number"].isna().any():
        bad = silver.loc[
            silver["battery_number"].isna(),
            ["farm_id", "house_number", "cage_id"],
        ].head(10)

        raise RuntimeError(
            "Some rows could not be enriched with master data:\n"
            + bad.to_string(index=False)
        )

    for col in [
        "battery_number",
        "level",
        "position",
        "cages_per_side",
        "position_group",
    ]:
        silver[col] = silver[col].astype(int)

    return silver


# ============================================================
# GOLD-LIKE DAILY PRODUCTION
# ============================================================

def build_daily_production(
    landing: pd.DataFrame,
    silver: pd.DataFrame,
    master: pd.DataFrame,
) -> pd.DataFrame:

    keys = [
        "farm_id",
        "house_number",
        "battery_number",
        "capture_date",
    ]

    daily = silver.groupby(
        keys,
        as_index=False,
    ).agg(
        n_records=("egg_count", "size"),
        total_egg_count=("egg_count", "sum"),
        mean_egg_count=("egg_count", "mean"),
        median_egg_count=("egg_count", "median"),
        zero_egg_records=(
            "egg_count",
            lambda x: int((x == 0).sum()),
        ),
    )

    daily["zero_egg_rate_pct"] = (
        100
        * daily["zero_egg_records"]
        / daily["n_records"]
    )

    if "confidence" in silver.columns:
        conf = silver.groupby(
            keys,
            as_index=False,
        ).agg(
            mean_confidence=("confidence", "mean")
        )

        daily = daily.merge(
            conf,
            on=keys,
            how="left",
        )
    else:
        daily["mean_confidence"] = np.nan

    # Error rate uses original Landing rows, including ERROR rows.
    landing_err = landing.merge(
        master[
            [
                "farm_id",
                "house_number",
                "cage_id",
                "battery_number",
            ]
        ],
        on=["farm_id", "house_number", "cage_id"],
        how="left",
        validate="many_to_one",
    )

    err = landing_err.groupby(
        keys,
        as_index=False,
    ).agg(
        total_inferences=("inference_status", "size"),
        error_records=(
            "inference_status",
            lambda x: int((x == "ERROR").sum()),
        ),
    )

    err["error_rate_pct"] = (
        100
        * err["error_records"]
        / err["total_inferences"]
    )

    daily = daily.merge(
        err,
        on=keys,
        how="left",
    )

    # Same temporal baseline concept as the anomaly notebook:
    # median of the OTHER available days of the same battery.
    baselines = []

    for _, row in daily.iterrows():
        historical = daily[
            (daily["farm_id"] == row["farm_id"])
            & (
                daily["house_number"]
                == row["house_number"]
            )
            & (
                daily["battery_number"]
                == row["battery_number"]
            )
            & (
                daily["capture_date"]
                != row["capture_date"]
            )
        ]["mean_egg_count"]

        baselines.append(
            historical.median()
            if not historical.empty
            else np.nan
        )

    daily["baseline_median"] = baselines

    daily["deviation_pct"] = np.where(
        daily["baseline_median"].notna()
        & (daily["baseline_median"] != 0),
        (
            (
                daily["mean_egg_count"]
                - daily["baseline_median"]
            )
            / daily["baseline_median"]
            * 100
        ),
        np.nan,
    )

    round_columns = [
        "mean_egg_count",
        "median_egg_count",
        "mean_confidence",
        "zero_egg_rate_pct",
        "error_rate_pct",
        "baseline_median",
        "deviation_pct",
    ]

    for col in round_columns:
        daily[col] = daily[col].round(4)

    return (
        daily.sort_values(keys)
        .reset_index(drop=True)
    )


# ============================================================
# GOLD-LIKE SPATIAL MONITORING
# ============================================================

def build_spatial_monitoring(
    silver: pd.DataFrame,
) -> pd.DataFrame:

    keys = [
        "farm_id",
        "house_number",
        "battery_number",
        "level",
        "side",
        "position_group",
        "capture_date",
    ]

    spatial = silver.groupby(
        keys,
        as_index=False,
    ).agg(
        n_records=("egg_count", "size"),
        total_egg_count=("egg_count", "sum"),
        mean_egg_count=("egg_count", "mean"),
        median_egg_count=("egg_count", "median"),
        zero_egg_records=(
            "egg_count",
            lambda x: int((x == 0).sum()),
        ),

        # Real cage IDs contained in each spatial group.
        cage_id_min=("cage_id", "min"),
        cage_id_max=("cage_id", "max"),
    )

    spatial["zero_egg_rate_pct"] = (
        100
        * spatial["zero_egg_records"]
        / spatial["n_records"]
    )

    if "confidence" in silver.columns:
        conf = silver.groupby(
            keys,
            as_index=False,
        ).agg(
            mean_confidence=("confidence", "mean")
        )

        spatial = spatial.merge(
            conf,
            on=keys,
            how="left",
        )
    else:
        spatial["mean_confidence"] = np.nan

    battery_day = [
        "farm_id",
        "house_number",
        "battery_number",
        "capture_date",
    ]

    medians = spatial.groupby(
        battery_day,
        as_index=False,
    ).agg(
        battery_median_egg_count=(
            "mean_egg_count",
            "median",
        ),
        battery_median_zero_rate=(
            "zero_egg_rate_pct",
            "median",
        ),
    )

    spatial = spatial.merge(
        medians,
        on=battery_day,
        how="left",
    )

    spatial["spatial_deviation_pct"] = np.where(
        spatial["battery_median_egg_count"] != 0,
        (
            (
                spatial["mean_egg_count"]
                - spatial["battery_median_egg_count"]
            )
            / spatial["battery_median_egg_count"]
            * 100
        ),
        np.nan,
    )

    round_columns = [
        "mean_egg_count",
        "median_egg_count",
        "mean_confidence",
        "zero_egg_rate_pct",
        "battery_median_egg_count",
        "battery_median_zero_rate",
        "spatial_deviation_pct",
    ]

    for col in round_columns:
        spatial[col] = spatial[col].round(4)

    spatial["cage_id_min"] = (
        spatial["cage_id_min"].astype(int)
    )
    spatial["cage_id_max"] = (
        spatial["cage_id_max"].astype(int)
    )

    return (
        spatial.sort_values(keys)
        .reset_index(drop=True)
    )


# ============================================================
# DASHBOARD PRODUCTION DATASET
# ============================================================

def build_production_dashboard(
    daily: pd.DataFrame,
    spatial: pd.DataFrame,
) -> pd.DataFrame:

    # One file for Streamlit, keeping spatial resolution
    # plus battery/day metrics.
    keys = [
        "farm_id",
        "house_number",
        "battery_number",
        "capture_date",
    ]

    daily2 = daily.rename(
        columns={
            "n_records": "battery_n_records",
            "total_egg_count": "battery_total_egg_count",
            "mean_egg_count": "battery_mean_egg_count",
            "median_egg_count": "battery_median_egg_count_daily",
            "zero_egg_records": "battery_zero_egg_records",
            "zero_egg_rate_pct": "battery_zero_egg_rate_pct",
            "mean_confidence": "battery_mean_confidence",
            "total_inferences": "battery_total_inferences",
            "error_records": "battery_error_records",
            "error_rate_pct": "battery_error_rate_pct",
            "baseline_median": "temporal_baseline_median",
            "deviation_pct": "temporal_deviation_pct",
        }
    )

    out = spatial.merge(
        daily2,
        on=keys,
        how="left",
        validate="many_to_one",
    )

    return (
        out.sort_values(
            [
                "capture_date",
                "farm_id",
                "house_number",
                "battery_number",
                "level",
                "side",
                "position_group",
            ]
        )
        .reset_index(drop=True)
    )


# ============================================================
# FINAL DETECTED ANOMALIES
# ============================================================

def build_detected_anomalies(
    master: pd.DataFrame,
) -> pd.DataFrame:
    """
    Recreate the same 11 anomaly rows obtained in Databricks.

    For SPATIAL anomalies, cage_id_min and cage_id_max are
    derived from the master mapping so the dashboard can show
    the actual cage IDs instead of only position_group.
    """

    rows = [
        [
            "farm_03", 1, 1, "2026-08-04",
            "TEMPORAL", -47.56, 0.515, 0.982,
            pd.NA, pd.NA, pd.NA, pd.NA,
        ],
        [
            "farm_03", 1, 2, "2026-08-04",
            "TEMPORAL", -45.30, 0.530, 0.969,
            pd.NA, pd.NA, pd.NA, pd.NA,
        ],
        [
            "farm_03", 1, 3, "2026-08-04",
            "TEMPORAL", -48.94, 0.507, 0.993,
            pd.NA, pd.NA, pd.NA, pd.NA,
        ],
        [
            "farm_03", 1, 4, "2026-08-04",
            "TEMPORAL", -46.92, 0.525, 0.989,
            pd.NA, pd.NA, pd.NA, pd.NA,
        ],
        [
            "farm_03", 2, 1, "2026-08-04",
            "TEMPORAL", -47.79, 0.509, 0.975,
            pd.NA, pd.NA, pd.NA, pd.NA,
        ],
        [
            "farm_03", 2, 2, "2026-08-04",
            "TEMPORAL", -45.41, 0.535, 0.980,
            pd.NA, pd.NA, pd.NA, pd.NA,
        ],
        [
            "farm_03", 2, 3, "2026-08-04",
            "TEMPORAL", -47.28, 0.514, 0.975,
            pd.NA, pd.NA, pd.NA, pd.NA,
        ],

        # Persistent spatial anomalies from the Databricks output.
        [
            "farm_02", 2, 4, pd.NaT,
            "SPATIAL", pd.NA, pd.NA, pd.NA,
            1, "FRONT", 451, 100.0,
        ],
        [
            "farm_02", 2, 4, pd.NaT,
            "SPATIAL", pd.NA, pd.NA, pd.NA,
            2, "FRONT", 451, 100.0,
        ],
        [
            "farm_02", 2, 4, pd.NaT,
            "SPATIAL", pd.NA, pd.NA, pd.NA,
            1, "BACK", 451, 100.0,
        ],
        [
            "farm_02", 2, 4, pd.NaT,
            "SPATIAL", pd.NA, pd.NA, pd.NA,
            2, "BACK", 451, 100.0,
        ],
    ]

    columns = [
        "farm_id",
        "house_number",
        "battery_number",
        "capture_date",
        "anomaly_type",
        "deviation_pct",
        "mean_egg_count",
        "baseline_median",
        "level",
        "side",
        "position_group",
        "persistence_pct",
    ]

    anomalies = pd.DataFrame(
        rows,
        columns=columns,
    )

    anomalies["capture_date"] = pd.to_datetime(
        anomalies["capture_date"],
        errors="coerce",
    )

    for col in [
        "house_number",
        "battery_number",
        "level",
        "position_group",
    ]:
        anomalies[col] = pd.to_numeric(
            anomalies[col],
            errors="coerce",
        ).astype("Int64")

    # --------------------------------------------------------
    # Add real cage ID limits to each spatial anomaly.
    # --------------------------------------------------------

    group_limits = (
        master.groupby(
            [
                "farm_id",
                "house_number",
                "battery_number",
                "level",
                "side",
                "position_group",
            ],
            as_index=False,
        )
        .agg(
            cage_id_min=("cage_id", "min"),
            cage_id_max=("cage_id", "max"),
        )
    )

    anomalies = anomalies.merge(
        group_limits,
        on=[
            "farm_id",
            "house_number",
            "battery_number",
            "level",
            "side",
            "position_group",
        ],
        how="left",
        validate="many_to_one",
    )

    # Temporal anomalies do not refer to one spatial cage range.
    temporal_mask = (
        anomalies["anomaly_type"] == "TEMPORAL"
    )

    anomalies.loc[
        temporal_mask,
        ["cage_id_min", "cage_id_max"],
    ] = pd.NA

    anomalies["cage_id_min"] = pd.to_numeric(
        anomalies["cage_id_min"],
        errors="coerce",
    ).astype("Int64")

    anomalies["cage_id_max"] = pd.to_numeric(
        anomalies["cage_id_max"],
        errors="coerce",
    ).astype("Int64")

    final_columns = [
        "farm_id",
        "house_number",
        "battery_number",
        "capture_date",
        "anomaly_type",
        "deviation_pct",
        "mean_egg_count",
        "baseline_median",
        "level",
        "side",
        "position_group",
        "cage_id_min",
        "cage_id_max",
        "persistence_pct",
    ]

    anomalies = anomalies[final_columns]

    return anomalies


# ============================================================
# VALIDATION
# ============================================================

def validate_outputs(
    production: pd.DataFrame,
    anomalies: pd.DataFrame,
) -> None:

    if len(anomalies) != 11:
        raise RuntimeError(
            f"Expected 11 anomalies, got {len(anomalies)}."
        )

    counts = anomalies["anomaly_type"].value_counts()

    if counts.get("TEMPORAL", 0) != 7:
        raise RuntimeError(
            "Expected 7 temporal anomalies."
        )

    if counts.get("SPATIAL", 0) != 4:
        raise RuntimeError(
            "Expected 4 spatial anomalies."
        )

    spatial = anomalies[
        anomalies["anomaly_type"] == "SPATIAL"
    ]

    if (
        spatial["cage_id_min"].isna().any()
        or spatial["cage_id_max"].isna().any()
    ):
        raise RuntimeError(
            "Some spatial anomalies have no cage_id range."
        )

    required_prod_cols = {
        "cage_id_min",
        "cage_id_max",
        "position_group",
        "mean_egg_count",
    }

    missing = required_prod_cols.difference(
        production.columns
    )

    if missing:
        raise RuntimeError(
            "Production dashboard is missing columns: "
            f"{sorted(missing)}"
        )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    print("1/6 Building local master data...")
    master = build_master_cages()
    print(f"  Master cages: {len(master):,}")

    print("2/6 Reading original Landing CSV files...")
    landing = read_landing_files()
    print(f"  Landing rows: {len(landing):,}")

    print(
        "3/6 Applying Silver-like cleaning + "
        "master-data integration..."
    )
    silver = build_silver(
        landing,
        master,
    )
    print(f"  Silver rows: {len(silver):,}")

    print("4/6 Building Gold-like production datasets...")
    daily = build_daily_production(
        landing,
        silver,
        master,
    )

    spatial = build_spatial_monitoring(
        silver
    )

    production = build_production_dashboard(
        daily,
        spatial,
    )

    print(
        f"  Battery/day rows: {len(daily):,}"
    )
    print(
        f"  Spatial rows: {len(spatial):,}"
    )
    print(
        f"  Dashboard rows: {len(production):,}"
    )

    print("5/6 Recreating final detected anomalies...")
    anomalies = build_detected_anomalies(
        master
    )

    validate_outputs(
        production,
        anomalies,
    )

    print(
        "  11 anomalies = "
        "7 temporal + 4 spatial"
    )

    print("  Spatial cage ranges:")

    print(
        anomalies.loc[
            anomalies["anomaly_type"] == "SPATIAL",
            [
                "farm_id",
                "house_number",
                "battery_number",
                "level",
                "side",
                "cage_id_min",
                "cage_id_max",
            ],
        ].to_string(index=False)
    )

    print("6/6 Saving CSV files...")

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    production_out = production.copy()

    production_out["capture_date"] = (
        production_out["capture_date"]
        .dt.strftime("%Y-%m-%d")
    )

    production_out.to_csv(
        PRODUCTION_FILE,
        index=False,
    )

    anomalies_out = anomalies.copy()

    anomalies_out["capture_date"] = (
        anomalies_out["capture_date"]
        .dt.strftime("%Y-%m-%d")
    )

    anomalies_out.to_csv(
        ANOMALIES_FILE,
        index=False,
    )

    print("\nDONE")
    print(f"  {PRODUCTION_FILE}")
    print(f"  {ANOMALIES_FILE}")


if __name__ == "__main__":
    main()
