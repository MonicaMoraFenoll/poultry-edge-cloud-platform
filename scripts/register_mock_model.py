from __future__ import annotations

import argparse
from pathlib import Path

import mlflow
from mlflow import MlflowClient


DEFAULT_TRACKING_URI = "http://127.0.0.1:5000"
DEFAULT_MODEL_NAME = "egg_detector"
DEFAULT_EXPERIMENT_NAME = "mock-yolo-model-registration"


def register_mock_model(
    model_path: Path,
    farm_id: str,
    model_name: str,
    tracking_uri: str,
) -> None:
    if not model_path.is_file():
        raise FileNotFoundError(
            f"Mock model file not found: '{model_path}'."
        )

    alias = f"{farm_id}_production"

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(
        DEFAULT_EXPERIMENT_NAME
    )

    client = MlflowClient(
        tracking_uri=tracking_uri
    )

    with mlflow.start_run() as run:
        run_id = run.info.run_id

        # ----------------------------------------------------
        # Run metadata
        # ----------------------------------------------------

        mlflow.log_param(
            "model_name",
            model_name,
        )

        mlflow.log_param(
            "farm_id",
            farm_id,
        )

        mlflow.log_param(
            "model_file",
            model_path.name,
        )

        mlflow.log_param(
            "mock_model",
            True,
        )

        # ----------------------------------------------------
        # Store model artifact
        # ----------------------------------------------------

        mlflow.log_artifact(
            str(model_path),
            artifact_path="model",
        )

        source = (
            f"runs:/{run_id}/model"
        )

        # ----------------------------------------------------
        # Create registered model if necessary
        # ----------------------------------------------------

        try:
            client.create_registered_model(
                model_name
            )

            print(
                f"Created registered model: "
                f"{model_name}"
            )

        except Exception:
            print(
                f"Registered model already exists: "
                f"{model_name}"
            )

        # ----------------------------------------------------
        # Create new version
        # ----------------------------------------------------

        model_version = (
            client.create_model_version(
                name=model_name,
                source=source,
                run_id=run_id,
                description=(
                    "Mock YOLO egg detection model "
                    f"for {farm_id}."
                ),
            )
        )

        version = str(
            model_version.version
        )

        # ----------------------------------------------------
        # Add version tags
        # ----------------------------------------------------

        client.set_model_version_tag(
            name=model_name,
            version=version,
            key="farm_id",
            value=farm_id,
        )

        client.set_model_version_tag(
            name=model_name,
            version=version,
            key="task",
            value="egg_detection",
        )

        client.set_model_version_tag(
            name=model_name,
            version=version,
            key="model_type",
            value="YOLO",
        )

        client.set_model_version_tag(
            name=model_name,
            version=version,
            key="mock_model",
            value="true",
        )

        # ----------------------------------------------------
        # Assign farm-specific production alias
        # ----------------------------------------------------

        client.set_registered_model_alias(
            name=model_name,
            alias=alias,
            version=version,
        )

        # ----------------------------------------------------
        # Summary
        # ----------------------------------------------------

        print()
        print(
            "Model registered successfully"
        )
        print(
            "-----------------------------"
        )
        print(
            f"Model name : {model_name}"
        )
        print(
            f"Version    : {version}"
        )
        print(
            f"Farm       : {farm_id}"
        )
        print(
            f"Alias      : {alias}"
        )
        print(
            f"Run ID     : {run_id}"
        )
        print(
            f"Artifact   : {source}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Register a mock YOLO model in "
            "MLflow Model Registry."
        )
    )

    parser.add_argument(
        "--model-path",
        type=Path,
        required=True,
        help="Path to the mock .pt file.",
    )

    parser.add_argument(
        "--farm-id",
        required=True,
        help=(
            "Farm identifier associated "
            "with this model version."
        ),
    )

    parser.add_argument(
        "--model-name",
        default=DEFAULT_MODEL_NAME,
        help="Registered model name.",
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
        farm_id=args.farm_id,
        model_name=args.model_name,
        tracking_uri=args.tracking_uri,
    )


if __name__ == "__main__":
    main()