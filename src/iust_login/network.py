"""Network detection for IUST Auto Login.

Detects network connectivity, university network, internet access,
and captive portal authentication requirements.
"""

import logging
import socket
import subprocess
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

# Connectivity check endpoints
CONNECTIVITY_URLS = [
    ("http://connectivitycheck.gstatic.com/generate_204", 204),
    ("http://www.gstatic.com/generate_204", 204),
    ("http://clients3.google.com/generate_204", 204),
]


class NetworkDetector:
    """Detects network state and university network presence."""

    def __init__(self, config):
        self.config = config

    def is_connected(self) -> bool:
        """Check if any network interface is connected."""
        try:
            result = subprocess.run(
                ["nmcli", "general", "status"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                output = result.stdout.lower()
                return "connected" in output and "disconnected" not in output.split("\n")[1] if len(output.split("\n")) > 1 else "connected" in output
        except FileNotFoundError:
            pass
        except subprocess.TimeoutExpired:
            pass
        except Exception as e:
            logger.debug("nmcli check failed: %s", e)

        # Fallback: check ip route
        try:
            result = subprocess.run(
                ["ip", "route", "show", "default"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return bool(result.stdout.strip())
        except Exception as e:
            logger.debug("ip route check failed: %s", e)

        return False

    def is_university_network(self) -> bool:
        """Check if connected to IUST university network."""
        # Method 1: Check Wi-Fi SSID
        if self._check_ssid():
            return True

        # Method 2: Check gateway
        if self._check_gateway():
            return True

        # Method 3: Check if login page is reachable
        if self._check_login_page_reachable():
            return True

        return False

    def _check_ssid(self) -> bool:
        """Check current Wi-Fi SSID against known university SSIDs."""
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line.startswith("yes:"):
                        ssid = line.split(":", 1)[1].strip()
                        logger.debug("Current SSID: %s", ssid)
                        for known_ssid in self.config.university_ssids:
                            if known_ssid.lower() in ssid.lower():
                                logger.info("University SSID detected: %s", ssid)
                                return True
        except Exception as e:
            logger.debug("SSID check failed: %s", e)
        return False

    def _check_gateway(self) -> bool:
        """Check if default gateway matches university network pattern."""
        try:
            result = subprocess.run(
                ["ip", "route", "show", "default"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                output = result.stdout.strip()
                # Look for gateway IP
                parts = output.split()
                for i, part in enumerate(parts):
                    if part == "via" and i + 1 < len(parts):
                        gateway = parts[i + 1]
                        if gateway.startswith(self.config.university_gateway_prefix):
                            logger.info("University gateway detected: %s", gateway)
                            return True
        except Exception as e:
            logger.debug("Gateway check failed: %s", e)
        return False

    def _check_login_page_reachable(self) -> bool:
        """Check if the university login page is reachable (internal network)."""
        try:
            # Try to resolve the login host
            host = "login.iust.ac.ir"
            addr = socket.gethostbyname(host)
            if addr.startswith("194.225."):
                return True
        except Exception:
            pass
        return False

    def has_internet(self) -> bool:
        """Check if internet is accessible."""
        for url, expected_code in CONNECTIVITY_URLS:
            try:
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=5) as response:
                    if response.getcode() == expected_code:
                        logger.debug("Internet check passed: %s", url)
                        return True
            except Exception:
                continue

        # Fallback: DNS resolution
        try:
            socket.setdefaulttimeout(5)
            socket.getaddrinfo("google.com", 80)
            # DNS works, try a simple connection
            sock = socket.create_connection(("google.com", 80), timeout=5)
            sock.close()
            return True
        except Exception:
            pass

        return False

    def needs_authentication(self) -> bool:
        """Check if captive portal authentication is needed."""
        if not self.is_connected():
            logger.debug("Not connected to any network")
            return False

        if self.has_internet():
            logger.debug("Internet is already available")
            return False

        if not self.is_university_network():
            logger.debug("Not on university network")
            return False

        # We're on university network without internet -> need auth
        logger.info("Authentication required: on university network without internet")
        return True
