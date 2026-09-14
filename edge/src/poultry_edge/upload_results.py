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

# Default location of the Edge configuration file inside the
# deployed environment.
DEFAULT_CONFIG_PATH = Path(
    "/opt/poultry-edge/config/edge.yaml"
)

# Azure Data Lake destination used by the upload process.
STORAGE_ACCOUNT_NAME = "mastermmf001sta"
FILE_SYSTEM_NAME = "landing"


# ============================================================
# LOGGING
# ============================================================

# Configure a common logging format for the complete upload process.
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
    """
    Parse command-line arguments for the upload process.

    Returns
    -------
    argparse.Namespace
        Parsed command-line arguments.

        The returned namespace contains the path to the Edge YAML
        configuration file.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Upload pending Edge inference results "
            "to Azure Data Lake Storage."
        )
    )

    # Allow the configuration path to be overridden while preserving
    # the standard deployment location as the default.
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
    """
    Run the complete Edge-to-cloud upload workflow.

    Workflow:

    1. Parse command-line arguments.
    2. Load the Edge configuration.
    3. Initialize the persistent SQLite upload-state database.
    4. Discover and register locally generated inference results.
    5. Create an authenticated Azure Data Lake client.
    6. Upload files currently marked as PENDING or FAILED.
    7. Log a final summary of successful and failed transfers.

    The local upload-state database allows files that fail during
    transfer to remain registered and be retried in later executions.
    """

    args = parse_args()

    # --------------------------------------------------------
    # 1. Load Edge configuration
    # --------------------------------------------------------

    # Load the farm-specific paths and upload-state configuration.
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

    # Ensure that the SQLite database and upload-state table exist
    # before discovering or processing files.
    initialize_upload_database(
        config.upload.state_database
    )

    # --------------------------------------------------------
    # 3. Discover new inference results
    # --------------------------------------------------------

    # Search the local output hierarchy for egg_prediction.csv files
    # and register any new files in the upload-state database.
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

    # Create the authenticated service client used for all transfers
    # in the current execution.
    service_client = create_datalake_service_client(
        storage_account_name=STORAGE_ACCOUNT_NAME,
    )

    # --------------------------------------------------------
    # 5. Upload PENDING and FAILED files
    # --------------------------------------------------------

    # Process both newly registered files and previous failed transfers
    # that are eligible for retry.
    successful, failed = process_pending_uploads(
        database_path=config.upload.state_database,
        service_client=service_client,
        file_system_name=FILE_SYSTEM_NAME,
    )

    # --------------------------------------------------------
    # 6. Summary
    # --------------------------------------------------------

    # Record the final batch result for operational monitoring.
    logger.info(
        "Upload process completed for farm '%s'. "
        "Successful=%d, Failed=%d.",
        config.farm.id,
        successful,
        failed,
    )


if __name__ == "__main__":
    main()