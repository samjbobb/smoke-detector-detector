#!/bin/bash
set -e

# Smoke Detector Detector - Installation Script
# This script sets up the smoke detector as a systemd service

echo "========================================="
echo "Smoke Detector Detector - Installation"
echo "========================================="

# Check if running on Raspberry Pi OS or Debian
if [ ! -f /etc/os-release ]; then
    echo "Error: Cannot detect OS version"
    exit 1
fi

source /etc/os-release
if [[ "$ID" != "raspbian" && "$ID" != "debian" ]]; then
    echo "Warning: This script is designed for Raspberry Pi OS/Debian"
    echo "Current OS: $ID"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Detect current user and home directory
CURRENT_USER="$USER"
USER_HOME="$HOME"

# Check if running as root
if [ "$EUID" -eq 0 ]; then
   echo "Please run this script as a regular user, not as root"
   exit 1
fi

# Configuration
SERVICE_NAME="smoke-detector"
SERVICE_FILE="${SERVICE_NAME}.service"
INSTALL_DIR="${USER_HOME}/smoke-detector-detector"
CURRENT_DIR="$(pwd)"

echo "Installing for user: $CURRENT_USER"
echo "Installation directory: $INSTALL_DIR"

# Check if we're in the right directory
if [ ! -f "$CURRENT_DIR/main.py" ] || [ ! -f "$CURRENT_DIR/smoke_detection_algorithm.py" ]; then
    echo "Error: Please run this script from the smoke-detector-detector directory"
    exit 1
fi

echo ""
echo "Step 1: Checking prerequisites..."
echo "---------------------------------"

# Check for Python 3.12+
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    echo "Please install with: sudo apt-get update && sudo apt-get install python3 python3-pip"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
REQUIRED_VERSION="3.11"
if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "Error: Python $REQUIRED_VERSION or higher is required (found $PYTHON_VERSION)"
    echo "You may need to install a newer Python version"
    exit 1
fi
echo "✓ Python $PYTHON_VERSION found"

# Install system dependencies
echo ""
echo "Step 2: Installing system dependencies..."
echo "-----------------------------------------"
echo "This will install audio libraries required for sound detection"
sudo apt-get update
sudo apt-get install -y portaudio19-dev python3-pyaudio ffmpeg libffi-dev

# Ensure user is in audio group
if ! groups | grep -q audio; then
    echo "Adding user to audio group..."
    sudo usermod -a -G audio $USER
    echo "Note: You may need to log out and back in for audio group membership to take effect"
fi

echo ""
echo "Step 3: Installing uv package manager..."
echo "-----------------------------------------"
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    echo "✓ uv installed"
else
    echo "✓ uv already installed"
fi

# Make sure uv is in PATH
export PATH="${USER_HOME}/.local/bin:$PATH"

echo ""
echo "Step 4: Copying project files..."
echo "---------------------------------"

# Copy the project to the standard location if not already there
if [ "$CURRENT_DIR" != "$INSTALL_DIR" ]; then
    echo "Copying project to $INSTALL_DIR..."
    if [ -d "$INSTALL_DIR" ]; then
        read -p "$INSTALL_DIR already exists. Overwrite? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$INSTALL_DIR"
        else
            echo "Installation cancelled"
            exit 1
        fi
    fi
    cp -r "$CURRENT_DIR" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
else
    echo "Already in installation directory: $INSTALL_DIR"
fi

echo ""
echo "Step 5: Installing Python dependencies..."
echo "------------------------------------------"
cd "$INSTALL_DIR"
${USER_HOME}/.local/bin/uv sync --no-dev
echo "✓ Dependencies installed"

echo ""
echo "Step 6: Configuring application settings..."
echo "-------------------------------------------"

CONFIG_FILE="$INSTALL_DIR/config.json"
if [ -f "$CONFIG_FILE" ]; then
    echo "✓ Using existing config.json"
else
    # Prompt for topic name
    read -p "ntfy.sh topic name (or press Enter for 'smoke-alarm'): " ntfy_input
    NTFY_TOPIC="${ntfy_input:-smoke-alarm}"

    # Create config.json
    cat > "$CONFIG_FILE" <<EOF
{
  "notifications": {
    "ntfy": {
      "enabled": true,
      "topic": "$NTFY_TOPIC",
      "server": "https://ntfy.sh"
    }
  },
  "audio": {
    "device": null
  }
}
EOF
    echo "✓ Created config.json with ntfy topic: $NTFY_TOPIC"
fi

echo ""
echo "Step 7: Setting up as systemd service..."
echo "-----------------------------------------"

# Create a temporary service file with the correct user and paths
TMP_SERVICE_FILE="/tmp/${SERVICE_FILE}"
sed -e "s|User=pi|User=$CURRENT_USER|g" \
    -e "s|/home/pi|$USER_HOME|g" \
    "$SERVICE_FILE" > "$TMP_SERVICE_FILE"

# Install the service
echo "Installing systemd service..."
sudo cp "$TMP_SERVICE_FILE" /etc/systemd/system/$SERVICE_FILE
rm "$TMP_SERVICE_FILE"
sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}.service

echo ""
echo "========================================="
echo "Installation Complete!"
echo "========================================="
echo ""
echo "Service installed as: ${SERVICE_NAME}.service"
echo "Installation directory: $INSTALL_DIR"
echo "Configuration file: $CONFIG_FILE"
echo ""
echo "Available commands:"
echo "  Start service:    sudo systemctl start $SERVICE_NAME"
echo "  Stop service:     sudo systemctl stop $SERVICE_NAME"
echo "  Service status:   sudo systemctl status $SERVICE_NAME"
echo "  View logs:        sudo journalctl -u $SERVICE_NAME -f"
echo "  Restart service:  sudo systemctl restart $SERVICE_NAME"
echo ""
echo "The service will automatically start on boot."
echo ""
read -p "Would you like to start the service now? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo systemctl start ${SERVICE_NAME}.service
    echo ""
    echo "Service started! Check status with: sudo systemctl status $SERVICE_NAME"
    echo "View live logs with: sudo journalctl -u $SERVICE_NAME -f"
else
    echo ""
    echo "You can start the service later with: sudo systemctl start $SERVICE_NAME"
fi

echo ""
echo "To test notifications, run: cd $INSTALL_DIR && ./main.py --test-notifications"