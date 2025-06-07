#!/bin/bash

# Check if the script is run as root
if [ "$(id -u)" -ne 0 ]; then
  echo "Please run this script as root or with sudo." >&2
  exit 1
fi

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
SOURCE_FILE="$SCRIPT_DIR/agent_zero_cli.py"
DEST_DIR="/usr/local/bin"
DEST_FILE="$DEST_DIR/agent_zero_cli.py"
ALIAS_NAME="A0"
ALIAS_PATH="$DEST_DIR/$ALIAS_NAME"

# Check if the source file exists
if [ ! -f "$SOURCE_FILE" ]; then
    echo "Error: $SOURCE_FILE not found."
    exit 1
fi

echo "Installing Agent Zero CLI..."

# Make the script executable
echo "1. Making agent_zero_cli.py executable..."
chmod +x "$SOURCE_FILE"
if [ $? -ne 0 ]; then
    echo "Error: Failed to make the script executable."
    exit 1
fi

# Copy the script to the destination directory
echo "2. Copying agent_zero_cli.py to $DEST_DIR..."
cp "$SOURCE_FILE" "$DEST_FILE"
if [ $? -ne 0 ]; then
    echo "Error: Failed to copy the script."
    exit 1
fi

# Create the symbolic link
echo "3. Creating the 'A0' alias..."
ln -sf "$DEST_FILE" "$ALIAS_PATH"
if [ $? -ne 0 ]; then
    echo "Error: Failed to create the alias."
    exit 1
fi

echo "✅ Installation complete!"
echo "You can now use 'A0' from anywhere in your terminal."