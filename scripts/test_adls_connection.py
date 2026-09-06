from pathlib import Path

from azure.identity import AzureCliCredential
from azure.storage.filedatalake import DataLakeServiceClient


STORAGE_ACCOUNT_NAME = "mastermmf001sta"
FILE_SYSTEM_NAME = "landing"

OUTPUT_ROOT = Path("data") / "outputs"


def main() -> None:
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
            with local_file.open("rb") as file_data:
                file_client.upload_data(
                    file_data,
                    overwrite=True,
                )

            successful_uploads += 1

            print("Upload completed successfully.")

        except Exception as exc:
            failed_uploads += 1

            print(f"Upload failed: {exc}")

    total_files = len(csv_files)

    success_rate = (
        successful_uploads / total_files * 100
    )

    print()
    print("----- TRANSFER SUMMARY -----")
    print(f"Total files:       {total_files}")
    print(f"Successful:        {successful_uploads}")
    print(f"Failed:            {failed_uploads}")
    print(f"Success rate:      {success_rate:.2f} %")


if __name__ == "__main__":
    main()