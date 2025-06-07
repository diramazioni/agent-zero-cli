export HOME=/home/es

# Set your NVM directory (modify if necessary)
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}" 

if [ -s "$NVM_DIR/nvm.sh" ]; then
  \. "$NVM_DIR/nvm.sh"
  echo "NVM loaded from $NVM_DIR/nvm.sh"
  echo "Active Node version: $(node -v)"
  echo "Path Node: $(which node)"
else
  echo "Error: NVM not found in $NVM_DIR" >&2
  exit 1
fi

# Run npx with the correct version of Node.js
echo "Run npx..."
package_name=$1
shift
exec npx -y "$package_name" "$@"

# If exec fails, print an error message and exit with a non-zero status
echo "Errore: npx failed to run" >&2
exit 1