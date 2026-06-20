import unittest
from unittest import mock

from src.core import screenshot_service
from src.core.screenshot_service import ScreenshotService


class FakeDvt:
    def __init__(self, service_provider):
        self.service_provider = service_provider
        self.exited = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.exited = True
        return False


class FakeDeviceManager:
    def __init__(self, connected=True, service_provider="sp"):
        self.connected = connected
        self.service_provider = service_provider


def _patch_dvt(screenshot_obj):
    """Patch the DVT proxy + Screenshot used inside the service."""
    return (
        mock.patch.object(screenshot_service, "DvtSecureSocketProxyService", FakeDvt),
        mock.patch.object(
            screenshot_service, "Screenshot", lambda dvt: screenshot_obj
        ),
    )


class ScreenshotServiceTests(unittest.TestCase):
    def test_capture_returns_png_and_reuses_channel(self):
        shot = mock.Mock()
        shot.get_screenshot.return_value = b"PNGDATA"
        dvt_factory = mock.Mock(side_effect=lambda sp: FakeDvt(sp))

        with mock.patch.object(screenshot_service, "DvtSecureSocketProxyService", dvt_factory), \
             mock.patch.object(screenshot_service, "Screenshot", lambda dvt: shot):
            svc = ScreenshotService(FakeDeviceManager())
            self.assertEqual(svc.capture_png(), b"PNGDATA")
            self.assertEqual(svc.capture_png(), b"PNGDATA")

        # The DVT connection is opened once and reused across frames.
        self.assertEqual(dvt_factory.call_count, 1)
        self.assertEqual(shot.get_screenshot.call_count, 2)

    def test_capture_raises_when_not_connected(self):
        svc = ScreenshotService(FakeDeviceManager(connected=False))
        with self.assertRaises(RuntimeError):
            svc.capture_png()

    def test_capture_resets_channel_on_error(self):
        shot = mock.Mock()
        shot.get_screenshot.side_effect = RuntimeError("channel broke")
        opened = []

        def dvt_factory(sp):
            d = FakeDvt(sp)
            opened.append(d)
            return d

        with mock.patch.object(screenshot_service, "DvtSecureSocketProxyService", dvt_factory), \
             mock.patch.object(screenshot_service, "Screenshot", lambda dvt: shot):
            svc = ScreenshotService(FakeDeviceManager())
            with self.assertRaises(RuntimeError):
                svc.capture_png()
            # Failed channel was torn down so the next attempt reconnects.
            self.assertTrue(opened[0].exited)
            self.assertIsNone(svc._screenshot)
            with self.assertRaises(RuntimeError):
                svc.capture_png()
            self.assertEqual(len(opened), 2)


if __name__ == "__main__":
    unittest.main()
