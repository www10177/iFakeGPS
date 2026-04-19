"""
notifier.py – Windows desktop notification helper.

Strategy (in order of preference):
  1. winsdk toast with Windows sound
"""

import sys
import threading
import os
from xml.sax.saxutils import escape

from src.utils.logger import logger

APP_ID = "iFakeGPS"
APP_DISPLAY_NAME = "iFakeGPS"
APP_ID_REG_PATH = rf"Software\Classes\AppUserModelId\{APP_ID}"


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
    _try_winsdk_toast(title, message)


def is_windows_app_id_registered() -> bool:
    """Check whether our AppUserModelID key exists in HKCU."""
    if sys.platform != "win32":
        return False
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APP_ID_REG_PATH):
            return True
    except OSError:
        return False


def register_windows_app_id(icon_path: str | None = None) -> bool:
    """Register AppUserModelID for current user to improve Win32 toast reliability."""
    if sys.platform != "win32":
        return False
    try:
        import winreg

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, APP_ID_REG_PATH) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_DISPLAY_NAME)
            if icon_path and os.path.exists(icon_path):
                winreg.SetValueEx(key, "IconUri", 0, winreg.REG_SZ, icon_path)
        logger.info("Windows AppUserModelID registered: %s", APP_ID)
        return True
    except Exception as e:
        logger.warning("Failed to register Windows AppUserModelID: %s", e)
        return False


def _try_winsdk_toast(title: str, message: str) -> bool:
    """Use winsdk (WinRT) to show a Windows toast with sound."""
    try:
        import winsdk.windows.data.xml.dom as dom
        import winsdk.windows.ui.notifications as notifications

        safe_title = escape(title)
        safe_message = escape(message)

        xml = f"""
        <toast duration="short">
          <visual>
            <binding template="ToastGeneric">
              <text>{safe_title}</text>
              <text>{safe_message}</text>
            </binding>
          </visual>
          <audio src="ms-winsoundevent:Notification.Default"/>
        </toast>"""

        xdoc = dom.XmlDocument()
        xdoc.load_xml(xml)

        # For source runs (python/run.bat), AppID-based toast often gets suppressed
        # unless Start Menu shortcut registration is present.
        for notifier_mode, app_id in (("default", None), ("explicit_app_id", APP_ID)):
            try:
                if app_id:
                    notifier = (
                        notifications.ToastNotificationManager.create_toast_notifier(
                            app_id
                        )
                    )
                else:
                    notifier = notifications.ToastNotificationManager.create_toast_notifier()
                notifier.show(notifications.ToastNotification(xdoc))
                logger.info(
                    "Windows toast sent successfully (mode=%s, app_id=%s)",
                    notifier_mode,
                    app_id or "<default>",
                )
                return True
            except Exception as inner_e:
                logger.warning(
                    "Windows toast send failed (mode=%s, app_id=%s): %s",
                    notifier_mode,
                    app_id or "<default>",
                    inner_e,
                )

        return False
    except Exception as e:
        logger.warning(f"winsdk toast failed: {e}")
        return False
