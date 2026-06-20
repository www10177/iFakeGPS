import os
import unittest
from unittest import mock

from src.core import update_checker, updater


class FakeResponse:
    """Minimal stand-in for a requests.Response (and its streaming context)."""

    def __init__(self, status=200, json_data=None, content=b"", headers=None):
        self.status_code = status
        self._json = json_data or {}
        self._content = content
        self.headers = headers or {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self._content), chunk_size):
            yield self._content[i : i + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class AssetParsingTests(unittest.TestCase):
    def test_picks_exe_asset(self):
        data = {
            "tag_name": "1.7.0",
            "html_url": "https://example/releases/1.7.0",
            "body": "notes",
            "assets": [
                {"name": "source.zip", "browser_download_url": "https://e/s.zip", "size": 10},
                {"name": "iFakeGPS.exe", "browser_download_url": "https://e/app.exe", "size": 58_000_000},
            ],
        }
        with mock.patch.object(update_checker.requests, "get", return_value=FakeResponse(json_data=data)):
            info = update_checker.fetch_latest_release()
        self.assertIsNotNone(info)
        self.assertEqual(info.asset_url, "https://e/app.exe")
        self.assertEqual(info.asset_size, 58_000_000)

    def test_no_exe_asset_leaves_url_none(self):
        data = {
            "tag_name": "1.7.0",
            "html_url": "https://example",
            "body": "b",
            "assets": [{"name": "src.zip", "browser_download_url": "u", "size": 1}],
        }
        with mock.patch.object(update_checker.requests, "get", return_value=FakeResponse(json_data=data)):
            info = update_checker.fetch_latest_release()
        self.assertIsNone(info.asset_url)


class DownloadValidationTests(unittest.TestCase):
    def _patch(self, payload):
        resp = FakeResponse(content=payload, headers={"Content-Length": str(len(payload))})
        return mock.patch.object(updater.requests, "get", return_value=resp)

    def test_rejects_non_pe_payload(self):
        payload = b"X" * 2_000_000  # large enough, but no "MZ" header
        with self._patch(payload):
            with self.assertRaises(ValueError):
                updater.download_update("https://e/app.exe")

    def test_rejects_too_small_payload(self):
        payload = b"MZ" + b"\x00" * 100  # valid header, implausibly small
        with self._patch(payload):
            with self.assertRaises(ValueError):
                updater.download_update("https://e/app.exe")

    def test_accepts_valid_exe_and_reports_progress(self):
        payload = b"MZ" + b"\x00" * 2_000_000
        progress = []
        with self._patch(payload):
            path = updater.download_update(
                "https://e/app.exe", progress_cb=lambda w, t: progress.append((w, t))
            )
        try:
            self.assertTrue(os.path.exists(path))
            self.assertEqual(os.path.getsize(path), len(payload))
            self.assertTrue(progress)
            self.assertEqual(progress[-1][0], len(payload))
        finally:
            if os.path.exists(path):
                os.remove(path)


class BatchTemplateTests(unittest.TestCase):
    def test_template_formats_with_pid_and_image(self):
        script = updater._BATCH_TEMPLATE.format(pid=42, image="iFakeGPS.exe")
        self.assertIn("PID eq 42", script)
        self.assertIn('taskkill /F /IM "iFakeGPS.exe"', script)
        self.assertIn("%~1", script)  # target path arg preserved


if __name__ == "__main__":
    unittest.main()
