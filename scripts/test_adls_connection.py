from pathlib import Path

from azure.identity import AzureCliCredential
from azure.storage.filedatalake import DataLakeServiceClient


STORAGE_ACCOUNT_NAME = "mastermmf001sta"
FILE_SYSTEM_NAME = "landing"

LOCAL_FILE = Path(
    r"C:\Users\monic\Desktop\Cursos\Master\TFM\codigo"
    r"\poultry-edge-cloud-platform\data\outputs"
    r"\farm_01\2026\08\01\egg_prediction.csv"
)

REMOTE_PATH = "farm_01/2026/08/01/egg_prediction.csv"


def main() -> None:
    # --------------------------------------------------------
    # Authenticate using the current Azure CLI session
    # --------------------------------------------------------

    credential = AzureCliCredential()

    service_client = DataLakeServiceClient(
        account_url=(
            f"https://{STORAGE_ACCOUNT_NAME}.dfs.core.windows.net"
        ),
        credential=credential,
    )

    file_system_client = (
        service_client.get_file_system_client(
            FILE_SYSTEM_NAME
        )
    )

    # --------------------------------------------------------
    # Check local file
    # --------------------------------------------------------

    if not LOCAL_FILE.is_file():
        raise FileNotFoundError(
            f"Local file not found: {LOCAL_FILE}"
        )

    print(f"Local file: {LOCAL_FILE}")
    print(f"Remote path: {REMOTE_PATH}")

    # --------------------------------------------------------
    # Upload
    # --------------------------------------------------------

    file_client = file_system_client.get_file_client(
        REMOTE_PATH
    )

    with LOCAL_FILE.open("rb") as local_file:
        file_client.upload_data(
            local_file,
            overwrite=True,
        )

    print("Upload completed successfully.")


if __name__ == "__main__":
    main()