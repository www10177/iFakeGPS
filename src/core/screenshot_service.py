"""Device screenshot capture over a dedicated DVT connection.

Used for the live "device preview" (pseudo-realtime burst capture). It opens its
OWN ``DvtSecureSocketProxyService`` — separate from the one DeviceManager keeps
for location simulation — so repeated frame grabs never race with location
updates on the same socket. The connection is reused across frames; reconnecting
per frame would be far too slow.
"""

import threading

from pymobiledevice3.services.dvt.dvt_secure_socket_proxy import (
    DvtSecureSocketProxyService,
)
from pymobiledevice3.services.dvt.instruments.screenshot import Screenshot

from src.utils.logger import logger


class ScreenshotService:
    def __init__(self, device_manager):
        self._device_manager = device_manager
        self._dvt = None
        self._screenshot = None
        self._lock = threading.Lock()

    def _ensure_channel(self) -> None:
        if self._screenshot is not None:
            return
        sp = self._device_manager.service_provider
        if sp is None or not self._device_manager.connected:
            raise RuntimeError("Device not connected")
        dvt = DvtSecureSocketProxyService(sp)
        dvt.__enter__()
        self._dvt = dvt
        self._screenshot = Screenshot(dvt)
        logger.info("Opened DVT screenshot channel")

    def capture_png(self) -> bytes:
        """Capture one screenshot as PNG bytes.

        Raises if the device is not connected or the channel breaks; on failure
        the channel is reset so the next call transparently reconnects.
        """
        with self._lock:
            try:
                self._ensure_channel()
                return self._screenshot.get_screenshot()
            except Exception:
                self._reset()
                raise

    def _reset(self) -> None:
        if self._dvt is not None:
            try:
                self._dvt.__exit__(None, None, None)
            except Exception as e:
                logger.debug("Error closing screenshot DVT channel: %s", e)
        self._dvt = None
        self._screenshot = None

    def close(self) -> None:
        with self._lock:
            self._reset()
            logger.info("Closed DVT screenshot channel")
