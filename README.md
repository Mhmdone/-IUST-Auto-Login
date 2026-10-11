# IUST Auto Login

Automatic authentication service for Iran University of Science and Technology (IUST) network on Linux/Ubuntu.

خب هدف اصلی ایجاد این ریپو اینطور بود که از وارد کردن دستی اطلاعات و تایید نا امن بودن برای وصل شدن به اینترنت دانشگاه خسته شدم، بنابر این گفتم یه فرایند خودکار ایجاد کنم تا دیگه نخوام اینکار هارو انجام بدم.
فقط یه نکته ای که داره اونم اینه که چون با selenium نوشته شده وصل شدن 3 الی 4 ثانیه ای طول میکشه که البته این برا زمانی که سیستم روشن کردید تا بخواهید کارتونو بکنید اوکی، اما اگر فرصت بشه سعی میکنم با request که خب فرایند سریع تر میکنه این پروژه رو انجام بدم. اگر دوست داشتید میتونید استار بدید :)
## Features

- 🔐 **Automatic Login** — Seamless authentication to IUST university network on boot
- 🖥️ **Headless Browser** — Silent Selenium automation with Chromium
- 🔄 **Auto-Reconnect** — Continuous monitoring with automatic re-authentication
- 🔑 **Secure Storage** — Credentials stored in system keyring or encrypted file
- ⚙️ **systemd Integration** — Runs as a user service, starts on boot
- 🛠️ **Professional CLI** — Easy-to-use command-line interface
- 📊 **Smart Detection** — University network and internet connectivity detection
- 🔁 **Exponential Backoff** — Intelligent retry mechanism

## Architecture

```
Boot → systemd → iust-login service
                       ↓
                Network Detection
                       ↓
                Internet Check ──→ OK → Monitor (sleep & recheck)
                       ↓
                Authentication Required
                       ↓
              ┌─── Selenium Start ───┐
              │                      │
              ▼                      │
     Stage 1: login.iust.ac.ir      │
     (username + password form)      │
              │                      │
              ▼                      │
     Stage 2: 192.168.253.14/login   │
     (Handle "Send anyway")         │
              │                      │
              ▼                      │
     Verify Internet ───────────────┘
              │
              ▼
     Monitor (continuous)
```

### Modules

| Module | Description |
|--------|-------------|
| `config.py` | Configuration management |
| `credentials.py` | Secure credential storage |
| `network.py` | Network & university detection |
| `browser.py` | Selenium/Chromium management |
| `authenticator.py` | Two-stage login automation |
| `monitor.py` | Connection monitoring |
| `service.py` | systemd integration |
| `cli.py` | Command-line interface |

## Requirements

- **OS**: Linux (Ubuntu 22.04, 24.04, 26.04+)
- **Python**: 3.9+
- **Browser**: Chromium or Google Chrome
- **Init**: systemd

## Installation

```bash
git clone <repo-url>
cd iust-auto-login
./install.sh
```

The installer will:
1. Check Python 3 and pip
2. Install Chromium if not present
3. Create a virtual environment
4. Install the package
5. Set up the `iust-login` command

## Setup

```bash
iust-login setup
```

Enter your IUST username and password. Credentials are stored securely using the system keyring or an encrypted file.

## Usage

### CLI Commands

| Command | Description |
|---------|-------------|
| `iust-login setup` | Configure login credentials |
| `iust-login login` | Run authentication manually |
| `iust-login login --debug` | Run with visible browser window |
| `iust-login status` | Show current status |
| `iust-login enable` | Enable auto-login service |
| `iust-login disable` | Disable auto-login service |
| `iust-login logs` | Show service logs |
| `iust-login logs -n 100` | Show last 100 log lines |
| `iust-login uninstall` | Remove service and config |

### Quick Start

```bash
# 1. Set up credentials
iust-login setup

# 2. Test login (visible browser for debugging)
iust-login login --debug

# 3. Enable automatic login on boot
iust-login enable

# 4. Check status
iust-login status
```

### Status Output

```
  IUST Auto Login v1.0.0
  ────────────────────────────────────
  Network           : ✓ Connected
  University        : ✓ Detected
  Internet          : ✓ Available
  Credentials       : ✓ Configured
  Service           : ✓ Running
  Auto-start        : ✓ Enabled
  ────────────────────────────────────
```

## systemd Service

The service runs as a **user service** (not root) and starts after network is available:

```bash
# Check service status
systemctl --user status iust-login

# View real-time logs
journalctl --user -u iust-login -f

# Restart service
systemctl --user restart iust-login
```

## Security

- ✅ Credentials stored in system keyring (or encrypted with Fernet)
- ✅ Passwords **never** logged or stored in plaintext
- ✅ Credential files restricted to `chmod 600`
- ✅ Service runs as regular user (not root)
- ✅ No unnecessary `--no-sandbox` flag
- ✅ No global certificate/security disabling
- ✅ `.gitignore` excludes all credential files
- ✅ No credentials sent to external services

## Troubleshooting

### Browser not found
```bash
sudo apt install chromium-browser
# or
sudo snap install chromium
```

### Service won't start
```bash
# Check logs
iust-login logs

# Try manual login with debug
iust-login login --debug

# Check if credentials are set
iust-login status
```

### ChromeDriver issues
Selenium 4.6+ includes Selenium Manager which automatically downloads the correct driver. If you have issues:
```bash
pip install --upgrade selenium
```

### Permission denied
```bash
# Make sure ~/.local/bin is in PATH
export PATH="$HOME/.local/bin:$PATH"
```

## Development

```bash
# Clone repository
git clone <repo-url>
cd iust-auto-login

# Create dev environment
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

## Testing

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test module
pytest tests/test_network.py
```

Tests use mocking and do **not** require actual network access or IUST credentials.

## License

MIT License - see [LICENSE](LICENSE) file.
