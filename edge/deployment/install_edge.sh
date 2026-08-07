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

Examples:

  Production installation:
      sudo ./install_edge.sh \
          --config ../config/farm_01.yml

  Local simulation:
      ./install_edge.sh \
          --config ../config/farm_01.yml \
          --install-root ../../../local-edge-simulation/farm_01
EOF
}


CONFIG_FILE=""
INSTALL_ROOT="/opt/poultry-edge"


while [[ $# -gt 0 ]]; do
    case "$1" in
        --config)
            if [[ $# -lt 2 ]]; then
                echo "Missing value for --config." >&2
                usage
                exit 2
            fi

            CONFIG_FILE="$2"
            shift 2
            ;;

        --install-root)
            if [[ $# -lt 2 ]]; then
                echo "Missing value for --install-root." >&2
                usage
                exit 2
            fi

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
    usage
    exit 2
fi


if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "Farm configuration not found: '$CONFIG_FILE'." >&2
    exit 1
fi


CONFIG_DIRECTORY="$INSTALL_ROOT/config"
DATA_DIRECTORY="$INSTALL_ROOT/data"
IMAGES_DIRECTORY="$DATA_DIRECTORY/images"
OUTPUTS_DIRECTORY="$DATA_DIRECTORY/outputs"
MODELS_DIRECTORY="$DATA_DIRECTORY/models"

ACTIVE_CONFIG_FILE="$CONFIG_DIRECTORY/edge.yaml"


echo
echo "========================================="
echo " Poultry Edge Installation"
echo "========================================="
echo
echo "Farm configuration : $CONFIG_FILE"
echo "Installation root  : $INSTALL_ROOT"
echo


echo "Creating directory structure..."

mkdir -p "$CONFIG_DIRECTORY"
echo "  ✓ config"

mkdir -p "$IMAGES_DIRECTORY"
echo "  ✓ images"

mkdir -p "$OUTPUTS_DIRECTORY"
echo "  ✓ outputs"

mkdir -p "$MODELS_DIRECTORY"
echo "  ✓ models"

echo


echo "Installing Edge configuration..."

cp "$CONFIG_FILE" "$ACTIVE_CONFIG_FILE"

if [[ ! -f "$ACTIVE_CONFIG_FILE" ]]; then
    echo "Could not install the Edge configuration." >&2
    exit 1
fi

echo "  ✓ edge.yaml"

echo
echo "Verifying installation..."

required_paths=(
    "$ACTIVE_CONFIG_FILE"
    "$IMAGES_DIRECTORY"
    "$OUTPUTS_DIRECTORY"
    "$MODELS_DIRECTORY"
)

for path in "${required_paths[@]}"; do
    if [[ ! -e "$path" ]]; then
        echo "Installation verification failed: '$path'." >&2
        exit 1
    fi
done

echo "  ✓ all required paths are available"

echo
echo "========================================="
echo " Edge installation completed successfully"
echo "========================================="
echo
echo "Installed configuration:"
echo "  $ACTIVE_CONFIG_FILE"
echo
echo "Persistent directories:"
echo "  Images  : $IMAGES_DIRECTORY"
echo "  Outputs : $OUTPUTS_DIRECTORY"
echo "  Models  : $MODELS_DIRECTORY"
echo