from __future__ import annotations

import logging
import sys
from datetime import date
from pathlib import Path
import os

from .config import load_edge_config
from .pipeline import run_daily_pipeline


# test

logger = logging.getLogger(__name__)


DEFAULT_CONFIG_PATH = Path(
    "/opt/poultry-edge/config/edge.yml"
)


def configure_logging() -> None:
    """
    Configure the application logging.

    Every module uses the same logging configuration.
    """

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        ),
    )


def main() -> int:
    """
    Entry point of the edge application.

    Workflow:

    1. Configure logging.
    2. Load the edge configuration.
    3. Read MLflow connection settings.
    4. Run the daily inference pipeline.
    """

    configure_logging()

    try:
        config = load_edge_config(
            config_path=DEFAULT_CONFIG_PATH,
        )

        logger.info(
            "Configuration loaded for farm '%s'.",
            config.farm.id,
        )

        tracking_uri = os.getenv(
            "MLFLOW_TRACKING_URI"
        )

        registry_uri = os.getenv(
            "MLFLOW_REGISTRY_URI",
            tracking_uri,
        )

        logger.info(
            "MLflow configuration. "
            "Tracking URI='%s', Registry URI='%s'.",
            tracking_uri,
            registry_uri,
        )

        processing_date = date.today()

        run_daily_pipeline(
            config=config,
            processing_date=processing_date,
            tracking_uri=tracking_uri,
            registry_uri=registry_uri,
        )

    except Exception:
        logger.exception(
            "The edge pipeline failed."
        )
        return 1

    logger.info(
        "Edge pipeline finished successfully."
    )

    return 0