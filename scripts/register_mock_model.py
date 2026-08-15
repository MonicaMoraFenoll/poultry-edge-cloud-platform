from __future__ import annotations

import argparse
from pathlib import Path

import mlflow
from mlflow import MlflowClient


DEFAULT_TRACKING_URI = "http://127.0.0.1:5000"
DEFAULT_MODEL_NAME = "egg_counter_farm_01"
DEFAULT_ALIAS = "production"
DEFAULT_EXPERIMENT_NAME = "mock-yolo-model-registration"


def register_mock_model(
    model_path: Path,
    model_name: str,
    alias: str,
    tracking_uri: str,
) -> None:
    if not model_path.is_file():
        raise FileNotFoundError(
            f"Mock model file not found: '{model_path}'."
        )

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(DEFAULT_EXPERIMENT_NAME)

    client = MlflowClient(tracking_uri=tracking_uri)

    with mlflow.start_run() as run:
        run_id = run.info.run_id

        mlflow.log_param("model_name", model_name)
        mlflow.log_param("model_file", model_path.name)
        mlflow.log_param("mock_model", True)

        mlflow.log_artifact(
            str(model_path),
            artifact_path="model",
        )

        source = f"runs:/{run_id}/model"

        try:
            client.create_registered_model(model_name)
            print(f"Created registered model: {model_name}")

        except Exception:
            print(
                f"Registered model already exists: {model_name}"
            )

        model_version = client.create_model_version(
            name=model_name,
            source=source,
            run_id=run_id,
            description="Mock YOLO model used to validate Edge model versioning.",
        )

        client.set_registered_model_alias(
            name=model_name,
            alias=alias,
            version=model_version.version,
        )

        print()
        print("Model registered successfully")
        print("-----------------------------")
        print(f"Model name : {model_name}")
        print(f"Version    : {model_version.version}")
        print(f"Alias      : {alias}")
        print(f"Run ID     : {run_id}")
        print(f"Artifact   : {source}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Register a mock YOLO model in the local MLflow Model Registry."
        )
    )

    parser.add_argument(
        "--model-path",
        type=Path,
        required=True,
        help="Path to the mock .pt file.",
    )

    parser.add_argument(
        "--model-name",
        default=DEFAULT_MODEL_NAME,
        help="Registered model name.",
    )

    parser.add_argument(
        "--alias",
        default=DEFAULT_ALIAS,
        help="Alias assigned to the new model version.",
    )

    parser.add_argument(
        "--tracking-uri",
        default=DEFAULT_TRACKING_URI,
        help="MLflow Tracking Server URI.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    register_mock_model(
        model_path=args.model_path,
        model_name=args.model_name,
        alias=args.alias,
        tracking_uri=args.tracking_uri,
    )


if __name__ == "__main__":
    main()