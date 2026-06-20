import atexit
import os
import subprocess
import sys
import threading
import time
from typing import Optional

import requests

from src.core.constants import TUNNELD_PORT, TUNNELD_URL
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
        self._atexit_registered = False

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
            response = requests.get(TUNNELD_URL, timeout=1)
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
            logger.info("Started tunneld service (pid=%s)", getattr(self.process, "pid", None))

            # Safety net: make sure the subprocess tree is torn down even if the
            # app crashes or exits without calling _on_close. Otherwise the frozen
            # tunneld child (which IS iFakeGPS.exe) keeps the exe locked and blocks
            # the user from overwriting it to update (forcing a reboot).
            if not self._atexit_registered:
                atexit.register(self.stop)
                self._atexit_registered = True

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
        """Stop the tunneld service and any process it leaked.

        IMPORTANT: a plain ``process.terminate()`` only kills the direct child and
        leaves tunneld's own grandchildren running. In the frozen exe those linger
        as iFakeGPS.exe copies that keep the executable locked, so updating requires
        a reboot. We therefore kill the whole process tree, and additionally sweep
        any orphaned tunneld still bound to the API port (covers the case where a
        previous session left one behind and we only "adopted" it with no handle).
        """
        if self.process:
            pid = self.process.pid
            try:
                self._kill_process_tree(pid)
            except Exception as e:
                logger.warning("Failed to kill tunneld tree (pid=%s): %s", pid, e)
            self.process = None

        # Sweep up any tunneld still holding the port (orphan / adopted instance).
        try:
            self._kill_port_owners(TUNNELD_PORT)
        except Exception as e:
            logger.warning("Failed to sweep tunneld on port %s: %s", TUNNELD_PORT, e)

        self.running = False
        logger.info("Stopped tunneld service")

    @staticmethod
    def _run_quiet(cmd: list) -> subprocess.CompletedProcess:
        """Run a short helper command without flashing a console window."""
        kwargs = {"capture_output": True, "text": True, "timeout": 10}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        return subprocess.run(cmd, **kwargs)

    def _kill_process_tree(self, pid: int) -> None:
        """Kill a process and all of its descendants."""
        if sys.platform == "win32":
            # /T kills the whole tree, /F forces it.
            self._run_quiet(["taskkill", "/F", "/T", "/PID", str(pid)])
            return

        # POSIX: try to kill the process group, fall back to the single pid.
        try:
            os.killpg(os.getpgid(pid), 9)
        except Exception:
            try:
                os.kill(pid, 9)
            except ProcessLookupError:
                pass

    def _kill_port_owners(self, port: int) -> None:
        """Find and kill (tree) any process listening on ``port``.

        Only used on Windows, where the frozen tunneld locks iFakeGPS.exe. On other
        platforms a leaked tunneld does not block updates, so this is a no-op.
        """
        if sys.platform != "win32":
            return

        result = self._run_quiet(["netstat", "-ano", "-p", "TCP"])
        if not result or not result.stdout:
            return

        needle = f":{port}"
        pids = set()
        for line in result.stdout.splitlines():
            if needle not in line or "LISTENING" not in line.upper():
                continue
            parts = line.split()
            if not parts:
                continue
            pid_str = parts[-1]
            if pid_str.isdigit() and pid_str != "0":
                pids.add(int(pid_str))

        for pid in pids:
            logger.info("Killing orphaned tunneld holding port %s (pid=%s)", port, pid)
            try:
                self._kill_process_tree(pid)
            except Exception as e:
                logger.warning("Failed to kill orphaned tunneld pid=%s: %s", pid, e)

    def restart(self) -> bool:
        """Restart the tunneld service."""
        self.stop()
        time.sleep(1)
        return self.start()
