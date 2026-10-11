"""Configuration management for IUST Auto Login."""

import configparser
import os
from dataclasses import dataclass, field
from pathlib import Path


def _default_config_dir() -> Path:
    return Path.home() / ".config" / "iust-login"


def _default_data_dir() -> Path:
    return Path.home() / ".local" / "share" / "iust-login"


@dataclass
class Config:
    """Application configuration with sensible defaults."""

    # Login URLs
    login_url: str = "https://login.iust.ac.ir/login.php"
    second_stage_url: str = "http://192.168.253.14/login"

    # Timing
    check_interval: int = 30
    retry_count: int = 5
    retry_delay: int = 10
    timeout: int = 30

    # Browser
    headless: bool = True
    browser: str = "chromium"

    # Paths
    config_dir: Path = field(default_factory=_default_config_dir)
    data_dir: Path = field(default_factory=_default_data_dir)

    # University network detection
    university_ssids: list = field(
        default_factory=lambda: ["IUST", "iust", "IUST-WiFi", "iust-wifi"]
    )
    university_gateway_prefix: str = "194.225."

    @property
    def config_file(self) -> Path:
        return self.config_dir / "config.ini"

    @property
    def log_file(self) -> Path:
        return self.data_dir / "iust-login.log"

    @property
    def screenshot_dir(self) -> Path:
        return self.data_dir / "screenshots"

    def save(self) -> None:
        """Save configuration to config.ini file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

        parser = configparser.ConfigParser()

        parser["urls"] = {
            "login_url": self.login_url,
            "second_stage_url": self.second_stage_url,
        }

        parser["timing"] = {
            "check_interval": str(self.check_interval),
            "retry_count": str(self.retry_count),
            "retry_delay": str(self.retry_delay),
            "timeout": str(self.timeout),
        }

        parser["browser"] = {
            "headless": str(self.headless),
            "browser": self.browser,
        }

        parser["network"] = {
            "university_ssids": ",".join(self.university_ssids),
            "university_gateway_prefix": self.university_gateway_prefix,
        }

        with open(self.config_file, "w") as f:
            parser.write(f)

    def load(self) -> None:
        """Load configuration from config.ini file if it exists."""
        if not self.config_file.exists():
            return

        parser = configparser.ConfigParser()
        parser.read(self.config_file)

        if "urls" in parser:
            self.login_url = parser["urls"].get("login_url", self.login_url)
            self.second_stage_url = parser["urls"].get(
                "second_stage_url", self.second_stage_url
            )

        if "timing" in parser:
            self.check_interval = parser["timing"].getint(
                "check_interval", self.check_interval
            )
            self.retry_count = parser["timing"].getint(
                "retry_count", self.retry_count
            )
            self.retry_delay = parser["timing"].getint(
                "retry_delay", self.retry_delay
            )
            self.timeout = parser["timing"].getint("timeout", self.timeout)

        if "browser" in parser:
            self.headless = parser["browser"].getboolean("headless", self.headless)
            self.browser = parser["browser"].get("browser", self.browser)

        if "network" in parser:
            ssids = parser["network"].get("university_ssids", "")
            if ssids:
                self.university_ssids = [s.strip() for s in ssids.split(",")]
            self.university_gateway_prefix = parser["network"].get(
                "university_gateway_prefix", self.university_gateway_prefix
            )

    def ensure_dirs(self) -> None:
        """Create all necessary directories."""
        self.config_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
