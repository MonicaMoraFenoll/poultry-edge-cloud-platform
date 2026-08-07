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


SCRIPT_DIRECTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CONFIG_DIRECTORY="$INSTALL_ROOT/config"
DATA_DIRECTORY="$INSTALL_ROOT/data"
IMAGES_DIRECTORY="$DATA_DIRECTORY/images"
OUTPUTS_DIRECTORY="$DATA_DIRECTORY/outputs"
MODELS_DIRECTORY="$DATA_DIRECTORY/models"
SCRIPTS_DIRECTORY="$INSTALL_ROOT/scripts"

ACTIVE_CONFIG_FILE="$CONFIG_DIRECTORY/edge.yaml"
RUN_EDGE_FILE="$SCRIPTS_DIRECTORY/run_edge.sh"

RUN_EDGE_SOURCE="$SCRIPT_DIRECTORY/run_edge.sh"
SERVICE_SOURCE="$SCRIPT_DIRECTORY/poultry-edge.service"
TIMER_SOURCE="$SCRIPT_DIRECTORY/poultry-edge.timer"

SERVICE_TARGET="/etc/systemd/system/poultry-edge.service"
TIMER_TARGET="/etc/systemd/system/poultry-edge.timer"


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

mkdir -p "$SCRIPTS_DIRECTORY"
echo "  ✓ scripts"

echo


echo "Installing Edge configuration..."

cp "$CONFIG_FILE" "$ACTIVE_CONFIG_FILE"

if [[ ! -f "$ACTIVE_CONFIG_FILE" ]]; then
    echo "Could not install the Edge configuration." >&2
    exit 1
fi

echo "  ✓ edge.yaml"


echo
echo "Installing Edge execution script..."

cp "$RUN_EDGE_SOURCE" "$RUN_EDGE_FILE"
chmod +x "$RUN_EDGE_FILE"

echo "  ✓ run_edge.sh"


echo
echo "Installing systemd units..."

cp "$SERVICE_SOURCE" "$SERVICE_TARGET"
cp "$TIMER_SOURCE" "$TIMER_TARGET"

echo "  ✓ poultry-edge.service"
echo "  ✓ poultry-edge.timer"


echo
echo "Reloading systemd..."

systemctl daemon-reload

echo "  ✓ systemd reloaded"


echo
echo "Enabling Poultry Edge timer..."

systemctl enable poultry-edge.timer
systemctl start poultry-edge.timer

echo "  ✓ timer enabled and started"


echo
echo "Verifying installation..."

required_paths=(
    "$ACTIVE_CONFIG_FILE"
    "$IMAGES_DIRECTORY"
    "$OUTPUTS_DIRECTORY"
    "$MODELS_DIRECTORY"
    "$RUN_EDGE_FILE"
    "$SERVICE_TARGET"
    "$TIMER_TARGET"
)

for path in "${required_paths[@]}"; do
    if [[ ! -e "$path" ]]; then
        echo "Installation verification failed: '$path'." >&2
        exit 1
    fi
done

echo "  ✓ all required paths are available"


if ! systemctl is-enabled poultry-edge.timer >/dev/null 2>&1; then
    echo "Poultry Edge timer is not enabled." >&2
    exit 1
fi

echo "  ✓ poultry-edge.timer enabled"


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
echo "Execution:"
echo "  Script  : $RUN_EDGE_FILE"
echo "  Service : $SERVICE_TARGET"
echo "  Timer   : $TIMER_TARGET"

echo