from __future__ import annotations

import argparse
import logging
from pathlib import Path

from poultry_edge.cloud_uploader import (
    create_datalake_service_client,
)
from poultry_edge.config import load_edge_config
from poultry_edge.upload_discovery import (
    discover_and_register_uploads,
)
from poultry_edge.upload_manager import (
    process_pending_uploads,
)
from poultry_edge.upload_state import (
    initialize_upload_database,
)


# ============================================================
# DEFAULT CONFIGURATION
# ============================================================

DEFAULT_CONFIG_PATH = Path(
    "/opt/poultry-edge/config/edge.yaml"
)

STORAGE_ACCOUNT_NAME = "mastermmf001sta"
FILE_SYSTEM_NAME = "landing"


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | %(levelname)s | "
        "%(name)s | %(message)s"
    ),
)

logger = logging.getLogger(__name__)


# ============================================================
# ARGUMENTS
# ============================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Upload pending Edge inference results "
            "to Azure Data Lake Storage."
        )
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=(
            "Path to the Edge YAML configuration file. "
            f"Default: {DEFAULT_CONFIG_PATH}"
        ),
    )

    return parser.parse_args()


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    args = parse_args()

    # --------------------------------------------------------
    # 1. Load Edge configuration
    # --------------------------------------------------------

    config = load_edge_config(
        args.config
    )

    logger.info(
        "Starting upload process for farm '%s'.",
        config.farm.id,
    )

    # --------------------------------------------------------
    # 2. Initialize persistent upload-state database
    # --------------------------------------------------------

    initialize_upload_database(
        config.upload.state_database
    )

    # --------------------------------------------------------
    # 3. Discover new inference results
    # --------------------------------------------------------

    discovered = discover_and_register_uploads(
        output_root=config.outputs.root_directory,
        farm_id=config.farm.id,
        database_path=config.upload.state_database,
    )

    logger.info(
        "Discovered %d result file(s).",
        discovered,
    )

    # --------------------------------------------------------
    # 4. Create Azure Data Lake client
    # --------------------------------------------------------

    service_client = create_datalake_service_client(
        storage_account_name=STORAGE_ACCOUNT_NAME,
    )

    # --------------------------------------------------------
    # 5. Upload PENDING and FAILED files
    # --------------------------------------------------------

    successful, failed = process_pending_uploads(
        database_path=config.upload.state_database,
        service_client=service_client,
        file_system_name=FILE_SYSTEM_NAME,
    )

    # --------------------------------------------------------
    # 6. Summary
    # --------------------------------------------------------

    logger.info(
        "Upload process completed for farm '%s'. "
        "Successful=%d, Failed=%d.",
        config.farm.id,
        successful,
        failed,
    )


if __name__ == "__main__":
    main()