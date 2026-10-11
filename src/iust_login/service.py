"""systemd service management for IUST Auto Login.

Installs, manages, and removes the systemd user service
that runs the auto-login monitor on boot.
"""

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


class ServiceManager:
    """Manages the systemd user service for IUST Auto Login."""

    SERVICE_NAME = "iust-login.service"

    def __init__(self):
        self.service_dir = Path.home() / ".config" / "systemd" / "user"
        self.service_file = self.service_dir / self.SERVICE_NAME

    def _get_exec_path(self) -> str:
        """Get the path to the iust-login executable."""
        # Check if installed in venv
        venv_path = Path.home() / ".local" / "share" / "iust-login" / "venv" / "bin" / "iust-login"
        if venv_path.exists():
            return str(venv_path)

        # Check if in PATH
        which = shutil.which("iust-login")
        if which:
            return which

        # Fallback to current Python
        return f"{sys.executable} -m iust_login.cli"

    def _generate_unit_content(self) -> str:
        """Generate the systemd unit file content."""
        exec_path = self._get_exec_path()

        return f"""[Unit]
Description=IUST Auto Login Service
Documentation=https://github.com/iust-auto-login
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={exec_path} run
Restart=on-failure
RestartSec=30
Environment=DISPLAY=:0
Environment=PYTHONUNBUFFERED=1

# Give network time to fully connect
ExecStartPre=/bin/sleep 5

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=%h/.config/iust-login %h/.local/share/iust-login

[Install]
WantedBy=default.target
"""

    def install(self) -> bool:
        """Install and enable the systemd user service."""
        try:
            # Create service directory
            self.service_dir.mkdir(parents=True, exist_ok=True)

            # Write unit file
            unit_content = self._generate_unit_content()
            self.service_file.write_text(unit_content)
            logger.info("Service file created: %s", self.service_file)

            # Reload systemd
            self._run_systemctl("daemon-reload")

            # Enable service
            self._run_systemctl("enable", self.SERVICE_NAME)

            # Start service
            self._run_systemctl("start", self.SERVICE_NAME)

            logger.info("Service installed and started")
            return True

        except Exception as e:
            logger.error("Failed to install service: %s", e)
            return False

    def uninstall(self) -> bool:
        """Stop, disable, and remove the systemd user service."""
        try:
            # Stop service
            self._run_systemctl("stop", self.SERVICE_NAME)

            # Disable service
            self._run_systemctl("disable", self.SERVICE_NAME)

            # Remove unit file
            if self.service_file.exists():
                self.service_file.unlink()
                logger.info("Service file removed")

            # Reload systemd
            self._run_systemctl("daemon-reload")

            logger.info("Service uninstalled")
            return True

        except Exception as e:
            logger.error("Failed to uninstall service: %s", e)
            return False

    def is_active(self) -> bool:
        """Check if the service is currently running."""
        try:
            result = subprocess.run(
                ["systemctl", "--user", "is-active", self.SERVICE_NAME],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip() == "active"
        except Exception:
            return False

    def is_enabled(self) -> bool:
        """Check if the service is enabled to start on boot."""
        try:
            result = subprocess.run(
                ["systemctl", "--user", "is-enabled", self.SERVICE_NAME],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip() == "enabled"
        except Exception:
            return False

    def _run_systemctl(self, *args) -> subprocess.CompletedProcess:
        """Run a systemctl --user command."""
        cmd = ["systemctl", "--user"] + list(args)
        logger.debug("Running: %s", " ".join(cmd))
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0 and result.stderr:
            logger.warning("systemctl warning: %s", result.stderr.strip())
        return result
