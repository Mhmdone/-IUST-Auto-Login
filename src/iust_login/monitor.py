"""Connection monitoring for IUST Auto Login.

Continuously monitors network connectivity and re-authenticates
when the connection drops. Uses exponential backoff for retries.
"""

import logging
import signal
import threading
import time

logger = logging.getLogger(__name__)


class ConnectionMonitor:
    """Monitors internet connectivity and re-authenticates when needed."""

    def __init__(self, config, network_detector, authenticator):
        self.config = config
        self.network = network_detector
        self.authenticator = authenticator
        self._stop_event = threading.Event()
        self._login_lock = threading.Lock()
        self._consecutive_failures = 0
        self._max_failures = config.retry_count

    def start(self) -> None:
        """Start the monitoring loop.

        This blocks until stop() is called or a signal is received.
        """
        logger.info("Connection monitor started (interval=%ds)", self.config.check_interval)

        # Register signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        while not self._stop_event.is_set():
            try:
                self._check_and_authenticate()
            except Exception as e:
                logger.error("Monitor check error: %s", e)

            # Wait for next check interval or stop event
            self._stop_event.wait(self.config.check_interval)

        logger.info("Connection monitor stopped")

    def stop(self) -> None:
        """Signal the monitor to stop."""
        logger.info("Stopping connection monitor...")
        self._stop_event.set()

    def _signal_handler(self, signum, frame):
        """Handle termination signals gracefully."""
        sig_name = signal.Signals(signum).name
        logger.info("Received signal %s, shutting down...", sig_name)
        self.stop()

    def _check_and_authenticate(self) -> None:
        """Check network status and authenticate if needed."""
        # Step 1: Check network connection
        if not self.network.is_connected():
            logger.debug("No network connection, waiting...")
            self._consecutive_failures = 0
            return

        # Step 2: Check internet
        if self.network.has_internet():
            if self._consecutive_failures > 0:
                logger.info("Internet restored after %d failures", self._consecutive_failures)
            self._consecutive_failures = 0
            logger.debug("Internet is available")
            return

        # Step 3: Check if on university network
        if not self.network.is_university_network():
            logger.debug("Not on university network, skipping authentication")
            return

        # Step 4: Authenticate
        logger.info("Internet unavailable on university network - authentication needed")
        self._perform_login()

    def _perform_login(self) -> None:
        """Perform login with lock to prevent concurrent attempts."""
        if not self._login_lock.acquire(blocking=False):
            logger.debug("Login already in progress, skipping")
            return

        try:
            if self._consecutive_failures >= self._max_failures:
                backoff = self._calculate_backoff(self._consecutive_failures)
                logger.warning(
                    "Too many failures (%d), backing off for %.0fs",
                    self._consecutive_failures,
                    backoff,
                )
                self._stop_event.wait(backoff)
                if self._stop_event.is_set():
                    return

            success = self.authenticator.authenticate()

            if success:
                logger.info("Login successful")
                self._consecutive_failures = 0
            else:
                self._consecutive_failures += 1
                logger.warning(
                    "Login failed (attempt %d/%d)",
                    self._consecutive_failures,
                    self._max_failures,
                )
        finally:
            self._login_lock.release()

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff delay.

        Args:
            attempt: Number of consecutive failures

        Returns:
            Delay in seconds (capped at 5 minutes)
        """
        delay = min(self.config.retry_delay * (2 ** (attempt - self._max_failures)), 300)
        return delay
