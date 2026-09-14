from pathlib import Path

from azure.identity import AzureCliCredential
from azure.storage.filedatalake import DataLakeServiceClient


STORAGE_ACCOUNT_NAME = "mastermmf001sta"
FILE_SYSTEM_NAME = "landing"

OUTPUT_ROOT = Path("data") / "outputs"


def main() -> None:
    """
    Upload locally generated Edge result files to Azure Data Lake Storage.

    The script authenticates using the active Azure CLI session, discovers
    all ``egg_prediction.csv`` files below the local output directory, and
    uploads them to the Landing filesystem while preserving their relative
    directory structure.

    Each file is processed independently so that a failed transfer does not
    prevent the remaining files from being uploaded.
    """

    # Use the credentials from the active Azure CLI session.
    credential = AzureCliCredential()

    # Create the client used to communicate with the ADLS Gen2 account.
    service_client = DataLakeServiceClient(
        account_url=(
            f"https://{STORAGE_ACCOUNT_NAME}.dfs.core.windows.net"
        ),
        credential=credential,
    )

    # Access the Landing filesystem where the Edge results are ingested.
    file_system_client = (
        service_client.get_file_system_client(
            FILE_SYSTEM_NAME
        )
    )

    # Discover all daily inference result files generated below
    # the local Edge output root.
    csv_files = sorted(
        OUTPUT_ROOT.rglob("egg_prediction.csv")
    )

    if not csv_files:
        raise FileNotFoundError(
            f"No CSV files found in '{OUTPUT_ROOT}'."
        )

    successful_uploads = 0
    failed_uploads = 0

    for local_file in csv_files:

        # Preserve the local farm/date hierarchy when building
        # the destination path in the Landing filesystem.
        relative_path = local_file.relative_to(
            OUTPUT_ROOT
        )

        remote_path = relative_path.as_posix()

        print()
        print(f"Local file:  {local_file}")
        print(f"Remote path: {remote_path}")

        file_client = (
            file_system_client.get_file_client(
                remote_path
            )
        )

        try:
            # Upload the CSV as binary data and replace an existing
            # destination file when the same path is uploaded again.
            with local_file.open("rb") as file_data:
                file_client.upload_data(
                    file_data,
                    overwrite=True,
                )

            successful_uploads += 1

            print("Upload completed successfully.")

        except Exception as exc:
            # Handle each transfer independently so that one failed
            # upload does not interrupt the remaining files.
            failed_uploads += 1

            print(f"Upload failed: {exc}")

    total_files = len(csv_files)

    success_rate = (
        successful_uploads / total_files * 100
    )

    # Report the overall result of the transfer batch.
    print()
    print("----- TRANSFER SUMMARY -----")
    print(f"Total files:       {total_files}")
    print(f"Successful:        {successful_uploads}")
    print(f"Failed:            {failed_uploads}")
    print(f"Success rate:      {success_rate:.2f} %")


if __name__ == "__main__":
    main()