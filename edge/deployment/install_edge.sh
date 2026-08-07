#!/usr/bin/env bash

set -Eeuo pipefail

usage() {
    cat <<'EOF'
Usage:
  install_edge.sh --config <farm_yaml> [--install-root <directory>]

Options:
  --config
      YAML configuration assigned to this Edge device.

  --install-root
      Root installation directory.

      Default:
          /opt/poultry-edge
EOF
}

CONFIG_FILE=""
INSTALL_ROOT="/opt/poultry-edge"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --install-root)
            INSTALL_ROOT="$2"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: '$1'." >&2
            usage
            exit 2
            ;;
    esac
done

if [[ -z "$CONFIG_FILE" ]]; then
    echo "The --config argument is required." >&2
    exit 2
fi

if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "Farm configuration not found: '$CONFIG_FILE'." >&2
    exit 1
fi

SCRIPT_DIRECTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CONFIG_DIRECTORY="$INSTALL_ROOT/config"
DATA_DIRECTORY="$INSTALL_ROOT/data"
IMAGES_DIRECTORY="$DATA_DIRECTORY/images"
OUTPUTS_DIRECTORY="$DATA_DIRECTORY/outputs"
MODELS_DIRECTORY="$DATA_DIRECTORY/models"
SCRIPTS_DIRECTORY="$INSTALL_ROOT/scripts"

ACTIVE_CONFIG_FILE="$CONFIG_DIRECTORY/edge.yaml"
RUN_EDGE_SOURCE="$SCRIPT_DIRECTORY/run_edge.sh"
RUN_EDGE_TARGET="$SCRIPTS_DIRECTORY/run_edge.sh"

echo "Creating directory structure..."

mkdir -p \
    "$CONFIG_DIRECTORY" \
    "$IMAGES_DIRECTORY" \
    "$OUTPUTS_DIRECTORY" \
    "$MODELS_DIRECTORY" \
    "$SCRIPTS_DIRECTORY"

echo "Installing Edge configuration..."

cp "$CONFIG_FILE" "$ACTIVE_CONFIG_FILE"

echo "Installing Edge execution script..."

cp "$RUN_EDGE_SOURCE" "$RUN_EDGE_TARGET"
chmod +x "$RUN_EDGE_TARGET"

echo "Verifying installation..."

required_paths=(
    "$ACTIVE_CONFIG_FILE"
    "$IMAGES_DIRECTORY"
    "$OUTPUTS_DIRECTORY"
    "$MODELS_DIRECTORY"
    "$RUN_EDGE_TARGET"
)

for path in "${required_paths[@]}"; do
    if [[ ! -e "$path" ]]; then
        echo "Installation verification failed: '$path'." >&2
        exit 1
    fi
done

echo "Edge installation completed successfully."