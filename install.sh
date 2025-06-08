#!/bin/bash

# Check if the script is run as root
if [ "$(id -u)" -ne 0 ]; then
  echo "Please run this script as root or with sudo." >&2
  exit 1
fi

# Function to check and install uv
install_uv() {
    # Ensure uv's install path is in PATH for this function
    export PATH="/root/.local/bin:$PATH"
    if ! command -v uv &> /dev/null; then
        echo "uv not found. Installing uv..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        if [ $? -ne 0 ]; then
            echo "Error: Failed to install uv."
            exit 1
        fi
        echo "uv installed successfully."
    else
        echo "uv is already installed."
    fi
}

# --- Configuration ---
# IMPORTANTE: Sostituisci questo URL con l'URL del contenuto raw del tuo repository
BASE_URL="https://raw.githubusercontent.com/diramazioni/agent-zero-cli/refs/heads/main"

# --- Setup Directory Temporanea ---
# Crea una directory temporanea per scaricare i file
TMP_DIR=$(mktemp -d)
if [ ! "$TMP_DIR" ] || [ ! -d "$TMP_DIR" ]; then
  echo "Errore: Impossibile creare la directory temporanea." >&2
  exit 1
fi

# Funzione per pulire la directory temporanea all'uscita
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

# --- Download dei file necessari ---
echo "Scaricamento dei file di installazione..."
curl -LsSf "$BASE_URL/agent_zero_cli.py" -o "$TMP_DIR/agent_zero_cli.py"
if [ $? -ne 0 ]; then echo "Errore: Download di agent_zero_cli.py fallito." >&2; exit 1; fi

curl -LsSf "$BASE_URL/pyproject.toml" -o "$TMP_DIR/pyproject.toml"
if [ $? -ne 0 ]; then echo "Errore: Download di pyproject.toml fallito." >&2; exit 1; fi

# .env è opzionale, quindi non generiamo un errore se manca
curl -LsSf "$BASE_URL/.env" -o "$TMP_DIR/.env" >/dev/null 2>&1


# --- Percorsi dei File ---
# Definisce i percorsi per i file scaricati e le directory di destinazione
SOURCE_FILE="$TMP_DIR/agent_zero_cli.py"
ENV_FILE="$TMP_DIR/.env"
PYPROJECT_TOML="$TMP_DIR/pyproject.toml"
VENV_DIR="/opt/agent_zero_venv"
DEST_DIR="/usr/local/bin"

# Check if the source file exists
if [ ! -f "$SOURCE_FILE" ]; then
    echo "Error: $SOURCE_FILE not found."
    exit 1
fi

echo "Installing Agent Zero CLI..."

# Install uv if not present
install_uv

# Create and activate a system-wide virtual environment
echo "1. Setting up Python virtual environment in $VENV_DIR..."
mkdir -p "$VENV_DIR"
if [ $? -ne 0 ]; then
    echo "Error: Failed to create virtual environment directory $VENV_DIR."
    exit 1
fi

# Ensure uv is in PATH for the current shell session
uv venv "$VENV_DIR"
if [ $? -ne 0 ]; then
    echo "Error: Failed to create virtual environment."
    exit 1
fi
echo "   - Virtual environment created."

# Install Python dependencies using uv
echo "2. Installing Python dependencies with uv..."
if [ -f "$PYPROJECT_TOML" ]; then
    # Use the system-wide uv to sync dependencies into the virtual environment
    uv pip sync --python "$VENV_DIR/bin/python" "$PYPROJECT_TOML"
    if [ $? -ne 0 ]; then
        echo "Error: Failed to install Python dependencies."
        exit 1
    fi
    echo "   - Python dependencies installed."
else
    echo "   - Warning: pyproject.toml not found. Skipping Python dependency installation."
fi

# Copy the script to the virtual environment's bin directory
echo "3. Copying agent_zero_cli.py to $VENV_DIR/bin/..."
cp "$SOURCE_FILE" "$VENV_DIR/bin/agent_zero_cli.py"
if [ $? -ne 0 ]; then
    echo "Error: Failed to copy the script to virtual environment."
    exit 1
fi

# Make the script executable within the venv
chmod +x "$VENV_DIR/bin/agent_zero_cli.py"
if [ $? -ne 0 ]; then
    echo "Error: Failed to make the script executable in virtual environment."
    exit 1
fi

# Create the symbolic link for the alias, pointing to the script in the venv
echo "4. Creating the 'A0' alias..."
ln -sf "$VENV_DIR/bin/agent_zero_cli.py" "$DEST_DIR/A0"
if [ $? -ne 0 ]; then
    echo "Error: Failed to create the alias."
    exit 1
fi

# Create system-wide config directory and copy .env file
echo "5. Setting up system-wide configuration..."
if [ -f "$ENV_FILE" ]; then
    mkdir -p "/etc/agent_zero"
    if [ $? -ne 0 ]; then
        echo "Error: Failed to create configuration directory /etc/agent_zero."
        exit 1
    fi
    cp "$ENV_FILE" "/etc/agent_zero/.env"
    if [ $? -ne 0 ]; then
        echo "Error: Failed to copy .env file to /etc/agent_zero/.env."
        exit 1
    fi
    echo "   - Configuration copied to /etc/agent_zero/.env"
else
    echo "   - Warning: .env file not found. Skipping configuration setup."
fi

echo "✅ Installation complete!"
echo "You can now use 'A0' from anywhere in your terminal."