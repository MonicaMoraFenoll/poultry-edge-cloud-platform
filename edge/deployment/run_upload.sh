#!/usr/bin/env bash

set -Eeuo pipefail

CONTAINER_NAME="poultry-edge-upload"

IMAGE="${POULTRY_EDGE_IMAGE:-ghcr.io/OWNER/poultry-edge:latest}"

CONFIG_FILE="${POULTRY_EDGE_CONFIG:-/opt/poultry-edge/config/edge.yaml}"
OUTPUTS_DIR="${POULTRY_EDGE_OUTPUTS:-/opt/poultry-edge/data/outputs}"
STATE_DIR="${POULTRY_EDGE_STATE:-/opt/poultry-edge/data/state}"

echo
echo "========================================="
echo " Poultry Edge Cloud Upload"
echo "========================================="
echo
echo "Docker image  : $IMAGE"
echo "Configuration : $CONFIG_FILE"
echo "Outputs       : $OUTPUTS_DIR"
echo "State         : $STATE_DIR"
echo

if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "Configuration file not found: '$CONFIG_FILE'." >&2
    exit 1
fi

required_directories=(
    "$OUTPUTS_DIR"
    "$STATE_DIR"
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

echo "Starting upload container..."

docker run \
    --rm \
    --name "$CONTAINER_NAME" \
    --mount type=bind,source="$CONFIG_FILE",target=/opt/poultry-edge/config/edge.yaml,readonly \
    --mount type=bind,source="$OUTPUTS_DIR",target=/app/data/outputs,readonly \
    --mount type=bind,source="$STATE_DIR",target=/app/data/state \
    "$IMAGE" \
    poultry-edge-upload

echo
echo "========================================="
echo " Poultry Edge cloud upload completed"
echo "========================================="
echo