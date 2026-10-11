#!/bin/bash
# IUST Auto Login - Installation Script
set -e

echo "=================================="
echo "  IUST Auto Login - Installer"
echo "=================================="
echo

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Check Python 3
info "Checking Python 3..."
if command -v python3 &> /dev/null; then
    PYTHON=$(command -v python3)
    PY_VERSION=$($PYTHON --version 2>&1)
    info "Found: $PY_VERSION"
else
    error "Python 3 is not installed. Install it with: sudo apt install python3 python3-pip python3-venv"
fi

# Check pip
info "Checking pip..."
if ! $PYTHON -m pip --version &> /dev/null; then
    warn "pip not found. Installing..."
    sudo apt install -y python3-pip || error "Failed to install pip"
fi

# Check venv module
info "Checking venv module..."
if ! $PYTHON -m venv --help &> /dev/null 2>&1; then
    warn "venv module not found. Installing..."
    sudo apt install -y python3-venv || error "Failed to install python3-venv"
fi

# Check Chromium/Chrome
info "Checking Chromium/Chrome..."
if command -v chromium-browser &> /dev/null; then
    info "Found: chromium-browser"
elif command -v chromium &> /dev/null; then
    info "Found: chromium"
elif command -v google-chrome &> /dev/null; then
    info "Found: google-chrome"
elif command -v google-chrome-stable &> /dev/null; then
    info "Found: google-chrome-stable"
else
    warn "No Chromium/Chrome found. Installing chromium-browser..."
    sudo apt install -y chromium-browser || {
        warn "apt install failed, trying snap..."
        sudo snap install chromium || error "Failed to install Chromium. Install manually."
    }
fi

# Create directories
INSTALL_DIR="$HOME/.local/share/iust-login"
VENV_DIR="$INSTALL_DIR/venv"
BIN_DIR="$HOME/.local/bin"

info "Creating installation directory: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"

# Create virtual environment
info "Creating virtual environment..."
$PYTHON -m venv "$VENV_DIR"

# Install project
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
info "Installing IUST Auto Login..."
"$VENV_DIR/bin/pip" install --upgrade pip setuptools wheel
"$VENV_DIR/bin/pip" install "$SCRIPT_DIR"

# Create symlink
info "Creating command symlink..."
ln -sf "$VENV_DIR/bin/iust-login" "$BIN_DIR/iust-login"

# Check if ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    warn "$BIN_DIR is not in your PATH."
    echo "Add this to your ~/.bashrc or ~/.profile:"
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo
    echo "Then run: source ~/.bashrc"
fi

echo
echo "=================================="
echo -e "  ${GREEN}Installation complete!${NC}"
echo "=================================="
echo
echo "Next steps:"
echo "  1. Set up credentials:  iust-login setup"
echo "  2. Test login:          iust-login login --debug"
echo "  3. Enable service:      iust-login enable"
echo
