"""Command-line interface for IUST Auto Login.

Provides commands: setup, login, status, enable, disable, logs, run, uninstall.
"""

import argparse
import getpass
import logging
import os
import subprocess
import sys

from . import __version__
from .config import Config
from .credentials import CredentialStore
from .network import NetworkDetector
from .browser import BrowserManager
from .authenticator import Authenticator
from .monitor import ConnectionMonitor
from .service import ServiceManager

logger = logging.getLogger("iust_login")


def setup_logging(config: Config, debug: bool = False) -> None:
    """Configure application logging."""
    config.ensure_dirs()

    level = logging.DEBUG if debug else logging.INFO
    fmt = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    # File handler
    file_handler = logging.FileHandler(config.log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    root = logging.getLogger("iust_login")
    root.setLevel(logging.DEBUG)
    root.addHandler(console)
    root.addHandler(file_handler)


def cmd_setup(args, config: Config) -> None:
    """Set up user credentials."""
    print("=" * 40)
    print("  IUST Auto Login - Setup")
    print("=" * 40)
    print()

    store = CredentialStore(config.config_dir)

    if store.exists():
        answer = input("Credentials already exist. Overwrite? [y/N]: ").strip().lower()
        if answer != "y":
            print("Setup cancelled.")
            return

    username = input("Username: ").strip()
    if not username:
        print("Error: Username cannot be empty.")
        sys.exit(1)

    password = getpass.getpass("Password: ")
    if not password:
        print("Error: Password cannot be empty.")
        sys.exit(1)

    password_confirm = getpass.getpass("Confirm Password: ")
    if password != password_confirm:
        print("Error: Passwords do not match.")
        sys.exit(1)

    store.save(username, password)

    # Save default config if not exists
    if not config.config_file.exists():
        config.save()

    print()
    print("✓ Credentials saved successfully.")
    print()
    print("Next steps:")
    print("  1. Test login:    iust-login login")
    print("  2. Enable service: iust-login enable")


def cmd_login(args, config: Config) -> None:
    """Run authentication manually."""
    if args.debug:
        config.headless = False

    setup_logging(config, debug=args.debug)

    store = CredentialStore(config.config_dir)
    if not store.exists():
        print("Error: No credentials found. Run 'iust-login setup' first.")
        sys.exit(1)

    browser = BrowserManager(config)
    auth = Authenticator(config, browser, store)

    print("Starting authentication...")
    success = auth.authenticate()

    if success:
        print("✓ Authentication successful! Internet should be available.")
    else:
        print("✗ Authentication failed. Check logs: iust-login logs")
        sys.exit(1)


def cmd_status(args, config: Config) -> None:
    """Show current status."""
    network = NetworkDetector(config)
    service = ServiceManager()
    store = CredentialStore(config.config_dir)

    is_connected = network.is_connected()
    is_university = network.is_university_network() if is_connected else False
    has_internet = network.has_internet() if is_connected else False
    service_active = service.is_active()
    service_enabled = service.is_enabled()
    has_credentials = store.exists()

    print()
    print("  IUST Auto Login v" + __version__)
    print("  " + "─" * 36)

    def status_line(label, value, ok_text, fail_text):
        icon = "✓" if value else "✗"
        text = ok_text if value else fail_text
        print(f"  {label:<18}: {icon} {text}")

    status_line("Network", is_connected, "Connected", "Disconnected")
    status_line("University", is_university, "Detected", "Not detected")
    status_line("Internet", has_internet, "Available", "Not available")
    status_line("Credentials", has_credentials, "Configured", "Not configured")
    status_line("Service", service_active, "Running", "Stopped")
    status_line("Auto-start", service_enabled, "Enabled", "Disabled")

    print("  " + "─" * 36)

    if not has_credentials:
        print("  → Run 'iust-login setup' to configure credentials")
    elif not has_internet and is_university:
        print("  → Run 'iust-login login' to authenticate")
    elif not service_enabled:
        print("  → Run 'iust-login enable' to enable auto-login")

    print()


def cmd_enable(args, config: Config) -> None:
    """Enable the systemd service."""
    store = CredentialStore(config.config_dir)
    if not store.exists():
        print("Error: No credentials found. Run 'iust-login setup' first.")
        sys.exit(1)

    service = ServiceManager()
    if service.install():
        print("✓ IUST Auto Login service enabled.")
        print("  The service will start automatically on boot.")
        print("  Check status: iust-login status")
    else:
        print("✗ Failed to enable service. Check logs for details.")
        sys.exit(1)


def cmd_disable(args, config: Config) -> None:
    """Disable the systemd service."""
    service = ServiceManager()
    if service.is_active() or service.is_enabled():
        service._run_systemctl("stop", service.SERVICE_NAME)
        service._run_systemctl("disable", service.SERVICE_NAME)
        print("✓ IUST Auto Login service disabled.")
    else:
        print("Service is not active.")


def cmd_logs(args, config: Config) -> None:
    """Show service logs."""
    # Try journalctl first
    try:
        lines = getattr(args, "lines", 50)
        subprocess.run(
            [
                "journalctl",
                "--user",
                "-u",
                "iust-login.service",
                "-n",
                str(lines),
                "--no-pager",
            ],
            timeout=10,
        )
    except FileNotFoundError:
        # Fallback: show log file
        if config.log_file.exists():
            with open(config.log_file) as f:
                lines_list = f.readlines()
                for line in lines_list[-50:]:
                    print(line, end="")
        else:
            print("No logs found.")


def cmd_run(args, config: Config) -> None:
    """Run the monitoring service (called by systemd)."""
    setup_logging(config)

    store = CredentialStore(config.config_dir)
    if not store.exists():
        logger.error("No credentials found. Run 'iust-login setup' first.")
        sys.exit(1)

    logger.info("IUST Auto Login v%s starting...", __version__)

    network = NetworkDetector(config)
    browser = BrowserManager(config)
    auth = Authenticator(config, browser, store)
    monitor = ConnectionMonitor(config, network, auth)

    try:
        monitor.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        logger.info("IUST Auto Login stopped")


def cmd_uninstall(args, config: Config) -> None:
    """Uninstall the service and remove configuration."""
    print("This will:")
    print("  - Stop and disable the systemd service")
    print("  - Remove stored credentials")
    print("  - Remove configuration files")
    print()
    answer = input("Are you sure? [y/N]: ").strip().lower()
    if answer != "y":
        print("Cancelled.")
        return

    # Disable service
    service = ServiceManager()
    service.uninstall()

    # Remove credentials
    store = CredentialStore(config.config_dir)
    store.delete()

    # Remove config and data dirs
    import shutil

    if config.config_dir.exists():
        shutil.rmtree(config.config_dir, ignore_errors=True)
    if config.data_dir.exists():
        shutil.rmtree(config.data_dir, ignore_errors=True)

    print("✓ IUST Auto Login uninstalled.")


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="iust-login",
        description="IUST Auto Login - Automated university network authentication",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # setup
    subparsers.add_parser("setup", help="Configure login credentials")

    # login
    login_parser = subparsers.add_parser("login", help="Run authentication manually")
    login_parser.add_argument(
        "--debug",
        action="store_true",
        help="Run in debug mode (visible browser window)",
    )

    # status
    subparsers.add_parser("status", help="Show current status")

    # enable
    subparsers.add_parser("enable", help="Enable automatic login service")

    # disable
    subparsers.add_parser("disable", help="Disable automatic login service")

    # logs
    logs_parser = subparsers.add_parser("logs", help="Show service logs")
    logs_parser.add_argument(
        "-n", "--lines", type=int, default=50, help="Number of log lines to show"
    )

    # run (for systemd)
    subparsers.add_parser("run", help="Run the monitoring service (used by systemd)")

    # uninstall
    subparsers.add_parser("uninstall", help="Uninstall service and remove config")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Load config
    config = Config()
    config.load()

    # Dispatch command
    commands = {
        "setup": cmd_setup,
        "login": cmd_login,
        "status": cmd_status,
        "enable": cmd_enable,
        "disable": cmd_disable,
        "logs": cmd_logs,
        "run": cmd_run,
        "uninstall": cmd_uninstall,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        cmd_func(args, config)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
