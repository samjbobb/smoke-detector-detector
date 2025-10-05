#!/bin/bash
set -e

# Smoke Detector Detector - Uninstallation Script

echo "========================================="
echo "Smoke Detector Detector - Uninstaller"
echo "========================================="

# Detect current user and home directory
CURRENT_USER="$USER"
USER_HOME="$HOME"

# Configuration
SERVICE_NAME="smoke-detector"
SERVICE_FILE="${SERVICE_NAME}.service"
INSTALL_DIR="${USER_HOME}/smoke-detector-detector"

# Check if running as root
if [ "$EUID" -eq 0 ]; then
   echo "Please run this script as a regular user, not as root"
   exit 1
fi

echo "Uninstalling for user: $CURRENT_USER"

echo ""
echo "This will uninstall the Smoke Detector service and optionally remove files."
read -p "Continue with uninstallation? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstallation cancelled"
    exit 0
fi

echo ""
echo "Step 1: Stopping service..."
echo "----------------------------"
if sudo systemctl is-active --quiet $SERVICE_NAME; then
    sudo systemctl stop $SERVICE_NAME
    echo "✓ Service stopped"
else
    echo "✓ Service was not running"
fi

echo ""
echo "Step 2: Disabling service..."
echo "-----------------------------"
if sudo systemctl is-enabled --quiet $SERVICE_NAME 2>/dev/null; then
    sudo systemctl disable $SERVICE_NAME
    echo "✓ Service disabled"
else
    echo "✓ Service was not enabled"
fi

echo ""
echo "Step 3: Removing service file..."
echo "---------------------------------"
if [ -f "/etc/systemd/system/$SERVICE_FILE" ]; then
    sudo rm /etc/systemd/system/$SERVICE_FILE
    sudo systemctl daemon-reload
    echo "✓ Service file removed"
else
    echo "✓ Service file was not installed"
fi

echo ""
echo "Step 4: Configuration file..."
echo "-----------------------------"
CONFIG_FILE="$INSTALL_DIR/config.json"
if [ -f "$CONFIG_FILE" ]; then
    echo "Configuration file found: $CONFIG_FILE"
    read -p "Keep configuration file for future use? (Y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        rm "$CONFIG_FILE"
        echo "✓ Configuration file removed"
    else
        # Move config to backup location before removing directory
        CONFIG_BACKUP="${USER_HOME}/.smoke-detector-config.json"
        cp "$CONFIG_FILE" "$CONFIG_BACKUP"
        echo "✓ Configuration backed up to: $CONFIG_BACKUP"
    fi
fi

echo ""
echo "Step 5: Application files..."
echo "-----------------------------"
if [ -d "$INSTALL_DIR" ]; then
    echo "Installation directory found at: $INSTALL_DIR"
    read -p "Remove installation directory and all files? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$INSTALL_DIR"
        echo "✓ Installation directory removed"
    else
        echo "✓ Installation directory preserved at: $INSTALL_DIR"
    fi
else
    echo "✓ Installation directory not found"
fi

echo ""
echo "========================================="
echo "Uninstallation Complete!"
echo "========================================="
echo ""
echo "The Smoke Detector service has been removed."

CONFIG_BACKUP="${USER_HOME}/.smoke-detector-config.json"
if [ -f "$CONFIG_BACKUP" ]; then
    echo ""
    echo "Your configuration was backed up to:"
    echo "  $CONFIG_BACKUP"
    echo ""
    echo "To restore it on reinstall, copy it to config.json after running install-pi.sh"
fi

echo ""
echo "Note: System dependencies (portaudio19-dev, python3-pyaudio, ffmpeg)"
echo "were NOT removed as they may be used by other applications."
echo ""
echo "If you want to remove them, run:"
echo "  sudo apt-get remove portaudio19-dev python3-pyaudio ffmpeg"