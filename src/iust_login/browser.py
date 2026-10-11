"""Browser management for IUST Auto Login.

Dynamically manages Selenium WebDriver lifecycle by automatically
detecting available browsers (Firefox, Chrome, Chromium) and
handling Linux-specific environment quirks (like Snap packages).
"""

import logging
import os
import shutil
from selenium import webdriver

logger = logging.getLogger(__name__)


class BrowserManager:
    """Dynamically manages WebDriver lifecycle across multiple browsers."""

    def __init__(self, config):
        self.config = config
        self.driver = None

    def start(self):
        """Start the browser by dynamically trying available options."""
        if self.driver is not None:
            logger.warning("Browser already running, stopping first")
            self.stop()

        errors = []

        # Strategy 1: Try Firefox (Preferred for Linux)
        try:
            self.driver = self._try_firefox()
            logger.info("Successfully started Firefox (Dynamic)")
            self._setup_driver()
            return self.driver
        except Exception as e:
            errors.append(f"Firefox Failed: {e}")
            logger.debug("Firefox attempt failed: %s", e)

        # Strategy 2: Try Chrome / Chromium
        try:
            self.driver = self._try_chrome()
            logger.info("Successfully started Chrome/Chromium (Dynamic)")
            self._setup_driver()
            return self.driver
        except Exception as e:
            errors.append(f"Chrome Failed: {e}")
            logger.debug("Chrome attempt failed: %s", e)

        # If all strategies fail
        logger.error("Could not start ANY browser dynamically. Errors: %s", " | ".join(errors))
        raise RuntimeError("No compatible browser found. Please ensure Firefox or Chrome is installed.")

    def _setup_driver(self):
        """Apply common settings to the successfully launched driver."""
        if self.driver:
            self.driver.set_page_load_timeout(self.config.timeout)
            self.driver.implicitly_wait(10)

    def stop(self) -> None:
        """Stop the browser safely."""
        if self.driver is not None:
            try:
                self.driver.quit()
                logger.info("Browser stopped")
            except Exception as e:
                logger.warning("Error stopping browser: %s", e)
            finally:
                self.driver = None

    def _try_firefox(self):
        """Attempt to launch Firefox, dynamically handling Snap constraints."""
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service

        options = Options()
        if self.config.headless:
            options.add_argument("-headless")
        
        options.accept_insecure_certs = True
        options.set_preference("browser.privatebrowsing.autostart", True)

        # Dynamic fix for Linux Snap bug ("binary is not a Firefox executable")
        firefox_path = shutil.which("firefox")
        if firefox_path:
            real_path = os.path.realpath(firefox_path)
            # If it's a snap wrapper, point Selenium directly to the actual binary
            if "snap" in real_path:
                snap_actual_bin = "/snap/firefox/current/usr/lib/firefox/firefox"
                if os.path.exists(snap_actual_bin):
                    options.binary_location = snap_actual_bin

        return webdriver.Firefox(service=Service(), options=options)

    def _try_chrome(self):
        """Attempt to launch Chrome or Chromium."""
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service

        options = Options()
        if self.config.headless:
            options.add_argument("--headless=new")

        options.add_argument("--no-first-run")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--window-size=1920,1080")

        return webdriver.Chrome(service=Service(), options=options)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False
