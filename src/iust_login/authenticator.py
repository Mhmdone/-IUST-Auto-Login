"""Authentication logic for IUST Auto Login.

Handles the two-stage university login process:
1. Login form at login.iust.ac.ir/login.php
2. Secondary page at 192.168.253.14/login with 'Send anyway' action
"""

import logging
import time
from datetime import datetime
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
)

logger = logging.getLogger(__name__)


class Authenticator:
    """Handles the IUST two-stage authentication process."""

    def __init__(self, config, browser_manager, credential_store):
        self.config = config
        self.browser = browser_manager
        self.credentials = credential_store

    def authenticate(self) -> bool:
        """Execute the full authentication flow.

        Returns True if authentication was successful.
        """
        logger.info("Starting authentication process")

        try:
            username, password = self.credentials.load()
        except Exception as e:
            logger.error("Failed to load credentials: %s", e)
            return False

        try:
            self.browser.start()
            driver = self.browser.driver

            # Stage 1: Login form
            if not self._login_first_stage(driver, username, password):
                logger.error("First stage login failed")
                self._take_screenshot(driver, "first_stage_failed")
                return False

            logger.info("First stage login completed")

            # Wait for potential redirect
            time.sleep(3)

            # Stage 2: Handle 'Send anyway' if needed
            if not self._login_second_stage(driver):
                logger.warning("Second stage handling completed (may not have been needed)")

            # Verify success
            if self._verify_success():
                logger.info("Authentication successful - internet is available")
                return True
            else:
                logger.error("Authentication completed but internet not available")
                self._take_screenshot(driver, "verification_failed")
                return False

        except Exception as e:
            logger.error("Authentication error: %s", e)
            try:
                self._take_screenshot(self.browser.driver, "auth_error")
            except Exception:
                pass
            return False
        finally:
            self.browser.stop()

    def _login_first_stage(self, driver, username: str, password: str) -> bool:
        """Navigate to login page and submit credentials.

        Args:
            driver: Selenium WebDriver instance
            username: User's username
            password: User's password (never logged)

        Returns:
            True if form was submitted successfully
        """
        try:
            logger.info("Navigating to login page: %s", self.config.login_url)
            driver.get(self.config.login_url)

            wait = WebDriverWait(driver, self.config.timeout)

            # Wait for and find username field
            logger.debug("Looking for username field")
            username_field = wait.until(
                EC.presence_of_element_located((By.NAME, "username"))
            )

            # Find password field
            logger.debug("Looking for password field")
            password_field = driver.find_element(By.NAME, "password")

            # Clear and fill fields
            username_field.clear()
            username_field.send_keys(username)
            logger.info("Username entered")

            password_field.clear()
            password_field.send_keys(password)
            logger.info("Password entered (value hidden)")

            # Find and click submit button
            submit_button = self._find_submit_button(driver)
            if submit_button:
                submit_button.click()
                logger.info("Login form submitted")
            else:
                # Fallback: submit the form directly
                password_field.submit()
                logger.info("Login form submitted via form.submit()")

            # Wait for page to change
            time.sleep(2)

            return True

        except TimeoutException:
            logger.error("Timeout waiting for login page elements")
            return False
        except NoSuchElementException as e:
            logger.error("Login form element not found: %s", e)
            return False
        except Exception as e:
            logger.error("Error during first stage login: %s", e)
            return False

    def _find_submit_button(self, driver):
        """Find the submit button on the login form."""
        # Try common submit button selectors
        selectors = [
            (By.CSS_SELECTOR, "input[type='submit']"),
            (By.CSS_SELECTOR, "button[type='submit']"),
            (By.CSS_SELECTOR, "input[type='button'][onclick]"),
            (By.CSS_SELECTOR, "button.login-btn"),
            (By.CSS_SELECTOR, "button.btn-primary"),
            (By.CSS_SELECTOR, "input.btn"),
        ]

        for by, selector in selectors:
            try:
                element = driver.find_element(by, selector)
                logger.debug("Found submit button: %s", selector)
                return element
            except NoSuchElementException:
                continue

        logger.warning("No explicit submit button found")
        return None

    def _login_second_stage(self, driver) -> bool:
        """Handle the second stage page (Send anyway).

        This page appears at http://192.168.253.14/login and may show
        a browser security warning or a 'Send anyway' button.

        Returns:
            True if second stage was handled successfully
        """
        current_url = driver.current_url
        logger.info("Current URL after first stage: %s", current_url)
        logger.info("Page title: %s", driver.title)

        # Check if we're on the second stage page
        is_second_stage = (
            "192.168.253.14" in current_url
            or self.config.second_stage_url in current_url
        )

        if not is_second_stage:
            # Maybe we need to navigate there explicitly
            try:
                logger.info("Navigating to second stage: %s", self.config.second_stage_url)
                driver.get(self.config.second_stage_url)
                time.sleep(2)
            except Exception as e:
                logger.warning("Could not navigate to second stage: %s", e)
                return False

        # Log page information for debugging
        logger.debug("Second stage page title: %s", driver.title)
        logger.debug("Second stage URL: %s", driver.current_url)

        # Try to find and click 'Send anyway' or similar button
        return self._handle_send_anyway(driver)

    def _handle_send_anyway(self, driver) -> bool:
        """Find and click the 'Send anyway' button/link.

        Tries multiple strategies to find the button without
        relying on fragile XPath selectors.
        """
        strategies = [
            # Strategy 1: Button with specific text content
            self._find_by_button_text,
            # Strategy 2: Input with specific value
            self._find_by_input_value,
            # Strategy 3: Link with specific text
            self._find_by_link_text,
            # Strategy 4: Any clickable element with matching text
            self._find_by_any_text,
            # Strategy 5: Form submit button on the page
            self._find_any_submit,
        ]

        for strategy in strategies:
            try:
                element = strategy(driver)
                if element:
                    element.click()
                    logger.info("'Send anyway' clicked using %s", strategy.__name__)
                    time.sleep(2)
                    return True
            except Exception as e:
                logger.debug("Strategy %s failed: %s", strategy.__name__, e)
                continue

        logger.warning("Could not find 'Send anyway' button - page may have changed")

        # Check if page is loaded but button is hidden
        logger.debug("Page URL at failure: %s", driver.current_url)

        return False

    def _find_by_button_text(self, driver):
        """Find button containing 'send' text."""
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
            text = btn.text.lower().strip()
            if "send" in text or "ارسال" in text or "continue" in text:
                logger.debug("Found button with text: %s", btn.text)
                return btn
        return None

    def _find_by_input_value(self, driver):
        """Find input button with 'send' in value attribute."""
        inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='submit'], input[type='button']")
        for inp in inputs:
            value = (inp.get_attribute("value") or "").lower()
            if "send" in value or "continue" in value or "ارسال" in value:
                logger.debug("Found input with value: %s", inp.get_attribute("value"))
                return inp
        return None

    def _find_by_link_text(self, driver):
        """Find link containing 'send' text."""
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            text = link.text.lower().strip()
            if "send" in text or "anyway" in text or "continue" in text:
                logger.debug("Found link with text: %s", link.text)
                return link
        return None

    def _find_by_any_text(self, driver):
        """Find any clickable element with matching text."""
        # Use a broad CSS selector for clickable elements
        clickable = driver.find_elements(
            By.CSS_SELECTOR,
            "button, a, input[type='submit'], input[type='button'], [role='button'], [onclick]"
        )
        for elem in clickable:
            text = (elem.text or elem.get_attribute("value") or "").lower()
            if "send" in text or "anyway" in text:
                logger.debug("Found clickable element: tag=%s, text=%s", elem.tag_name, text)
                return elem
        return None

    def _find_any_submit(self, driver):
        """Find any submit button on the page as last resort."""
        try:
            return driver.find_element(By.CSS_SELECTOR, "input[type='submit']")
        except NoSuchElementException:
            try:
                return driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            except NoSuchElementException:
                return None

    def _verify_success(self) -> bool:
        """Verify that internet is accessible after authentication."""
        # Import here to avoid circular imports
        from .network import NetworkDetector

        detector = NetworkDetector(self.config)

        # Give the network a moment to stabilize
        time.sleep(2)

        # Try multiple times
        for attempt in range(3):
            if detector.has_internet():
                return True
            logger.debug("Verification attempt %d failed, retrying...", attempt + 1)
            time.sleep(2)

        return False

    def _take_screenshot(self, driver, name: str) -> None:
        """Take a screenshot for debugging purposes."""
        try:
            self.config.ensure_dirs()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = self.config.screenshot_dir / f"{name}_{timestamp}.png"
            driver.save_screenshot(str(filepath))
            logger.info("Screenshot saved: %s", filepath)
        except Exception as e:
            logger.debug("Failed to save screenshot: %s", e)
