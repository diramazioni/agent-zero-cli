#!/bin/bash

# Check if the script is run as root
if [ "$(id -u)" -ne 0 ]; then
  echo "Please run this script as root or with sudo." >&2
  exit 1
fi

echo "Uninstalling Agent Zero CLI..."

# Define paths
ALIAS_PATH="/usr/local/bin/A0"
VENV_DIR="/opt/agent_zero_venv"
CONFIG_DIR="/etc/agent_zero"

# 1. Remove the symbolic link
if [ -L "$ALIAS_PATH" ]; then
    echo "1. Removing alias 'A0'..."
    rm -f "$ALIAS_PATH"
    if [ $? -eq 0 ]; then
        echo "   - Alias removed."
    else
        echo "   - Warning: Failed to remove alias. It might not exist or there was a permission issue."
    fi
else
    echo "1. Alias 'A0' not found, skipping."
fi

# 2. Remove the virtual environment
if [ -d "$VENV_DIR" ]; then
    echo "2. Removing virtual environment..."
    rm -rf "$VENV_DIR"
    if [ $? -eq 0 ]; then
        echo "   - Virtual environment removed."
    else
        echo "   - Error: Failed to remove virtual environment directory $VENV_DIR." >&2
    fi
else
    echo "2. Virtual environment directory not found, skipping."
fi

# 3. Remove the system-wide configuration
if [ -d "$CONFIG_DIR" ]; then
    echo "3. Removing system-wide configuration..."
    rm -rf "$CONFIG_DIR"
    if [ $? -eq 0 ]; then
        echo "   - Configuration directory removed."
    else
        echo "   - Error: Failed to remove configuration directory $CONFIG_DIR." >&2
    fi
else
    echo "3. Configuration directory not found, skipping."
fi

echo "✅ Uninstallation complete!"