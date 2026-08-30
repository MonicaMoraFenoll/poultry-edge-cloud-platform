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


# ============================================================
# Installation paths
# ============================================================

CONFIG_DIRECTORY="$INSTALL_ROOT/config"
DATA_DIRECTORY="$INSTALL_ROOT/data"

IMAGES_DIRECTORY="$DATA_DIRECTORY/images"
OUTPUTS_DIRECTORY="$DATA_DIRECTORY/outputs"
MODELS_DIRECTORY="$DATA_DIRECTORY/models"
STATE_DIRECTORY="$DATA_DIRECTORY/state"

SCRIPTS_DIRECTORY="$INSTALL_ROOT/scripts"
ENV_DIRECTORY="$INSTALL_ROOT/env"


ACTIVE_CONFIG_FILE="$CONFIG_DIRECTORY/edge.yaml"
ENV_FILE="$ENV_DIRECTORY/poultry-edge.env"

RUN_EDGE_FILE="$SCRIPTS_DIRECTORY/run_edge.sh"
RUN_UPLOAD_FILE="$SCRIPTS_DIRECTORY/run_upload.sh"


# ============================================================
# Deployment sources
# ============================================================

RUN_EDGE_SOURCE="$SCRIPT_DIRECTORY/run_edge.sh"
RUN_UPLOAD_SOURCE="$SCRIPT_DIRECTORY/run_upload.sh"

SERVICE_SOURCE="$SCRIPT_DIRECTORY/poultry-edge.service"
TIMER_SOURCE="$SCRIPT_DIRECTORY/poultry-edge.timer"

UPLOAD_SERVICE_SOURCE="$SCRIPT_DIRECTORY/poultry-edge-upload.service"
UPLOAD_TIMER_SOURCE="$SCRIPT_DIRECTORY/poultry-edge-upload.timer"


# ============================================================
# systemd targets
# ============================================================

SERVICE_TARGET="/etc/systemd/system/poultry-edge.service"
TIMER_TARGET="/etc/systemd/system/poultry-edge.timer"

UPLOAD_SERVICE_TARGET="/etc/systemd/system/poultry-edge-upload.service"
UPLOAD_TIMER_TARGET="/etc/systemd/system/poultry-edge-upload.timer"


# The real Edge installation uses /opt/poultry-edge.
# Alternative roots are treated as simulations and do not modify systemd.
PRODUCTION_INSTALLATION=false

if [[ "$INSTALL_ROOT" == "/opt/poultry-edge" ]]; then
    PRODUCTION_INSTALLATION=true
fi


echo
echo "========================================="
echo " Poultry Edge Installation"
echo "========================================="
echo
echo "Farm configuration : $CONFIG_FILE"
echo "Installation root  : $INSTALL_ROOT"
echo "Production mode    : $PRODUCTION_INSTALLATION"
echo


# ============================================================
# Persistent directory structure
# ============================================================

echo "Creating directory structure..."

mkdir -p "$CONFIG_DIRECTORY"
echo "  ✓ config"

mkdir -p "$IMAGES_DIRECTORY"
echo "  ✓ images"

mkdir -p "$OUTPUTS_DIRECTORY"
echo "  ✓ outputs"

mkdir -p "$MODELS_DIRECTORY"
echo "  ✓ models"

mkdir -p "$STATE_DIRECTORY"
echo "  ✓ state"

mkdir -p "$SCRIPTS_DIRECTORY"
echo "  ✓ scripts"

mkdir -p "$ENV_DIRECTORY"
echo "  ✓ env"

echo


# ============================================================
# Edge configuration
# ============================================================

echo "Installing Edge configuration..."

cp "$CONFIG_FILE" "$ACTIVE_CONFIG_FILE"

if [[ ! -f "$ACTIVE_CONFIG_FILE" ]]; then
    echo "Could not install the Edge configuration." >&2
    exit 1
fi

echo "  ✓ edge.yaml"


# ============================================================
# Environment file
# ============================================================

echo
echo "Preparing environment file..."

# Preserve an existing environment file during updates.
if [[ ! -f "$ENV_FILE" ]]; then
    touch "$ENV_FILE"
fi

echo "  ✓ poultry-edge.env"


# ============================================================
# Execution scripts
# ============================================================

echo
echo "Installing Edge execution scripts..."

cp "$RUN_EDGE_SOURCE" "$RUN_EDGE_FILE"
chmod +x "$RUN_EDGE_FILE"

echo "  ✓ run_edge.sh"

cp "$RUN_UPLOAD_SOURCE" "$RUN_UPLOAD_FILE"
chmod +x "$RUN_UPLOAD_FILE"

echo "  ✓ run_upload.sh"


# ============================================================
# systemd
# ============================================================

if [[ "$PRODUCTION_INSTALLATION" == true ]]; then

    echo
    echo "Installing systemd units..."

    cp "$SERVICE_SOURCE" "$SERVICE_TARGET"
    cp "$TIMER_SOURCE" "$TIMER_TARGET"

    cp "$UPLOAD_SERVICE_SOURCE" "$UPLOAD_SERVICE_TARGET"
    cp "$UPLOAD_TIMER_SOURCE" "$UPLOAD_TIMER_TARGET"

    echo "  ✓ poultry-edge.service"
    echo "  ✓ poultry-edge.timer"
    echo "  ✓ poultry-edge-upload.service"
    echo "  ✓ poultry-edge-upload.timer"


    echo
    echo "Reloading systemd..."

    systemctl daemon-reload

    echo "  ✓ systemd reloaded"


    echo
    echo "Enabling Poultry Edge timers..."

    systemctl enable poultry-edge.timer
    systemctl enable poultry-edge-upload.timer

    systemctl start poultry-edge.timer
    systemctl start poultry-edge-upload.timer

    echo "  ✓ inference timer enabled and started"
    echo "  ✓ upload timer enabled and started"

else

    echo
    echo "Simulation mode:"
    echo "  systemd units are not installed or started."

fi


# ============================================================
# Verification
# ============================================================

echo
echo "Verifying installation..."

required_paths=(
    "$ACTIVE_CONFIG_FILE"
    "$IMAGES_DIRECTORY"
    "$OUTPUTS_DIRECTORY"
    "$MODELS_DIRECTORY"
    "$STATE_DIRECTORY"
    "$ENV_FILE"
    "$RUN_EDGE_FILE"
    "$RUN_UPLOAD_FILE"
)

for path in "${required_paths[@]}"; do
    if [[ ! -e "$path" ]]; then
        echo "Installation verification failed: '$path'." >&2
        exit 1
    fi
done

echo "  ✓ all required Edge paths are available"


if [[ "$PRODUCTION_INSTALLATION" == true ]]; then

    required_systemd_paths=(
        "$SERVICE_TARGET"
        "$TIMER_TARGET"
        "$UPLOAD_SERVICE_TARGET"
        "$UPLOAD_TIMER_TARGET"
    )

    for path in "${required_systemd_paths[@]}"; do
        if [[ ! -e "$path" ]]; then
            echo "systemd installation verification failed: '$path'." >&2
            exit 1
        fi
    done

    if ! systemctl is-enabled poultry-edge.timer >/dev/null 2>&1; then
        echo "Poultry Edge inference timer is not enabled." >&2
        exit 1
    fi

    if ! systemctl is-enabled poultry-edge-upload.timer >/dev/null 2>&1; then
        echo "Poultry Edge upload timer is not enabled." >&2
        exit 1
    fi

    echo "  ✓ systemd timers enabled"

fi


# ============================================================
# Summary
# ============================================================

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
echo "  State   : $STATE_DIRECTORY"

echo
echo "Execution scripts:"
echo "  Inference : $RUN_EDGE_FILE"
echo "  Upload    : $RUN_UPLOAD_FILE"

if [[ "$PRODUCTION_INSTALLATION" == true ]]; then
    echo
    echo "systemd:"
    echo "  Inference service : $SERVICE_TARGET"
    echo "  Inference timer   : $TIMER_TARGET"
    echo "  Upload service    : $UPLOAD_SERVICE_TARGET"
    echo "  Upload timer      : $UPLOAD_TIMER_TARGET"
fi

echo