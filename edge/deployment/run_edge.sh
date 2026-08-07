#!/usr/bin/env bash

set -Eeuo pipefail

CONTAINER_NAME="poultry-edge"

IMAGE="${POULTRY_EDGE_IMAGE:-ghcr.io/OWNER/poultry-edge:latest}"

CONFIG_FILE="${POULTRY_EDGE_CONFIG:-/opt/poultry-edge/config/edge.yaml}"
IMAGES_DIR="${POULTRY_EDGE_IMAGES:-/opt/poultry-edge/data/images}"
OUTPUTS_DIR="${POULTRY_EDGE_OUTPUTS:-/opt/poultry-edge/data/outputs}"
MODELS_DIR="${POULTRY_EDGE_MODELS:-/opt/poultry-edge/data/models}"


echo
echo "========================================="
echo " Poultry Edge Inference"
echo "========================================="
echo
echo "Docker image  : $IMAGE"
echo "Configuration : $CONFIG_FILE"
echo "Images        : $IMAGES_DIR"
echo "Outputs       : $OUTPUTS_DIR"
echo "Models        : $MODELS_DIR"
echo


if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "Configuration file not found: '$CONFIG_FILE'." >&2
    exit 1
fi

required_directories=(
    "$IMAGES_DIR"
    "$OUTPUTS_DIR"
    "$MODELS_DIR"
)

for directory in "${required_directories[@]}"; do
    if [[ ! -d "$directory" ]]; then
        echo "Required directory not found: '$directory'." >&2
        exit 1
    fi
done


if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is not installed or is not available in PATH." >&2
    exit 1
fi


echo "Starting Docker container..."

docker run \
    --rm \
    --gpus all \
    --name "$CONTAINER_NAME" \
    --env MLFLOW_TRACKING_URI \
    --env MLFLOW_REGISTRY_URI \
    --mount type=bind,source="$CONFIG_FILE",target=/opt/poultry-edge/config/edge.yaml,readonly \
    --mount type=bind,source="$IMAGES_DIR",target=/app/data/images,readonly \
    --mount type=bind,source="$OUTPUTS_DIR",target=/app/data/outputs \
    --mount type=bind,source="$MODELS_DIR",target=/app/models \
    "$IMAGE"

echo
echo "========================================="
echo " Poultry Edge inference completed"
echo "========================================="
echo