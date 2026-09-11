#!/bin/bash
# systemd/install.sh
# Install moodle-agent as a systemd service (SSE mode)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SERVICE_NAME="moodle-agent"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "Installing Moodle MCP Server as systemd service..."
echo ""
echo "Project directory: $PROJECT_DIR"
echo "Service file: $SERVICE_FILE"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
  echo "Error: This script must be run as root (use 'sudo')"
  exit 1
fi

# Copy service file
echo "Installing service file..."
cp "$SCRIPT_DIR/${SERVICE_NAME}.service" "$SERVICE_FILE"
chmod 644 "$SERVICE_FILE"

# Update paths in service file to match actual project directory
sed -i "s|/home/pi/moodle-agent|${PROJECT_DIR}|g" "$SERVICE_FILE"

echo "Reloading systemd daemon..."
systemctl daemon-reload

echo ""
echo "✓ Service installed successfully"
echo ""
echo "Next steps:"
echo "  1. (First time only) Run login: python scripts/login.py"
echo "  2. Start service:     sudo systemctl start ${SERVICE_NAME}"
echo "  3. Check status:      sudo systemctl status ${SERVICE_NAME}"
echo "  4. Enable on boot:    sudo systemctl enable ${SERVICE_NAME}"
echo "  5. View logs:         sudo journalctl -u ${SERVICE_NAME} -f"
echo ""
