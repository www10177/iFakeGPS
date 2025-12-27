import subprocess
import sys
import threading
import time
from typing import Optional

import requests

from src.utils.logger import logger


class TunneldManager:
    """
    Manages the tunneld service for iOS 17+ device connections.
    Automatically starts tunneld if not running.
    """

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.running = False
        self._output_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self.on_device_detected: Optional[callable] = None
        self.on_status_change: Optional[callable] = None

    @staticmethod
    def is_admin() -> bool:
        """Check if running with administrator privileges."""
        try:
            if sys.platform == "win32":
                import ctypes

                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            else:
                import os

                return os.geteuid() == 0
        except Exception:
            return False

    def is_tunneld_running(self) -> bool:
        """Check if tunneld is already running by trying to connect to its API."""
        try:
            # The tunneld API uses / (root) endpoint, not /list-tunnels
            response = requests.get("http://127.0.0.1:49151/", timeout=1)
            return response.status_code == 200
        except Exception:
            return False

    def start(self) -> bool:
        """Start the tunneld service."""
        if self.is_tunneld_running():
            logger.info("tunneld is already running")
            self.running = True
            return True

        try:
            # Start tunneld as a subprocess
            # Note: This may require admin privileges
            python_exec = sys.executable

            # Determine command arguments based on environment
            if getattr(sys, "frozen", False):
                # Running as frozen executable - use internal flag to avoid recursion loop
                cmd_args = [python_exec, "--internal-tunneld"]
            else:
                # Running as script
                cmd_args = [python_exec, "-m", "pymobiledevice3", "remote", "tunneld"]

            # Create the process with CREATE_NEW_CONSOLE flag on Windows to avoid blocking
            if sys.platform == "win32":
                # On Windows, we need to run with proper privileges
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

                self.process = subprocess.Popen(
                    cmd_args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                self.process = subprocess.Popen(
                    cmd_args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

            self.running = True
            logger.info("Started tunneld service")

            # Start output monitoring thread
            self._output_thread = threading.Thread(
                target=self._monitor_output, daemon=True
            )
            self._output_thread.start()

            # Start stderr monitoring thread
            self._stderr_thread = threading.Thread(
                target=self._monitor_stderr, daemon=True
            )
            self._stderr_thread.start()

            # Wait a moment for tunneld to initialize
            time.sleep(2)

            return True

        except Exception as e:
            logger.error(f"Failed to start tunneld: {e}")
            self.running = False
            return False

    def _monitor_output(self):
        """Monitor tunneld output for device connections."""
        if not self.process:
            return

        try:
            while self.process and self.process.poll() is None:
                line = self.process.stdout.readline()
                if line:
                    decoded = line.decode("utf-8", errors="ignore").strip()
                    logger.debug(f"tunneld: {decoded}")

                    # Check for device connection events
                    if (
                        "tunnel created" in decoded.lower()
                        or "device" in decoded.lower()
                    ):
                        if self.on_device_detected:
                            self.on_device_detected()
        except Exception as e:
            logger.warning(f"tunneld output monitor error: {e}")

        self.running = False
        if self.on_status_change:
            self.on_status_change(False)

    def _monitor_stderr(self):
        """Monitor tunneld stderr for errors."""
        if not self.process:
            return

        try:
            while self.process and self.process.poll() is None:
                line = self.process.stderr.readline()
                if line:
                    decoded = line.decode("utf-8", errors="ignore").strip()
                    logger.error(f"tunneld [ERR]: {decoded}")
        except Exception as e:
            logger.warning(f"tunneld stderr monitor error: {e}")

    def stop(self):
        """Stop the tunneld service."""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
        self.running = False
        logger.info("Stopped tunneld service")

    def restart(self) -> bool:
        """Restart the tunneld service."""
        self.stop()
        time.sleep(1)
        return self.start()
