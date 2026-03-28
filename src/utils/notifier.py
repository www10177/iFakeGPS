"""
notifier.py – Windows desktop notification helper.

Strategy (in order of preference):
  1. winsdk  – proper WinRT toast (already a project dependency)
  2. ctypes  – MessageBoxW as a non-blocking fallback (zero extra deps)
"""

import sys
import threading

from src.utils.logger import logger


def notify(title: str, message: str) -> None:
    """Fire-and-forget desktop notification."""
    threading.Thread(
        target=_notify_impl,
        args=(title, message),
        daemon=True,
    ).start()


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _notify_impl(title: str, message: str) -> None:
    if sys.platform != "win32":
        return
    if _try_winsdk_toast(title, message):
        return
    _ctypes_msgbox(title, message)


def _try_winsdk_toast(title: str, message: str) -> bool:
    """Use the winsdk package (WinRT) to show a modern Windows toast."""
    try:
        import winsdk.windows.data.xml.dom as dom
        import winsdk.windows.ui.notifications as notifications

        xml = f"""
        <toast>
          <visual>
            <binding template="ToastGeneric">
              <text>{title}</text>
              <text>{message}</text>
            </binding>
          </visual>
        </toast>"""

        xdoc = dom.XmlDocument()
        xdoc.load_xml(xml)

        notifier = notifications.ToastNotificationManager.create_toast_notifier(
            "iFakeGPS"
        )
        notifier.show(notifications.ToastNotification(xdoc))
        return True
    except Exception as e:
        logger.warning(f"winsdk toast failed: {e}")
        return False


def _ctypes_msgbox(title: str, message: str) -> None:
    """Fallback: blocking Win32 MessageBoxW (runs on its own daemon thread)."""
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message, title, 0x40)  # MB_ICONINFORMATION
    except Exception as e:
        logger.warning(f"ctypes MessageBox fallback failed: {e}")
